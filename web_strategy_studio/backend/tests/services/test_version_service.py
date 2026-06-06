"""Tests for VersionService — strategy version management service layer.

Uses an in-memory SQLite database with the real SQLAlchemy models.
All tests are async (pytest-asyncio with asyncio_mode=auto).
"""

from __future__ import annotations

import os

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import SessionLocal, engine
from studio_api.models import Base, Strategy, StrategyVersion
from studio_api.services.version_service import VersionService


@pytest.fixture
async def session():
    """Provide a clean in-memory DB session per test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def svc() -> VersionService:
    return VersionService()


async def _seed_strategy(session: AsyncSession) -> str:
    """Create a strategy with one version for testing."""
    strat = Strategy(
        id="strat_test_001",
        name="Test Strategy",
        current_version=1,
    )
    sv = StrategyVersion(
        id="sv_test_001",
        strategy_id="strat_test_001",
        version=1,
        source_code="print('v1')",
        content_hash="abc123",
    )
    session.add(strat)
    session.add(sv)
    await session.commit()
    return strat.id


# ---------------------------------------------------------------------------
# create_version
# ---------------------------------------------------------------------------


class TestCreateVersion:
    async def test_creates_new_version(self, session, svc):
        sid = await _seed_strategy(session)
        version = await svc.create_version(session, sid, "print('v2')", "second version")

        assert version.version == 2
        assert version.source_code == "print('v2')"
        assert version.label == "second version"
        assert version.content_hash is not None

    async def test_bumps_strategy_current_version(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "print('v2')")

        from sqlalchemy import select

        result = await session.execute(select(Strategy).where(Strategy.id == sid))
        strat = result.scalar_one()
        assert strat.current_version == 2

    async def test_multiple_creates_increment(self, session, svc):
        sid = await _seed_strategy(session)
        v2 = await svc.create_version(session, sid, "v2 code")
        v3 = await svc.create_version(session, sid, "v3 code")
        v4 = await svc.create_version(session, sid, "v4 code")

        assert v2.version == 2
        assert v3.version == 3
        assert v4.version == 4

    async def test_empty_comment_is_none_label(self, session, svc):
        sid = await _seed_strategy(session)
        version = await svc.create_version(session, sid, "code")
        assert version.label is None

    async def test_nonexistent_strategy_raises(self, session, svc):
        with pytest.raises(ValueError, match="not found"):
            await svc.create_version(session, "nonexistent", "code")


# ---------------------------------------------------------------------------
# get_versions
# ---------------------------------------------------------------------------


class TestGetVersions:
    async def test_returns_versions_newest_first(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "v2")
        await svc.create_version(session, sid, "v3")

        versions = await svc.get_versions(session, sid)
        assert len(versions) == 3
        assert versions[0].version == 3
        assert versions[1].version == 2
        assert versions[2].version == 1

    async def test_empty_for_unknown_strategy(self, session, svc):
        versions = await svc.get_versions(session, "nonexistent")
        assert versions == []

    async def test_limit_and_offset(self, session, svc):
        sid = await _seed_strategy(session)
        for i in range(5):
            await svc.create_version(session, sid, f"code {i+2}")

        # Total 6 versions (1 seed + 5 created)
        versions = await svc.get_versions(session, sid, limit=2, offset=1)
        assert len(versions) == 2
        assert versions[0].version == 5  # offset 1 from newest (6)
        assert versions[1].version == 4


# ---------------------------------------------------------------------------
# get_version
# ---------------------------------------------------------------------------


class TestGetVersion:
    async def test_gets_specific_version(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "v2 code")

        sv = await svc.get_version(session, sid, 1)
        assert sv is not None
        assert sv.source_code == "print('v1')"

        sv2 = await svc.get_version(session, sid, 2)
        assert sv2 is not None
        assert sv2.source_code == "v2 code"

    async def test_returns_none_for_missing(self, session, svc):
        sid = await _seed_strategy(session)
        sv = await svc.get_version(session, sid, 99)
        assert sv is None


# ---------------------------------------------------------------------------
# restore_version
# ---------------------------------------------------------------------------


class TestRestoreVersion:
    async def test_restores_old_code(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "v2 code")
        await svc.create_version(session, sid, "v3 code")

        # Restore to v1
        strat = await svc.restore_version(session, sid, 1)
        assert strat is not None
        assert strat.current_version == 4

        # The new version (v4) should have v1's code
        sv = await svc.get_version(session, sid, 4)
        assert sv is not None
        assert sv.source_code == "print('v1')"
        assert sv.label == "restore from v1"

    async def test_returns_none_for_missing_strategy(self, session, svc):
        result = await svc.restore_version(session, "nonexistent", 1)
        assert result is None

    async def test_returns_none_for_missing_version(self, session, svc):
        sid = await _seed_strategy(session)
        result = await svc.restore_version(session, sid, 99)
        assert result is None


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    async def test_generates_diff(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "print('v2 changed')")

        result = await svc.get_diff(session, sid, 1, 2)
        assert result is not None
        assert result["from_version"] == 1
        assert result["to_version"] == 2
        assert result["from_code"] == "print('v1')"
        assert result["to_code"] == "print('v2 changed')"
        assert len(result["diff"]) > 0

    async def test_returns_none_for_missing_version(self, session, svc):
        sid = await _seed_strategy(session)
        result = await svc.get_diff(session, sid, 1, 99)
        assert result is None

    async def test_diff_contains_unified_format(self, session, svc):
        sid = await _seed_strategy(session)
        await svc.create_version(session, sid, "print('v2 changed')")

        result = await svc.get_diff(session, sid, 1, 2)
        diff_text = "".join(result["diff"])
        assert "--- v1" in diff_text
        assert "+++ v2" in diff_text
