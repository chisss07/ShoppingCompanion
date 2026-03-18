"""
SQLAlchemy ORM models used by the worker for persisting search results.

These mirror the schema owned by the backend service. The worker only writes;
the backend handles reads and the public API. Column definitions must stay in
sync with the backend's app/models/search.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    """Shared declarative base for all worker models."""


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    session_token: Mapped[str] = mapped_column(String(128), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_query: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_sources_queried: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_sessions.id", ondelete="SET NULL"), nullable=True
    )


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    product_title: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    price: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    shipping_cost: Mapped[Optional[Any]] = mapped_column(Numeric(8, 2), nullable=True)
    availability: Mapped[str] = mapped_column(String(80), nullable=False)
    seller_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    seller_rating: Mapped[Optional[Any]] = mapped_column(Numeric(5, 2), nullable=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    condition: Mapped[str] = mapped_column(String(40), nullable=False, default="new")
    deal_score: Mapped[Optional[Any]] = mapped_column(Numeric(5, 4), nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)


class SearchSummary(Base):
    __tablename__ = "search_summaries"
    __table_args__ = (UniqueConstraint("session_id", name="uq_search_summaries_session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    top_pick_summary: Mapped[str] = mapped_column(Text, nullable=False)
    comparison_table_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    alternatives_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caveats: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class AlternativeProduct(Base):
    __tablename__ = "alternative_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model_relationship: Mapped[str] = mapped_column(String(40), nullable=False)
    comparison_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_differences: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    price_min: Mapped[Optional[Any]] = mapped_column(Numeric(10, 2), nullable=True)
    price_max: Mapped[Optional[Any]] = mapped_column(Numeric(10, 2), nullable=True)
    recommendation_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    source_urls: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class AppSetting(Base):
    """Key-value store for runtime-configurable settings (managed via the UI Settings page)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)
