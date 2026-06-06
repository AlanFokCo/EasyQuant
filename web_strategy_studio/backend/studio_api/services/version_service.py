"""Version management service for strategies.

Wraps the SQLAlchemy operations used by the strategies router into a
reusable service layer with clean async API.
"""

from __future__ import annotations

import difflib
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api.models import Strategy, StrategyVersion


def _hash(source_code: str) -> str:
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    import secrets
    return f"{prefix}_{secrets.token_hex(8)}"


class VersionService:
    """Service for managing strategy versions."""

    async def create_version(
        self,
        session: AsyncSession,
        strategy_id: str,
        code: str,
        comment: str = "",
    ) -> StrategyVersion:
        """Create a new version snapshot.

        Args:
            session: Database session.
            strategy_id: Strategy ID.
            code: Source code to snapshot.
            comment: Optional label/comment for the version.

        Returns:
            The newly created StrategyVersion row.
        """
        result = await session.execute(
            select(Strategy)
            .options(selectinload(Strategy.versions))
            .where(Strategy.id == strategy_id)
        )
        strat = result.scalar_one_or_none()
        if strat is None:
            raise ValueError(f"Strategy {strategy_id} not found")

        now = datetime.now(timezone.utc)
        new_ver = strat.current_version + 1
        strat.current_version = new_ver
        strat.updated_at = now

        version = StrategyVersion(
            id=_new_id("sv"),
            strategy_id=strategy_id,
            version=new_ver,
            source_code=code,
            content_hash=_hash(code),
            label=comment if comment else None,
        )
        session.add(version)
        await session.commit()
        await session.refresh(version)
        return version

    async def get_versions(
        self,
        session: AsyncSession,
        strategy_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StrategyVersion]:
        """Get version history for a strategy (latest first).

        Args:
            session: Database session.
            strategy_id: Strategy ID.
            limit: Maximum versions to return.
            offset: Number of versions to skip.

        Returns:
            List of StrategyVersion rows, newest first.
        """
        result = await session.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.version.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_version(
        self,
        session: AsyncSession,
        strategy_id: str,
        version_number: int,
    ) -> Optional[StrategyVersion]:
        """Get a specific version by number.

        Args:
            session: Database session.
            strategy_id: Strategy ID.
            version_number: Version number to retrieve.

        Returns:
            The StrategyVersion row, or None if not found.
        """
        result = await session.execute(
            select(StrategyVersion)
            .where(
                StrategyVersion.strategy_id == strategy_id,
                StrategyVersion.version == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def restore_version(
        self,
        session: AsyncSession,
        strategy_id: str,
        version_number: int,
    ) -> Optional[Strategy]:
        """Restore a strategy to a specific version.

        Creates a new version row with the old code, preserving history.

        Args:
            session: Database session.
            strategy_id: Strategy ID.
            version_number: Version number to restore.

        Returns:
            The updated Strategy, or None if strategy/version not found.
        """
        result = await session.execute(
            select(Strategy)
            .options(selectinload(Strategy.versions))
            .where(Strategy.id == strategy_id)
        )
        strat = result.scalar_one_or_none()
        if strat is None:
            return None

        sv = next((v for v in strat.versions if v.version == version_number), None)
        if sv is None:
            return None

        now = datetime.now(timezone.utc)
        new_ver = strat.current_version + 1
        strat.current_version = new_ver
        strat.updated_at = now

        session.add(
            StrategyVersion(
                id=_new_id("sv"),
                strategy_id=strategy_id,
                version=new_ver,
                source_code=sv.source_code,
                content_hash=sv.content_hash or _hash(sv.source_code),
                label=f"restore from v{version_number}",
            )
        )
        await session.commit()
        await session.refresh(strat)
        return strat

    async def get_diff(
        self,
        session: AsyncSession,
        strategy_id: str,
        from_version: int,
        to_version: int,
    ) -> Optional[dict]:
        """Generate a unified diff between two versions.

        Args:
            session: Database session.
            strategy_id: Strategy ID.
            from_version: Older version number.
            to_version: Newer version number.

        Returns:
            Dict with from_code, to_code, and diff lines, or None if not found.
        """
        from_sv = await self.get_version(session, strategy_id, from_version)
        to_sv = await self.get_version(session, strategy_id, to_version)
        if from_sv is None or to_sv is None:
            return None

        from_lines = from_sv.source_code.splitlines(keepends=True)
        to_lines = to_sv.source_code.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
        ))

        return {
            "from_version": from_version,
            "to_version": to_version,
            "from_code": from_sv.source_code,
            "to_code": to_sv.source_code,
            "diff": diff,
        }
