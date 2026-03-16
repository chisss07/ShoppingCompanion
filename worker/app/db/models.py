"""
SQLAlchemy ORM models used by the worker for persisting search results.

These mirror the schema owned by the backend service. The worker only writes;
the backend handles reads and the public API. Column definitions must stay in
sync with the Alembic migrations managed by the backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all worker models."""


class SearchSession(Base):
    """
    Represents a single user-initiated product search session.

    Lifecycle: pending -> running -> complete | error
    """

    __tablename__ = "search_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    # Claude-parsed query understanding payload
    parsed_query: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # AI-generated summary payload
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Any fatal error message
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listings: Mapped[list[ProductListing]] = relationship(
        "ProductListing",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alternatives: Mapped[list[AlternativeProduct]] = relationship(
        "AlternativeProduct",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SearchSession id={self.id} status={self.status!r}>"


class ProductListing(Base):
    """
    A single product listing returned by one shopping source adapter.

    Multiple listings can share the same product across different sellers /
    marketplaces. The deal_score is computed by the price_ranker service.
    """

    __tablename__ = "product_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    product_title: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    seller_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    model_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Computed ranking fields
    deal_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Source-specific extra fields
    raw_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[SearchSession] = relationship(
        "SearchSession", back_populates="listings"
    )

    def __repr__(self) -> str:
        return (
            f"<ProductListing source={self.source_name!r} "
            f"title={self.product_title[:40]!r} price={self.price}>"
        )


class AlternativeProduct(Base):
    """
    An alternative or related product identified by Claude for a search session.
    """

    __tablename__ = "alternative_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    comparison_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_differences: Mapped[list | None] = mapped_column(JSON, nullable=True)
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_strength: Mapped[str] = mapped_column(
        String(16), nullable=False, default="moderate"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[SearchSession] = relationship(
        "SearchSession", back_populates="alternatives"
    )

    def __repr__(self) -> str:
        return (
            f"<AlternativeProduct name={self.product_name[:40]!r} "
            f"relationship={self.model_relationship!r}>"
        )
