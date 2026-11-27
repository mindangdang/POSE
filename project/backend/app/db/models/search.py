from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from project.backend.app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("idx_documents_source_fetched", "source", "fetched_at"),)

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, server_default="web_page")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "embedding_model", "embedding_version", "content_hash",
            name="uq_document_embedding_cache",
        ),
        Index("idx_document_embeddings_model", "embedding_model", "embedding_version"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    normalized: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (Index("idx_user_preferences_owner_scope", "user_id", "scope", "active"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attribute: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="positive")
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="1")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default="global")
    domain: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="explicit")
    evidence_event_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class SearchSession(Base):
    __tablename__ = "search_sessions"
    __table_args__ = (Index("idx_search_sessions_user_created", "user_id", "created_at"),)

    search_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    query: Mapped[str] = mapped_column(Text, nullable=False)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class SearchImpression(Base):
    __tablename__ = "search_impressions"
    __table_args__ = (
        UniqueConstraint("search_id", "document_id", name="uq_search_impression"),
        Index("idx_search_impressions_user_search", "user_id", "search_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    search_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class SearchFeedback(Base):
    __tablename__ = "search_feedback"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_search_feedback_idempotency"),
        Index("idx_search_feedback_search", "search_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    search_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(String(64))
    original_rank: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_reason: Mapped[str | None] = mapped_column(Text)
    affected_criterion: Mapped[str | None] = mapped_column(String(120))
    feedback_scope: Mapped[str] = mapped_column(String(32), nullable=False, server_default="session")
    feedback_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )


class SearchTrace(Base):
    __tablename__ = "search_traces"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    search_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    trace_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

