"""
Alembic environment script.

This script is invoked by Alembic both for:
  - `alembic upgrade head`  (online mode — real DB connection)
  - `alembic revision --autogenerate`  (offline mode — inspects metadata only)

Migrations run synchronously via psycopg2. The caller (app/main.py) converts
the asyncpg DATABASE_URL to psycopg2 before invoking Alembic, so this script
never needs asyncio.run() and is safe to call from inside a running event loop.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# ── Import all models so Alembic autogenerate can see them ──────────────────
from app.db.base import Base  # noqa: F401
import app.models.search  # noqa: F401

# ── Alembic Config object (wraps alembic.ini) ───────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override the URL from the environment (without asyncpg driver — Alembic
# needs a sync driver; main.py already swaps asyncpg → psycopg2).
db_url = os.environ.get("DATABASE_URL")
if db_url:
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    config.set_main_option("sqlalchemy.url", sync_url)


# ── Offline mode ─────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
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


# ── Online mode ───────────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
