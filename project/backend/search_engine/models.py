from __future__ import annotations

from typing import Any

import httpx
from typing import Protocol

from project.backend.app.manage.settings import get_settings
from project.backend.search_engine.schemas import EmbeddingBatch, EmbeddingSpace


def coerce_embedding_batch(result: Any) -> EmbeddingBatch | None:
    """Adapt legacy in-process clients; production responses must provide full metadata."""
    if result is None:
        return None
    if isinstance(result, EmbeddingBatch):
        return result
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], list)
        and isinstance(result[1], str)
    ):
        vectors, model_id = result
        if not vectors:
            return None
        if model_id in {"cpu", "cuda", "mps"}:
            model_id = get_settings().embedding_model
        return EmbeddingBatch(
            space=EmbeddingSpace(
                model_id=model_id,
                model_version="legacy-unversioned",
                dimension=len(vectors[0]),
                pooling_method="unknown",
            ),
            embeddings=vectors,
        )
    return None


class SearchModelClient(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingBatch | None: ...

    async def rerank(
        self, query: str, documents: list[dict[str, str]]
    ) -> tuple[dict[str, float], str] | None: ...


class ModelServerClient:
    """Optional BGE model server adapter with deterministic retrieval fallback."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (
            base_url or get_settings().gpu_server_url or "http://localhost:8001"
        ).rstrip("/")
        self.timeout_seconds = get_settings().model_server_timeout_seconds

    async def embed(self, texts: list[str]) -> EmbeddingBatch | None:
        if not texts:
            settings = get_settings()
            return EmbeddingBatch(
                space=EmbeddingSpace(
                    model_id=settings.embedding_model,
                    model_version=settings.embedding_model_version,
                    dimension=1024,
                    pooling_method="cls",
                ),
                embeddings=[],
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/embed/batch",
                    json={"texts": texts, "normalize": True},
                )
                response.raise_for_status()
            data: dict[str, Any] = response.json()
            embeddings = data.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                return None
            space = EmbeddingSpace(
                model_id=data["model_id"],
                model_version=data["model_version"],
                dimension=data["embedding_dimension"],
                pooling_method=data["pooling_method"],
            )
            return EmbeddingBatch(space=space, embeddings=embeddings)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return None

    async def rerank(self, query: str, documents: list[dict[str, str]]) -> tuple[dict[str, float], str] | None:
        if not documents:
            return {}, "BAAI/bge-reranker-v2-m3"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/rerank",
                    json={"query": query, "documents": documents[:30]},
                )
                response.raise_for_status()
            data = response.json()
            results = data.get("results")
            if not isinstance(results, list):
                return None
            return (
                {item["id"]: float(item["raw_score"]) for item in results},
                str(data.get("model_id", "BAAI/bge-reranker-v2-m3")),
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return None
