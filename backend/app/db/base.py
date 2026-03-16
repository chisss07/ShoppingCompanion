"""
SQLAlchemy 2.0 async database layer.

Exports:
    engine          - The async engine (used by Alembic env.py too)
    AsyncSessionLocal - Session factory; use via get_db() in FastAPI deps
    get_db()        - FastAPI dependency that yields an AsyncSession
    Base            - DeclarativeBase for all ORM models
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    All model classes in app/models/ inherit from this base so that
    Alembic's autogenerate can discover them via metadata inspection.
    """

    # Allow arbitrary Python types in column annotations (e.g., UUID, Decimal)
    type_annotation_map: dict[Any, Any] = {}


def _build_engine() -> AsyncEngine:
    """
    Create the async SQLAlchemy engine with appropriate pool settings.

    Pool sizing:
      - pool_size=5 keeps 5 persistent connections open per worker process.
        With 4 uvicorn workers that is 20 connections to PostgreSQL.
      - max_overflow=10 allows burst headroom; total ceiling is 60 connections
        which aligns with PgBouncer's max_db_connections setting.
      - pool_pre_ping=True issues a lightweight SELECT 1 before handing out
        a connection from the pool, catching stale connections transparently.
    """
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL in development; off in production
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections after 1 hour (match PgBouncer)
        future=True,
    )


# Module-level singletons; created once per process
engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Attributes remain accessible after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    The session is always closed in the finally block, even if the
    endpoint raises an exception.  Callers are responsible for committing
    or rolling back transactions explicitly.

    Usage in a route:
        from app.db.base import get_db
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(MyModel))
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
