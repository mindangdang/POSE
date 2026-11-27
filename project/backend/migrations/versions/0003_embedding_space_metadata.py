"""Persist embedding-space metadata and invalidate mean-pooling cache entries.

Revision ID: 0003_embedding_space_metadata
Revises: 0002_generic_search
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_embedding_space_metadata"
down_revision: str | Sequence[str] | None = "0002_generic_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_embeddings",
        sa.Column("embedding_dimension", sa.Integer(), nullable=False, server_default="1024"),
    )
    op.add_column(
        "document_embeddings",
        sa.Column("pooling_method", sa.String(32), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("embedding_space", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("UPDATE document_embeddings SET embedding_version = 'legacy-mean-v1' WHERE embedding_version = 'v1'")


def downgrade() -> None:
    raise RuntimeError("Embedding metadata migration is additive and has no automatic downgrade.")
