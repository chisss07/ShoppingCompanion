"""
Security utilities: password hashing, JWT issuance/validation, and the
FastAPI dependency that resolves the currently authenticated admin user.

Dependencies:
    bcrypt       — password hashing (used directly, not via passlib)
    python-jose  — JWT encoding / decoding

Note: passlib 1.7.x is incompatible with bcrypt >= 4.x (the __about__
attribute was removed). We call bcrypt directly and pre-hash passwords
with SHA-256 so we stay well under bcrypt's 72-byte input limit.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_db
from app.models.auth import AdminUser

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_ACCESS_TOKEN_EXPIRE_DAYS = 7
_ALGORITHM = "HS256"

_http_bearer = HTTPBearer()


def _prepare(password: str) -> bytes:
    """
    SHA-256 pre-hash the password before passing to bcrypt.

    bcrypt silently truncates inputs longer than 72 bytes, making long
    passwords equivalent to their first 72 bytes. SHA-256 produces a
    fixed 64-character hex string that is always within the limit.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* value."""
    return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(data: dict) -> str:
    """
    Encode *data* into a signed JWT that expires in 7 days.

    The ``exp`` claim is added automatically.  The caller is responsible for
    including a ``sub`` claim (typically the admin user's username or UUID).

    Args:
        data: Arbitrary claims dict to encode.

    Returns:
        Signed JWT string.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=_ACCESS_TOKEN_EXPIRE_DAYS)
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify *token*.

    Returns the claims dict on success, or ``None`` if the token is invalid,
    expired, or the signature cannot be verified.

    Args:
        token: Raw JWT string (without the ``Bearer `` prefix).

    Returns:
        Decoded claims dict, or None on any error.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    FastAPI dependency that validates the Bearer JWT and returns the
    corresponding ``AdminUser`` row.

    Raises:
        401 Unauthorized — if the token is missing, malformed, expired, or
                           does not correspond to an existing admin user.

    Usage::

        @router.get("/protected")
        async def endpoint(admin: AdminUser = Depends(get_current_admin)):
            ...
    """
    _credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _credentials_exception

    username: Optional[str] = payload.get("sub")
    if not username:
        raise _credentials_exception

    result = await db.execute(
        select(AdminUser).where(AdminUser.username == username)
    )
    admin: Optional[AdminUser] = result.scalars().first()

    if admin is None:
        raise _credentials_exception

    return admin
