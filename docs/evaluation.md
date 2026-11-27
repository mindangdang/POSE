# Evaluation

## Deterministic fixture benchmark

Run `just eval` (or `python3 -m project.backend.search_engine.evaluation.generate_dataset` followed by `python3 -m project.backend.search_engine.evaluation.benchmark`). It creates 30 deterministic synthetic cases over a 10-document fixture corpus and writes `report.json` and `metrics.csv` beneath `project/backend/search_engine/evaluation/results/`.

Labels are explicitly marked `synthetic_fixture`, not human-reviewed judgments. The benchmark uses the same fixture corpus and no network/model weights. B0–B8 outputs are useful wiring/baseline comparisons only. In particular B5 currently duplicates hybrid fallback ranking because no cross-encoder is loaded in the offline baseline harness; B6/B7 are lightweight hashing baselines, not trained user towers.

Metrics include Recall@5/10, Precision@5/10, NDCG@5/10, MRR, personalized pairwise accuracy across same-query profiles with conflicting judgments, plus operational metrics for the full pipeline: mean/P50/P95 wall latency, mean external query count, hard-constraint violation rate, unknown rate, evidence coverage, and duplicate rate. A query with no relevant labels is excluded from recall/NDCG/MRR denominators; precision still uses the requested `k`. A constraint rate with no labeled returned results contributes 0 for that case and is therefore an operational summary, not a quality judgment.

Latest local fixture run: 30 cases; B8 POSE full achieved Recall@5 0.944, NDCG@5 0.991, MRR 1.000, and query-conditioned personalized pairwise accuracy 1.000. The same run reported 10.01 ms mean latency, 5.31 ms P50, 6.52 ms P95, 3.4 mean external query calls, 0 hard-constraint violations, 0 unknown-constraint rate, 0.833 evidence coverage, and 0 duplicate rate. These are synthetic, in-process fixture measurements; they are not real-web quality or service-latency claims.

## AutoRAG Legacy

`evaluation/autorag_adapter.py` exports the official Legacy `corpus.parquet` and `qa.parquet` columns (`doc_id`, `contents`, `metadata`; `qid`, `query`, `retrieval_gt`, `generation_gt`). Pandas and a Parquet engine are optional. `evaluation/configs/autorag_legacy.yaml` sketches lexical, semantic, hybrid RRF, and reranker experiments. AutoRAG itself is intentionally not part of the API runtime. The adapter/config have not been run against an installed AutoRAG Legacy environment yet.

Official references: [AutoRAG Legacy repository](https://github.com/Marker-Inc-Korea/AutoRAG/tree/main/legacy), [data format](https://marker-inc-korea.github.io/AutoRAG/data_creation/data_format.html), and [retrieval nodes](https://marker-inc-korea.github.io/AutoRAG/nodes/retrieval/retrieval.html).

## Interpretation and limitations

Do not claim user-level quality gains from the synthetic fixture. Collect a human-reviewed held-out dataset before tuning weights. Keep profiles and related queries together in train/dev/test splits to avoid profile leakage. Report external API candidate-generation results separately from same-corpus retrieval experiments. Do not report model latency unless the relevant local model is actually loaded and measured.
