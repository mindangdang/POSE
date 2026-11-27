from __future__ import annotations

from typing import Protocol

from project.backend.search_engine.schemas import SearchCandidate


class CachedDocumentRepository(Protocol):
    async def search(
        self,
        query_embedding: list[float],
        embedding_model: str,
        limit: int,
    ) -> list[SearchCandidate]: ...

    async def upsert(self, documents: list[SearchCandidate]) -> None: ...
