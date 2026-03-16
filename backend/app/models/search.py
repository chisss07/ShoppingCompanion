"""
SQLAlchemy 2.0 ORM models for the search pipeline.

All four tables that store search state, results, AI summaries, and
alternative product recommendations are defined here.

Relationships:
    SearchSession  --(1:N)--> SearchResult
    SearchSession  --(1:1)--> SearchSummary
    SearchSession  --(1:N)--> AlternativeProduct
    SearchSession  --(self-ref FK)--> parent SearchSession (re-searches)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    """Return a new UUID4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# SearchSession
# ---------------------------------------------------------------------------

class SearchSession(Base):
    """
    One row per search initiated by a user (or anonymous session).

    Lifecycle:
        pending  -> processing (Celery task started)
        processing -> complete  (all pipeline stages finished)
        processing -> failed    (unrecoverable error in pipeline)

    Re-searches (POST /search/{id}/refresh) create a new SearchSession with
    parent_session_id pointing to the original, allowing price delta tracking.
    """

    __tablename__ = "search_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
        doc="Primary key; used as the public session identifier in all APIs.",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Application-level user ID; NULL for anonymous sessions.",
    )
    session_token: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        doc="Anonymous session token (UUID or JWT sub claim) for grouping activity.",
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The raw search query submitted by the user (max 500 chars enforced at API layer).",
    )
    parsed_query: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Stage 1 output: structured product specification extracted by Claude.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        doc="One of: pending, processing, complete, failed.",
    )
    result_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Total number of search_results rows written for this session.",
    )
    total_sources_queried: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="How many external sources were queried (including those that timed out).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        index=True,
        doc="When the session was created (used for history ordering and retention).",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the pipeline finished (status became complete or failed).",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Soft-delete timestamp; rows with a value here are excluded from history queries.",
    )
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="SET NULL"),
        nullable=True,
        doc="FK to the original session when this session is a re-search (refresh).",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    results: Mapped[list[SearchResult]] = relationship(
        "SearchResult",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )
    summary: Mapped[Optional[SearchSummary]] = relationship(
        "SearchSummary",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    alternatives: Mapped[list[AlternativeProduct]] = relationship(
        "AlternativeProduct",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )
    # Self-referential: child sessions link back to their parent
    child_sessions: Mapped[list[SearchSession]] = relationship(
        "SearchSession",
        foreign_keys=[parent_session_id],
        backref="parent_session",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<SearchSession id={self.id} status={self.status!r} "
            f"query={self.query_text[:40]!r}>"
        )


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

class SearchResult(Base):
    """
    One row per product listing found from a single external source.

    Multiple rows share the same session_id; they differ by source_name
    and product_url. rank=1 denotes the best deal (highest deal_score).
    """

    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        doc="Canonical source identifier, e.g. 'amazon', 'bestbuy', 'google_shopping'.",
    )
    product_title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Raw product title as returned by the source.",
    )
    brand: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    model_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
    )
    shipping_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        doc="NULL means unknown; 0.00 means free shipping.",
    )
    availability: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        doc="Human-readable availability string, e.g. 'In Stock', 'Ships in 3 days'.",
    )
    seller_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    seller_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        doc="Seller rating on a 0.00-5.00 scale.",
    )
    product_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    condition: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="new",
        doc="One of: new, renewed, open-box, used.",
    )
    deal_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        doc=(
            "Composite deal score (0.0000-1.0000) computed by the ranking algorithm. "
            "Higher is better."
        ),
    )
    rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Display rank within the session; rank=1 is the top pick.",
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Source-specific supplementary data preserved for debugging and future enrichment.",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        doc="When this listing was fetched from the source.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    session: Mapped[SearchSession] = relationship(
        "SearchSession",
        back_populates="results",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<SearchResult id={self.id} source={self.source_name!r} "
            f"price={self.price} rank={self.rank}>"
        )


# ---------------------------------------------------------------------------
# SearchSummary
# ---------------------------------------------------------------------------

class SearchSummary(Base):
    """
    AI-generated natural-language summary and structured comparison data
    for a completed search session.

    One session has at most one summary (UNIQUE on session_id).
    The Celery pipeline writes this row during Stage 6 (Summary Generation).
    """

    __tablename__ = "search_summaries"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_search_summaries_session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    top_pick_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="3-4 sentence plain-English summary of the top pick and why.",
    )
    comparison_table_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc=(
            "Structured data for the frontend comparison table. "
            "Schema: {columns: [...], rows: [...]}."
        ),
    )
    alternatives_brief: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Short paragraph explaining whether alternatives are worth considering.",
    )
    caveats: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Warnings about the pricing, seller quality, or availability.",
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
    )
    model_version: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        doc="Claude model identifier used to generate this summary.",
    )
    token_usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Token consumption: {input_tokens: N, output_tokens: N} for cost tracking.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    session: Mapped[SearchSession] = relationship(
        "SearchSession",
        back_populates="summary",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<SearchSummary id={self.id} session_id={self.session_id}>"


# ---------------------------------------------------------------------------
# AlternativeProduct
# ---------------------------------------------------------------------------

class AlternativeProduct(Base):
    """
    AI-identified alternative or related product for a given search session.

    Stage 5 (Alternative Model Identification) writes 2-5 rows per session.
    Each row represents one product that the user might consider instead of
    (or in addition to) the top-ranked result.
    """

    __tablename__ = "alternative_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full product name of the alternative (as identified by Claude).",
    )
    model_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    model_relationship: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        doc="One of: successor, predecessor, competitor, budget_alternative.",
    )
    comparison_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="2-3 sentence plain-English comparison with the searched product.",
    )
    key_differences: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        doc=(
            "Structured list of spec differences. "
            "Each element: {attribute, target_value, alternative_value}."
        ),
    )
    price_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Lowest price found for this alternative across all sources queried.",
    )
    price_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Highest price found for this alternative across all sources queried.",
    )
    recommendation_strength: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="One of: strong, moderate, weak.",
    )
    source_urls: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        doc="Array of product page URLs where this alternative was found with current pricing.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    session: Mapped[SearchSession] = relationship(
        "SearchSession",
        back_populates="alternatives",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<AlternativeProduct id={self.id} "
            f"product_name={self.product_name!r} "
            f"relationship={self.model_relationship!r}>"
        )
