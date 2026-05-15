"""Tests for orphan run cleanup on startup (B17)."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_orphan_test")


@pytest.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_orphan_runs_marked_failed(event_loop):
    """Runs in running/queued state at startup must be marked failed: SERVER_RESTART."""

    async def _run():
        from studio_api.db import SessionLocal, init_db
        from studio_api.models import Run
        from studio_api.run_queue import mark_orphan_runs_failed

        await init_db()

        # Insert orphan runs directly
        async with SessionLocal() as session:
            strat_id = "strat_orphan_test"
            for run_id, status in [
                ("run_orphan_running", "running"),
                ("run_orphan_queued", "queued"),
                ("run_orphan_done", "succeeded"),  # should NOT be touched
            ]:
                run = Run(
                    id=run_id,
                    strategy_id=strat_id,
                    strategy_version=1,
                    status=status,
                    progress=0.5 if status == "running" else 0.0,
                    params={},
                )
                session.add(run)
            await session.commit()

        # Run orphan cleanup
        await mark_orphan_runs_failed()

        # Verify results
        async with SessionLocal() as session:
            for run_id, expected_status in [
                ("run_orphan_running", "failed"),
                ("run_orphan_queued", "failed"),
                ("run_orphan_done", "succeeded"),  # unchanged
            ]:
                run = await session.get(Run, run_id)
                assert run is not None, f"Run {run_id} not found"
                assert (
                    run.status == expected_status
                ), f"Run {run_id}: expected {expected_status}, got {run.status}"
                if expected_status == "failed":
                    assert run.error_code == "SERVER_RESTART"
                    assert run.finished_at is not None

    event_loop.run_until_complete(_run())


def test_orphan_cleanup_idempotent(event_loop):
    """Running orphan cleanup twice must not raise or double-modify runs."""

    async def _run():
        from studio_api.db import SessionLocal, init_db
        from studio_api.models import Run
        from studio_api.run_queue import mark_orphan_runs_failed

        await init_db()

        async with SessionLocal() as session:
            run = Run(
                id="run_orphan_idem",
                strategy_id="strat_idem",
                strategy_version=1,
                status="running",
                progress=0.3,
                params={},
            )
            session.add(run)
            await session.commit()

        await mark_orphan_runs_failed()
        # Call again — should be a no-op (no more running/queued runs)
        await mark_orphan_runs_failed()

        async with SessionLocal() as session:
            run = await session.get(Run, "run_orphan_idem")
            assert run.status == "failed"

    event_loop.run_until_complete(_run())


def test_no_orphans_does_not_raise(event_loop):
    """mark_orphan_runs_failed with no orphans must not raise."""

    async def _run():
        from studio_api.db import init_db
        from studio_api.run_queue import mark_orphan_runs_failed

        await init_db()
        # Should complete without error even when no orphans exist
        await mark_orphan_runs_failed()

    event_loop.run_until_complete(_run())
