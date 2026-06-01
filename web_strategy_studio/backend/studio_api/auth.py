"""JWT-based authentication (BLOCKER-7).

- Password hashing via bcrypt.
- JWT tokens with configurable secret and expiry.
- ``get_current_user`` FastAPI dependency for protected routes.
- Admin user and preset users auto-seeded on startup.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
import yaml
from fastapi import Depends, HTTPException, Query
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
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


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
    token: Optional[str] = Query(None, description="JWT token for SSE/EventSource endpoints"),
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
    admin_pass = os.environ.get("EQ_ADMIN_PASSWORD")
    if not admin_pass:
        # E1: Refuse to start with default credentials — require explicit password
        raise RuntimeError(
            "EQ_ADMIN_PASSWORD environment variable is not set. "
            "Please set it to a strong password before starting the server."
        )
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


# ── Preset users seeding ──────────────────────────────────────────────────────
def _load_preset_users_from_yaml() -> list[dict[str, str]]:
    """Load preset users from users.yaml config file."""
    # Look for users.yaml in backend directory
    config_path = Path(__file__).resolve().parent.parent / "users.yaml"
    if not config_path.is_file():
        return []

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return []

    users = data.get("preset_users", [])
    if not isinstance(users, list):
        return []

    result: list[dict[str, str]] = []
    for u in users:
        if not isinstance(u, dict):
            continue
        username = u.get("username", "")
        password = u.get("password", "")
        if isinstance(username, str) and isinstance(password, str):
            username = username.strip()
            password = password.strip()
            if username and password:
                result.append({"username": username, "password": password})

    return result


def _load_preset_users_from_env() -> list[dict[str, str]]:
    """Load preset users from environment variable EQ_PRESET_USERS."""
    preset_env = os.environ.get("EQ_PRESET_USERS", "")
    if not preset_env:
        return []

    result: list[dict[str, str]] = []
    pairs = preset_env.split(",")
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(":")
        if len(parts) != 2:
            continue
        username, password = parts[0].strip(), parts[1].strip()
        if username and password:
            result.append({"username": username, "password": password})

    return result


async def ensure_preset_users(session: AsyncSession) -> list[User]:
    """Create preset users from both users.yaml config file and EQ_PRESET_USERS env.

    Config file format (users.yaml):
        preset_users:
          - username: demo
            password: demo123
          - username: analyst
            password: analyst456

    Env format:
        EQ_PRESET_USERS="user1:pass1,user2:pass2"

    If both are configured, both sets of users will be created.
    """
    # Combine users from both sources
    all_users = _load_preset_users_from_yaml() + _load_preset_users_from_env()

    if not all_users:
        return []

    users: list[User] = []
    for user_def in all_users:
        username = user_def["username"]
        password = user_def["password"]

        existing = await session.get(User, username)
        if existing is not None:
            users.append(existing)
            continue

        user = User(
            id=username,
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(user)
        users.append(user)

    if users:
        await session.commit()
        for u in users:
            await session.refresh(u)

    return users
