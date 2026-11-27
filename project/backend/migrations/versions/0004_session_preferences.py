"""Add explicit user-session ownership to session-scoped preferences.

Revision ID: 0004_session_preferences
Revises: 0003_embedding_space_metadata
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_session_preferences"
down_revision: str | Sequence[str] | None = "0003_embedding_space_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_preferences", sa.Column("session_id", sa.String(36), nullable=True))
    op.create_index(
        "idx_user_preferences_session",
        "user_preferences",
        ["user_id", "session_id", "active"],
    )


def downgrade() -> None:
    op.drop_index("idx_user_preferences_session", table_name="user_preferences")
    op.drop_column("user_preferences", "session_id")
