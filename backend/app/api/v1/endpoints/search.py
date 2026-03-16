"""
Search API endpoints.

Routes (all prefixed with /api/v1 in the router):
    POST   /search                       Initiate a new search
    GET    /search/{session_id}           Poll session status
    GET    /search/{session_id}/results   Fetch complete results
    POST   /search/{session_id}/refresh  Re-run a past search
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.base import get_db
from app.models.search import (
    AlternativeProduct,
    SearchResult,
    SearchSession,
    SearchSummary,
)
from app.schemas.search import (
    Alternative,
    PriceEntry,
    SearchRequest,
    SearchResultsResponse,
    SearchSessionResponse,
    SearchStatusResponse,
    SummaryDict,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_websocket_url(session_id: uuid.UUID) -> str:
    return f"/ws/search/{session_id}"


def _shipping_display(cost: Optional[Decimal]) -> Optional[str]:
    """Convert a Decimal shipping cost to a display string."""
    if cost is None:
        return None
    if cost == Decimal("0.00") or cost == 0:
        return "Free"
    return f"${cost:.2f}"


def _build_price_entry(result: SearchResult) -> PriceEntry:
    return PriceEntry(
        rank=result.rank or 0,
        source=result.source_name,
        product_title=result.product_title,
        price=float(result.price),
        shipping=_shipping_display(result.shipping_cost),
        availability=result.availability,
        seller_rating=float(result.seller_rating) if result.seller_rating is not None else None,
        condition=result.condition,
        deal_score=float(result.deal_score) if result.deal_score is not None else None,
        url=result.product_url,
        image_url=result.image_url,
        brand=result.brand,
        model_number=result.model_number,
    )


def _build_alternative(alt: AlternativeProduct) -> Alternative:
    price_range: Optional[dict[str, Any]] = None
    if alt.price_min is not None or alt.price_max is not None:
        price_range = {
            "min": float(alt.price_min) if alt.price_min is not None else None,
            "max": float(alt.price_max) if alt.price_max is not None else None,
        }
    return Alternative(
        product_name=alt.product_name,
        model_relationship=alt.model_relationship,
        comparison_summary=alt.comparison_summary,
        key_differences=alt.key_differences,
        price_range=price_range,
        recommendation_strength=alt.recommendation_strength,
        source_urls=alt.source_urls if isinstance(alt.source_urls, list) else [],
    )


def _build_summary_dict(summary: SearchSummary) -> SummaryDict:
    return SummaryDict(
        top_pick=summary.top_pick_summary,
        alternatives_brief=summary.alternatives_brief,
        caveats=summary.caveats,
        model_version=summary.model_version,
        generated_at=summary.generated_at,
        token_usage=summary.token_usage,
    )


async def _get_session_or_404(
    session_id: uuid.UUID, db: AsyncSession
) -> SearchSession:
    """Fetch a SearchSession by ID, raising 404 if missing or soft-deleted."""
    stmt = (
        select(SearchSession)
        .where(
            SearchSession.id == session_id,
            SearchSession.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Search session {session_id} not found.",
                    "recoverable": False,
                }
            },
        )
    return session


def _get_session_token(
    # In a production system this would come from JWT claims or a cookie.
    # For MVP we generate a deterministic token per request or read from header.
    # The token is passed in as a query parameter or header in a real client;
    # here we use a placeholder that satisfies the schema's NOT NULL constraint.
) -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=SearchSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a product search",
    response_description=(
        "Session ID and WebSocket URL returned immediately. "
        "The actual search runs asynchronously via Celery."
    ),
)
async def create_search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchSessionResponse:
    """
    Validate the search request, create a SearchSession in the database,
    dispatch the Celery pipeline task, and return a 202 with the session
    details and the WebSocket URL for real-time progress updates.
    """
    session_id = uuid.uuid4()
    # In production: derive session_token from request headers / JWT sub claim
    session_token = str(uuid.uuid4())

    new_session = SearchSession(
        id=session_id,
        session_token=session_token,
        query_text=body.query,
        status="pending",
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    logger.info(
        "search_session_created",
        session_id=str(session_id),
        query=body.query,
        include_alternatives=body.include_alternatives,
        min_sources=body.min_sources,
        max_price=body.max_price,
    )

    # Dispatch the Celery task.  The import is deferred to avoid circular
    # imports at module load time and to allow the app to start even if
    # Celery/Redis is temporarily unavailable.
    try:
        from app.tasks.search_tasks import run_search  # noqa: PLC0415

        run_search.delay(
            str(session_id),
            body.query,
            {
                "max_price": body.max_price,
                "min_sources": body.min_sources,
                "include_alternatives": body.include_alternatives,
            },
        )
        logger.info("celery_task_dispatched", session_id=str(session_id))
    except Exception as exc:  # pylint: disable=broad-except
        # If Celery is unavailable we still return the session so the client
        # can poll for status rather than crashing the POST.
        logger.warning(
            "celery_dispatch_failed",
            session_id=str(session_id),
            error=str(exc),
        )
        # Mark the session as failed immediately
        new_session.status = "failed"
        await db.commit()

    return SearchSessionResponse(
        session_id=session_id,
        status=new_session.status,
        websocket_url=_make_websocket_url(session_id),
        estimated_duration_seconds=15,
    )


# ---------------------------------------------------------------------------
# GET /search/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{session_id}",
    response_model=SearchStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get search session status",
)
async def get_search_status(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SearchStatusResponse:
    """
    Lightweight status poll endpoint. Returns the session status and basic
    metadata without fetching all result rows.
    """
    session = await _get_session_or_404(session_id, db)

    logger.debug("search_status_polled", session_id=str(session_id), status=session.status)

    return SearchStatusResponse(
        session_id=session.id,
        status=session.status,
        query_text=session.query_text,
        created_at=session.created_at,
        completed_at=session.completed_at,
        result_count=session.result_count,
        total_sources_queried=session.total_sources_queried,
    )


# ---------------------------------------------------------------------------
# GET /search/{session_id}/results
# ---------------------------------------------------------------------------

@router.get(
    "/{session_id}/results",
    response_model=SearchResultsResponse,
    summary="Get full search results",
    responses={
        202: {"description": "Search still in progress; partial or no results available."},
        404: {"description": "Session not found."},
    },
)
async def get_search_results(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SearchResultsResponse:
    """
    Return the full results payload for a completed search session.

    - Returns HTTP 202 with an empty comparison list if the session is still
      processing (allows progressive polling).
    - Returns HTTP 200 with complete data once status='complete'.
    - Returns HTTP 404 if the session does not exist or has been deleted.
    """
    # Fetch session with all related data in one query using eager loading
    stmt = (
        select(SearchSession)
        .options(
            selectinload(SearchSession.results),
            selectinload(SearchSession.summary),
            selectinload(SearchSession.alternatives),
        )
        .where(
            SearchSession.id == session_id,
            SearchSession.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Search session {session_id} not found.",
                    "recoverable": False,
                }
            },
        )

    # If still processing, return 202 with whatever data is available so far
    http_status = (
        status.HTTP_200_OK
        if session.status in ("complete", "failed")
        else status.HTTP_202_ACCEPTED
    )

    # Sort results by rank ascending (rank=1 first)
    sorted_results = sorted(
        session.results or [],
        key=lambda r: (r.rank is None, r.rank or 0),
    )

    response = SearchResultsResponse(
        session_id=session.id,
        query=session.query_text,
        status=session.status,
        created_at=session.created_at,
        completed_at=session.completed_at,
        summary=_build_summary_dict(session.summary) if session.summary else None,
        comparison=[_build_price_entry(r) for r in sorted_results],
        alternatives=[_build_alternative(a) for a in (session.alternatives or [])],
    )

    logger.debug(
        "search_results_fetched",
        session_id=str(session_id),
        status=session.status,
        result_count=len(sorted_results),
    )

    if http_status == status.HTTP_202_ACCEPTED:
        # FastAPI does not support returning a non-default status from a
        # response model function directly, so we raise an HTTP exception
        # with the response body embedded.  The client checks the status code.
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        return JSONResponse(
            status_code=http_status,
            content=response.model_dump(mode="json"),
        )  # type: ignore[return-value]

    return response


# ---------------------------------------------------------------------------
# POST /search/{session_id}/refresh
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/refresh",
    response_model=SearchSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run a past search with fresh data",
)
async def refresh_search(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SearchSessionResponse:
    """
    Create a new SearchSession linked to an existing one via parent_session_id.
    This allows price delta tracking between the original and new search.

    The new session inherits the query and options from the parent.
    A new Celery pipeline task is dispatched for the new session.
    """
    parent = await _get_session_or_404(session_id, db)

    new_session_id = uuid.uuid4()
    session_token = str(uuid.uuid4())

    new_session = SearchSession(
        id=new_session_id,
        session_token=session_token,
        query_text=parent.query_text,
        status="pending",
        parent_session_id=parent.id,
        # Carry forward the parsed query options from the parent if available
        parsed_query=parent.parsed_query,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    logger.info(
        "search_refresh_created",
        parent_session_id=str(session_id),
        new_session_id=str(new_session_id),
        query=parent.query_text,
    )

    try:
        from app.tasks.search_tasks import run_search  # noqa: PLC0415

        run_search.delay(
            str(new_session_id),
            parent.query_text,
            {
                "max_price": None,
                "min_sources": 3,
                "include_alternatives": True,
                "parent_session_id": str(parent.id),
            },
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "celery_dispatch_failed_on_refresh",
            new_session_id=str(new_session_id),
            error=str(exc),
        )
        new_session.status = "failed"
        await db.commit()

    return SearchSessionResponse(
        session_id=new_session_id,
        status=new_session.status,
        websocket_url=_make_websocket_url(new_session_id),
        estimated_duration_seconds=15,
    )
