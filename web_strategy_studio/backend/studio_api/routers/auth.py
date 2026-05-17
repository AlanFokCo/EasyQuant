"""Auth router: register, login, me."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import get_session
from studio_api.models import User
from studio_api import auth as auth_mod
from studio_api.schemas import api_error

router = APIRouter(prefix="/api/v1", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterBody, session: AsyncSession = Depends(get_session)):
    """Create a new user and return JWT token."""
    # Check if username already taken
    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=api_error("USERNAME_TAKEN", f"Username '{body.username}' already exists"),
        )

    user = User(
        id=f"user_{body.username}",
        username=body.username,
        hashed_password=auth_mod.hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return AuthResponse(
        access_token=auth_mod.create_access_token(user.id),
        user_id=user.id,
        username=user.username,
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(body: LoginBody, session: AsyncSession = Depends(get_session)):
    """Authenticate and return JWT token."""
    res = await session.execute(select(User).where(User.username == body.username))
    user = res.scalar_one_or_none()
    if user is None or not auth_mod.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail=api_error("INVALID_CREDENTIALS", "Invalid username or password"),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=api_error("USER_DISABLED", "Account is disabled"),
        )

    return AuthResponse(
        access_token=auth_mod.create_access_token(user.id),
        user_id=user.id,
        username=user.username,
    )


@router.get("/auth/me")
async def me(user: User = Depends(auth_mod.get_current_user)):
    """Return current user info."""
    return {"id": user.id, "username": user.username, "is_active": user.is_active}
