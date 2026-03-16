"""
Search orchestration task.

``run_search`` is the entry point for the full AI-powered search pipeline.
It is dispatched by the backend API and runs inside a Celery worker process
using gevent for concurrency.

Pipeline stages:
    1. Publish ``search:started`` event.
    2. Parse the user query with Claude (``query_understanding``).
    3. Fan out to all configured source adapters concurrently.
    4. Publish per-source progress events.
    5. Rank all listings with the scoring model (``price_ranker``).
    6. Identify alternative products with Claude (``alternative_finder``).
    7. Generate a comparison summary with Claude streaming (``summary_generator``).
    8. Persist all results to PostgreSQL.
    9. Publish ``search:complete`` event.

Gevent / asyncio interaction:
    Celery workers use the gevent pool. Each task runs inside a gevent
    greenlet. Asyncio coroutines are executed via ``asyncio.run()`` which
    creates and tears down a fresh event loop per call, compatible with
    gevent's cooperative scheduling.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import redis as redis_sync
import structlog
from anthropic import AsyncAnthropic
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from app.celery_app import app
from app.core.config import get_settings
from app.sources.base import RawProductListing

logger = structlog.get_logger(__name__)
celery_logger = get_task_logger(__name__)

settings = get_settings()


# ---------------------------------------------------------------------------
# Redis pub/sub helpers
# ---------------------------------------------------------------------------

def _get_redis_client() -> redis_sync.Redis:
    """Return a synchronous Redis client for pub/sub publishing."""
    return redis_sync.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _next_sequence(redis_client: redis_sync.Redis, session_id: str) -> int:
    """Atomically increment and return the event sequence counter for a session."""
    return redis_client.incr(f"seq:{session_id}")


def _publish_event(
    redis_client: redis_sync.Redis,
    session_id: str,
    event_type: str,
    search_id: str,
    data: dict,
) -> None:
    """
    Publish a JSON event to the Redis pub/sub channel for a search session.

    Channel format: ``ws:search:{session_id}``

    Args:
        redis_client: Synchronous Redis client.
        session_id: Search session UUID string.
        event_type: Event name (e.g. ``search:started``).
        search_id: Search UUID (may equal session_id or be a sub-identifier).
        data: Arbitrary event payload dict.
    """
    import json

    sequence = _next_sequence(redis_client, session_id)
    payload = {
        "event": event_type,
        "search_id": search_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "data": data,
    }
    channel = f"ws:search:{session_id}"
    redis_client.publish(channel, json.dumps(payload))
    logger.debug(
        "redis_event_published",
        channel=channel,
        event_type=event_type,
        sequence=sequence,
    )


# ---------------------------------------------------------------------------
# Database persistence helpers
# ---------------------------------------------------------------------------

async def _save_results(
    session_id: str,
    parsed_query: dict,
    ranked_listings: list[dict],
    alternatives: list[dict],
    summary: dict,
) -> None:
    """
    Persist all search results to PostgreSQL.

    Updates the ``SearchSession`` row with the parsed query and summary,
    inserts all ``ProductListing`` rows and ``AlternativeProduct`` rows.

    Args:
        session_id: UUID string of the search session.
        parsed_query: Claude-parsed query structure.
        ranked_listings: All ranked listing dicts.
        alternatives: Alternative product dicts from Claude.
        summary: Comparison summary dict from Claude.
    """
    import uuid as _uuid

    from sqlalchemy import update

    from app.db.models import AlternativeProduct, ProductListing, SearchSession
    from app.db.session import get_async_session

    session_uuid = _uuid.UUID(session_id)

    async with get_async_session() as db:
        # Update the session record
        await db.execute(
            update(SearchSession)
            .where(SearchSession.id == session_uuid)
            .values(
                status="complete",
                parsed_query=parsed_query,
                summary=summary,
                updated_at=datetime.now(timezone.utc),
            )
        )

        # Insert product listings
        for listing in ranked_listings:
            db.add(
                ProductListing(
                    session_id=session_uuid,
                    source_name=listing.get("source_name", ""),
                    product_title=listing.get("product_title", ""),
                    price=float(listing.get("price", 0)),
                    currency=listing.get("currency", "USD"),
                    url=listing.get("url", ""),
                    availability=listing.get("availability", "in_stock"),
                    seller_name=listing.get("seller_name"),
                    seller_rating=listing.get("seller_rating"),
                    image_url=listing.get("image_url"),
                    shipping_cost=listing.get("shipping_cost"),
                    condition=listing.get("condition", "new"),
                    model_number=listing.get("model_number"),
                    brand=listing.get("brand"),
                    deal_score=listing.get("deal_score"),
                    rank=listing.get("rank"),
                    raw_metadata=listing.get("raw_metadata") or {},
                )
            )

        # Insert alternative products
        for alt in alternatives:
            db.add(
                AlternativeProduct(
                    session_id=session_uuid,
                    product_name=alt.get("product_name", ""),
                    model_relationship=alt.get("model_relationship", "competitor"),
                    comparison_summary=alt.get("comparison_summary", ""),
                    key_differences=alt.get("key_differences", []),
                    price_min=alt.get("price_min"),
                    price_max=alt.get("price_max"),
                    recommendation_strength=alt.get("recommendation_strength", "moderate"),
                )
            )


async def _mark_session_error(session_id: str, error_message: str) -> None:
    """
    Update the session record to status='error' with the given error message.

    Args:
        session_id: UUID string of the search session.
        error_message: Human-readable error description.
    """
    import uuid as _uuid

    from sqlalchemy import update

    from app.db.models import SearchSession
    from app.db.session import get_async_session

    try:
        async with get_async_session() as db:
            await db.execute(
                update(SearchSession)
                .where(SearchSession.id == _uuid.UUID(session_id))
                .values(
                    status="error",
                    error_message=error_message,
                    updated_at=datetime.now(timezone.utc),
                )
            )
    except Exception as db_exc:
        logger.error(
            "session_error_update_failed",
            session_id=session_id,
            error=str(db_exc),
        )


# ---------------------------------------------------------------------------
# Main search pipeline task
# ---------------------------------------------------------------------------

@app.task(
    bind=True,
    name="app.tasks.search_tasks.run_search",
    queue="search",
    max_retries=2,
    default_retry_delay=10,
)
def run_search(self, session_id: str, query: str, options: dict) -> dict:
    """
    Execute the full AI-powered search pipeline for a user query.

    This task is the primary entry point dispatched by the backend API after
    creating a ``SearchSession`` record in the database.

    Args:
        session_id: UUID string matching an existing ``SearchSession`` row.
        query: Raw natural-language product search query from the user.
        options: Optional overrides dict. Supported keys:
            - ``max_price`` (float | None): Override parsed price ceiling.
            - ``sources`` (list[str]): Restrict to specific source adapters.

    Returns:
        Summary dict: ``{"status": "complete", "listing_count": int, "session_id": str}``.

    Raises:
        celery.exceptions.Retry: On transient failures (up to ``max_retries``).
    """
    log = logger.bind(session_id=session_id, task_id=self.request.id)
    log.info("search_task_started", query=query)

    try:
        result = asyncio.run(
            _run_pipeline(self, session_id, query, options, log)
        )
        return result
    except SoftTimeLimitExceeded:
        log.error("search_task_soft_time_limit_exceeded")
        asyncio.run(_mark_session_error(session_id, "Search timed out"))
        redis_client = _get_redis_client()
        _publish_event(
            redis_client, session_id, "search:error",
            session_id,
            {"message": "Search timed out. Please try again."},
        )
        raise
    except Exception as exc:
        log.error("search_task_fatal_error", error=str(exc), exc_info=True)
        # Attempt retry for transient errors
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)
        except self.MaxRetriesExceededError:
            asyncio.run(_mark_session_error(session_id, str(exc)))
            redis_client = _get_redis_client()
            _publish_event(
                redis_client, session_id, "search:error",
                session_id,
                {"message": "Search failed after multiple attempts. Please try again."},
            )
            raise


async def _run_pipeline(
    task,
    session_id: str,
    query: str,
    options: dict,
    log: structlog.BoundLogger,
) -> dict:
    """
    Async implementation of the search pipeline, called via ``asyncio.run()``.

    Args:
        task: Bound Celery task instance (for self.request etc.).
        session_id: Search session UUID string.
        query: Raw user query.
        options: Pipeline options dict.
        log: Bound structlog logger with session context.

    Returns:
        Result dict with status and listing count.
    """
    from app.services.alternative_finder import identify_alternatives
    from app.services.price_ranker import rank_listings
    from app.services.query_understanding import parse_query
    from app.services.summary_generator import generate_summary
    from app.sources.source_manager import SourceManager

    redis_client = _get_redis_client()
    anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    source_manager = SourceManager(settings)

    # ── Stage 1: search:started ──────────────────────────────────────────────
    _publish_event(
        redis_client, session_id, "search:started", session_id,
        {"query": query, "source_count": len(source_manager.adapters)},
    )
    log.info("pipeline_stage_started", stage="query_understanding")

    # ── Stage 2: Query understanding ─────────────────────────────────────────
    try:
        parsed_query = await parse_query(query, anthropic_client)
    except Exception as exc:
        log.error("query_understanding_failed", error=str(exc))
        # Fall back to using the raw query as the keyword
        parsed_query = {
            "product_category": "unknown",
            "key_attributes": [],
            "brand_preference": None,
            "price_ceiling": None,
            "search_keywords": [query],
            "model_hints": [],
        }

    # Allow options dict to override the price ceiling
    max_price: float | None = options.get("max_price") or parsed_query.get("price_ceiling")
    keywords: list[str] = parsed_query.get("search_keywords") or [query]

    log.info(
        "pipeline_stage_complete",
        stage="query_understanding",
        keywords=keywords,
        max_price=max_price,
    )

    # ── Stage 3 & 4: Concurrent source queries with progress events ──────────
    log.info("pipeline_stage_started", stage="source_search")
    all_raw_listings: list[RawProductListing] = []

    async def on_source_start(source_name: str) -> None:
        _publish_event(
            redis_client, session_id, "search:source_checking", session_id,
            {"source": source_name},
        )

    async def on_source_complete(
        source_name: str,
        results: list[RawProductListing],
        error: Exception | None,
    ) -> None:
        all_raw_listings.extend(results)
        top_results = [r.to_dict() for r in results[:3]]
        _publish_event(
            redis_client, session_id, "search:source_complete", session_id,
            {
                "source": source_name,
                "result_count": len(results),
                "top_results": top_results,
                "error": str(error) if error else None,
            },
        )

    await source_manager.search_all(keywords, max_price, on_source_start, on_source_complete)
    log.info(
        "pipeline_stage_complete",
        stage="source_search",
        total_listings=len(all_raw_listings),
    )

    # ── Stage 5: Ranking ─────────────────────────────────────────────────────
    log.info("pipeline_stage_started", stage="ranking")
    raw_listing_dicts = [r.to_dict() for r in all_raw_listings]
    ranked_listings = rank_listings(raw_listing_dicts)

    _publish_event(
        redis_client, session_id, "search:comparison_ready", session_id,
        {
            "total_listings": len(ranked_listings),
            "top_listings": ranked_listings[:5],
        },
    )
    log.info("pipeline_stage_complete", stage="ranking", ranked_count=len(ranked_listings))

    # ── Stage 6: Alternative finder ──────────────────────────────────────────
    log.info("pipeline_stage_started", stage="alternatives")
    top_product = ranked_listings[0] if ranked_listings else {}
    alternatives = await identify_alternatives(
        query, top_product, ranked_listings, anthropic_client
    )

    _publish_event(
        redis_client, session_id, "search:alternatives_found", session_id,
        {"alternatives": alternatives, "count": len(alternatives)},
    )
    log.info(
        "pipeline_stage_complete",
        stage="alternatives",
        alternative_count=len(alternatives),
    )

    # ── Stage 7: Summary generation ──────────────────────────────────────────
    log.info("pipeline_stage_started", stage="summary")
    summary = await generate_summary(query, ranked_listings, alternatives, anthropic_client)
    log.info(
        "pipeline_stage_complete",
        stage="summary",
        token_usage=summary.get("token_usage"),
    )

    # ── Stage 8: Persist to PostgreSQL ───────────────────────────────────────
    log.info("pipeline_stage_started", stage="persist")
    await _save_results(session_id, parsed_query, ranked_listings, alternatives, summary)
    log.info("pipeline_stage_complete", stage="persist")

    # ── Stage 9: search:complete ─────────────────────────────────────────────
    _publish_event(
        redis_client, session_id, "search:complete", session_id,
        {
            "listing_count": len(ranked_listings),
            "alternative_count": len(alternatives),
            "top_pick": ranked_listings[0].get("product_title") if ranked_listings else None,
            "summary": summary,
        },
    )

    log.info(
        "search_task_complete",
        listing_count=len(ranked_listings),
        alternative_count=len(alternatives),
    )

    return {
        "status": "complete",
        "session_id": session_id,
        "listing_count": len(ranked_listings),
        "alternative_count": len(alternatives),
    }
