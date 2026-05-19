"""JWT-based authentication (BLOCKER-7).

- Password hashing via bcrypt.
- JWT tokens with configurable secret and expiry.
- ``get_current_user`` FastAPI dependency for protected routes.
- Admin user auto-seeded on startup.
"""

from __future__ import annotations

import datetime
import os
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import get_session
from studio_api.models import User

security = HTTPBearer(description="JWT bearer token")

# ── Configuration ────────────────────────────────────────────────────────────
# Read from env; generate a random secret per session if not set (dev-friendly).
JWT_SECRET = os.environ.get("EQ_JWT_SECRET") or os.urandom(32).hex()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("EQ_JWT_EXPIRE_MINUTES", "1440"))  # 24 h default


# ── Password helpers ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT token ────────────────────────────────────────────────────────────────
def create_access_token(user_id: str, expires_minutes: int = JWT_EXPIRE_MINUTES) -> str:
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expires_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── FastAPI dependency ───────────────────────────────────────────────────────
async def get_current_user(
    session: AsyncSession = Depends(get_session),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(description="JWT bearer token", auto_error=False)
    ),
    token: Optional[str] = None,
) -> User:
    """Extract and verify JWT, return the authenticated User.

    Supports both Bearer header (via ``credentials``) and ``?token=`` query
    parameter — the latter needed by SSE/EventSource which can't set headers.
    """
    raw_token = credentials.credentials if credentials else token
    if raw_token is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_MISSING", "message": "Authentication required"},
        )
    try:
        payload = decode_access_token(raw_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail={"code": "TOKEN_EXPIRED", "message": "Token expired"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, detail={"code": "TOKEN_INVALID", "message": "Invalid token"}
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=401, detail={"code": "TOKEN_INVALID", "message": "Invalid token"}
        )

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=401, detail={"code": "USER_NOT_FOUND", "message": "User not found"}
        )
    return user


# ── Optional auth (for routes that work both with and without auth) ──────────
async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(description="JWT bearer token (optional)", auto_error=False)
    ),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Return the authenticated User if a valid token is present, else None."""
    if creds is None:
        return None
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.InvalidTokenError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return await session.get(User, user_id)


# ── Admin seeding ────────────────────────────────────────────────────────────
async def ensure_admin_user(session: AsyncSession) -> User:
    """Create or return the default admin user."""
    admin_id = os.environ.get("EQ_ADMIN_ID", "admin")
    admin_pass = os.environ.get("EQ_ADMIN_PASSWORD", "admin123")
    existing = await session.get(User, admin_id)
    if existing is not None:
        return existing
    user = User(
        id=admin_id,
        username=admin_id,
        hashed_password=hash_password(admin_pass),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
