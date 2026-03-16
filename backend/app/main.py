"""
Shopping Companion — FastAPI application entry point.

Startup sequence (lifespan):
  1. Configure structlog (JSON in prod, colored console in dev)
  2. Run Alembic migrations (ensures schema is current before serving traffic)
  3. Verify Redis connectivity
  4. Register routers and middleware

Shutdown sequence (lifespan):
  1. Dispose the SQLAlchemy async engine (closes all pooled connections)
  2. Close the Redis client

CORS is configured from the ALLOWED_ORIGINS environment variable so the
list of permitted frontend origins can change per deployment environment
without a code change.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import engine

settings = get_settings()

# Configure logging before anything else so all startup log lines are formatted
configure_logging(
    log_level=settings.LOG_LEVEL,
    is_production=settings.is_production,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Everything before ``yield`` runs on startup; everything after runs on
    shutdown.  Exceptions during startup propagate and prevent the server
    from accepting requests.
    """
    # ── Startup ─────────────────────────────────────────────────────────────
    logger.info(
        "app_starting",
        app_env=settings.APP_ENV,
        log_level=settings.LOG_LEVEL,
        debug=settings.DEBUG,
    )

    # Create all tables that don't yet exist.
    # Uses the async asyncpg engine — no psycopg2 needed, no event-loop conflict.
    # create_all() is idempotent: it skips tables that already exist.
    try:
        from app.db.base import Base
        import app.models.search  # noqa: F401 — register models before create_all
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_schema_ready")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("database_schema_failed", error=str(exc))
        if settings.is_production:
            raise

    # Verify Redis is reachable before opening the server
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=5)
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("redis_connected", url=settings.REDIS_URL.split("@")[-1])
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("redis_connection_warning", error=str(exc))
        # Redis unavailability is non-fatal at startup — the health endpoint
        # will surface the issue and requests that need Redis will fail gracefully.

    logger.info("app_ready", host="0.0.0.0", port=8000)

    yield  # ← Server is live here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("app_shutting_down")

    # Dispose the async engine, which closes all pooled connections cleanly.
    await engine.dispose()
    logger.info("database_connections_closed")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application instance.

    Separated from module-level execution so tests can call this function
    with a test-specific environment.
    """
    app = FastAPI(
        title="Shopping Companion API",
        description=(
            "AI-powered product price comparison and alternative recommendation API. "
            "Find the best deals across Amazon, Best Buy, Walmart, and more."
        ),
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS middleware ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Session-Token"],
        max_age=600,  # Preflight cache: 10 minutes
    )

    # ── Global exception handler ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=str(request.url.path),
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred.",
                    "recoverable": False,
                }
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    # /health — no /api/v1 prefix (used by load balancers and Docker healthcheck)
    app.include_router(health_router)

    # /api/v1/search, /api/v1/history, /api/v1/sources
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


# ---------------------------------------------------------------------------
# Module-level application instance (used by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
