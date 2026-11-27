from __future__ import annotations

from collections import defaultdict


DEFAULT_RRF_WEIGHTS = {
    "cached": 0.10,
    "external": 0.225,
    "sparse": 0.225,
    "dense": 0.27,
    "personalized_dense": 0.18,
}


def weighted_reciprocal_rank_fusion(
    rankings: dict[str, list[str]],
    weights: dict[str, float] | None = None,
    k: int = 60,
    personalized_enabled: bool = True,
) -> dict[str, float]:
    weights = dict(weights or DEFAULT_RRF_WEIGHTS)
    if not personalized_enabled and weights.get("personalized_dense", 0):
        removed = weights.pop("personalized_dense")
        active_sum = sum(weights.values()) or 1.0
        for name in weights:
            weights[name] += removed * weights[name] / active_sum
    result: defaultdict[str, float] = defaultdict(float)
    for channel, ranking in rankings.items():
        weight = weights.get(channel, 0.0)
        for rank, document_id in enumerate(ranking, start=1):
            result[document_id] += weight / (k + rank)
    return dict(result)
