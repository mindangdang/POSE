from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from sqlalchemy import Table, delete, select
from sqlalchemy.dialects.postgresql import insert

from project.backend.app.db.models.search import Document as DocumentRow
from project.backend.app.db.models.search import DocumentEmbedding
from project.backend.search_engine.schemas import SearchCandidate


class PostgresCachedDocumentRepository:
    """PostgreSQL/pgvector cache for public search documents and BGE vectors."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    async def search(
        self,
        query_embedding: list[float],
        embedding_model: str,
        limit: int,
    ) -> list[SearchCandidate]:
        if len(query_embedding) != 1024 or limit <= 0:
            return []
        async with self.session_factory() as db:
            rows = (
                await db.execute(
                    select(DocumentRow, DocumentEmbedding)
                    .join(
                        DocumentEmbedding,
                        DocumentEmbedding.document_id == DocumentRow.document_id,
                    )
                    .where(
                        DocumentEmbedding.embedding_model == embedding_model,
                        DocumentEmbedding.embedding_version == "v1",
                        DocumentEmbedding.normalized.is_(True),
                    )
                    .order_by(DocumentEmbedding.embedding.cosine_distance(query_embedding))
                    .limit(limit)
                )
            ).all()
        candidates: list[SearchCandidate] = []
        for rank, (document, embedding) in enumerate(rows, start=1):
            candidates.append(
                SearchCandidate(
                    document_id=document.document_id,
                    canonical_url=document.canonical_url,
                    source_url=document.source_url,
                    title=document.title,
                    snippet=document.snippet,
                    content=document.content,
                    source=document.source,
                    document_type=document.document_type,
                    published_at=document.published_at,
                    fetched_at=document.fetched_at,
                    metadata=document.metadata_json or {},
                    embedding_model=embedding.embedding_model,
                    embedding_version=embedding.embedding_version,
                    embedding=list(embedding.embedding),
                    retrieval_ranks={"cached": rank},
                )
            )
        return candidates

    async def upsert(self, documents: list[SearchCandidate]) -> None:
        async with self.session_factory() as db:
            document_table = cast(Table, DocumentRow.__table__)
            for document in documents:
                if (
                    document.embedding is None
                    or len(document.embedding) != 1024
                    or not document.embedding_model
                ):
                    continue
                serialized_content = json.dumps(
                    [document.title, document.snippet, document.content],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                content_hash = hashlib.sha256(serialized_content.encode("utf-8")).hexdigest()
                document_values = {
                    "document_id": document.document_id,
                    "canonical_url": document.canonical_url,
                    "source_url": document.source_url,
                    "title": document.title,
                    "snippet": document.snippet,
                    "content": document.content,
                    "source": document.source,
                    "document_type": document.document_type,
                    "published_at": document.published_at,
                    "fetched_at": document.fetched_at,
                    "metadata": document.metadata,
                    "content_hash": content_hash,
                }
                await db.execute(
                    insert(document_table)
                    .values(**document_values)
                    .on_conflict_do_update(
                        index_elements=[document_table.c.document_id],
                        set_={
                            key: value
                            for key, value in document_values.items()
                            if key != "document_id"
                        },
                    )
                )
                await db.execute(
                    delete(DocumentEmbedding).where(
                        DocumentEmbedding.document_id == document.document_id,
                        DocumentEmbedding.embedding_model == document.embedding_model,
                        DocumentEmbedding.embedding_version == (document.embedding_version or "v1"),
                        DocumentEmbedding.content_hash != content_hash,
                    )
                )
                embedding_values = {
                    "document_id": document.document_id,
                    "embedding_model": document.embedding_model,
                    "embedding_version": document.embedding_version or "v1",
                    "content_hash": content_hash,
                    "embedding": document.embedding,
                    "normalized": True,
                }
                await db.execute(
                    insert(DocumentEmbedding)
                    .values(**embedding_values)
                    .on_conflict_do_nothing(constraint="uq_document_embedding_cache")
                )
            await db.commit()
