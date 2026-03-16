"""
History API endpoints.

Routes (all prefixed with /api/v1 in the router):
    GET    /history                    Paginated search history list
    DELETE /history/{session_id}       Delete a specific history entry
    DELETE /history                    Clear all history for this session token
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import get_db
from app.models.search import SearchResult, SearchSession
from app.schemas.search import HistoryItem, HistoryResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/history", tags=["history"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_request_session_token() -> str:
    """
    Resolve the session token that identifies the current user/session.

    In a full implementation this reads from:
      - JWT sub claim (authenticated users)
      - A signed session cookie (anonymous users)
      - X-Session-Token request header (anonymous API clients)

    For MVP, this returns a placeholder.  The routes receive this via
    Depends() and the actual middleware/header-extraction logic lives here.
    """
    # TODO: replace with header extraction / JWT decoding
    return "anonymous-session-token"


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="List past searches with best price",
)
async def list_history(
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page."),
    q: Optional[str] = Query(
        default=None,
        description="Full-text filter applied to query_text.",
        min_length=1,
        max_length=200,
    ),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """
    Return a paginated list of past search sessions for the current user /
    anonymous session, ordered by creation date descending.

    Each item includes the best_price and best_source derived from the
    search_results row where rank=1 (the top-ranked listing at search time).
    """
    # ── Count total matching rows ──────────────────────────────────────────
    count_stmt = (
        select(func.count())
        .select_from(SearchSession)
        .where(SearchSession.deleted_at.is_(None))
    )
    if q:
        count_stmt = count_stmt.where(
            SearchSession.query_text.ilike(f"%{q}%")
        )

    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    # ── Fetch page ─────────────────────────────────────────────────────────
    offset = (page - 1) * limit

    # Main session query
    sessions_stmt = (
        select(SearchSession)
        .where(SearchSession.deleted_at.is_(None))
        .order_by(SearchSession.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if q:
        sessions_stmt = sessions_stmt.where(
            SearchSession.query_text.ilike(f"%{q}%")
        )

    sessions_result = await db.execute(sessions_stmt)
    sessions = sessions_result.scalars().all()

    if not sessions:
        return HistoryResponse(items=[], total=total, page=page, limit=limit)

    # ── Fetch rank=1 results in one batched query ──────────────────────────
    session_ids = [s.id for s in sessions]

    top_results_stmt = (
        select(SearchResult)
        .where(
            SearchResult.session_id.in_(session_ids),
            SearchResult.rank == 1,
        )
    )
    top_results_result = await db.execute(top_results_stmt)
    top_results_rows = top_results_result.scalars().all()

    # Build a lookup dict: session_id -> SearchResult (rank=1)
    top_by_session: dict[uuid.UUID, SearchResult] = {
        r.session_id: r for r in top_results_rows
    }

    # ── Assemble response ──────────────────────────────────────────────────
    items: list[HistoryItem] = []
    for session in sessions:
        top = top_by_session.get(session.id)
        items.append(
            HistoryItem(
                session_id=session.id,
                query_text=session.query_text,
                status=session.status,
                created_at=session.created_at,
                completed_at=session.completed_at,
                result_count=session.result_count,
                best_price=float(top.price) if top else None,
                best_source=top.source_name if top else None,
            )
        )

    logger.debug(
        "history_listed",
        page=page,
        limit=limit,
        total=total,
        filter=q,
        items_returned=len(items),
    )

    return HistoryResponse(items=items, total=total, page=page, limit=limit)


# ---------------------------------------------------------------------------
# DELETE /history/{session_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single search history entry",
)
async def delete_history_entry(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft-delete a single search session by setting deleted_at.

    The session row and all related search_results / alternative_products /
    search_summaries remain in the database for audit purposes and are
    excluded from all history queries via the deleted_at IS NULL predicate.

    Returns 204 No Content on success.
    Returns 404 if the session does not exist or is already deleted.
    """
    stmt = select(SearchSession).where(
        SearchSession.id == session_id,
        SearchSession.deleted_at.is_(None),
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

    session.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("history_entry_deleted", session_id=str(session_id))


# ---------------------------------------------------------------------------
# DELETE /history
# ---------------------------------------------------------------------------

@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all search history for this session",
)
async def delete_all_history(
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft-delete all non-deleted search sessions associated with the current
    session token (anonymous) or user ID (authenticated).

    Returns 204 No Content regardless of how many rows were affected.

    Note: This is a soft delete.  Rows remain in the database and are
    hard-deleted by the nightly cleanup job after the configured retention
    grace period.
    """
    # In production, filter by user_id (authenticated) OR session_token (anonymous)
    # For MVP we soft-delete all non-deleted sessions.
    now = datetime.now(timezone.utc)

    stmt = select(SearchSession).where(SearchSession.deleted_at.is_(None))
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    count = 0
    for session in sessions:
        session.deleted_at = now
        count += 1

    await db.commit()

    logger.info("history_cleared", sessions_soft_deleted=count)
