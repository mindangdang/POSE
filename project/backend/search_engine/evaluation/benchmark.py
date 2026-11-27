from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
from pathlib import Path
from statistics import median
import time
from typing import Any

from project.backend.search_engine.evaluation.baselines import baseline_rankings
from project.backend.search_engine.evaluation.metrics import (
    aggregate_metrics,
    personalized_pairwise_accuracy,
)
from project.backend.search_engine.models import ModelServerClient, SearchModelClient
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import Preference, SearchContext, SearchRequest
from project.backend.search_engine.sources.fixture import FixtureSearchProvider


class NoopModelServer:
    async def embed(self, texts):
        return None

    async def rerank(self, query, documents):
        return None


def load_cases() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("datasets") / "pose_v2_fixture.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _full_results(response):
    return [*response.verified_results, *response.unverified_results]


def _constraint_summary(cases: list[dict[str, Any]], orders: list[list[str]]) -> dict[str, float]:
    violations: list[float] = []
    unknowns: list[float] = []
    for case, order in zip(cases, orders):
        labels = case["hard_constraint_labels"]
        known = [labels[doc_id] for doc_id in order if doc_id in labels]
        violations.append(sum(value == "violated" for value in known) / len(known) if known else 0.0)
        unknowns.append(sum(value == "unknown" for value in known) / len(known) if known else 0.0)
    return {
        "hard_constraint_violation_rate": sum(violations) / max(len(violations), 1),
        "unknown_constraint_rate": sum(unknowns) / max(len(unknowns), 1),
    }


def _evidence_coverage(responses: list[Any]) -> float:
    returned = [result for response in responses for result in _full_results(response)]
    return (
        sum(bool(result.evaluations and any(item.evidence_excerpt for item in result.evaluations)) for result in returned)
        / len(returned)
        if returned
        else 0.0
    )


async def run_benchmark(
    output_dir: Path,
    model_client: SearchModelClient | None = None,
) -> dict[str, Any]:
    cases = load_cases()
    provider = FixtureSearchProvider()
    documents = await provider.search("fixture corpus", 50, SearchContext())
    active_model = model_client or NoopModelServer()
    baseline_orders: dict[str, list[list[str]]] = {}
    ground_truth_orders: list[list[str]] = []
    end_to_end_orders: list[list[str]] = []
    end_to_end_responses = []
    end_to_end_latency: list[float] = []
    tool_calls: list[int] = []
    duplicate_rates: list[float] = []
    cross_encoder_orders: list[list[str]] = []
    observed_embedding_models: set[str] = set()
    hashing_fallback_cases = 0
    every_case_reranked = True

    for case in cases:
        preferences = [Preference.model_validate(item) for item in case.get("preferences", [])]
        baseline_context = SearchContext(
            session_id=case["query_id"],
            criteria_overrides=case.get("criteria") or None,
            exclusion_overrides=case.get("exclusions") or None,
        )
        baseline = await baseline_rankings(
            case["query"], documents, preferences, baseline_context
        )
        for name, order in baseline.items():
            baseline_orders.setdefault(name, []).append(order)

        rerank_docs = [
            {
                "id": document.document_id,
                "text": " ".join((document.title, document.snippet, document.content))[:20000],
            }
            for document in documents[:30]
        ]
        reranked = await active_model.rerank(case["query"], rerank_docs)
        if reranked is None or not reranked[0]:
            every_case_reranked = False
        else:
            cross_encoder_orders.append(
                sorted(
                    (document.document_id for document in documents),
                    key=lambda doc_id: (-reranked[0].get(doc_id, float("-inf")), doc_id),
                )
            )

        ground_truth_request = SearchRequest(
            query=case["query"], context=baseline_context, limit=10
        )
        ground_truth_response = await SearchPipeline(
            provider=provider,
            use_llm=False,
            enable_evidence_fetch=False,
            model_client=active_model,
        ).run(
            ground_truth_request,
            user_id=case["user_profile_id"],
            preferences=preferences,
            search_id=case["query_id"] + "-gt",
        )
        ground_truth_order = [item.document.document_id for item in _full_results(ground_truth_response)]
        ground_truth_orders.append(ground_truth_order)

        end_to_end_request = SearchRequest(
            query=case["query"],
            context=SearchContext(session_id=case["query_id"]),
            limit=10,
        )
        started = time.perf_counter()
        end_to_end_response = await SearchPipeline(
            provider=provider,
            use_llm=False,
            enable_evidence_fetch=False,
            model_client=active_model,
        ).run(
            end_to_end_request,
            user_id=case["user_profile_id"],
            preferences=preferences,
            search_id=case["query_id"] + "-e2e",
        )
        end_to_end_latency.append((time.perf_counter() - started) * 1000)
        end_to_end_responses.append(end_to_end_response)
        embedding_spans = [
            span
            for span in end_to_end_response.trace
            if span.node in {"embed_query_and_preferences", "embed_documents"}
        ]
        observed_embedding_models.update(
            str(span.attributes["model_id"])
            for span in embedding_spans
            if span.attributes.get("model_id")
        )
        if any(span.status == "fallback" for span in embedding_spans):
            hashing_fallback_cases += 1
        end_to_end_order = [item.document.document_id for item in _full_results(end_to_end_response)]
        end_to_end_orders.append(end_to_end_order)
        tool_calls.append(end_to_end_response.tool_calls)
        duplicate_rates.append(
            (len(end_to_end_order) - len(set(end_to_end_order))) / len(end_to_end_order)
            if end_to_end_order
            else 0.0
        )

    if every_case_reranked and len(cross_encoder_orders) == len(cases):
        baseline_orders["B5_cross_encoder"] = cross_encoder_orders

    baseline_metrics = {
        name: {
            **aggregate_metrics(cases, orders),
            "personalized_pairwise_accuracy": personalized_pairwise_accuracy(cases, orders),
        }
        for name, orders in baseline_orders.items()
    }
    p95_latency = (
        sorted(end_to_end_latency)[max(0, math.ceil(len(end_to_end_latency) * 0.95) - 1)]
        if end_to_end_latency
        else None
    )
    report: dict[str, Any] = {
        "dataset": "pose_v2_fixture.jsonl",
        "label_source": "synthetic_fixture (not human-validated)",
        "case_count": len(cases),
        "model_execution": {
            "observed_embedding_models": sorted(observed_embedding_models),
            "hashing_fallback_cases": hashing_fallback_cases,
            "cross_encoder": "measured" if "B5_cross_encoder" in baseline_orders else "not_run_or_unavailable",
            "cross_encoder_scored_cases": len(cross_encoder_orders),
        },
        "baselines": baseline_metrics,
        "evaluation_modes": {
            "ground_truth_criteria": {
                "input": "Synthetic labeled criteria passed directly as request overrides; intent extraction quality is not measured.",
                "metrics": aggregate_metrics(cases, ground_truth_orders),
                **_constraint_summary(cases, ground_truth_orders),
            },
            "end_to_end_intent": {
                "input": "Original query only; the deterministic intent parser extracts criteria without labeled overrides.",
                "metrics": aggregate_metrics(cases, end_to_end_orders),
                **_constraint_summary(cases, end_to_end_orders),
            },
        },
        "full_pipeline_operational": {
            "measurement_mode": "end_to_end_intent",
            "mean_latency_ms": sum(end_to_end_latency) / max(len(end_to_end_latency), 1),
            "p50_latency_ms": median(end_to_end_latency) if end_to_end_latency else None,
            "p95_latency_ms": p95_latency,
            "mean_external_query_calls": sum(tool_calls) / max(len(tool_calls), 1),
            "evidence_coverage": _evidence_coverage(end_to_end_responses),
            "duplicate_rate": sum(duplicate_rates) / max(len(duplicate_rates), 1),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_metrics = next(iter(baseline_metrics.values()), {})
    with (output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["baseline", *csv_metrics.keys()],
            lineterminator="\n",
        )
        writer.writeheader()
        for name, metrics in baseline_metrics.items():
            writer.writerow({"baseline": name, **metrics})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline POSE v2 benchmark; uses deterministic fixtures only.")
    parser.add_argument("--output-dir", default="project/backend/search_engine/evaluation/results")
    parser.add_argument(
        "--model-server-url",
        help="Optional model server endpoint. B5 is reported only if every case returns reranker scores.",
    )
    args = parser.parse_args()
    client = ModelServerClient(args.model_server_url) if args.model_server_url else None
    report = asyncio.run(run_benchmark(Path(args.output_dir), client))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
