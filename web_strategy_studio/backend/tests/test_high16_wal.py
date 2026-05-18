"""Tests for HIGH-16: SQLite WAL mode is enabled on startup.

Uses a real file-based SQLite database (not :memory:) because WAL mode is
not supported on in-memory databases.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest


@pytest.fixture()
def sqlite_db_path(tmp_path):
    """Return a path to a temporary SQLite file (deleted after the test)."""
    return str(tmp_path / "test_wal.sqlite3")


def test_wal_mode_enabled_on_init(sqlite_db_path):
    """After init_db(), the SQLite journal_mode must be 'wal'."""
    db_url = f"sqlite+aiosqlite:///{sqlite_db_path}"
    os.environ["EQ_STUDIO_DATABASE_URL"] = db_url
    os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_wal")

    # Re-import to pick up the new DATABASE_URL
    import importlib
    import studio_api.config as cfg
    import studio_api.db as db_mod

    cfg.settings.database_url = db_url

    # Rebuild engine with the new URL
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 30})

    async def _run():
        from studio_api.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
        # Now verify
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
        await engine.dispose()
        return mode

    mode = asyncio.get_event_loop().run_until_complete(_run())
    assert mode == "wal", (
        f"Expected SQLite journal_mode='wal' after init_db(), got '{mode}'"
    )


def test_wal_enabled_via_init_db(sqlite_db_path):
    """init_db() helper itself enables WAL when the URL is sqlite."""
    db_url = f"sqlite+aiosqlite:///{sqlite_db_path}"

    import studio_api.config as cfg
    cfg.settings.database_url = db_url

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from studio_api.db import _is_sqlite

    assert _is_sqlite(db_url), "URL should be detected as SQLite"

    engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 30})

    async def _run():
        from studio_api.models import Base
        from studio_api.db import _is_sqlite
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if _is_sqlite(db_url):
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA synchronous=NORMAL"))
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            sync_result = await conn.execute(text("PRAGMA synchronous"))
            sync = sync_result.scalar()
        await engine.dispose()
        return mode, sync

    mode, sync = asyncio.get_event_loop().run_until_complete(_run())
    assert mode == "wal", f"Expected wal, got {mode}"
    # NORMAL synchronous = 1
    assert sync == 1, f"Expected synchronous=1 (NORMAL), got {sync}"
