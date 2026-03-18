"""
Security utilities: password hashing, JWT issuance/validation, and the
FastAPI dependency that resolves the currently authenticated admin user.

Dependencies:
    passlib[bcrypt]  — password hashing
    python-jose      — JWT encoding / decoding
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_db
from app.models.auth import AdminUser

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ACCESS_TOKEN_EXPIRE_DAYS = 7
_ALGORITHM = "HS256"

_http_bearer = HTTPBearer()


def hash_password(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* value."""
    return _pwd_context.verify(plain, hashed)


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
