"""Auth router: register, login, sessions, admin (Module E)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api import auth as auth_mod
from studio_api.db import get_session
from studio_api.middleware.rbac import require_permission, require_role
from studio_api.models import User, UserSession
from studio_api.schemas import api_error
from studio_api.services import auth_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


# ── Request / response schemas ───────────────────────────────────────────────
class RegisterBody(BaseModel):
    username: str
    password: str
    invite_code: str = ""


class LoginBody(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str = "user"
    session_id: Optional[str] = None


class SessionItem(BaseModel):
    session_id: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: str
    last_used_at: str
    current: bool = False


class SessionListResponse(BaseModel):
    sessions: List[SessionItem]


class UserItem(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: str


class SetRoleBody(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in auth_mod.ROLE_PERMISSIONS:
            raise ValueError(
                f"Invalid role. Choose from: {', '.join(sorted(auth_mod.ROLE_PERMISSIONS))}"
            )
        return v


class SetActiveBody(BaseModel):
    is_active: bool


# ── Registration ─────────────────────────────────────────────────────────────
@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user. Subject to registration policy (E2)."""
    # Password strength is checked inside auth_service.register_user
    # but we also pre-validate here so pydantic returns 422 with proper details.
    issues = auth_mod.validate_password_strength(body.password)
    if issues:
        raise HTTPException(
            status_code=422,
            detail=api_error("WEAK_PASSWORD", "Password does not meet requirements", issues),
        )

    user = await auth_service.register_user(
        session,
        username=body.username,
        password=body.password,
        invite_code=body.invite_code,
    )

    # Also log the user in (create a session) after registration
    _, token, sid = await auth_service.login_user(
        session,
        username=body.username,
        password=body.password,
        request=request,
    )

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=sid,
    )


# ── Login ────────────────────────────────────────────────────────────────────
@router.post("/auth/login", response_model=AuthResponse)
async def login(
    body: LoginBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate and return JWT token. Implements E5 lockout."""
    user, token, sid = await auth_service.login_user(
        session,
        username=body.username,
        password=body.password,
        request=request,
    )
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=sid,
    )


# ── Logout / sessions ────────────────────────────────────────────────────────
@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke the current session (logout this device)."""
    auth_header = request.headers.get("Authorization", "")
    sid = None
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:]
        try:
            payload = auth_mod.decode_access_token(raw_token)
            sid = payload.get("sid")
        except Exception:
            pass
    if sid:
        await auth_service.revoke_session(session, user_id=user.id, session_id=sid)
    return None


class RevokeSessionBody(BaseModel):
    session_id: str


@router.get("/auth/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all active sessions for the current user (E6)."""
    # Determine current session id
    current_sid = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = auth_mod.decode_access_token(auth_header[7:])
            current_sid = payload.get("sid")
        except Exception:
            pass

    sessions = await auth_service.list_sessions(session, user.id)
    items = []
    for s in sessions:
        items.append(
            SessionItem(
                session_id=s.id,
                user_agent=s.user_agent,
                ip_address=s.ip_address,
                created_at=s.created_at.isoformat() if s.created_at else "",
                last_used_at=s.last_used_at.isoformat() if s.last_used_at else "",
                current=(s.id == current_sid),
            )
        )
    return SessionListResponse(sessions=items)


@router.post("/auth/sessions/revoke", status_code=204)
async def revoke_session_endpoint(
    body: RevokeSessionBody,
    user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke a specific session by id (E6)."""
    ok = await auth_service.revoke_session(
        session, user_id=user.id, session_id=body.session_id
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=api_error("SESSION_NOT_FOUND", "Session not found or already revoked"),
        )
    return None


@router.post("/auth/sessions/revoke-all", status_code=204)
async def revoke_all_sessions_endpoint(
    user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Force-logout from all devices (E6)."""
    count = await auth_service.revoke_all_sessions(session, user_id=user.id)
    return None


# ── SSE token (kept from original) ───────────────────────────────────────────
class SseTokenResponse(BaseModel):
    token: str


@router.post("/auth/sse-token", response_model=SseTokenResponse)
async def get_sse_token(user: User = Depends(auth_mod.get_current_user)):
    """Issue a short-lived SSE token for EventSource connections."""
    token = auth_mod.create_sse_token(user.id)
    return SseTokenResponse(token=token)


# ── /me ──────────────────────────────────────────────────────────────────────
@router.get("/auth/me")
async def me(user: User = Depends(auth_mod.get_current_user)):
    """Return current user info (includes role)."""
    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "role": user.role,
        "permissions": sorted(auth_mod.ROLE_PERMISSIONS.get(user.role, set())),
    }


# ── Admin endpoints ──────────────────────────────────────────────────────────
@router.get("/admin/users", response_model=List[UserItem])
async def admin_list_users(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_permission("admin")),
):
    """List all users (admin only)."""
    users = await auth_service.list_users(session)
    return [
        UserItem(
            id=u.id,
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@router.patch("/admin/users/{user_id}/role", response_model=UserItem)
async def admin_set_role(
    user_id: str,
    body: SetRoleBody,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_permission("admin")),
):
    """Change a user's role (admin only)."""
    user = await auth_service.set_user_role(session, user_id=user_id, role=body.role)
    return UserItem(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.patch("/admin/users/{user_id}/active", response_model=UserItem)
async def admin_set_active(
    user_id: str,
    body: SetActiveBody,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_permission("admin")),
):
    """Enable or disable a user (admin only). Disabling also revokes sessions."""
    user = await auth_service.set_user_active(
        session, user_id=user_id, is_active=body.is_active
    )
    return UserItem(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/admin/users/{user_id}/force-logout", status_code=204)
async def admin_force_logout(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_permission("admin")),
):
    """Revoke all sessions of a specific user (admin only)."""
    await auth_service.revoke_all_sessions(session, user_id=user_id)
    return None
