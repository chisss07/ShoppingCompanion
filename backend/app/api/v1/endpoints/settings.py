"""
Settings management endpoints (admin-only).

Routes:
    GET /settings   — List all managed API key settings (values masked).
    PUT /settings   — Upsert one or more settings by key.

Managed keys:
    SERPAPI_KEY, ANTHROPIC_API_KEY, BESTBUY_API_KEY, EBAY_APP_ID,
    EBAY_OAUTH_TOKEN

Design notes:
    - All routes require a valid admin JWT (via get_current_admin dependency).
    - Values are stored in the app_settings table (key is the primary key),
      so writes are always upserts.
    - GET responses mask values: only the last 4 characters are revealed
      (e.g. "****abc1").  An empty or null value shows as "".
    - An empty string in a PUT body means "clear this key" (stored as NULL).
    - Keys not in the managed list are silently ignored in PUT requests.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_admin
from app.db.base import get_db
from app.models.auth import AdminUser, AppSetting

router = APIRouter(prefix="/settings", tags=["settings"])

# The full set of API-key settings managed through this interface.
_MANAGED_KEYS: list[str] = [
    "SERPAPI_KEY",
    "ANTHROPIC_API_KEY",
    "BESTBUY_API_KEY",
    "EBAY_APP_ID",
    "EBAY_OAUTH_TOKEN",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mask_value(value: str | None) -> str:
    """
    Return a masked representation of *value*.

    - If value is None or empty: returns ``""``
    - If value has 4 or fewer characters: returns ``"****"``
    - Otherwise: returns ``"****"`` + the last 4 characters.
    """
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def _build_setting_entry(key: str, db_row: AppSetting | None) -> dict[str, Any]:
    """Build the response dict for a single setting."""
    raw_value = db_row.value if db_row else None
    return {
        "key": key,
        "masked_value": _mask_value(raw_value),
        "is_set": bool(raw_value),
    }


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List all managed API key settings (admin only)",
    response_model=list,
)
async def get_settings_endpoint(
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    """
    Return all managed API key settings with masked values.

    Each entry in the response list has the shape::

        {
            "key": "SERPAPI_KEY",
            "masked_value": "****ab12",   # last 4 chars, or "" if not set
            "is_set": true
        }

    Requires a valid admin Bearer token.
    """
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_(_MANAGED_KEYS))
    )
    rows: dict[str, AppSetting] = {row.key: row for row in result.scalars().all()}

    return [_build_setting_entry(key, rows.get(key)) for key in _MANAGED_KEYS]


# ---------------------------------------------------------------------------
# PUT /settings
# ---------------------------------------------------------------------------


@router.put(
    "",
    summary="Upsert API key settings (admin only)",
)
async def put_settings_endpoint(
    body: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> dict[str, Any]:
    """
    Upsert one or more managed API key settings.

    Request body is a plain JSON object mapping setting keys to new values::

        {
            "SERPAPI_KEY": "sk-...",
            "ANTHROPIC_API_KEY": ""
        }

    Rules:
    - Only keys in the managed list are processed; unknown keys are ignored.
    - An empty string clears the key (stored as NULL in the database).
    - Returns the list of keys that were actually written.

    Requires a valid admin Bearer token.

    Raises:
        400: Request body contains no recognised managed keys.
    """
    from datetime import datetime, timezone

    to_upsert = {k: v for k, v in body.items() if k in _MANAGED_KEYS}

    if not to_upsert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No managed settings keys found in request. "
                f"Valid keys: {_MANAGED_KEYS}"
            ),
        )

    now = datetime.now(timezone.utc)

    for key, raw_value in to_upsert.items():
        # Treat empty string as "clear" — store NULL
        stored_value: str | None = raw_value if raw_value else None

        stmt = (
            pg_insert(AppSetting)
            .values(key=key, value=stored_value, updated_at=now)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": stored_value, "updated_at": now},
            )
        )
        await db.execute(stmt)

    await db.commit()

    return {"updated": list(to_upsert.keys())}
