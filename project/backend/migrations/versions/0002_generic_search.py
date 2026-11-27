"""Additive generic search, preference, and feedback schema.

Revision ID: 0002_generic_search
Revises: 0001_baseline
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "0002_generic_search"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(64), primary_key=True),
        sa.Column("canonical_url", sa.Text(), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False, server_default="web_page"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_documents_source_fetched", "documents", ["source", "fetched_at"])
    op.create_table(
        "document_embeddings",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("normalized", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("document_id", "embedding_model", "embedding_version", "content_hash", name="uq_document_embedding_cache"),
    )
    op.create_index("idx_document_embeddings_model", "document_embeddings", ["embedding_model", "embedding_version"])
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribute", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("polarity", sa.String(16), nullable=False, server_default="positive"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("scope", sa.String(16), nullable=False, server_default="global"),
        sa.Column("domain", sa.String(255)),
        sa.Column("source", sa.String(16), nullable=False, server_default="explicit"),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("embedding", Vector(1024)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_user_preferences_owner_scope", "user_preferences", ["user_id", "scope", "active"])
    op.create_table(
        "search_sessions",
        sa.Column("search_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_search_sessions_user_created", "search_sessions", ["user_id", "created_at"])
    op.create_table(
        "search_impressions",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("search_id", sa.String(36), sa.ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(64), nullable=False),
        sa.Column("original_rank", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("search_id", "document_id", name="uq_search_impression"),
    )
    op.create_index("idx_search_impressions_user_search", "search_impressions", ["user_id", "search_id"])
    op.create_table(
        "search_feedback",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_id", sa.String(36), sa.ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(64)),
        sa.Column("original_rank", sa.Integer()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("feedback_type", sa.String(32), nullable=False),
        sa.Column("feedback_reason", sa.Text()),
        sa.Column("affected_criterion", sa.String(120)),
        sa.Column("feedback_scope", sa.String(32), nullable=False, server_default="session"),
        sa.Column("feedback_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_search_feedback_idempotency"),
    )
    op.create_index("idx_search_feedback_search", "search_feedback", ["search_id"])
    op.create_table(
        "search_traces",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("search_id", sa.String(36), sa.ForeignKey("search_sessions.search_id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=False, unique=True),
        sa.Column("trace_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    # Preserve user search and feedback history by refusing implicit teardown.
    raise RuntimeError("This migration is additive and intentionally has no automatic downgrade.")
