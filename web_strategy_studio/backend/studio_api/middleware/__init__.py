"""RBAC (Role-Based Access Control) middleware and dependencies (Module E4)."""

from __future__ import annotations

from functools import wraps
from typing import Callable, Optional, Sequence

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from studio_api import auth as auth_mod
from studio_api.models import User
from studio_api.schemas import api_error


# ── Dependency: require a specific permission ────────────────────────────────
def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory: returns the current user only if their role
    grants ``permission``. Usage::

        @router.get("/admin", dependencies=[Depends(require_permission("admin"))])
        async def admin_view(): ...

    Or inject the user directly::

        @router.get("/admin")
        async def admin_view(user: User = Depends(require_permission("admin"))): ...
    """

    async def _dependency(user: User = Depends(auth_mod.get_current_user)) -> User:
        if not auth_mod.has_permission(user.role, permission):
            raise HTTPException(
                status_code=403,
                detail=api_error(
                    "FORBIDDEN",
                    f"Role '{user.role}' does not grant permission '{permission}'",
                ),
            )
        return user

    return _dependency


def require_role(*roles: str) -> Callable:
    """Require the current user to have one of the listed roles."""

    async def _dependency(user: User = Depends(auth_mod.get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=api_error(
                    "FORBIDDEN",
                    f"This endpoint requires one of roles: {', '.join(roles)}",
                ),
            )
        return user

    return _dependency


def require_active_user(user: User = Depends(auth_mod.get_current_user)) -> User:
    """Ensure the current user is active (not disabled)."""
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=api_error("USER_DISABLED", "Account is disabled"),
        )
    return user


# ── Utility: decorator for sync routes ───────────────────────────────────────
def with_permission(permission: str):
    """Decorator for use on route handlers to inject a permission check.

    Less common in FastAPI (prefer ``Depends``), but handy for non-async code.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            user: Optional[User] = None
            for v in kwargs.values():
                if isinstance(v, User):
                    user = v
                    break
            if user is None:
                raise HTTPException(
                    status_code=401,
                    detail=api_error("UNAUTHORIZED", "Authentication required"),
                )
            if not auth_mod.has_permission(user.role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=api_error(
                        "FORBIDDEN",
                        f"Role '{user.role}' lacks permission '{permission}'",
                    ),
                )
            return await fn(*args, **kwargs)

        return wrapper

    return decorator
