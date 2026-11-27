# Evaluation

## Deterministic fixture benchmark

Run `just eval` (or `python3 -m project.backend.search_engine.evaluation.generate_dataset` followed by `python3 -m project.backend.search_engine.evaluation.benchmark`). It creates 30 deterministic synthetic cases over a 10-document fixture corpus and writes `report.json` and `metrics.csv` beneath `project/backend/search_engine/evaluation/results/`.

Labels are explicitly marked `synthetic_fixture`, not human-reviewed judgments. The default benchmark uses the same fixture corpus and deterministic hashing without network/model weights. B0–B4 and B6/B7 are wiring/baseline comparisons only. B5 is omitted unless a model server actually returns cross-encoder scores for every case; pass `--model-server-url` to opt into that measurement. B6 and B7 use the same query text, candidate corpus, hashing dense channel, and ranker; only the static profile representation versus query-conditioned preference representation changes. They are lightweight hashing baselines, not trained user towers.

The report separates two evaluation modes. `ground_truth_criteria` passes synthetic labeled criteria directly as request overrides and measures ranking with those criteria; it does not measure intent extraction. `end_to_end_intent` passes the original query without criterion overrides so the deterministic intent parser must infer criteria. Both use the same synthetic relevance and hard-constraint labels, which still do not represent human judgments.

Metrics include Recall@5/10, Precision@5/10, NDCG@5/10, MRR, personalized pairwise accuracy across same-query profiles with conflicting judgments, plus end-to-end operational measures: mean/P50/P95 wall latency, external query count, evidence coverage, and duplicate rate. Constraint violation and unknown rates are reported separately for the two evaluation modes. A query with no relevant labels is excluded from recall/NDCG/MRR denominators; precision still uses the requested `k`. A constraint rate with no labeled returned results contributes 0 for that case and is an operational summary, not a quality judgment.

The checked-in report is generated from the latest local run. Treat fixture latency as an in-process measurement only; comparisons against older reports are not apples-to-apples when evaluation modes or execution counts change. These metrics are not real-web quality or service-latency claims.

## AutoRAG Legacy

`evaluation/autorag_adapter.py` exports the official Legacy `corpus.parquet` and `qa.parquet` columns (`doc_id`, `contents`, `metadata`; `qid`, `query`, `retrieval_gt`, `generation_gt`). Pandas and a Parquet engine are optional. `evaluation/configs/autorag_legacy.yaml` sketches lexical, semantic, hybrid RRF, and reranker experiments. AutoRAG itself is intentionally not part of the API runtime. The adapter/config have not been run against an installed AutoRAG Legacy environment yet.

Official references: [AutoRAG Legacy repository](https://github.com/Marker-Inc-Korea/AutoRAG/tree/main/legacy), [data format](https://marker-inc-korea.github.io/AutoRAG/data_creation/data_format.html), and [retrieval nodes](https://marker-inc-korea.github.io/AutoRAG/nodes/retrieval/retrieval.html).

## Interpretation and limitations

Do not claim user-level quality gains from the synthetic fixture. Collect a human-reviewed held-out dataset before tuning weights. Keep profiles and related queries together in train/dev/test splits to avoid profile leakage. Report external API candidate-generation results separately from same-corpus retrieval experiments. Do not report model latency unless the relevant local model is actually loaded and measured.
