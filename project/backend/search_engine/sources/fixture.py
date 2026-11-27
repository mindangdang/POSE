from __future__ import annotations

from project.backend.search_engine.schemas import SearchCandidate, SearchContext
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id


_FIXTURES = [
    {
        "url": "https://demo.pose.local/cafes/quiet-study",
        "title": "Quiet study cafe with spacious tables",
        "snippet": "A calm cafe with power outlets, large tables, and reliable Wi-Fi.",
        "content": "Quiet neighborhood cafe for studying. Spacious comfortable seats, power outlets at every table, reliable Wi-Fi, and low background music.",
        "metadata": {"entity": "cafe", "noise_level": "quiet", "wifi": True, "outlets": True},
    },
    {
        "url": "https://demo.pose.local/cafes/loud-market",
        "title": "Busy market cafe",
        "snippet": "Popular cafe in a lively shopping area.",
        "content": "Busy cafe with loud music, crowded small tables, and frequent queues. No power outlets.",
        "metadata": {"entity": "cafe", "noise_level": "loud", "wifi": False, "outlets": False},
    },
    {
        "url": "https://demo.pose.local/cafes/accessible",
        "title": "Accessible cafe near transit",
        "snippet": "Step-free access and quiet seating by the window.",
        "content": "Quiet cafe with step-free entrance, accessible restroom, comfortable seats, and power outlets.",
        "metadata": {"entity": "cafe", "noise_level": "quiet", "step_free": True, "outlets": True},
    },
    {
        "url": "https://demo.pose.local/research/open-search",
        "title": "An introduction to information retrieval",
        "snippet": "Survey of ranking, retrieval, and evaluation methods.",
        "content": "Open educational article explaining information retrieval, search ranking, BM25, and evaluation.",
        "metadata": {"entity": "article", "access": "open"},
    },
    {
        "url": "https://demo.pose.local/research/paywalled",
        "title": "Modern ranking systems",
        "snippet": "Research on learned ranking systems.",
        "content": "",
        "metadata": {"entity": "article", "access": "unknown"},
    },
    {
        "url": "https://demo.pose.local/jobs/remote",
        "title": "Remote data engineer role",
        "snippet": "Remote role with flexible hours.",
        "content": "Full-time remote data engineer position. Flexible hours, Python, SQL, and search infrastructure.",
        "metadata": {"entity": "job", "remote": True},
    },
    {
        "url": "https://demo.pose.local/jobs/on-site",
        "title": "Office data engineer role",
        "snippet": "Data engineer role based in the city office.",
        "content": "Full-time office-based data engineer role. Python and SQL experience required.",
        "metadata": {"entity": "job", "remote": False},
    },
    {
        "url": "https://demo.pose.local/places/park",
        "title": "Riverside public park",
        "snippet": "Green public space with a walking path.",
        "content": "A public riverside park with walking paths, trees, and benches.",
        "metadata": {"entity": "place", "outdoors": True},
    },
    {
        "url": "https://demo.pose.local/products/linen",
        "title": "Linen overshirt",
        "snippet": "Lightweight natural-fiber overshirt.",
        "content": "Linen overshirt with relaxed fit, natural fabric, and two front pockets.",
        "metadata": {"entity": "product", "material": "linen"},
    },
    {
        "url": "https://demo.pose.local/repos/search",
        "title": "Small search engine example",
        "snippet": "A minimal open source search implementation.",
        "content": "Example repository implementing a small search engine with a BM25 ranker and tests.",
        "metadata": {"entity": "repository", "license": "MIT"},
    },
]


class FixtureSearchProvider:
    name = "fixture"

    def __init__(self, documents: list[dict] | None = None):
        self.documents = documents if documents is not None else _FIXTURES

    async def search(
        self, query: str, limit: int, context: SearchContext
    ) -> list[SearchCandidate]:
        terms = set(query.casefold().split())

        def match_score(document: dict) -> int:
            text = " ".join(
                (document["title"], document["snippet"], document["content"])
            ).casefold()
            return sum(1 for term in terms if term in text)

        ordered = sorted(
            self.documents,
            key=lambda item: (-match_score(item), item["url"]),
        )
        candidates = []
        for document in ordered[:limit]:
            canonical = canonicalize_url(document["url"])
            candidates.append(
                SearchCandidate(
                    document_id=stable_document_id(canonical),
                    canonical_url=canonical,
                    source_url=document["url"],
                    title=document["title"],
                    snippet=document.get("snippet", ""),
                    content=document.get("content", ""),
                    source=self.name,
                    metadata=document.get("metadata", {}),
                )
            )
        return candidates
