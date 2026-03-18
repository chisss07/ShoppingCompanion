"""
SQLAlchemy 2.0 ORM models for authentication and application settings.

Tables:
    admin_users   — Single administrator account used to protect the
                    settings and management surfaces of the app.
    app_settings  — Key/value store for runtime-configurable API keys
                    and feature flags managed via the /settings endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    """Return a new UUID4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# AdminUser
# ---------------------------------------------------------------------------


class AdminUser(Base):
    """
    Single administrator account.

    The application enforces a one-admin model: the POST /auth/setup endpoint
    only succeeds when no rows exist in this table.  Subsequent logins use
    POST /auth/login with bcrypt-verified credentials.
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
        doc="Primary key; UUID v4 generated on insertion.",
    )
    username: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        doc="Unique login name chosen during setup.",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="bcrypt hash of the administrator password.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        doc="When the admin account was created.",
    )

    def __repr__(self) -> str:
        return f"<AdminUser id={self.id} username={self.username!r}>"


# ---------------------------------------------------------------------------
# AppSetting
# ---------------------------------------------------------------------------


class AppSetting(Base):
    """
    Runtime key/value configuration persisted in the database.

    Used to store sensitive API keys (SerpAPI, Anthropic, etc.) that the
    administrator configures through the authenticated /settings endpoints.
    The key column is the primary key, so upserting is naturally idempotent.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(
        String(120),
        primary_key=True,
        doc="Setting identifier, e.g. 'SERPAPI_KEY'.  Case-sensitive.",
    )
    value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Setting value.  NULL or empty string means 'not configured'.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        onupdate=_now_utc,
        doc="Timestamp of the most recent write.",
    )

    def __repr__(self) -> str:
        return f"<AppSetting key={self.key!r} updated_at={self.updated_at}>"
