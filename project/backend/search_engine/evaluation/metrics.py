from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable


def recall_at_k(ranking: list[str], labels: dict[str, int], k: int) -> float | None:
    relevant = {doc_id for doc_id, grade in labels.items() if grade > 0}
    if not relevant:
        return None
    return len(set(ranking[:k]) & relevant) / len(relevant)


def precision_at_k(ranking: list[str], labels: dict[str, int], k: int) -> float:
    return sum(labels.get(doc_id, 0) > 0 for doc_id in ranking[:k]) / k


def ndcg_at_k(ranking: list[str], labels: dict[str, int], k: int) -> float | None:
    if not any(grade > 0 for grade in labels.values()):
        return None
    dcg = sum((2 ** labels.get(doc_id, 0) - 1) / math.log2(index + 2) for index, doc_id in enumerate(ranking[:k]))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
    return dcg / idcg if idcg else None


def reciprocal_rank(ranking: list[str], labels: dict[str, int]) -> float | None:
    if not any(grade > 0 for grade in labels.values()):
        return None
    for index, doc_id in enumerate(ranking, start=1):
        if labels.get(doc_id, 0) > 0:
            return 1.0 / index
    return 0.0


def personalized_pairwise_accuracy(
    cases: list[dict], rankings: list[list[str]]
) -> float | None:
    grouped: defaultdict[str, list[tuple[dict, list[str]]]] = defaultdict(list)
    for case, ranking in zip(cases, rankings):
        grouped[case["query"]].append((case, ranking))
    correct = total = 0
    for variants in grouped.values():
        for index, (left_case, left_rank) in enumerate(variants):
            left_positions = {doc_id: i for i, doc_id in enumerate(left_rank)}
            for right_case, right_rank in variants[index + 1 :]:
                right_positions = {doc_id: i for i, doc_id in enumerate(right_rank)}
                docs = set(left_case["relevance_labels"]) & set(right_case["relevance_labels"])
                for first in docs:
                    for second in docs:
                        left_pref = left_case["relevance_labels"][first] - left_case["relevance_labels"][second]
                        right_pref = right_case["relevance_labels"][first] - right_case["relevance_labels"][second]
                        if left_pref != 0 and right_pref != 0 and left_pref == right_pref:
                            continue
                        # A pair contributes only when users explicitly order it differently.
                        if left_pref * right_pref >= 0:
                            continue
                        total += 1
                        left_agrees = left_positions.get(first, 10**6) < left_positions.get(second, 10**6)
                        right_agrees = right_positions.get(first, 10**6) < right_positions.get(second, 10**6)
                        correct += int(
                            left_agrees == (left_pref > 0)
                            and right_agrees == (right_pref > 0)
                        )
    return correct / total if total else None


def aggregate_metrics(cases: list[dict], rankings: list[list[str]]) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for k in (5, 10):
        recall_values = [recall_at_k(order, case["relevance_labels"], k) for case, order in zip(cases, rankings)]
        ndcg_values = [ndcg_at_k(order, case["relevance_labels"], k) for case, order in zip(cases, rankings)]
        metrics[f"recall@{k}"] = _mean(recall_values)
        metrics[f"precision@{k}"] = _mean([precision_at_k(order, case["relevance_labels"], k) for case, order in zip(cases, rankings)])
        metrics[f"ndcg@{k}"] = _mean(ndcg_values)
    metrics["mrr"] = _mean([reciprocal_rank(order, case["relevance_labels"]) for case, order in zip(cases, rankings)])
    return metrics


def _mean(values: Iterable[float | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None
