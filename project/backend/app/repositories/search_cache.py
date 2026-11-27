from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Table, delete, select
from sqlalchemy.dialects.postgresql import insert

from project.backend.app.db.models.search import Document as DocumentRow
from project.backend.app.db.models.search import DocumentEmbedding
from project.backend.search_engine.schemas import SearchCandidate
from project.backend.search_engine.retrieval.cache import document_content_hash


class PostgresCachedDocumentRepository:
    """PostgreSQL/pgvector cache for public search documents and BGE vectors."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    async def search(
        self,
        query_embedding: list[float],
        embedding_model: str,
        limit: int,
        *,
        model_version: str = "bge-m3-cls-v1",
        dimension: int = 1024,
        pooling_method: str = "cls",
    ) -> list[SearchCandidate]:
        if dimension != 1024 or len(query_embedding) != dimension or limit <= 0:
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
                        DocumentEmbedding.embedding_version == model_version,
                        DocumentEmbedding.embedding_dimension == dimension,
                        DocumentEmbedding.pooling_method == pooling_method,
                        DocumentEmbedding.normalized.is_(True),
                        DocumentEmbedding.content_hash == DocumentRow.content_hash,
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
                    embedding_dimension=getattr(embedding, "embedding_dimension", len(embedding.embedding)),
                    embedding_pooling_method=getattr(embedding, "pooling_method", "unknown"),
                    embedding_content_hash=getattr(embedding, "content_hash", None),
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
                    or document.embedding_dimension != 1024
                    or document.embedding_pooling_method != "cls"
                ):
                    continue
                content_hash = document_content_hash(document)
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
                    "embedding_dimension": document.embedding_dimension,
                    "pooling_method": document.embedding_pooling_method,
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
