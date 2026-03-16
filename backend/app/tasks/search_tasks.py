"""
Celery tasks for the search pipeline.

Task: run_search
    Orchestrates the six-stage AI search pipeline for a given session.
    Publishes Redis pub/sub progress events consumed by the WebSocket server.

Pipeline stages (each publishes progress events to Redis channel
``search:{session_id}`` before and after execution):

    Stage 1: Query understanding   (Claude API)
    Stage 2: Multi-source search   (async HTTP / APIs / scraping)
    Stage 3: Data normalization    (Claude API batch extraction)
    Stage 4: Price ranking         (algorithm)
    Stage 5: Alternative finder    (Claude API)  -- optional
    Stage 6: Summary generation    (Claude API streaming)

All database I/O inside Celery tasks uses the synchronous SQLAlchemy engine
(not the async one) because Celery workers run in gevent greenlets, not an
asyncio event loop.  The async engine is reserved for the FastAPI request
handlers.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from app.celery_app import celery_app

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Redis pub/sub helpers
# ---------------------------------------------------------------------------

def _publish_event(
    redis_client: Any,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """
    Publish a progress event to the Redis channel for this session.

    Channel naming: ``search:{session_id}`` (DB 4 per architecture doc).
    The WebSocket server subscribes to this channel and forwards events to
    the connected browser client.
    """
    channel = f"search:{session_id}"
    message = json.dumps({"type": event_type, **payload})
    redis_client.publish(channel, message)


# ---------------------------------------------------------------------------
# Sync DB session helper (for Celery workers)
# ---------------------------------------------------------------------------

def _get_sync_session():
    """
    Return a synchronous SQLAlchemy session for use inside Celery tasks.

    Celery workers use the gevent pool; they cannot run an asyncio event
    loop.  We create a plain sync engine from the same DATABASE_URL.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings

    settings = get_settings()
    # Convert async URL to sync URL for the worker process
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    engine = create_engine(sync_url, pool_pre_ping=True, pool_size=2)
    Session = sessionmaker(bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# Main search task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.tasks.search_tasks.run_search",
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
    queue="search",
)
def run_search(
    self: Task,
    session_id: str,
    query: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the full six-stage search pipeline for a session.

    Args:
        session_id: UUID string of the SearchSession to populate.
        query:      Raw user query text.
        options:    Dict with keys: max_price, min_sources, include_alternatives,
                    parent_session_id (optional).

    Returns:
        Dict summary with session_id, status, result_count.
    """
    import redis as sync_redis

    from app.core.config import get_settings
    from app.models.search import SearchSession

    settings = get_settings()

    # Open a synchronous Redis connection for pub/sub publishing
    # Use DB 4 as per architecture spec (WebSocket pub/sub database)
    redis_url_db4 = settings.REDIS_URL.rsplit("/", 1)[0] + "/4"
    r = sync_redis.from_url(redis_url_db4)

    db = _get_sync_session()

    def publish(event_type: str, payload: dict[str, Any]) -> None:
        _publish_event(r, session_id, event_type, payload)

    try:
        # ── Mark session as processing ─────────────────────────────────────
        session = db.get(SearchSession, uuid.UUID(session_id))
        if session is None:
            logger.error("run_search: session not found", session_id=session_id)
            return {"status": "failed", "session_id": session_id}

        session.status = "processing"
        db.commit()
        publish("stage_update", {"stage": "started", "status": "in_progress"})

        # ── Stage 1: Query understanding ───────────────────────────────────
        publish("stage_update", {"stage": "understanding", "status": "in_progress"})

        parsed_query = _stage1_query_understanding(query, options, settings)
        session.parsed_query = parsed_query
        db.commit()

        publish(
            "stage_update",
            {
                "stage": "understanding",
                "status": "complete",
                "detail": f"Parsed as {parsed_query.get('product_category', 'product')} search",
            },
        )

        # ── Stage 2: Multi-source search ───────────────────────────────────
        min_sources: int = options.get("min_sources", 3)
        publish(
            "stage_update",
            {
                "stage": "searching",
                "status": "in_progress",
                "detail": f"Querying sources...",
                "sources_total": 5,
                "sources_complete": 0,
            },
        )

        raw_listings = _stage2_multi_source_search(parsed_query, options, publish)
        publish(
            "stage_update",
            {
                "stage": "searching",
                "status": "complete",
                "detail": f"Found {len(raw_listings)} listings",
            },
        )

        # ── Stage 3: Normalization ─────────────────────────────────────────
        publish("stage_update", {"stage": "normalizing", "status": "in_progress"})
        normalized = _stage3_normalize(raw_listings, settings)
        publish("stage_update", {"stage": "normalizing", "status": "complete"})

        # ── Stage 4: Ranking ───────────────────────────────────────────────
        publish("stage_update", {"stage": "comparing", "status": "in_progress"})
        ranked = _stage4_rank(normalized, options)
        publish(
            "stage_update",
            {
                "stage": "comparing",
                "status": "complete",
                "detail": (
                    f"Best price: ${ranked[0]['price']:.2f} at {ranked[0]['source_name']}"
                    if ranked else "No results to rank"
                ),
            },
        )

        # ── Persist search results ─────────────────────────────────────────
        from app.models.search import SearchResult

        for item in ranked:
            result_row = SearchResult(
                session_id=uuid.UUID(session_id),
                source_name=item["source_name"],
                product_title=item["product_title"],
                brand=item.get("brand"),
                model_number=item.get("model_number"),
                price=item["price"],
                currency=item.get("currency", "USD"),
                shipping_cost=item.get("shipping_cost"),
                availability=item.get("availability", "Unknown"),
                seller_name=item.get("seller_name"),
                seller_rating=item.get("seller_rating"),
                product_url=item["product_url"],
                image_url=item.get("image_url"),
                condition=item.get("condition", "new"),
                deal_score=item.get("deal_score"),
                rank=item.get("rank"),
                raw_metadata=item.get("raw_metadata", {}),
                fetched_at=datetime.now(timezone.utc),
            )
            db.add(result_row)

        session.result_count = len(ranked)
        db.commit()

        # ── Stage 5: Alternative identification (optional) ─────────────────
        alternatives_data: list[dict[str, Any]] = []
        if options.get("include_alternatives", True) and ranked:
            publish("stage_update", {"stage": "alternatives", "status": "in_progress"})
            alternatives_data = _stage5_find_alternatives(
                query, ranked[:1], settings, publish
            )
            publish(
                "stage_update",
                {
                    "stage": "alternatives",
                    "status": "complete",
                    "detail": f"Found {len(alternatives_data)} alternatives",
                },
            )

            from app.models.search import AlternativeProduct

            for alt in alternatives_data:
                alt_row = AlternativeProduct(
                    session_id=uuid.UUID(session_id),
                    product_name=alt["product_name"],
                    model_number=alt.get("model_number"),
                    model_relationship=alt["model_relationship"],
                    comparison_summary=alt["comparison_summary"],
                    key_differences=alt.get("key_differences", []),
                    price_min=alt.get("price_min"),
                    price_max=alt.get("price_max"),
                    recommendation_strength=alt["recommendation_strength"],
                    source_urls=alt.get("source_urls", []),
                )
                db.add(alt_row)
            db.commit()

        # ── Stage 6: Summary generation ────────────────────────────────────
        publish("stage_update", {"stage": "summary", "status": "in_progress"})
        summary_data = _stage6_generate_summary(
            query, ranked, alternatives_data, settings, publish
        )

        from app.models.search import SearchSummary

        summary_row = SearchSummary(
            session_id=uuid.UUID(session_id),
            top_pick_summary=summary_data["top_pick_summary"],
            comparison_table_data=summary_data["comparison_table_data"],
            alternatives_brief=summary_data.get("alternatives_brief"),
            caveats=summary_data.get("caveats"),
            model_version=summary_data["model_version"],
            token_usage=summary_data.get("token_usage", {}),
        )
        db.add(summary_row)

        # ── Mark session complete ──────────────────────────────────────────
        session.status = "complete"
        session.completed_at = datetime.now(timezone.utc)
        session.total_sources_queried = summary_data.get("sources_queried", 5)
        db.commit()

        total_sources = summary_data.get("sources_queried", 5)
        publish(
            "complete",
            {
                "session_id": session_id,
                "total_time_ms": 0,  # Workers don't track wall time for simplicity
                "result_count": len(ranked),
                "sources_queried": total_sources,
            },
        )

        logger.info(
            "run_search_complete",
            session_id=session_id,
            result_count=len(ranked),
            alternatives=len(alternatives_data),
        )

        return {
            "status": "complete",
            "session_id": session_id,
            "result_count": len(ranked),
        }

    except Exception as exc:
        logger.exception("run_search_failed", session_id=session_id, error=str(exc))

        try:
            session = db.get(SearchSession, uuid.UUID(session_id))
            if session:
                session.status = "failed"
                session.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:  # pylint: disable=broad-except
            pass

        publish(
            "error",
            {
                "code": "PIPELINE_ERROR",
                "message": "An error occurred during the search pipeline.",
                "detail": str(exc),
                "recoverable": True,
            },
        )

        # Retry on transient errors
        raise self.retry(exc=exc)

    finally:
        db.close()
        r.close()


# ---------------------------------------------------------------------------
# Stage implementations (stubs — full implementations in services/ modules)
# ---------------------------------------------------------------------------

def _stage1_query_understanding(
    query: str,
    options: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """
    Call the Claude API to extract a structured product specification from
    the raw user query.

    Returns a dict with keys: product_category, key_attributes, brand_preference,
    price_ceiling, search_keywords, model_hints.

    Falls back to a simple keyword-based parser if the Claude API is unavailable.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        system_prompt = (
            "You are a product search specialist. Given a user's shopping query, "
            "extract a structured product specification. Return valid JSON with these keys: "
            "product_category (string), key_attributes (list of strings), "
            "brand_preference (string or null), price_ceiling (number or null), "
            "search_keywords (list of 2-3 optimized search strings), "
            "model_hints (list of specific model numbers if mentioned, else [])."
        )
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": query}],
        )
        raw_text = message.content[0].text.strip()
        # Strip markdown code fences if Claude wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        return json.loads(raw_text)
    except Exception as exc:
        logger.warning("stage1_claude_failed_fallback", error=str(exc))
        # Keyword-based fallback parser
        words = query.lower().split()
        return {
            "product_category": "product",
            "key_attributes": words[:5],
            "brand_preference": None,
            "price_ceiling": options.get("max_price"),
            "search_keywords": [query, " ".join(words[:4])],
            "model_hints": [],
        }


def _stage2_multi_source_search(
    parsed_query: dict[str, Any],
    options: dict[str, Any],
    publish_fn: Any,
) -> list[dict[str, Any]]:
    """
    Fan out the structured query to all configured source adapters.
    Returns a flat list of raw product listing dicts.

    Each listing dict contains: source_name, product_title, price,
    product_url, availability, and optional fields.

    The full implementation lives in app/services/source_manager.py.
    This stub returns an empty list so the pipeline can run end-to-end
    before the source adapters are built.
    """
    logger.info(
        "stage2_search",
        keywords=parsed_query.get("search_keywords", []),
        max_price=options.get("max_price"),
    )
    # Stub: real implementation calls source adapters concurrently
    return []


def _stage3_normalize(
    raw_listings: list[dict[str, Any]],
    settings: Any,
) -> list[dict[str, Any]]:
    """
    Clean and enrich raw listings into a unified schema.

    The full implementation is in app/services/data_normalizer.py.
    """
    return raw_listings


def _stage4_rank(
    normalized: list[dict[str, Any]],
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Compute Deal Score for each listing and return ranked list.

    Deal Score formula (from architecture spec):
        score = 0.45 * price_score
              + 0.25 * seller_score
              + 0.15 * availability_score
              + 0.10 * shipping_score
              + 0.05 * return_policy_score

    The full implementation is in app/services/price_ranker.py.
    """
    if not normalized:
        return []

    max_price = max((item.get("price", 0) for item in normalized), default=1)

    for item in normalized:
        price = float(item.get("price", 0))
        price_score = 1.0 - (price / max_price) if max_price > 0 else 0.0
        seller_score = float(item.get("seller_rating", 0) or 0) / 5.0
        avail = (item.get("availability") or "").lower()
        availability_score = (
            1.0 if "stock" in avail else 0.5 if "ship" in avail else 0.0
        )
        shipping = float(item.get("shipping_cost") or 0)
        shipping_score = 1.0 if shipping == 0 else max(0.0, 1.0 - shipping / price)

        item["deal_score"] = round(
            0.45 * price_score
            + 0.25 * seller_score
            + 0.15 * availability_score
            + 0.10 * shipping_score,
            4,
        )

    ranked = sorted(normalized, key=lambda x: x.get("deal_score", 0), reverse=True)
    for i, item in enumerate(ranked, start=1):
        item["rank"] = i

    return ranked


def _stage5_find_alternatives(
    query: str,
    top_results: list[dict[str, Any]],
    settings: Any,
    publish_fn: Any,
) -> list[dict[str, Any]]:
    """
    Use Claude to identify alternative or newer model products.

    The full implementation is in app/services/alternative_finder.py.
    This stub returns an empty list.
    """
    logger.info("stage5_alternatives_stub")
    return []


def _stage6_generate_summary(
    query: str,
    ranked: list[dict[str, Any]],
    alternatives: list[dict[str, Any]],
    settings: Any,
    publish_fn: Any,
) -> dict[str, Any]:
    """
    Generate a natural-language summary using Claude.

    Returns a dict with keys: top_pick_summary, comparison_table_data,
    alternatives_brief, caveats, model_version, token_usage, sources_queried.

    Falls back to a template-based summary if Claude is unavailable.
    """
    model_version = "claude-sonnet-4-20250514"
    token_usage: dict[str, Any] = {}

    if ranked:
        top = ranked[0]
        fallback_summary = (
            f"The best deal found for '{query}' is "
            f"{top.get('product_title', 'the product')} "
            f"at ${float(top.get('price', 0)):.2f} "
            f"from {top.get('source_name', 'a retailer')}."
        )
    else:
        fallback_summary = (
            f"No results were found for '{query}'. "
            "Try broadening your search or adjusting the price limit."
        )

    try:
        import anthropic

        if not settings.ANTHROPIC_API_KEY or not ranked:
            raise ValueError("No API key or no results to summarize")

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = (
            f"User searched for: {query}\n\n"
            f"Top result: {ranked[0].get('product_title')} "
            f"at ${float(ranked[0].get('price', 0)):.2f} "
            f"from {ranked[0].get('source_name')}.\n\n"
            f"Total results: {len(ranked)} listings from "
            f"{len(set(r.get('source_name') for r in ranked))} sources.\n\n"
            "Write a 3-4 sentence summary for a consumer explaining the best deal "
            "and why it is the top pick. Be concise and neutral."
        )

        # Publish streaming chunks to WebSocket clients
        full_text = ""
        with client.messages.stream(
            model=model_version,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                full_text += chunk
                publish_fn("summary_chunk", {"text": chunk, "is_final": False})

        publish_fn("summary_chunk", {"text": "", "is_final": True})

        usage = stream.get_final_message().usage
        token_usage = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }

        top_pick_summary = full_text or fallback_summary

    except Exception as exc:
        logger.warning("stage6_claude_failed_fallback", error=str(exc))
        top_pick_summary = fallback_summary
        publish_fn("summary_chunk", {"text": top_pick_summary, "is_final": True})

    # Build comparison table data (structured for frontend rendering)
    comparison_table_data = {
        "columns": ["Source", "Price", "Shipping", "Availability", "Seller Rating", "Deal Score"],
        "rows": [
            {
                "source": r.get("source_name", ""),
                "price": float(r.get("price", 0)),
                "shipping": (
                    "Free" if (r.get("shipping_cost") or 0) == 0 else f"${r.get('shipping_cost', '')}"
                ),
                "availability": r.get("availability", "Unknown"),
                "seller_rating": float(r.get("seller_rating") or 0),
                "deal_score": float(r.get("deal_score") or 0),
            }
            for r in ranked[:10]  # Top 10 for the table
        ],
    }

    alternatives_brief: str | None = None
    if alternatives:
        alts_text = ", ".join(a.get("product_name", "") for a in alternatives[:3])
        alternatives_brief = (
            f"You may also want to consider: {alts_text}. "
            "See the alternatives section for detailed comparisons."
        )

    return {
        "top_pick_summary": top_pick_summary,
        "comparison_table_data": comparison_table_data,
        "alternatives_brief": alternatives_brief,
        "caveats": None,
        "model_version": model_version,
        "token_usage": token_usage,
        "sources_queried": len(set(r.get("source_name") for r in ranked)) if ranked else 0,
    }
