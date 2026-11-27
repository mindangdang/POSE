from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from project.backend.search_engine.agent.graph import build_search_graph
from project.backend.search_engine.agent.state import SearchState
from project.backend.search_engine.retrieval.service import execute_retrieval
from project.backend.search_engine.ranking.service import execute_ranking
from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.tracing import SearchTrace
from project.backend.search_engine.models import (
    ModelServerClient,
    SearchModelClient,
    coerce_embedding_batch,
)
from project.backend.search_engine.personalization.encoder import QueryEncoder
from project.backend.search_engine.personalization.preferences import (
    conflicts_with_intent,
    merge_explicit_conditions,
    retrieve_relevant_preferences,
)
from project.backend.search_engine.ranking.utility_ranker import rank_candidates
from project.backend.search_engine.ranking.utility_ranker import UtilityWeights
from project.backend.search_engine.ranking.constraints import SemanticEvaluator
from project.backend.search_engine.retrieval.cache import (
    CachedDocumentRepository,
)
from project.backend.search_engine.schemas import (
    EmbeddingVector,
    Preference,
    SearchRequest,
    SearchResponse,
    SearchTraceSpan,
)
from project.backend.search_engine.sources.base import SearchProvider
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.sources.serpapi import SerpApiSearchProvider
from project.backend.search_engine.understanding.parser import IntentParser
from project.backend.search_engine.understanding.intent_parser import DeterministicIntentParser
from project.backend.search_engine.understanding.semantic import OpenAICompatibleSemanticEvaluator
from project.backend.app.manage.settings import get_settings


def default_provider() -> SearchProvider:
    settings = get_settings()
    name = settings.search_provider.casefold()
    if name == "fixture":
        return FixtureSearchProvider()
    if name != "serpapi":
        raise ValueError(f"Unsupported search provider: {settings.search_provider}")
    provider = SerpApiSearchProvider(
        api_key=settings.serpapi_api_key or settings.serp_api_key
    )
    if not provider.api_key:
        raise RuntimeError("SEARCH_PROVIDER=serpapi requires SERPAPI_API_KEY or SERP_API_KEY")
    return provider


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
        semantic_evaluator: SemanticEvaluator | None = None,
    ) -> None:
        self.provider = provider or default_provider()
        settings = get_settings()
        llm_enabled = use_llm if use_llm is not None else bool(settings.llm_base_url)
        self.parser = IntentParser(use_llm=llm_enabled)
        self.semantic_evaluator = semantic_evaluator or (
            OpenAICompatibleSemanticEvaluator() if llm_enabled else None
        )
        self.semantic_semaphore = asyncio.Semaphore(
            max(1, settings.search_max_concurrent_semantic)
        )
        self.encoder = QueryEncoder()
        self.enable_evidence_fetch = (
            enable_evidence_fetch
            if enable_evidence_fetch is not None
            else settings.pose_fetch_evidence
        )
        self.semaphore = asyncio.Semaphore(max_concurrency or settings.search_max_concurrency)
        self.evidence_semaphore = asyncio.Semaphore(
            max(1, settings.search_max_concurrent_evidence)
        )
        self.rrf_weights = {
            "cached": settings.search_rrf_cached_weight,
            "external": settings.search_rrf_external_weight,
            "sparse": settings.search_rrf_sparse_weight,
            "dense": settings.search_rrf_dense_weight,
            "personalized_dense": settings.search_rrf_personalized_dense_weight,
        }
        self.utility_threshold = utility_threshold if utility_threshold is not None else settings.search_result_threshold
        self.max_reranker_candidates = settings.search_max_reranker_candidates
        self.utility_weights = UtilityWeights(
            relevance=settings.search_relevance_weight,
            preference=settings.search_preference_weight,
            constraints=settings.search_constraint_weight,
            evidence=settings.search_evidence_weight,
            reranker=settings.search_reranker_weight,
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
            "warnings": [],
            "trace": SearchTrace(trace_id=str(uuid4())),
            "budget": SearchBudget(
                max_rounds=settings.search_max_rounds,
                max_queries_per_round=settings.search_max_queries_per_round,
                max_external_calls=settings.search_max_external_calls,
                max_candidates=settings.search_max_candidates,
                max_evidence_documents=settings.search_max_evidence_documents,
                max_concurrent_evidence=settings.search_max_concurrent_evidence,
                max_semantic_evaluations=settings.search_max_semantic_evaluations,
                deadline_seconds=settings.search_deadline_seconds,
            ),
            "executed_queries": [],
        }
        latest_state = cast(SearchState, dict(state))

        def checkpoint(updated: SearchState) -> None:
            latest_state.update(updated)

        state["checkpoint_callback"] = checkpoint
        graph = build_search_graph(self, checkpoint_callback=checkpoint)
        try:
            result = await asyncio.wait_for(
                graph.ainvoke(state), timeout=state["budget"].deadline_seconds
            )
        except TimeoutError:
            latest_state["trace"].record("total", state["budget"].started_at, status="timeout")
            if (
                not latest_state.get("verified_results")
                and not latest_state.get("unverified_results")
                and latest_state.get("candidates")
                and latest_state.get("intent")
            ):
                partial_verified, partial_unverified, partial_excluded = rank_candidates(
                    query=latest_state["intent"].rewritten_query,
                    documents=latest_state["candidates"],
                    fused_scores=latest_state.get("fused_scores", {}),
                    preferences=latest_state.get("selected_preferences", []),
                    criteria=latest_state["intent"].criteria,
                    exclusions=latest_state["intent"].exclusions,
                    limit=request.limit,
                    weights=self.utility_weights,
                )
                latest_state["verified_results"] = partial_verified
                latest_state["unverified_results"] = partial_unverified
                latest_state["excluded_result_count"] = partial_excluded
            return SearchResponse(
                search_id=state["search_id"],
                status="partial",
                intent=latest_state.get("intent"),
                preferences_used=[item.id for item in latest_state.get("selected_preferences", [])],
                verified_results=latest_state.get("verified_results", []),
                unverified_results=latest_state.get("unverified_results", []),
                excluded_result_count=latest_state.get("excluded_result_count", 0),
                errors=[*latest_state.get("errors", []), "Search deadline exceeded"],
                warnings=latest_state.get("warnings", []),
                trace=[
                    SearchTraceSpan(
                        node=event.node,
                        status=event.status,
                        latency_ms=event.latency_ms,
                        attributes=event.attributes,
                    )
                    for event in latest_state["trace"].events
                ],
                tool_calls=latest_state["budget"].external_calls,
                completed_at=datetime.now(timezone.utc),
            )
        return result["response"]

    async def prepare(self, state: dict) -> dict:
        started = time.perf_counter()
        state.setdefault("warnings", [])
        request: SearchRequest = state["request"]
        candidates_preferences = state["preferences"] if request.personalization_enabled else []
        descriptions = [request.query] + [
            f"{item.attribute} {item.value}" for item in candidates_preferences[:100]
        ]
        embedding_started = time.perf_counter()
        initial_batch = coerce_embedding_batch(await self.model_client.embed(descriptions))
        if initial_batch is None:
            state["warnings"].append(
                "Embedding model unavailable; deterministic hashing retrieval is active."
            )
        state["trace"].record(
            "embed_query_and_preferences",
            embedding_started,
            status="ok" if initial_batch else "fallback",
            model_id=initial_batch.space.model_id if initial_batch else None,
            count=len(descriptions),
        )
        query_embedding = initial_batch.embeddings[0] if initial_batch and initial_batch.embeddings else None
        preference_vectors: dict[str, list[float]] = {}
        if initial_batch:
            for item, vector in zip(candidates_preferences[:100], initial_batch.embeddings[1:]):
                preference_vectors[item.id] = vector
        similarities = None
        if initial_batch and query_embedding is not None and preference_vectors:
            from project.backend.search_engine.retrieval.dense import cosine_similarity
            similarities = {}
            for item in candidates_preferences:
                preference_vector = preference_vectors.get(item.id)
                if preference_vector is not None:
                    similarities[item.id] = max(
                        0.0,
                        cosine_similarity(
                            EmbeddingVector(space=initial_batch.space, values=query_embedding),
                            EmbeddingVector(space=initial_batch.space, values=preference_vector),
                        ),
                    )
        selected = retrieve_relevant_preferences(
            request.query,
            candidates_preferences,
            request.context,
            limit=5,
            semantic_similarities=similarities,
        )
        # Resolve explicit query constraints without memory before giving any
        # preference to the LLM rewrite. Revalidate against its final intent below.
        explicit_intent = await DeterministicIntentParser().parse(
            request.query, request.context, []
        )
        if request.context.criteria_overrides is not None:
            explicit_intent = explicit_intent.model_copy(
                update={"criteria": request.context.criteria_overrides}
            )
        if request.context.exclusion_overrides is not None:
            explicit_intent = explicit_intent.model_copy(
                update={"exclusions": request.context.exclusion_overrides}
            )
        selected = [item for item in selected if not conflicts_with_intent(item, explicit_intent)]
        for item in selected:
            item.embedding = preference_vectors.get(item.id)
            item.embedding_space = (
                initial_batch.space
                if item.id in preference_vectors and initial_batch
                else None
            )
        intent, parser_error = await self.parser.parse(
            request.query, request.context, selected
        )
        if request.context.criteria_overrides is not None:
            intent = intent.model_copy(update={"criteria": request.context.criteria_overrides})
        if request.context.exclusion_overrides is not None:
            intent = intent.model_copy(update={"exclusions": request.context.exclusion_overrides})
        selected = [item for item in selected if not conflicts_with_intent(item, intent)]
        intent = merge_explicit_conditions(intent, selected)
        rewritten_started = time.perf_counter()
        rewritten_batch = coerce_embedding_batch(
            await self.model_client.embed([intent.rewritten_query])
        )
        if rewritten_batch is None or (
            initial_batch is not None and rewritten_batch.space != initial_batch.space
        ):
            warning = "Rewritten query embedding unavailable or incompatible; deterministic hashing is active."
            if warning not in state["warnings"]:
                state["warnings"].append(warning)
        state["trace"].record(
            "embed_rewritten_query",
            rewritten_started,
            status="ok" if rewritten_batch else "fallback",
            model_id=rewritten_batch.space.model_id if rewritten_batch else None,
        )
        rewritten_embedding = (
            rewritten_batch.embeddings[0]
            if rewritten_batch and rewritten_batch.embeddings
            else None
        )
        embedding_space = (
            initial_batch.space
            if initial_batch and rewritten_batch and initial_batch.space == rewritten_batch.space
            else None
        )
        if embedding_space is None:
            query_embedding = None
            rewritten_embedding = None
        state["intent"] = intent
        state["selected_preferences"] = selected
        state["embedding_space"] = embedding_space
        state["embedding_model_id"] = embedding_space.model_id if embedding_space else None
        state["query_representation"] = await self.encoder.encode(
            intent,
            selected,
            request.context,
            semantic_similarities=similarities,
            original_query_embedding=query_embedding,
            rewritten_query_embedding=rewritten_embedding,
            embedding_space=embedding_space,
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
        return await execute_retrieval(self, state)

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

    async def rank(self, state: dict) -> dict:
        return await execute_ranking(self, state)

    async def finalize(self, state: dict) -> dict:
        status = state.get("status", "completed")
        if status != "clarification_required":
            status = "partial" if state["errors"] and not state.get("verified_results") else "completed"
        state["trace"].record("finalize_results", time.perf_counter(), status=status)
        state["trace"].record("total", state["budget"].started_at, status=status)
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
            warnings=state["warnings"],
            trace=[
                SearchTraceSpan(
                    node=event.node,
                    status=event.status,
                    latency_ms=event.latency_ms,
                    attributes=event.attributes,
                )
                for event in state["trace"].events
            ],
            completed_at=datetime.now(timezone.utc),
        )
        state["response"] = response
        return state
