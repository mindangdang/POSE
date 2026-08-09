"""Create the initial normalized schema.

This revision is for an empty database. It must not be stamped onto a database
that still has the legacy denormalized saved_posts schema.

Revision ID: 0001_baseline
Revises:
"""
from __future__ import annotations

import os
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    shops = op.create_table(
        "shops",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.bulk_insert(
        shops,
        [
            {"name": "UNKNOWN"},
            {"name": "FRUITS FAMILY"},
            {"name": "FETCHING"},
            {"name": "EMPTY"},
            {"name": "WORKSOUT"},
            {"name": "8DIVISION"},
            {"name": "IAMSHOP"},
            {"name": "THE BOUNCE"},
            {"name": "THE X SHOP"},
            {"name": "COLLECTIV"},
            {"name": "KREAM"},
            {"name": "MUSINSA"},
            {"name": "EQL"},
            {"name": "29CM"},
            {"name": "Bunjang"},
            {"name": "Danggeun Market"},
            {"name": "Joonggonara"},
            {"name": "ZARA"},
        ],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("profile_image", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "product_db",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_vector", Vector(768)),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("is_soldout", sa.Boolean()),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_vector", Vector(768)),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("gender", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_product_db_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("source_url", "title"),
    )

    op.create_table(
        "saved_posts",
        sa.Column("product_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dislikes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product_db.id"],
            name="fk_saved_posts_product_id_product_db",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_saved_posts_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Integer()),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Text()),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_event_logs_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "idx_event_logs_user_action", "event_logs", ["user_id", "action"]
    )
    op.create_index(
        "idx_event_logs_entity", "event_logs", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    if os.getenv("ALEMBIC_ALLOW_DESTRUCTIVE") != "1":
        raise RuntimeError(
            "Baseline downgrade deletes all managed tables. Set "
            "ALEMBIC_ALLOW_DESTRUCTIVE=1 only for a disposable database."
        )

    op.drop_index("idx_event_logs_entity", table_name="event_logs")
    op.drop_index("idx_event_logs_user_action", table_name="event_logs")
    op.drop_table("event_logs")
    op.drop_table("saved_posts")
    op.drop_table("product_db")
    op.drop_table("shops")
    op.drop_table("users")
