from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.evidence import fetch_candidate_evidence
from project.backend.search_engine.models import coerce_embedding_batch
from project.backend.search_engine.retrieval.cache import document_content_hash
from project.backend.search_engine.retrieval.dense import dense_scores
from project.backend.search_engine.retrieval.fusion import weighted_reciprocal_rank_fusion
from project.backend.search_engine.retrieval.sparse import bm25_scores
from project.backend.search_engine.schemas import SearchCandidate, SearchRequest
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id


async def _fetch_evidence_limited(pipeline: Any, document: SearchCandidate) -> bool:
    async with pipeline.evidence_semaphore:
        return await fetch_candidate_evidence(document)


async def execute_retrieval(pipeline: Any, state: dict) -> dict:
    self = pipeline
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
        embedding_space = state.get("embedding_space")
        vector = state["query_representation"].original_embedding
        if repository is None or embedding_space is None or embedding_space.dimension != 1024:
            return []
        try:
            cache_limit = max(1, budget.max_candidates // 3)
            return await repository.search(
                vector,
                embedding_space.model_id,
                cache_limit,
                model_version=embedding_space.model_version,
                dimension=embedding_space.dimension,
                pooling_method=embedding_space.pooling_method,
            )
        except TypeError:
            # Compatibility for injected in-memory repository adapters.
            try:
                return await repository.search(
                    vector, embedding_space.model_id, max(1, budget.max_candidates // 3)
                )
            except Exception as exc:
                state["errors"].append(f"Cached retrieval failed: {type(exc).__name__}")
                return []
        except Exception as exc:
            state["errors"].append(f"Cached retrieval failed: {type(exc).__name__}")
            return []

    async def call_provider(query: str) -> tuple[str, list[SearchCandidate], str | None]:
        call_started = time.perf_counter()
        try:
            async with self.semaphore:
                items = await asyncio.wait_for(
                    self.provider.search(query, budget.max_candidates, request.context),
                    timeout=max(0.01, budget.deadline_seconds - (time.perf_counter() - budget.started_at)),
                )
            state["trace"].record(
                "provider_search", call_started, provider=self.provider.name, status="ok",
                candidate_count=len(items),
            )
            return query, items, None
        except Exception as exc:
            state["trace"].record(
                "provider_search", call_started, provider=self.provider.name,
                status="fallback", error_code=type(exc).__name__,
            )
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
                existing.embedding_dimension = document.embedding_dimension
                existing.embedding_pooling_method = document.embedding_pooling_method
                existing.embedding_content_hash = document.embedding_content_hash
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

    state["candidates"] = documents
    checkpoint = state.get("checkpoint_callback")
    if checkpoint is not None:
        checkpoint(dict(state))

    evidence_started = time.perf_counter()
    evidence_candidates = [
        document
        for document in documents
        if not document.content
    ] if self.enable_evidence_fetch else []
    evidence_count = budget.consume_evidence(len(evidence_candidates))
    evidence_targets = evidence_candidates[:evidence_count]
    await self.emit(state["search_id"], "EVIDENCE_CHECK_STARTED", count=len(evidence_targets))
    evidence_successes = sum(await asyncio.gather(
        *(_fetch_evidence_limited(pipeline, document) for document in evidence_targets)
    )) if evidence_targets else 0
    state["trace"].record(
        "evidence_check",
        evidence_started,
        checked=len(evidence_targets),
        fetched=evidence_successes,
    )

    # Fetch full text before embedding so the vector and cache hash describe the
    # same content that will be evaluated and stored.
    embedding_space = state.get("embedding_space")
    documents_to_embed = [
        item for item in documents
        if embedding_space is not None
        and embedding_space.pooling_method != "hashing"
        and (
            item.embedding is None
            or item.embedding_model != embedding_space.model_id
            or item.embedding_version != embedding_space.model_version
            or item.embedding_dimension != embedding_space.dimension
            or item.embedding_pooling_method != embedding_space.pooling_method
            or len(item.embedding) != embedding_space.dimension
            or item.embedding_content_hash != document_content_hash(item)
        )
    ]
    candidate_embedding_started = time.perf_counter()
    candidate_batch = coerce_embedding_batch(
        await self.model_client.embed(
            [" ".join((item.title, item.snippet, item.content)) for item in documents_to_embed]
        )
    ) if documents_to_embed else None
    if candidate_batch and embedding_space == candidate_batch.space:
        for document, vector in zip(documents_to_embed, candidate_batch.embeddings):
            document.embedding = vector
            document.embedding_model = candidate_batch.space.model_id
            document.embedding_version = candidate_batch.space.model_version
            document.embedding_dimension = candidate_batch.space.dimension
            document.embedding_pooling_method = candidate_batch.space.pooling_method
            document.embedding_content_hash = document_content_hash(document)
    state["trace"].record(
        "embed_documents",
        candidate_embedding_started,
        status="ok" if candidate_batch and embedding_space == candidate_batch.space else "fallback",
        model_id=candidate_batch.space.model_id if candidate_batch else None,
        count=len(documents_to_embed),
    )
    cache_started = time.perf_counter()
    if self.document_repository is not None:
        try:
            await self.document_repository.upsert(documents)
        except Exception as exc:
            state["errors"].append(f"Cached document write failed: {type(exc).__name__}")
    state["trace"].record("document_cache", cache_started, candidate_count=len(documents))
    representation = state["query_representation"]
    state["dense_original_embedding"] = representation.original_vector
    state["dense_personalized_embedding"] = representation.personalized_vector

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
        "dense": [doc.document_id for doc, score in original_dense if score > 0],
        "personalized_dense": [doc.document_id for doc, score in personalized_dense if score > 0],
    }
    fused = weighted_reciprocal_rank_fusion(
        rankings,
        self.rrf_weights,
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
    if checkpoint is not None:
        checkpoint(dict(state))
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

