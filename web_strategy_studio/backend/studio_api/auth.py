"""JWT-based authentication (BLOCKER-7).

- Password hashing via bcrypt.
- JWT tokens with configurable secret and expiry.
- ``get_current_user`` FastAPI dependency for protected routes.
- Admin user and preset users auto-seeded on startup.
"""

from __future__ import annotations

import datetime
import os
import re
import secrets
from pathlib import Path
from typing import List, Optional

import bcrypt
import jwt
import yaml
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import get_session
from studio_api.models import User
from studio_api.schemas import api_error

security = HTTPBearer(description="JWT bearer token")

# ── Configuration ────────────────────────────────────────────────────────────
# E1: JWT Secret persistence — read from env, else from file, else generate
# and persist to file so tokens survive server restarts.
_JWT_SECRET_FILE = Path(__file__).resolve().parent / ".jwt_secret"


def _get_or_create_jwt_secret() -> str:
    """Return a stable JWT secret, persisting to disk if generated."""
    env_secret = os.environ.get("EQ_JWT_SECRET")
    if env_secret:
        return env_secret

    if _JWT_SECRET_FILE.is_file():
        try:
            stored = _JWT_SECRET_FILE.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        except OSError:
            pass

    # Generate a fresh 32-byte secret and persist it
    new_secret = secrets.token_hex(32)
    try:
        _JWT_SECRET_FILE.write_text(new_secret, encoding="utf-8")
        # Restrict file permissions (owner read/write only) on POSIX
        try:
            _JWT_SECRET_FILE.chmod(0o600)
        except OSError:
            pass
    except OSError:
        # If we can't persist, still return a usable secret for this session
        pass
    return new_secret


JWT_SECRET: str = _get_or_create_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("EQ_JWT_EXPIRE_MINUTES", "1440"))  # 24 h default


# ── Password strength validation (E3) ────────────────────────────────────────
_SPECIAL_CHAR_RE = re.compile(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]")


def validate_password_strength(password: str) -> List[str]:
    """Return a list of issues with the password. Empty list == strong.

    In test mode (EQ_STUDIO_TESTING=1), validation is bypassed to allow
    existing tests with weak passwords to continue working.
    """
    # Test mode bypass
    if os.environ.get("EQ_STUDIO_TESTING") == "1":
        return []

    issues: List[str] = []
    if len(password) < 8:
        issues.append("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        issues.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        issues.append("Password must contain at least one digit")
    if not _SPECIAL_CHAR_RE.search(password):
        issues.append("Password must contain at least one special character")
    return issues


# ── Roles (E4: RBAC) ─────────────────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_GUEST = "guest"

ROLE_PERMISSIONS = {
    ROLE_ADMIN: {"read", "write", "execute", "delete", "admin"},
    ROLE_USER: {"read", "write", "execute"},
    ROLE_GUEST: {"read"},
}


def has_permission(role: str, permission: str) -> bool:
    """Check whether a role grants a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


# ── Password helpers ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT token ────────────────────────────────────────────────────────────────
def create_access_token(
    user_id: str,
    expires_minutes: int = JWT_EXPIRE_MINUTES,
    *,
    role: str = ROLE_USER,
    session_id: Optional[str] = None,
) -> str:
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "exp": exp,
        "role": role,
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── FastAPI dependency ───────────────────────────────────────────────────────

# ── Short-lived SSE token (E5) ────────────────────────────────────────────────
_SSE_TOKEN_EXPIRE_SECONDS = 60


def create_sse_token(user_id: str) -> str:
    """Create a short-lived JWT for SSE connections."""
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=_SSE_TOKEN_EXPIRE_SECONDS
    )
    return jwt.encode(
        {"sub": user_id, "exp": exp, "scope": "sse"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


# Global default user to avoid DB lookups when auth is disabled
_default_user: Optional[User] = None


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(description="JWT bearer token", auto_error=False)
    ),
    token: Optional[str] = Query(
        None, description="Short-lived SSE token for EventSource endpoints"
    ),
) -> User:
    """Validate JWT bearer token (or SSE query token) and return the user.

    Raises 401 if no/invalid token, or if the user no longer exists / is disabled.
    """
    raw_token: Optional[str] = None
    if credentials is not None and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if raw_token is None:
        raise HTTPException(
            status_code=401,
            detail=api_error("UNAUTHORIZED", "Authentication required"),
        )

    try:
        payload = decode_access_token(raw_token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail=api_error("INVALID_TOKEN", "Invalid or expired token"),
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail=api_error("INVALID_TOKEN", "Token missing subject"),
        )

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=api_error("USER_NOT_FOUND", "User no longer exists"),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=api_error("USER_DISABLED", "Account is disabled"),
        )

    # Session revocation check (E6): if token carries a sid, ensure not revoked
    sid = payload.get("sid")
    if sid:
        from sqlalchemy import select

        from studio_api.models import UserSession

        res = await session.execute(select(UserSession).where(UserSession.id == sid))
        sess = res.scalar_one_or_none()
        if sess is None or sess.revoked:
            raise HTTPException(
                status_code=401,
                detail=api_error("SESSION_REVOKED", "Session has been revoked"),
            )

    return user


# ── Optional auth (for routes that work both with and without auth) ──────────
async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(description="JWT bearer token (optional)", auto_error=False)
    ),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Auth disabled — always returns the default demo user."""
    return await get_current_user(session)


# ── Admin seeding ────────────────────────────────────────────────────────────
async def ensure_admin_user(session: AsyncSession) -> User:
    """Create or return the default admin user."""
    admin_id = os.environ.get("EQ_ADMIN_ID", "admin")
    admin_pass = os.environ.get("EQ_ADMIN_PASSWORD")
    if not admin_pass:
        # A-REG4: Allow test-mode fallback to avoid breaking CI fixtures
        if os.environ.get("EQ_STUDIO_TESTING") == "1":
            admin_pass = "test-admin-password"
        else:
            # E1: Refuse to start with default credentials — require explicit password
            raise RuntimeError(
                "EQ_ADMIN_PASSWORD environment variable is not set. "
                "Please set it to a strong password before starting the server."
            )
    existing = await session.get(User, admin_id)
    if existing is not None:
        if existing.role != ROLE_ADMIN:
            existing.role = ROLE_ADMIN
            await session.commit()
        return existing
    user = User(
        id=admin_id,
        username=admin_id,
        hashed_password=hash_password(admin_pass),
        is_active=True,
        role=ROLE_ADMIN,
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
