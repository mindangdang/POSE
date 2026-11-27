from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from project.backend.search_engine.schemas import SearchCandidate, SearchContext
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id


class SerpApiSearchProvider:
    """Google Organic adapter. The key is read at request time and never logged."""

    name = "serpapi"
    endpoint = "https://serpapi.com/search.json"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 12):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY") or os.getenv("SERP_API_KEY")
        self.timeout_seconds = timeout_seconds

    async def search(
        self, query: str, limit: int, context: SearchContext
    ) -> list[SearchCandidate]:
        if not self.api_key:
            raise RuntimeError("SERPAPI_API_KEY is not configured")
        params: dict[str, str | int] = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": min(max(limit, 1), 100),
            "hl": "ko" if context.locale.lower().startswith("ko") else "en",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
            data = response.json()

        results: list[SearchCandidate] = []
        for item in data.get("organic_results", [])[:limit]:
            url = item.get("link")
            if not url:
                continue
            try:
                canonical = canonicalize_url(url)
            except ValueError:
                continue
            results.append(
                SearchCandidate(
                    document_id=str(item.get("position") or stable_document_id(canonical)),
                    canonical_url=canonical,
                    source_url=url,
                    title=item.get("title") or "",
                    snippet=item.get("snippet") or "",
                    source=self.name,
                    document_type="web_page",
                    fetched_at=datetime.now(timezone.utc),
                    metadata={"provider_position": item.get("position")},
                )
            )
        return results
