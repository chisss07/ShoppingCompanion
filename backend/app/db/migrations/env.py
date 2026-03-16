"""
Alembic environment script — async SQLAlchemy 2.0 edition.

This script is invoked by Alembic both for:
  - `alembic upgrade head`  (online mode — real DB connection)
  - `alembic revision --autogenerate`  (offline mode — inspects metadata only)

We use SQLAlchemy's async engine but bridge it to Alembic's synchronous runner
via `run_sync`, which is the recommended approach for async projects.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Import all models so Alembic autogenerate can see them ──────────────────
# This must happen before target_metadata is read.
from app.db.base import Base  # noqa: F401
import app.models.search  # noqa: F401  — registers SearchSession, SearchResult, etc.

# ── Alembic Config object (wraps alembic.ini) ───────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object that autogenerate inspects.
target_metadata = Base.metadata

# Override the sqlalchemy.url with the DATABASE_URL env var when present
# (avoids hard-coding credentials in alembic.ini).
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # asyncpg driver is needed at runtime but Alembic's synchronous inspector
    # wants psycopg2; swap the driver for offline autogenerate comparisons.
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    config.set_main_option("sqlalchemy.url", sync_url)


# ── Offline migrations (no live DB connection) ───────────────────────────────

def run_migrations_offline() -> None:
    """
    Emit migration SQL to stdout without a live database connection.
    Useful for generating a migration script to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (live async DB connection) ─────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside run_sync."""
    # Build a *synchronous-compatible* URL from the async one for Alembic.
    cfg_section = config.get_section(config.config_ini_section) or {}
    url = cfg_section.get("sqlalchemy.url", "")

    # If the URL still has the asyncpg driver (e.g. run via `alembic upgrade`
    # inside the container where DATABASE_URL is set), swap to psycopg2 for
    # Alembic's synchronous inspector.  At runtime the migration is applied
    # through the async engine below, which uses asyncpg.
    async_url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    cfg_section["sqlalchemy.url"] = async_url

    connectable = async_engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
