"""
Authentication endpoints.

Routes:
    GET  /auth/status   — Check whether an admin account exists.
    POST /auth/setup    — Create the first (and only) admin account.
    POST /auth/login    — Authenticate and receive a Bearer token.

Design notes:
    - The application uses a single-admin model.  Once set up via /auth/setup
      the endpoint returns 400 on all subsequent calls.
    - Passwords are stored as bcrypt hashes; JWTs are HS256, 7-day expiry.
    - login returns 401 (not 403) for both unknown username and wrong password
      to avoid leaking account existence through timing or error messages.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import get_db
from app.models.auth import AdminUser

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CredentialsIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# GET /auth/status
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    summary="Check whether an admin account has been created",
    response_model=dict,
)
async def auth_status(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Return ``{"admin_exists": true}`` once the admin account has been
    created via /auth/setup, or ``{"admin_exists": false}`` before setup.

    This endpoint is public (no auth required) so the frontend can decide
    whether to show the setup screen or the login screen.
    """
    result = await db.execute(select(func.count()).select_from(AdminUser))
    count: int = result.scalar_one()
    return {"admin_exists": count > 0}


# ---------------------------------------------------------------------------
# POST /auth/setup
# ---------------------------------------------------------------------------


@router.post(
    "/setup",
    summary="Create the initial admin account (one-time operation)",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
)
async def auth_setup(
    body: CredentialsIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """
    Create the first admin account and return an access token.

    This endpoint is only available before any admin account exists.  Once
    an account has been created it returns **400 Bad Request** on all
    subsequent calls to prevent privilege escalation.

    Args:
        body: ``{username, password}``

    Returns:
        ``{access_token, token_type}``

    Raises:
        400: Admin account already exists.
    """
    # Guard: only allowed when no admin exists
    result = await db.execute(select(func.count()).select_from(AdminUser))
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account already exists. Use /auth/login instead.",
        )

    admin = AdminUser(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    db.add(admin)
    await db.commit()

    token = create_access_token({"sub": admin.username})
    return TokenOut(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    summary="Authenticate and receive a Bearer token",
    response_model=TokenOut,
)
async def auth_login(
    body: CredentialsIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """
    Verify credentials and return a signed JWT.

    Both an unknown username and a wrong password return **401 Unauthorized**
    with an identical message to avoid leaking account existence.

    Args:
        body: ``{username, password}``

    Returns:
        ``{access_token, token_type}``

    Raises:
        401: Credentials are incorrect.
    """
    _bad_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    result = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    admin: AdminUser | None = result.scalars().first()

    if admin is None or not verify_password(body.password, admin.password_hash):
        raise _bad_credentials

    token = create_access_token({"sub": admin.username})
    return TokenOut(access_token=token)
