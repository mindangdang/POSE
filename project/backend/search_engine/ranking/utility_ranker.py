from __future__ import annotations

from dataclasses import dataclass

from project.backend.search_engine.ranking.constraints import (
    SemanticJudgment,
    assess_candidate,
    evaluate_expression,
)
from project.backend.search_engine.retrieval.dense import cosine_similarity
from project.backend.search_engine.retrieval.sparse import tokenize
from project.backend.search_engine.schemas import (
    Criterion,
    ConditionExpression,
    Preference,
    RankingFeatures,
    SearchCandidate,
    SearchResult,
)


@dataclass(frozen=True)
class UtilityWeights:
    relevance: float = 0.40
    preference: float = 0.20
    constraints: float = 0.25
    evidence: float = 0.15
    reranker: float = 0.35
    uncertainty_penalty: float = 0.15
    threshold: float = 0.50


def _preference_coverage(preference_text: str, document_text: str) -> float:
    wanted, available = set(tokenize(preference_text)), set(tokenize(document_text))
    return len(wanted & available) / len(wanted) if wanted else 0.0


def rank_candidates(
    query: str,
    documents: list[SearchCandidate],
    fused_scores: dict[str, float],
    preferences: list[Preference],
    criteria: list[Criterion],
    exclusions: list[Criterion],
    limit: int = 10,
    weights: UtilityWeights | None = None,
    cross_encoder_scores: dict[str, float] | None = None,
    semantic_judgments: dict[str, dict[str, SemanticJudgment]] | None = None,
    condition: ConditionExpression | None = None,
) -> tuple[list[SearchResult], list[SearchResult], int]:
    weights = weights or UtilityWeights()
    preference_total = sum(w for w in (weights.relevance, weights.preference, weights.constraints, weights.evidence))
    active = {"r": weights.relevance, "p": weights.preference, "c": weights.constraints, "e": weights.evidence}
    if not preferences:
        removed = active.pop("p")
        denominator = sum(active.values()) or 1
        for key in active:
            active[key] += removed * active[key] / denominator
    if not any(item.weight * item.confidence > 0 for item in [*criteria, *exclusions]):
        removed = active.pop("c")
        denominator = sum(active.values()) or 1
        for key in active:
            active[key] += removed * active[key] / denominator
    active_total = sum(active.values()) or preference_total or 1

    scored: list[tuple[SearchResult, bool]] = []
    excluded_count = 0
    for document in documents:
        evaluations, hard_violated, hard_unknown = assess_candidate(
            document, criteria, exclusions, semantic_judgments
        )
        condition_evaluation = (
            evaluate_expression(condition, document, semantic_judgments)
            if condition is not None
            else None
        )
        if condition_evaluation is not None:
            assert condition is not None
            known_ids = {item.criterion_id for item in evaluations}
            evaluations.extend(
                item
                for item in condition_evaluation.evaluations
                if item.criterion_id not in known_ids
            )
            expression_criteria: list[Criterion] = []
            pending = [condition]
            while pending:
                node = pending.pop()
                if node.criterion is not None:
                    expression_criteria.append(node.criterion)
                else:
                    pending.extend(node.operands)
            if any(item.is_hard_constraint for item in expression_criteria):
                hard_violated = hard_violated or condition_evaluation.status == "violated"
                hard_unknown = hard_unknown or condition_evaluation.status == "unknown"
        if hard_violated:
            excluded_count += 1
            continue
        body = " ".join((document.title, document.snippet, document.content))
        # RRF is a relative retrieval score. It can order candidates, but it is
        # not a calibrated relevance probability and must not set the threshold.
        lexical_relevance = _preference_coverage(query, body)
        reranker_score = (cross_encoder_scores or {}).get(document.document_id)
        relevance = (
            lexical_relevance * (1 - weights.reranker)
            + max(0.0, min(1.0, reranker_score)) * weights.reranker
            if reranker_score is not None
            else lexical_relevance
        )
        positive = [p for p in preferences if p.polarity == "positive"]
        negative = [p for p in preferences if p.polarity == "negative"]

        def preference_match(item: Preference) -> float:
            lexical = _preference_coverage(item.value, body)
            dense = 0.0
            if item.embedding and document.embedding and len(item.embedding) == len(document.embedding):
                dense = max(0.0, cosine_similarity(item.embedding, document.embedding))
            return max(lexical, dense)

        positive_weight = sum(item.weight * item.confidence for item in positive)
        negative_weight = sum(item.weight * item.confidence for item in negative)
        positive_score = (
            sum(preference_match(item) * item.weight * item.confidence for item in positive)
            / positive_weight
            if positive_weight
            else 0.0
        )
        negative_score = (
            sum(preference_match(item) * item.weight * item.confidence for item in negative)
            / negative_weight
            if negative_weight
            else 0.0
        )
        preference = max(0.0, min(1.0, positive_score - negative_score))
        satisfied = [e for e in evaluations if e.status == "satisfied"]
        unknown = [e for e in evaluations if e.status == "unknown"]
        criteria_by_id = {item.id: item for item in [*criteria, *exclusions]}
        if condition is not None:
            assert condition is not None
            pending = [condition]
            while pending:
                node = pending.pop()
                if node.criterion is not None:
                    criteria_by_id.setdefault(node.criterion.id, node.criterion)
                else:
                    pending.extend(node.operands)
        criterion_weights = {
            evaluation.criterion_id: criteria_by_id[evaluation.criterion_id].weight
            * criteria_by_id[evaluation.criterion_id].confidence
            * evaluation.confidence
            for evaluation in evaluations
        }
        total_criterion_weight = sum(criterion_weights.values())
        if condition_evaluation is not None:
            condition_score = {
                "satisfied": 1.0,
                "violated": 0.0,
                "unknown": 0.5,
            }[condition_evaluation.status]
            constraint = condition_score if total_criterion_weight else 0.5
        else:
            constraint = (
                sum(
                (1.0 if item.status == "satisfied" else 0.5 if item.status == "unknown" else 0.0)
                * criterion_weights[item.criterion_id]
                for item in evaluations
                )
                / total_criterion_weight
                if total_criterion_weight
                else 0.5
            )
        availability = 1.0 if document.content.strip() else 0.5 if document.snippet.strip() else 0.0
        evidence = availability
        if document.content.strip():
            evidence = 1.0 if document.fetched_at is not None or document.source != "unknown" else 0.75
        uncertainty = len(unknown) / len(evaluations) if evaluations else (0.0 if document.content or document.snippet else 0.5)
        score = (
            active.get("r", 0) * relevance
            + active.get("p", 0) * preference
            + active.get("c", 0) * constraint
            + active.get("e", 0) * evidence
        ) / active_total - weights.uncertainty_penalty * uncertainty
        score = max(0.0, min(1.0, score))
        is_verified = not hard_unknown and bool(document.content.strip() or document.snippet.strip())
        reason_parts = []
        if relevance > 0:
            reason_parts.append("검색어와 관련된 내용이 있습니다")
        if preference > 0:
            reason_parts.append("저장된 선호와 일치하는 단서가 있습니다")
        if satisfied:
            reason_parts.append("조건을 확인할 근거가 있습니다")
        if unknown:
            reason_parts.append("확인하지 못한 조건이 있습니다")
        result = SearchResult(
            document=document,
            rank=0,
            score=score,
            verified=is_verified,
            reason="; ".join(reason_parts) or "검색 결과로 수집되었습니다",
            satisfied_criteria=[e.criterion_id for e in satisfied],
            uncertain_criteria=[e.criterion_id for e in unknown],
            evaluations=evaluations,
            features=RankingFeatures(
                query_relevance=relevance,
                preference_compatibility=preference,
                constraint_satisfaction=constraint,
                evidence_quality=evidence,
                content_availability=availability,
                uncertainty=uncertainty,
            ),
        )
        scored.append((result, hard_unknown))

    scored.sort(key=lambda item: (-item[0].score, item[0].document.document_id))
    verified_results: list[SearchResult] = []
    unverified: list[SearchResult] = []
    for result, hard_unknown in scored:
        if result.score < weights.threshold:
            continue
        target = unverified if hard_unknown or not result.verified else verified_results
        target.append(result)
    for index, result in enumerate(verified_results[:limit], start=1):
        result.rank = index
    for index, result in enumerate(unverified[:limit], start=1):
        result.rank = index
    return verified_results[:limit], unverified[:limit], excluded_count
