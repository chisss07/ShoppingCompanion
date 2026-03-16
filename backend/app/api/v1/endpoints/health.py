"""
Health check and source status endpoints.

Routes:
    GET /health              Service health (DB + Redis connectivity)
    GET /api/v1/sources      List configured shopping sources and their status
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import get_db

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="Service health check",
    response_description=(
        "Returns 200 with all checks 'ok', or 503 with the failing component."
    ),
)
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Perform liveness checks on the PostgreSQL database and Redis cache.

    Used by Docker Compose and load balancers to determine if the container
    is ready to serve traffic.

    Returns:
        200: All dependencies healthy.
        503: One or more dependencies unavailable.
    """
    checks: dict[str, str] = {}
    healthy = True

    # ── Database check ─────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("health_check_db_failed", error=str(exc))
        checks["db"] = "error"
        healthy = False

    # ── Redis check ────────────────────────────────────────────────────────
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await redis_client.ping()
        await redis_client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("health_check_redis_failed", error=str(exc))
        checks["redis"] = "error"
        healthy = False

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    payload: dict[str, Any] = {"status": "ok" if healthy else "degraded", **checks}

    return JSONResponse(status_code=http_status, content=payload)


# ---------------------------------------------------------------------------
# GET /sources  (mounted under /api/v1 by the router)
# ---------------------------------------------------------------------------

# Canonical list of source adapters and their Redis health key pattern.
# In a full implementation this would be read from a database or config file.
_KNOWN_SOURCES: list[dict[str, str]] = [
    {"name": "amazon",         "display_name": "Amazon",         "type": "api"},
    {"name": "bestbuy",        "display_name": "Best Buy",       "type": "api"},
    {"name": "walmart",        "display_name": "Walmart",        "type": "api"},
    {"name": "google_shopping","display_name": "Google Shopping","type": "api"},
    {"name": "ebay",           "display_name": "eBay",           "type": "api"},
    {"name": "bhphoto",        "display_name": "B&H Photo",      "type": "scraper"},
    {"name": "newegg",         "display_name": "Newegg",         "type": "scraper"},
    {"name": "target",         "display_name": "Target",         "type": "playwright"},
    {"name": "costco",         "display_name": "Costco",         "type": "playwright"},
]


@router.get(
    "/api/v1/sources",
    summary="List shopping data sources and their current status",
    tags=["meta"],
)
async def list_sources() -> dict[str, Any]:
    """
    Return the list of configured shopping source adapters along with their
    current health status from the Redis health cache.

    The Redis key pattern is ``health:{source_name}`` (TTL: 5 minutes).
    A missing key means the source has not been checked recently and is
    treated as 'unknown'.
    """
    source_statuses: list[dict[str, Any]] = []

    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)

        for source in _KNOWN_SOURCES:
            key = f"health:{source['name']}"
            raw: bytes | None = await redis_client.get(key)
            cached_status = raw.decode() if raw else "unknown"
            source_statuses.append(
                {
                    "name": source["name"],
                    "display_name": source["display_name"],
                    "type": source["type"],
                    "status": cached_status,
                }
            )

        await redis_client.aclose()

    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("sources_redis_unavailable", error=str(exc))
        # Degrade gracefully: return all sources as 'unknown'
        source_statuses = [
            {
                "name": s["name"],
                "display_name": s["display_name"],
                "type": s["type"],
                "status": "unknown",
            }
            for s in _KNOWN_SOURCES
        ]

    return {
        "sources": source_statuses,
        "total": len(source_statuses),
    }
