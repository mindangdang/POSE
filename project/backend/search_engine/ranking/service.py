from __future__ import annotations

import asyncio
import time
from typing import Any

from project.backend.app.manage.settings import get_settings
from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.ranking.constraints import SemanticJudgment
from project.backend.search_engine.ranking.utility_ranker import rank_candidates
from project.backend.search_engine.schemas import CriterionOperator, SearchCandidate, SearchRequest


async def evaluate_semantics(pipeline: Any, state: dict) -> dict[str, dict[str, SemanticJudgment]]:
    self = pipeline
    judgments: dict[str, dict[str, SemanticJudgment]] = state.setdefault(
        "semantic_judgments", {}
    )
    intent = state["intent"]
    criteria = {item.id: item for item in [*intent.criteria, *intent.exclusions]}
    pending_nodes = [intent.condition] if intent.condition is not None else []
    while pending_nodes:
        node = pending_nodes.pop()
        if node.criterion is not None:
            criteria.setdefault(node.criterion.id, node.criterion)
        else:
            pending_nodes.extend(node.operands)
    semantic_criteria = [
        item for item in criteria.values()
        if item.operator == CriterionOperator.SEMANTIC_MATCH
    ]
    if not semantic_criteria:
        return judgments
    if self.semantic_evaluator is None:
        state["trace"].record(
            "semantic_judgment", time.perf_counter(), status="fallback",
            reason="evaluator_unavailable", checked=0,
        )
        state["warnings"].append(
            "Semantic evaluator unavailable; semantic conditions remain unknown unless supported by structured metadata."
        )
        return judgments

    pending: list[tuple[SearchCandidate, Any, str]] = []
    for document in state["candidates"]:
        evidence = "\n".join(
            part for part in (document.title, document.snippet, document.content) if part
        )[:8000]
        if not evidence:
            continue
        for criterion in semantic_criteria:
            if criterion.id in judgments.get(document.document_id, {}):
                continue
            if any(key.casefold() == criterion.attribute.casefold() for key in document.metadata):
                continue
            pending.append((document, criterion, evidence))

    budget: SearchBudget = state["budget"]
    granted = budget.consume_semantic(len(pending))
    bounded = pending[:granted]
    started = time.perf_counter()
    failures = 0

    async def judge(document: SearchCandidate, criterion, evidence: str) -> None:
        nonlocal failures
        try:
            async with self.semantic_semaphore:
                raw = await asyncio.wait_for(
                    self.semantic_evaluator.evaluate(criterion, evidence),
                    timeout=get_settings().search_semantic_timeout_seconds,
                )
            judgment = raw if isinstance(raw, SemanticJudgment) else SemanticJudgment.model_validate(raw)
            judgments.setdefault(document.document_id, {})[criterion.id] = judgment
        except Exception:
            failures += 1

    await asyncio.gather(*(judge(*item) for item in bounded))
    state["trace"].record(
        "semantic_judgment",
        started,
        status="fallback" if failures or granted < len(pending) else "ok",
        checked=len(bounded) - failures,
        failed=failures,
        budget_exhausted=max(0, len(pending) - granted),
        model_id=getattr(self.semantic_evaluator, "model", type(self.semantic_evaluator).__name__),
    )
    if failures or granted < len(pending):
        state["errors"].append("Some semantic criteria could not be evaluated within the search budget")
    return judgments



async def execute_ranking(pipeline: Any, state: dict) -> dict:
    self = pipeline
    if state.get("status") == "clarification_required":
        return state
    request: SearchRequest = state["request"]
    intent = state["intent"]
    semantic_judgments = await evaluate_semantics(pipeline, state)
    await self.emit(state["search_id"], "RANKING_STARTED", count=min(30, len(state["candidates"])))
    rerank_docs = [
        {
            "id": document.document_id,
            "text": " ".join((document.title, document.snippet, document.content))[:20000],
        }
        for document in state["candidates"][: self.max_reranker_candidates]
    ]
    rerank_started = time.perf_counter()
    reranked = await self.model_client.rerank(intent.rewritten_query, rerank_docs)
    if reranked:
        raw_scores, model_id = reranked
        import math

        state["reranker_scores"] = {
            document_id: 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, score))))
            for document_id, score in raw_scores.items()
        }
        state["trace"].record("cross_encoder", rerank_started, model_id=model_id, candidate_count=len(raw_scores))
    else:
        state["trace"].record("cross_encoder", rerank_started, status="fallback", candidate_count=len(rerank_docs))
        if rerank_docs:
            state["warnings"].append(
                "Cross-encoder unavailable; ranking uses deterministic utility signals."
            )
    utility_started = time.perf_counter()
    verified, unverified, excluded = rank_candidates(
        query=intent.rewritten_query,
        documents=state["candidates"],
        fused_scores=state["fused_scores"],
        preferences=state["selected_preferences"],
        criteria=intent.criteria,
        exclusions=intent.exclusions,
        limit=request.limit,
        cross_encoder_scores=state.get("reranker_scores"),
        semantic_judgments=semantic_judgments,
        condition=intent.condition,
        weights=self.utility_weights,
    )
    state.update(
        verified_results=verified,
        unverified_results=unverified,
        excluded_result_count=excluded,
    )
    state["trace"].record(
        "utility_ranking",
        utility_started,
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

