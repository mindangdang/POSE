from __future__ import annotations

from typing import Any

import httpx
from typing import Protocol

from project.backend.app.manage.settings import get_settings


class SearchModelClient(Protocol):
    async def embed(self, texts: list[str]) -> tuple[list[list[float]], str] | None: ...

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

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], str] | None:
        if not texts:
            return [], "BAAI/bge-m3"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/embed/batch",
                    json={"texts": texts, "normalize": True},
                )
                response.raise_for_status()
            data: dict[str, Any] = response.json()
            embeddings = data.get("embeddings")
            if (
                not isinstance(embeddings, list)
                or len(embeddings) != len(texts)
                or any(not isinstance(item, list) or len(item) != data.get("embedding_dimension") for item in embeddings)
            ):
                return None
            return embeddings, str(data.get("model_id", "BAAI/bge-m3"))
        except (httpx.HTTPError, ValueError, TypeError):
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
