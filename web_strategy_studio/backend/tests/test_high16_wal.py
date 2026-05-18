"""Tests for HIGH-16: SQLite WAL mode is enabled on startup.

Uses a real file-based SQLite database (not :memory:) because WAL mode is
not supported on in-memory databases.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture()
def patched_db(tmp_path):
    """Redirect the production db module's engine to a temporary SQLite file."""
    import studio_api.config as cfg
    import studio_api.db as db_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test_wal.sqlite3'}"
    os.environ["EQ_STUDIO_DATABASE_URL"] = db_url
    os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))

    cfg.settings.database_url = db_url
    original_engine = db_mod.engine
    original_session = db_mod.SessionLocal
    db_mod.engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 30})
    db_mod.SessionLocal = async_sessionmaker(
        db_mod.engine, class_=AsyncSession, expire_on_commit=False
    )

    yield db_mod

    db_mod.engine = original_engine
    db_mod.SessionLocal = original_session


def test_init_db_enables_wal_on_sqlite(patched_db):
    """init_db() must enable WAL + NORMAL on SQLite via PRAGMA."""
    db_mod = patched_db

    async def _run():
        # ⬇️ This is the entire point: call PRODUCTION init_db, not inline PRAGMA.
        await db_mod.init_db()
        async with db_mod.engine.connect() as conn:
            mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
            sync = (await conn.execute(text("PRAGMA synchronous"))).scalar()
        await db_mod.engine.dispose()
        return mode, sync

    mode, sync = asyncio.run(_run())
    assert mode == "wal", f"init_db must set journal_mode=wal, got {mode!r}"
    assert sync == 1, f"init_db must set synchronous=NORMAL (1), got {sync!r}"


def test_init_db_skips_pragma_for_non_sqlite(patched_db, monkeypatch):
    """init_db must not run sqlite-specific PRAGMAs on non-SQLite backends."""
    db_mod = patched_db

    # Force _is_sqlite to return False to simulate a Postgres-like backend
    monkeypatch.setattr(db_mod, "_is_sqlite", lambda url: False)

    async def _run():
        await db_mod.init_db()
        async with db_mod.engine.connect() as conn:
            mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        await db_mod.engine.dispose()
        return mode

    mode = asyncio.run(_run())
    # Without PRAGMA, SQLite defaults to "delete" journal mode
    assert mode != "wal", f"init_db must NOT set WAL when _is_sqlite returns False, got {mode!r}"
