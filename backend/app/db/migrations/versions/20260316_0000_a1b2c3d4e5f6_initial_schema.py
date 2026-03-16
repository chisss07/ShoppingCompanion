"""Initial schema — search_sessions, search_results, search_summaries, alternative_products

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-03-16 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── search_sessions ──────────────────────────────────────────────────────
    op.create_table(
        "search_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_token", sa.String(128), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("parsed_query", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("total_sources_queried", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_session_id"],
            ["search_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_sessions_created_at", "search_sessions", ["created_at"])
    op.create_index("ix_search_sessions_status", "search_sessions", ["status"])
    op.create_index("ix_search_sessions_user_id", "search_sessions", ["user_id"])
    op.create_index("ix_search_sessions_session_token", "search_sessions", ["session_token"])
    # Full-text trigram index for history search
    op.execute(
        "CREATE INDEX ix_search_sessions_query_trgm "
        "ON search_sessions USING GIN (query_text gin_trgm_ops)"
    )
    # Partial index: only non-deleted sessions
    op.execute(
        "CREATE INDEX ix_search_sessions_active "
        "ON search_sessions (created_at DESC) "
        "WHERE deleted_at IS NULL"
    )

    # ── search_results ───────────────────────────────────────────────────────
    op.create_table(
        "search_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(120), nullable=False),
        sa.Column("product_title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(200), nullable=True),
        sa.Column("model_number", sa.String(200), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("shipping_cost", sa.Numeric(8, 2), nullable=True),
        sa.Column("availability", sa.String(80), nullable=False),
        sa.Column("seller_name", sa.String(200), nullable=True),
        sa.Column("seller_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("condition", sa.String(40), nullable=False, server_default="new"),
        sa.Column("deal_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["search_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_results_session_id", "search_results", ["session_id"])
    op.create_index("ix_search_results_model_number", "search_results", ["model_number"])
    op.create_index("ix_search_results_rank", "search_results", ["rank"])
    # Composite index for the common "get ranked results for session" query
    op.execute(
        "CREATE INDEX ix_search_results_session_rank "
        "ON search_results (session_id, rank ASC NULLS LAST)"
    )

    # ── search_summaries ─────────────────────────────────────────────────────
    op.create_table(
        "search_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("top_pick_summary", sa.Text(), nullable=False),
        sa.Column(
            "comparison_table_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("alternatives_brief", sa.Text(), nullable=True),
        sa.Column("caveats", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column(
            "token_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["search_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_search_summaries_session_id"),
    )
    op.create_index("ix_search_summaries_session_id", "search_summaries", ["session_id"])

    # ── alternative_products ─────────────────────────────────────────────────
    op.create_table(
        "alternative_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("model_number", sa.String(200), nullable=True),
        sa.Column("model_relationship", sa.String(40), nullable=False),
        sa.Column("comparison_summary", sa.Text(), nullable=False),
        sa.Column(
            "key_differences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("price_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("price_max", sa.Numeric(10, 2), nullable=True),
        sa.Column("recommendation_strength", sa.String(20), nullable=False),
        sa.Column(
            "source_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["search_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alternative_products_session_id", "alternative_products", ["session_id"]
    )


def downgrade() -> None:
    op.drop_table("alternative_products")
    op.drop_table("search_summaries")
    op.drop_table("search_results")
    op.drop_table("search_sessions")
