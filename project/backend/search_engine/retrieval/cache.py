from __future__ import annotations

import hashlib
import json
from typing import Protocol

from project.backend.search_engine.schemas import SearchCandidate


def document_content_hash(document: SearchCandidate) -> str:
    content = json.dumps(
        [document.title, document.snippet, document.content],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class CachedDocumentRepository(Protocol):
    async def search(
        self,
        query_embedding: list[float],
        embedding_model: str,
        limit: int,
        *,
        model_version: str = "bge-m3-cls-v1",
        dimension: int = 1024,
        pooling_method: str = "cls",
    ) -> list[SearchCandidate]: ...

    async def upsert(self, documents: list[SearchCandidate]) -> None: ...
