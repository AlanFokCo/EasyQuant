from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Authentication user (BLOCKER-7, E-auth)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="1")
    # E4: RBAC role (admin / user / guest)
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    # E5: login lockout — track failed attempts
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategies: Mapped[List["Strategy"]] = relationship(back_populates="owner")
    sessions: Mapped[List["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """E6: Tracks active sessions (one per device) for force-logout."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE")
    )
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    revoked: Mapped[bool] = mapped_column(default=False, server_default="0")

    user: Mapped["User"] = relationship(back_populates="sessions")


class RevokedToken(Base):
    """E6: JWT blacklist — stores jti (session IDs) that have been revoked."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    default_params: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="strategies")
    versions: Mapped[List["StrategyVersion"]] = relationship(
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyVersion.version",
    )
    runs: Mapped[List["Run"]] = relationship(back_populates="strategy")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("strategies.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    source_code: Mapped[str] = mapped_column(Text)
    # B4/B15: content hash for dedup; sha256 hex (64 chars) or NULL for legacy rows
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Named snapshot label (set by POST /snapshot)
    label: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategy: Mapped["Strategy"] = relationship(back_populates="versions")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("strategies.id", ondelete="CASCADE")
    )
    strategy_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    params: Mapped[Dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    json_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_hostname: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    strategy: Mapped["Strategy"] = relationship(back_populates="runs")
