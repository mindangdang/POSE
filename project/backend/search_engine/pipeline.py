from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from project.backend.search_engine.agent.graph import build_search_graph
from project.backend.search_engine.agent.state import SearchState
from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.evidence import fetch_public_html
from project.backend.search_engine.harness.tracing import SearchTrace
from project.backend.search_engine.models import ModelServerClient, SearchModelClient
from project.backend.search_engine.personalization.encoder import QueryEncoder
from project.backend.search_engine.personalization.preferences import (
    conflicts_with_intent,
    merge_explicit_conditions,
    retrieve_relevant_preferences,
)
from project.backend.search_engine.ranking.utility_ranker import rank_candidates
from project.backend.search_engine.ranking.utility_ranker import UtilityWeights
from project.backend.search_engine.retrieval.dense import dense_scores, hashing_embedding
from project.backend.search_engine.retrieval.cache import CachedDocumentRepository
from project.backend.search_engine.retrieval.fusion import (
    DEFAULT_RRF_WEIGHTS,
    weighted_reciprocal_rank_fusion,
)
from project.backend.search_engine.retrieval.sparse import bm25_scores
from project.backend.search_engine.schemas import (
    Preference,
    SearchCandidate,
    SearchRequest,
    SearchResponse,
)
from project.backend.search_engine.sources.base import SearchProvider
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.sources.serpapi import SerpApiSearchProvider
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id
from project.backend.search_engine.understanding.parser import IntentParser
from project.backend.app.manage.settings import get_settings


def default_provider() -> SearchProvider:
    settings = get_settings()
    name = settings.search_provider.casefold()
    if name == "fixture":
        return FixtureSearchProvider()
    provider = SerpApiSearchProvider(
        api_key=settings.serpapi_api_key or settings.serp_api_key
    )
    return provider if provider.api_key else FixtureSearchProvider()


class SearchPipeline:
    """Bounded, fixture-first pipeline. Python owns retrieval, filtering, and ranking."""

    def __init__(
        self,
        provider: SearchProvider | None = None,
        *,
        use_llm: bool | None = None,
        enable_evidence_fetch: bool | None = None,
        max_concurrency: int | None = None,
        utility_threshold: float | None = None,
        event_callback=None,
        model_client: SearchModelClient | None = None,
        document_repository: CachedDocumentRepository | None = None,
    ) -> None:
        self.provider = provider or default_provider()
        settings = get_settings()
        self.parser = IntentParser(use_llm=use_llm if use_llm is not None else bool(settings.llm_base_url))
        self.encoder = QueryEncoder()
        self.enable_evidence_fetch = (
            enable_evidence_fetch
            if enable_evidence_fetch is not None
            else settings.pose_fetch_evidence
        )
        self.semaphore = asyncio.Semaphore(max_concurrency or settings.search_max_concurrency)
        self.utility_threshold = utility_threshold if utility_threshold is not None else settings.search_result_threshold
        self.max_reranker_candidates = settings.search_max_reranker_candidates
        self.utility_weights = UtilityWeights(
            relevance=settings.search_relevance_weight,
            preference=settings.search_preference_weight,
            constraints=settings.search_constraint_weight,
            evidence=settings.search_evidence_weight,
            uncertainty_penalty=settings.search_uncertainty_penalty,
            threshold=self.utility_threshold,
        )
        self.event_callback = event_callback
        self.model_client = model_client or ModelServerClient()
        self.document_repository = document_repository

    async def emit(self, search_id: str, event_type: str, **payload) -> None:
        if self.event_callback:
            result = self.event_callback({"search_id": search_id, "type": event_type, **payload})
            if asyncio.iscoroutine(result):
                await result

    async def run(
        self,
        request: SearchRequest,
        user_id: str | int,
        preferences: list[Preference] | None = None,
        search_id: str | None = None,
    ) -> SearchResponse:
        settings = get_settings()
        state: SearchState = {
            "search_id": search_id or str(uuid4()),
            "user_id": str(user_id),
            "request": request,
            "preferences": preferences or [],
            "errors": [],
            "trace": SearchTrace(trace_id=str(uuid4())),
            "budget": SearchBudget(
                max_rounds=settings.search_max_rounds,
                max_queries_per_round=settings.search_max_queries_per_round,
                max_external_calls=settings.search_max_external_calls,
                max_candidates=settings.search_max_candidates,
                max_evidence_documents=settings.search_max_evidence_documents,
                deadline_seconds=settings.search_deadline_seconds,
            ),
            "executed_queries": [],
        }
        graph = build_search_graph(self)
        try:
            result = await asyncio.wait_for(
                graph.ainvoke(state), timeout=state["budget"].deadline_seconds
            )
        except TimeoutError:
            return SearchResponse(
                search_id=state["search_id"],
                status="partial",
                intent=state.get("intent"),
                preferences_used=[item.id for item in state.get("selected_preferences", [])],
                errors=[*state["errors"], "Search deadline exceeded"],
                tool_calls=state["budget"].external_calls,
                completed_at=datetime.now(timezone.utc),
            )
        return result["response"]

    async def prepare(self, state: dict) -> dict:
        started = time.perf_counter()
        request: SearchRequest = state["request"]
        candidates_preferences = state["preferences"] if request.personalization_enabled else []
        preference_vectors: dict[str, list[float]] = {}
        query_embedding = None
        query_embedding_model = None
        if candidates_preferences:
            descriptions = [request.query] + [
                f"{item.attribute} {item.value}" for item in candidates_preferences[:100]
            ]
            embeddings = await self.model_client.embed(descriptions)
            if embeddings:
                vectors, query_embedding_model = embeddings
                query_embedding = vectors[0]
                for item, vector in zip(candidates_preferences[:100], vectors[1:]):
                    preference_vectors[item.id] = vector
        elif not candidates_preferences:
            embeddings = await self.model_client.embed([request.query])
            if embeddings:
                vectors, query_embedding_model = embeddings
                query_embedding = vectors[0]
        similarities = None
        if query_embedding is not None and preference_vectors:
            from project.backend.search_engine.retrieval.dense import cosine_similarity

            similarities = {}
            for item in candidates_preferences:
                preference_vector = preference_vectors.get(item.id)
                if preference_vector is not None:
                    similarities[item.id] = max(
                        0.0,
                        cosine_similarity(query_embedding, preference_vector),
                    )
        selected = retrieve_relevant_preferences(
            request.query,
            candidates_preferences,
            request.context,
            limit=5,
            semantic_similarities=similarities,
        )
        for item in selected:
            item.embedding = preference_vectors.get(item.id)
        intent, parser_error = await self.parser.parse(
            request.query, request.context, selected
        )
        if request.context.criteria_overrides is not None:
            intent = intent.model_copy(update={"criteria": request.context.criteria_overrides})
        if request.context.exclusion_overrides is not None:
            intent = intent.model_copy(update={"exclusions": request.context.exclusion_overrides})
        selected = [item for item in selected if not conflicts_with_intent(item, intent)]
        intent = merge_explicit_conditions(intent, selected)
        rewritten_embedding = await self.model_client.embed([intent.rewritten_query])
        if rewritten_embedding:
            vectors, query_embedding_model = rewritten_embedding
            query_embedding = vectors[0]
        state["intent"] = intent
        state["selected_preferences"] = selected
        state["embedding_model_id"] = query_embedding_model
        state["query_representation"] = await self.encoder.encode(
            intent,
            selected,
            request.context,
            query_embedding=query_embedding,
            semantic_similarities=similarities,
        )
        if parser_error:
            state["errors"].append(parser_error)
        state["trace"].record(
            "parse_intent",
            started,
            criteria_count=len(intent.criteria),
            preferences_count=len(selected),
            retry_count=self.parser.last_retry_count,
        )
        state["status"] = "clarification_required" if intent.clarification_required else "running"
        await self.emit(
            state["search_id"],
            "CLARIFICATION_REQUIRED" if intent.clarification_required else "INTENT_PARSED",
            intent=intent.model_dump(mode="json"),
        )
        return state

    async def retrieve(self, state: dict) -> dict:
        if state.get("status") == "clarification_required":
            return state
        started = time.perf_counter()
        request: SearchRequest = state["request"]
        intent = state["intent"]
        budget: SearchBudget = state["budget"]
        queries = list(dict.fromkeys(state.get("next_queries") or intent.sub_queries))
        queries = [query for query in queries if query not in state["executed_queries"]]
        queries = queries[: budget.max_queries_per_round]
        if not queries:
            fallback_query = intent.rewritten_query
            if fallback_query not in state["executed_queries"]:
                queries = [fallback_query]
        if not queries or not budget.can_search(len(queries)):
            state["retry_reason"] = None
            return state
        budget.consume_search(len(queries))
        state["executed_queries"].extend(queries)
        state.pop("next_queries", None)
        await self.emit(state["search_id"], "RETRIEVAL_STARTED", queries=queries)

        async def search_cached_documents() -> list[SearchCandidate]:
            repository = self.document_repository
            model_id = state.get("embedding_model_id")
            vector = state["query_representation"].original_embedding
            if repository is None or not model_id or len(vector) != 1024:
                return []
            try:
                cache_limit = max(1, budget.max_candidates // 3)
                return await repository.search(vector, model_id, cache_limit)
            except Exception as exc:
                state["errors"].append(f"Cached retrieval failed: {type(exc).__name__}")
                return []

        async def call_provider(query: str) -> tuple[str, list[SearchCandidate], str | None]:
            try:
                async with self.semaphore:
                    items = await asyncio.wait_for(
                        self.provider.search(query, budget.max_candidates, request.context),
                        timeout=max(0.01, budget.deadline_seconds - (time.perf_counter() - budget.started_at)),
                    )
                return query, items, None
            except Exception as exc:
                return query, [], f"{self.provider.name} search failed: {type(exc).__name__}"

        cache_task = asyncio.create_task(search_cached_documents())
        fetched = await asyncio.gather(*(call_provider(query) for query in queries))
        cached_documents = await cache_task
        previous_documents = list(state.get("candidates", []))
        previous_ids = {document.document_id for document in previous_documents}
        by_url: dict[str, SearchCandidate] = {
            document.canonical_url: document for document in previous_documents
        }
        for rank, document in enumerate(cached_documents, start=1):
            try:
                canonical = canonicalize_url(document.canonical_url)
            except ValueError:
                continue
            document.document_id = stable_document_id(canonical)
            document.canonical_url = canonical
            document.retrieval_ranks["cached"] = rank
            existing = by_url.get(canonical)
            if existing is None:
                by_url[canonical] = document
            else:
                if existing.embedding is None and document.embedding is not None:
                    existing.embedding = document.embedding
                    existing.embedding_model = document.embedding_model
                    existing.embedding_version = document.embedding_version
                if not existing.content and document.content:
                    existing.content = document.content
        external_positions: defaultdict[str, list[int]] = defaultdict(list)
        for document in by_url.values():
            for channel, rank in document.retrieval_ranks.items():
                if channel.startswith("external:"):
                    external_positions[document.document_id].append(rank)
        for query_index, (query, items, error) in enumerate(fetched):
            if error:
                state["errors"].append(error)
                continue
            for rank, document in enumerate(items, start=1):
                try:
                    canonical = canonicalize_url(document.canonical_url)
                except ValueError:
                    continue
                stable_id = stable_document_id(canonical)
                existing = by_url.get(canonical)
                if existing is None:
                    document.document_id = stable_id
                    document.canonical_url = canonical
                    by_url[canonical] = document
                    existing = document
                elif not existing.content and document.content:
                    existing.content = document.content
                existing.retrieval_ranks[f"external:{budget.rounds}:{query_index}"] = rank
                external_positions[stable_id].append(rank)
        documents = list(by_url.values())
        if len(documents) > budget.max_candidates:
            def retrieval_priority(document: SearchCandidate) -> tuple[float, str]:
                score = sum(1.0 / (60 + rank) for rank in document.retrieval_ranks.values())
                return (-score, document.document_id)

            current_documents = [
                document for document in documents if document.document_id not in previous_ids
            ]
            if budget.rounds > 1 and previous_documents and current_documents:
                current_slots = min(
                    max(1, budget.max_candidates // 4),
                    len(current_documents),
                )
                retained_current = sorted(current_documents, key=retrieval_priority)[:current_slots]
                retained_ids = {document.document_id for document in retained_current}
                retained_previous = sorted(
                    (document for document in previous_documents if document.document_id not in retained_ids),
                    key=retrieval_priority,
                )[: budget.max_candidates - len(retained_current)]
                documents = sorted(
                    [*retained_current, *retained_previous],
                    key=retrieval_priority,
                )
            else:
                documents = sorted(documents, key=retrieval_priority)[: budget.max_candidates]

        model_id = state.get("embedding_model_id")
        documents_to_embed = [
            item for item in documents
            if item.embedding is None or (model_id and item.embedding_model != model_id)
        ]
        candidate_vectors = await self.model_client.embed(
            [" ".join((item.title, item.snippet, item.content)) for item in documents_to_embed]
        ) if documents_to_embed else None
        if candidate_vectors:
            vectors, model_id = candidate_vectors
            for document, vector in zip(documents_to_embed, vectors):
                document.embedding = vector
                document.embedding_model = model_id
                document.embedding_version = "v1"
        cache_started = time.perf_counter()
        if self.document_repository is not None:
            try:
                await self.document_repository.upsert(documents)
            except Exception as exc:
                state["errors"].append(f"Cached document write failed: {type(exc).__name__}")
        state["trace"].record("document_cache", cache_started, candidate_count=len(documents))
        representation = state["query_representation"]
        if documents and documents[0].embedding is not None:
            if len(representation.original_embedding) != len(documents[0].embedding):
                state["dense_original_embedding"] = hashing_embedding(intent.rewritten_query)
                personalized_text = " ".join(
                    [intent.rewritten_query]
                    + [
                        f"{item.attribute} {item.value}"
                        for item in state["selected_preferences"]
                        if item.polarity == "positive"
                    ]
                )
                state["dense_personalized_embedding"] = hashing_embedding(personalized_text)
            else:
                state["dense_original_embedding"] = representation.original_embedding
                state["dense_personalized_embedding"] = representation.personalized_embedding
        else:
            state["dense_original_embedding"] = hashing_embedding(intent.rewritten_query)
            personalized_text = " ".join(
                [intent.rewritten_query]
                + [
                    f"{item.attribute} {item.value}"
                    for item in state["selected_preferences"]
                    if item.polarity == "positive"
                ]
            )
            state["dense_personalized_embedding"] = hashing_embedding(personalized_text)

        evidence_started = time.perf_counter()
        evidence_targets = [
            document
            for document in documents[: budget.max_evidence_documents]
            if not document.content
        ] if self.enable_evidence_fetch else []
        await self.emit(state["search_id"], "EVIDENCE_CHECK_STARTED", count=len(evidence_targets))
        evidence_successes = sum(await asyncio.gather(
            *(self._fetch_evidence(document) for document in evidence_targets)
        )) if evidence_targets else 0
        state["trace"].record(
            "evidence_check",
            evidence_started,
            checked=len(evidence_targets),
            fetched=evidence_successes,
        )

        sparse_order = sorted(
            zip(documents, bm25_scores(intent.rewritten_query, documents)),
            key=lambda pair: (-pair[1], pair[0].document_id),
        )
        sparse = [doc.document_id for doc, score in sparse_order if score > 0]

        original_dense = sorted(
            zip(documents, dense_scores(state["dense_original_embedding"], documents)),
            key=lambda pair: (-pair[1], pair[0].document_id),
        )
        personalized_dense = sorted(
            zip(documents, dense_scores(state["dense_personalized_embedding"], documents)),
            key=lambda pair: (-pair[1], pair[0].document_id),
        )
        external = sorted(
            external_positions,
            key=lambda document_id: (
                min(external_positions[document_id]),
                document_id,
            ),
        )
        cached = [
            document.document_id
            for document in sorted(
                (doc for doc in documents if "cached" in doc.retrieval_ranks),
                key=lambda doc: (doc.retrieval_ranks["cached"], doc.document_id),
            )
        ]
        rankings = {
            "cached": cached,
            "external": external,
            "sparse": sparse,
            "dense": [doc.document_id for doc, _ in original_dense],
            "personalized_dense": [doc.document_id for doc, _ in personalized_dense],
        }
        fused = weighted_reciprocal_rank_fusion(
            rankings,
            DEFAULT_RRF_WEIGHTS,
            personalized_enabled=request.personalization_enabled and bool(state["selected_preferences"]),
        )
        state.update(
            {
                "candidates": documents,
                "rankings": rankings,
                "fused_scores": fused,
                "reranker_scores": {},
            }
        )
        state["trace"].record(
            "hybrid_retrieval",
            started,
            candidate_count=len(documents),
            query_count=len(queries),
            external_calls=len(queries),
            provider=self.provider.name,
            error_count=len(state["errors"]),
        )
        await self.emit(
            state["search_id"], "CANDIDATES_FOUND", count=len(documents), errors=len(state["errors"])
        )
        return state

    async def evaluate_coverage(self, state: dict) -> dict:
        """Permit one bounded deterministic refinement when the first pass is thin."""
        budget: SearchBudget = state["budget"]
        if state.get("status") == "clarification_required":
            state["retry_reason"] = None
            return state
        verified = state.get("verified_results", [])
        intent = state["intent"]
        hard_criteria = [
            item for item in [*intent.criteria, *intent.exclusions]
            if item.is_hard_constraint
        ]
        satisfied_ids = {
            evaluation.criterion_id
            for result in verified
            for evaluation in result.evaluations
            if evaluation.status == "satisfied"
        }
        missing = [item for item in hard_criteria if item.id not in satisfied_ids]
        should_refine = len(verified) < min(3, state["request"].limit) or bool(missing)
        if not should_refine or budget.rounds >= budget.max_rounds or not budget.has_time():
            state["retry_reason"] = None
            return state

        variants = [
            " ".join((intent.rewritten_query, str(item.value)))
            for item in missing[: budget.max_queries_per_round]
        ]
        if not variants:
            variants = [f"{intent.rewritten_query} guide", f"{intent.rewritten_query} options"]
        remaining = budget.max_external_calls - budget.external_calls
        next_queries = [
            query for query in dict.fromkeys(variants)
            if query not in state["executed_queries"]
        ][: min(budget.max_queries_per_round, remaining)]
        state["next_queries"] = next_queries
        state["retry_reason"] = "INSUFFICIENT_CRITERION_COVERAGE" if missing else "LOW_VERIFIED_RESULT_COUNT"
        if not next_queries:
            state["retry_reason"] = None
            return state
        await self.emit(
            state["search_id"],
            "RETRIEVAL_REFINED",
            reason_code=state["retry_reason"],
            missing_criteria=[item.id for item in missing],
            remaining_search_calls=remaining,
        )
        return state

    async def _fetch_evidence(self, document: SearchCandidate) -> bool:
        try:
            final_url, content = await fetch_public_html(document.canonical_url)
            document.source_url = final_url
            document.content = content
            document.fetched_at = datetime.now(timezone.utc)
            return True
        except Exception:
            # Keep a safe snippet-only candidate; unknown evidence is never satisfied.
            return False

    async def rank(self, state: dict) -> dict:
        if state.get("status") == "clarification_required":
            return state
        started = time.perf_counter()
        request: SearchRequest = state["request"]
        intent = state["intent"]
        await self.emit(state["search_id"], "RANKING_STARTED", count=min(30, len(state["candidates"])))
        rerank_docs = [
            {
                "id": document.document_id,
                "text": " ".join((document.title, document.snippet, document.content))[:20000],
            }
            for document in state["candidates"][: self.max_reranker_candidates]
        ]
        reranked = await self.model_client.rerank(intent.rewritten_query, rerank_docs)
        if reranked:
            raw_scores, model_id = reranked
            import math

            state["reranker_scores"] = {
                document_id: 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, score))))
                for document_id, score in raw_scores.items()
            }
            state["trace"].record("cross_encoder", started, model_id=model_id, candidate_count=len(raw_scores))
        else:
            state["trace"].record("cross_encoder", started, status="fallback", candidate_count=len(rerank_docs))
        verified, unverified, excluded = rank_candidates(
            query=intent.rewritten_query,
            documents=state["candidates"],
            fused_scores=state["fused_scores"],
            preferences=state["selected_preferences"],
            criteria=intent.criteria,
            exclusions=intent.exclusions,
            limit=request.limit,
            cross_encoder_scores=state.get("reranker_scores"),
            weights=self.utility_weights,
        )
        state.update(
            verified_results=verified,
            unverified_results=unverified,
            excluded_result_count=excluded,
        )
        state["trace"].record(
            "utility_ranking",
            started,
            verified_count=len(verified),
            unverified_count=len(unverified),
            excluded_count=excluded,
        )
        await self.emit(
            state["search_id"],
            "RANKING_UPDATED",
            verified_count=len(verified),
            unverified_count=len(unverified),
            excluded_count=excluded,
        )
        return state

    async def finalize(self, state: dict) -> dict:
        status = state.get("status", "completed")
        if status != "clarification_required":
            status = "partial" if state["errors"] and not state.get("verified_results") else "completed"
        response = SearchResponse(
            search_id=state["search_id"],
            status=status,
            intent=state.get("intent"),
            preferences_used=[preference.id for preference in state.get("selected_preferences", [])],
            verified_results=state.get("verified_results", []),
            unverified_results=state.get("unverified_results", []),
            excluded_result_count=state.get("excluded_result_count", 0),
            tool_calls=state["budget"].external_calls,
            errors=state["errors"],
            completed_at=datetime.now(timezone.utc),
        )
        state["response"] = response
        state["trace"].record("finalize_results", time.perf_counter(), status=status)
        await self.emit(
            state["search_id"],
            "SEARCH_COMPLETED" if status == "completed" else "SEARCH_PARTIAL",
            status=status,
        )
        return state
