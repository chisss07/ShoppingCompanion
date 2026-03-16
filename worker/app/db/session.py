"""
Async SQLAlchemy session management for the worker.

The worker runs inside gevent greenlets but uses asyncio event loops (via
``asyncio.run()``) when it needs to await database calls. Each ``asyncio.run()``
invocation gets its own event loop so the engine must be created fresh per
loop or use NullPool (which creates connections on demand without pooling
across loops).

Usage:
    async with get_async_session() as session:
        session.add(obj)
        await session.commit()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool is essential in a worker context where each task may run in a
# separate asyncio event-loop invocation (via asyncio.run()). A standard pool
# holds connections bound to a specific loop which would error on reuse.
_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG,
    connect_args={
        "server_settings": {"application_name": "shopping_worker"},
        "command_timeout": 30,
    },
)

_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a transactional database session.

    Commits on clean exit, rolls back on any exception, and always closes
    the session to return the connection to the pool.

    Example:
        async with get_async_session() as session:
            result = await session.execute(select(SearchSession))
    """
    session: AsyncSession = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_db_connectivity() -> bool:
    """
    Perform a lightweight connectivity check against PostgreSQL.

    Returns:
        True if the database is reachable, False otherwise.
    """
    try:
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
