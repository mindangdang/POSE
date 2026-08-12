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
        sa.Column("domain", sa.String(255), unique=True),
        sa.Column("url", sa.Text()),
    )
    op.bulk_insert(
        shops,
        [
            {"name": "UNKNOWN", "domain": None, "url": None},
            {"name": "FRUITS FAMILY", "domain": "fruitsfamily.com", "url": "https://fruitsfamily.com"},
            {"name": "FETCHING", "domain": "fetching.co.kr", "url": "https://fetching.co.kr"},
            {"name": "EMPTY", "domain": "empty.seoul.kr", "url": "https://empty.seoul.kr"},
            {"name": "WORKSOUT", "domain": "worksout.co.kr", "url": "https://worksout.co.kr"},
            {"name": "8DIVISION", "domain": "8division.com", "url": "https://8division.com"},
            {"name": "IAMSHOP", "domain": "iamshop-online.com", "url": "https://iamshop-online.com"},
            {"name": "THE BOUNCE", "domain": "thebounce.co.kr", "url": "https://thebounce.co.kr"},
            {"name": "THE X SHOP", "domain": "thexshop.co.kr", "url": "https://thexshop.co.kr"},
            {"name": "COLLECTIV", "domain": "collectiv.kr", "url": "https://collectiv.kr"},
            {"name": "KREAM", "domain": "kream.co.kr", "url": "https://kream.co.kr"},
            {"name": "MUSINSA", "domain": "musinsa.com", "url": "https://musinsa.com"},
            {"name": "EQL", "domain": "eqlstore.com", "url": "https://eqlstore.com"},
            {"name": "29CM", "domain": "29cm.co.kr", "url": "https://29cm.co.kr"},
            {"name": "Bunjang", "domain": "bunjang.co.kr", "url": "https://bunjang.co.kr"},
            {"name": "Danggeun Market", "domain": "daangn.com", "url": "https://www.daangn.com"},
            {"name": "Joonggonara", "domain": "joongna.com", "url": "https://www.joongna.com"},
            {"name": "ZARA", "domain": "zara.com", "url": "https://www.zara.com"},
        ],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("oauth_user_id", sa.String(255), nullable=False, unique=True),
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
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_vector", Vector(768)),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KRW"),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("is_soldout", sa.Boolean()),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_vector", Vector(768)),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("gender", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_product_db_shop_id_shops",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "saved_posts",
        sa.Column("product_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
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
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
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
