from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from project.backend.search_engine.evaluation.benchmark import load_cases
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.schemas import SearchContext


async def export_parquet(output_dir: Path) -> tuple[Path, Path]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "AutoRAG export needs the optional evaluation dependencies: pandas and pyarrow. "
            "Install them in a separate evaluation environment."
        ) from exc
    cases = load_cases()
    corpus = await FixtureSearchProvider().search("fixture corpus", 50, SearchContext())
    now = datetime.now(timezone.utc)
    corpus_rows = [
        {
            "doc_id": item.document_id,
            "contents": " ".join((item.title, item.snippet, item.content)),
            "path": item.canonical_url,
            "metadata": {
                **item.metadata,
                "source": item.source,
                "last_modified_datetime": item.fetched_at or now,
            },
        }
        for item in corpus
    ]
    qa_rows = []
    for case in cases:
        relevant = [
            document_id
            for document_id, grade in case["relevance_labels"].items()
            if grade > 0
        ]
        accepted = [
            " ".join((item.title, item.snippet, item.content))
            for item in corpus
            if item.document_id in relevant
        ]
        qa_rows.append(
            {
                "qid": case["query_id"],
                "query": case["query"],
                "retrieval_gt": [relevant] if relevant else [],
                "generation_gt": accepted,
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path, qa_path = output_dir / "corpus.parquet", output_dir / "qa.parquet"
    pd.DataFrame(corpus_rows).reset_index(drop=True).to_parquet(corpus_path, index=False)
    pd.DataFrame(qa_rows).reset_index(drop=True).to_parquet(qa_path, index=False)
    return corpus_path, qa_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export fixtures to AutoRAG Legacy Parquet schema.")
    parser.add_argument("--output-dir", default="project/backend/search_engine/evaluation/autorag_export")
    args = parser.parse_args()
    import asyncio

    try:
        corpus_path, qa_path = asyncio.run(export_parquet(Path(args.output_dir)))
    except Exception as exc:
        raise SystemExit(f"AutoRAG export not completed: {exc}") from exc
    print(json.dumps({"corpus": str(corpus_path), "qa": str(qa_path)}, indent=2))


if __name__ == "__main__":
    main()
