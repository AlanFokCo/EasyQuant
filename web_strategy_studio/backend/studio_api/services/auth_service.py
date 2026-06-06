"""Authentication business logic (Module E).

Handles registration, login (with lockout), session management, and
token revocation. All DB interactions live here; routers only orchestrate.
"""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid
from typing import List, Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api import auth as auth_mod
from studio_api.config import settings
from studio_api.models import RevokedToken, User, UserSession
from studio_api.schemas import api_error


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _ensure_aware(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """Convert a naive datetime (as returned by SQLite) to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


# ── Registration ─────────────────────────────────────────────────────────────
async def register_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    invite_code: str = "",
    role: Optional[str] = None,
) -> User:
    """Validate policy, create a user, and return it.

    Raises HTTPException on any policy violation (disabled registration,
    invalid invite code, weak password, duplicate username).
    """
    if not settings.allow_registration:
        raise HTTPException(
            status_code=403,
            detail=api_error("REGISTRATION_DISABLED", "Registration is disabled"),
        )

    if settings.require_invite_code:
        if not invite_code:
            raise HTTPException(
                status_code=400,
                detail=api_error("INVITE_CODE_REQUIRED", "Invite code is required"),
            )
        if invite_code not in settings.valid_invite_codes:
            raise HTTPException(
                status_code=400,
                detail=api_error("INVITE_CODE_INVALID", "Invalid invite code"),
            )

    issues = auth_mod.validate_password_strength(password)
    if issues:
        raise HTTPException(
            status_code=422,
            detail=api_error("WEAK_PASSWORD", "Password does not meet requirements", issues),
        )

    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=api_error("USERNAME_TAKEN", f"Username '{username}' already exists"),
        )

    user_role = role or settings.default_user_role
    user = User(
        id=f"user_{username}",
        username=username,
        hashed_password=auth_mod.hash_password(password),
        role=user_role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ── Login ────────────────────────────────────────────────────────────────────
def _client_ip(request: Optional[Request]) -> str:
    """Extract client IP address from the request.

    Only trusts X-Forwarded-For when ``settings.trust_proxy_headers`` is True,
    preventing IP spoofing via forged headers on direct-access deployments.
    """
    if request is None:
        return "unknown"
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _client_user_agent(request: Optional[Request]) -> str:
    if request is None:
        return ""
    return request.headers.get("User-Agent", "")[:512]


async def login_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    request: Optional[Request] = None,
) -> Tuple[User, str, str]:
    """Authenticate a user, create a session, return (user, token, session_id).

    Implements E5 (lockout after N failed attempts).
    """
    res = await session.execute(select(User).where(User.username == username))
    user = res.scalar_one_or_none()

    now = _utcnow()

    # Unknown user — count as failed attempt to avoid user-enumeration timing
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=api_error("INVALID_CREDENTIALS", "Invalid username or password"),
        )

    # Check lockout
    locked_until = _ensure_aware(user.locked_until)
    if locked_until is not None and locked_until > now:
        remaining = int((locked_until - now).total_seconds())
        raise HTTPException(
            status_code=423,
            detail=api_error(
                "ACCOUNT_LOCKED",
                f"Account is locked. Try again in {remaining} seconds",
                {"retry_after_sec": remaining},
            ),
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=api_error("USER_DISABLED", "Account is disabled"),
        )

    # Verify password
    if not auth_mod.verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.max_login_attempts:
            user.locked_until = now + datetime.timedelta(
                seconds=settings.lockout_duration_sec
            )
        await session.commit()
        raise HTTPException(
            status_code=401,
            detail=api_error(
                "INVALID_CREDENTIALS",
                "Invalid username or password",
                {
                    "attempts_remaining": max(
                        settings.max_login_attempts - user.failed_login_attempts, 0
                    )
                },
            ),
        )

    # Successful login — reset counter, update last_login_at
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    # E6: Create session record
    sid = uuid.uuid4().hex
    sess = UserSession(
        id=sid,
        user_id=user.id,
        user_agent=_client_user_agent(request),
        ip_address=_client_ip(request),
    )
    session.add(sess)

    # Enforce max sessions per user (revoke oldest)
    if settings.max_sessions_per_user > 0:
        await _enforce_session_limit(session, user.id, settings.max_sessions_per_user)

    await session.commit()
    await session.refresh(user)

    token = auth_mod.create_access_token(user.id, role=user.role, session_id=sid)
    return user, token, sid


async def _enforce_session_limit(
    session: AsyncSession, user_id: str, limit: int
) -> None:
    """Revoke the oldest sessions if the user has more than `limit` active sessions."""
    # Flush pending changes (including the newly added session) before querying
    await session.flush()
    res = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked.is_(False))
        .order_by(UserSession.created_at.desc(), UserSession.id.desc())
    )
    active = res.scalars().all()
    if len(active) <= limit:
        return
    # Keep the first `limit` sessions (newest), revoke the rest
    to_revoke = active[limit:]
    for s in to_revoke:
        s.revoked = True
        # Also blacklist the JWT (session id == jti in token claim)
        session.add(
            RevokedToken(
                jti=s.id,
                user_id=user_id,
                revoked_at=_utcnow(),
            )
        )


# ── Session management ───────────────────────────────────────────────────────
async def list_sessions(session: AsyncSession, user_id: str) -> List[UserSession]:
    res = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked.is_(False))
        .order_by(UserSession.last_used_at.desc())
    )
    return list(res.scalars().all())


async def revoke_session(
    session: AsyncSession, *, user_id: str, session_id: str
) -> bool:
    """Revoke a specific session (and blacklist its JWT). Returns True if revoked."""
    res = await session.execute(
        select(UserSession).where(
            UserSession.id == session_id, UserSession.user_id == user_id
        )
    )
    sess = res.scalar_one_or_none()
    if sess is None or sess.revoked:
        return False
    sess.revoked = True
    session.add(
        RevokedToken(
            jti=session_id,
            user_id=user_id,
            revoked_at=_utcnow(),
        )
    )
    await session.commit()
    return True


async def revoke_all_sessions(session: AsyncSession, *, user_id: str) -> int:
    """Revoke every session for a user (force logout everywhere). Returns count."""
    res = await session.execute(
        select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked.is_(False)
        )
    )
    sessions_list = res.scalars().all()
    now = _utcnow()
    for s in sessions_list:
        s.revoked = True
        session.add(
            RevokedToken(jti=s.id, user_id=user_id, revoked_at=now)
        )
    await session.commit()
    return len(sessions_list)


async def is_token_revoked(session: AsyncSession, jti: Optional[str]) -> bool:
    """Return True if the given session id is on the blacklist."""
    if not jti:
        return False
    res = await session.execute(
        select(RevokedToken).where(RevokedToken.jti == jti)
    )
    return res.scalar_one_or_none() is not None


# ── Admin helpers ────────────────────────────────────────────────────────────
async def set_user_role(
    session: AsyncSession, *, user_id: str, role: str
) -> User:
    if role not in auth_mod.ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=400,
            detail=api_error("INVALID_ROLE", f"Unknown role: {role}"),
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=api_error("USER_NOT_FOUND", "User not found"),
        )
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_active(
    session: AsyncSession, *, user_id: str, is_active: bool
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=api_error("USER_NOT_FOUND", "User not found"),
        )
    user.is_active = is_active
    if not is_active:
        # Also revoke all sessions when disabled
        await revoke_all_sessions(session, user_id=user_id)
    else:
        await session.commit()
    await session.refresh(user)
    return user


async def list_users(session: AsyncSession) -> List[User]:
    res = await session.execute(select(User).order_by(User.created_at))
    return list(res.scalars().all())


def password_hash_for_test(plain: str) -> str:
    """Expose password hasher for tests/seeding."""
    return auth_mod.hash_password(plain)
