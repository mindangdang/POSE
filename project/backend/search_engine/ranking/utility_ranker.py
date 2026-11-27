from __future__ import annotations

from dataclasses import dataclass

from project.backend.search_engine.ranking.constraints import assess_candidate
from project.backend.search_engine.retrieval.dense import cosine_similarity
from project.backend.search_engine.retrieval.sparse import tokenize
from project.backend.search_engine.schemas import (
    Criterion,
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
    uncertainty_penalty: float = 0.15
    threshold: float = 0.50


def _overlap(left: str, right: str) -> float:
    a, b = set(tokenize(left)), set(tokenize(right))
    return len(a & b) / len(a | b) if a and b else 0.0


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
) -> tuple[list[SearchResult], list[SearchResult], int]:
    weights = weights or UtilityWeights()
    maximum_fused = max(fused_scores.values(), default=0.0)
    preference_total = sum(w for w in (weights.relevance, weights.preference, weights.constraints, weights.evidence))
    active = {"r": weights.relevance, "p": weights.preference, "c": weights.constraints, "e": weights.evidence}
    if not preferences:
        removed = active.pop("p")
        denominator = sum(active.values()) or 1
        for key in active:
            active[key] += removed * active[key] / denominator
    if not criteria:
        removed = active.pop("c")
        denominator = sum(active.values()) or 1
        for key in active:
            active[key] += removed * active[key] / denominator
    active_total = sum(active.values()) or preference_total or 1

    scored: list[tuple[SearchResult, bool]] = []
    excluded_count = 0
    for document in documents:
        evaluations, hard_violated, hard_unknown = assess_candidate(document, criteria, exclusions)
        if hard_violated:
            excluded_count += 1
            continue
        body = " ".join((document.title, document.snippet, document.content))
        relevance = max(0.0, min(1.0, fused_scores.get(document.document_id, 0.0) / maximum_fused)) if maximum_fused else _overlap(query, body)
        if cross_encoder_scores and document.document_id in cross_encoder_scores:
            relevance = 0.6 * relevance + 0.4 * cross_encoder_scores[document.document_id]
        positive = [p for p in preferences if p.polarity == "positive"]
        preference_values = []
        for item in positive:
            lexical = _overlap(f"{item.attribute} {item.value}", body)
            dense = 0.0
            if item.embedding and document.embedding and len(item.embedding) == len(document.embedding):
                dense = max(0.0, cosine_similarity(item.embedding, document.embedding))
            preference_values.append(max(lexical, dense) * item.weight * item.confidence)
        preference = max(preference_values, default=0.0)
        satisfied = [e for e in evaluations if e.status == "satisfied"]
        unknown = [e for e in evaluations if e.status == "unknown"]
        constraint = len(satisfied) / len(evaluations) if evaluations else 0.5
        evidence = 1.0 if document.content.strip() else 0.5 if document.snippet.strip() else 0.0
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
