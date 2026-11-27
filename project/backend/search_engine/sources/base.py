from __future__ import annotations

from typing import Protocol

from project.backend.search_engine.schemas import SearchCandidate, SearchContext


class SearchProvider(Protocol):
    name: str

    async def search(
        self, query: str, limit: int, context: SearchContext
    ) -> list[SearchCandidate]: ...
