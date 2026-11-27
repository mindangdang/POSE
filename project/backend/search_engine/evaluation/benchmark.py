from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
from statistics import median
import time
from pathlib import Path
from typing import Any

from project.backend.search_engine.evaluation.baselines import baseline_rankings
from project.backend.search_engine.evaluation.metrics import (
    aggregate_metrics,
    personalized_pairwise_accuracy,
)
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import Preference, SearchContext, SearchRequest
from project.backend.search_engine.sources.fixture import FixtureSearchProvider


class NoopModelServer:
    async def embed(self, texts):
        return None

    async def rerank(self, query, documents):
        return None


def load_cases() -> list[dict]:
    path = Path(__file__).with_name("datasets") / "pose_v2_fixture.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_benchmark(output_dir: Path) -> dict:
    cases = load_cases()
    provider = FixtureSearchProvider()
    documents = await provider.search("fixture corpus", 50, SearchContext())
    rankings: dict[str, list[list[str]]] = {name: [] for name in (
        "B0_external", "B1_bm25", "B2_dense", "B3_hybrid", "B4_rewrite_hybrid",
        "B5_reranker_fallback", "B6_static_user_vector", "B7_query_conditioned", "B8_pose_full",
    )}
    latency_ms: list[float] = []
    tool_calls: list[int] = []
    hard_violations: list[float] = []
    unknown_rates: list[float] = []
    evidence_coverage: list[float] = []
    duplicate_rates: list[float] = []

    for case in cases:
        preferences = [Preference.model_validate(item) for item in case.get("preferences", [])]
        context = SearchContext(
            session_id=case["query_id"],
            criteria_overrides=case.get("criteria") or None,
            exclusion_overrides=case.get("exclusions") or None,
        )
        baseline = await baseline_rankings(case["query"], documents, preferences, context)
        for name, order in baseline.items():
            rankings[name].append(order)
        request = SearchRequest(query=case["query"], context=context, limit=10)
        started = time.perf_counter()
        response = await SearchPipeline(
            provider=provider,
            use_llm=False,
            enable_evidence_fetch=False,
            model_client=NoopModelServer(),
        ).run(request, user_id=case["user_profile_id"], preferences=preferences, search_id=case["query_id"])
        latency_ms.append((time.perf_counter() - started) * 1000)
        tool_calls.append(response.tool_calls)
        full = [*response.verified_results, *response.unverified_results]
        full.sort(key=lambda item: (not item.verified, item.rank))
        order = [item.document.document_id for item in full]
        rankings["B8_pose_full"].append(order)
        known = [case["hard_constraint_labels"].get(doc_id) for doc_id in order]
        known = [value for value in known if value is not None]
        hard_violations.append(sum(value == "violated" for value in known) / len(known) if known else 0.0)
        unknown_rates.append(sum(value == "unknown" for value in known) / len(known) if known else 0.0)
        evidence_coverage.append(
            sum(bool(item.evaluations and any(e.evidence_excerpt for e in item.evaluations)) for item in full)
            / len(full)
            if full else 0.0
        )
        duplicate_rates.append((len(order) - len(set(order))) / len(order) if order else 0.0)

    report: dict[str, Any] = {
        "dataset": "pose_v2_fixture.jsonl",
        "label_source": "synthetic_fixture (not human-validated)",
        "case_count": len(cases),
        "baselines": {
            name: {
                **aggregate_metrics(cases, orders),
                "personalized_pairwise_accuracy": personalized_pairwise_accuracy(cases, orders),
            }
            for name, orders in rankings.items()
        },
        "full_pipeline_operational": {
            "mean_latency_ms": sum(latency_ms) / max(len(latency_ms), 1),
            "p50_latency_ms": median(latency_ms) if latency_ms else None,
            "p95_latency_ms": sorted(latency_ms)[max(0, math.ceil(len(latency_ms) * 0.95) - 1)] if latency_ms else None,
            "mean_tool_calls": sum(tool_calls) / max(len(tool_calls), 1),
            "hard_constraint_violation_rate": sum(hard_violations) / max(len(hard_violations), 1),
            "unknown_constraint_rate": sum(unknown_rates) / max(len(unknown_rates), 1),
            "evidence_coverage": sum(evidence_coverage) / max(len(evidence_coverage), 1),
            "duplicate_rate": sum(duplicate_rates) / max(len(duplicate_rates), 1),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["baseline", *next(iter(report["baselines"].values())).keys()])
        writer.writeheader()
        for name, metrics in report["baselines"].items():
            writer.writerow({"baseline": name, **metrics})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline POSE v2 benchmark; uses deterministic fixtures only.")
    parser.add_argument("--output-dir", default="project/backend/search_engine/evaluation/results")
    args = parser.parse_args()
    report = asyncio.run(run_benchmark(Path(args.output_dir)))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
