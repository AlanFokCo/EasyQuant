"""Tests for StreamHub ring buffer and Last-Event-ID replay (B6/B13)."""

from __future__ import annotations

import asyncio

import pytest

pytest_plugins = ("anyio",)


@pytest.fixture
def hub():
    """Fresh StreamHub for each test, with a 5-second buffer TTL."""
    from studio_api.stream_hub import StreamHub
    return StreamHub(max_queued=100, buffer_ttl_sec=5)


# ── Basic ring buffer ────────────────────────────────────────────────────────

def test_buffer_created_on_publish(hub):
    asyncio.get_event_loop().run_until_complete(_test_buffer_created(hub))


async def _test_buffer_created(hub):
    await hub.publish("run_1", "progress", {"progress": 0.1})
    buf = hub.get_buffer("run_1")
    assert buf is not None
    assert len(buf.events) == 1
    assert buf.events[0]["event"] == "progress"


def test_ring_buffer_max_size(hub):
    asyncio.get_event_loop().run_until_complete(_test_ring_size(hub))


async def _test_ring_size(hub):
    from studio_api.stream_hub import _RING_SIZE
    for i in range(_RING_SIZE + 10):
        await hub.publish("run_r", "log", {"line": f"line {i}"})
    buf = hub.get_buffer("run_r")
    assert buf is not None
    assert len(buf.events) == _RING_SIZE


def test_terminal_event_sets_expires(hub):
    asyncio.get_event_loop().run_until_complete(_test_terminal(hub))


async def _test_terminal(hub):
    await hub.publish("run_t", "done", {"status": "succeeded"})
    buf = hub.get_buffer("run_t")
    assert buf is not None
    assert buf.terminal is not None
    assert buf.terminal["event"] == "done"
    assert buf._expires_at is not None


def test_buffer_expiry(hub):
    asyncio.get_event_loop().run_until_complete(_test_expiry(hub))


async def _test_expiry(hub):
    import time
    from studio_api.stream_hub import StreamHub
    short_hub = StreamHub(max_queued=100, buffer_ttl_sec=0)  # expires immediately
    await short_hub.publish("run_e", "done", {"status": "succeeded"})
    # Manually set expires_at to the past
    buf = short_hub._buffers["run_e"]
    buf._expires_at = time.monotonic() - 1  # expired 1 second ago
    assert short_hub.get_buffer("run_e") is None


# ── missed_since replay ──────────────────────────────────────────────────────

def test_missed_since_returns_correct_events(hub):
    asyncio.get_event_loop().run_until_complete(_test_missed_since(hub))


async def _test_missed_since(hub):
    for i in range(5):
        await hub.publish("run_m", "log", {"n": i})
    await hub.publish("run_m", "done", {"status": "succeeded"})

    buf = hub.get_buffer("run_m")
    assert buf is not None
    all_events = buf.missed_since(0)
    assert len(all_events) == 6  # 5 log + 1 done

    # Only events after id=3
    missed = buf.missed_since(3)
    assert all(e["id"] > 3 for e in missed)
    assert len(missed) == 3  # ids 4, 5, 6


def test_missed_since_empty_if_up_to_date(hub):
    asyncio.get_event_loop().run_until_complete(_test_no_missed(hub))


async def _test_no_missed(hub):
    await hub.publish("run_n", "done", {"status": "succeeded"})
    buf = hub.get_buffer("run_n")
    last_id = buf.events[-1]["id"]
    assert buf.missed_since(last_id) == []


# ── SSE endpoint: terminal run → immediate done ──────────────────────────────

def test_stream_terminal_run_immediate_done():
    """GET /runs/{id}/stream on a terminal run returns done without waiting."""
    import os
    os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_stream_test")

    from fastapi.testclient import TestClient
    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=True) as client:
        # Create a strategy + run
        tpl = client.get("/api/v1/strategies/_new/template")
        strat = client.post(
            "/api/v1/strategies",
            json={"name": "stream-test", "description": "", "source_code": tpl.json()["source_code"]},
        )
        assert strat.status_code in (200, 201)

        # We cannot actually run a full backtest in unit tests, but we can
        # verify the SSE endpoint at least responds. For a terminal run that
        # was never started (no buffer), it should synthesise a done event
        # immediately when the DB says failed.
        # We simulate this by directly creating a Run record in the DB.
        import asyncio
        from datetime import datetime, timezone
        from studio_api.db import SessionLocal
        from studio_api.models import Run

        run_id = "run_test_stream_terminal"

        async def _insert_terminal_run():
            async with SessionLocal() as session:
                run = Run(
                    id=run_id,
                    strategy_id=strat.json()["id"],
                    strategy_version=1,
                    status="failed",
                    progress=0.0,
                    params={},
                    error_code="TEST",
                    error_message="test failure",
                    finished_at=datetime.now(timezone.utc),
                )
                session.add(run)
                await session.commit()

        asyncio.get_event_loop().run_until_complete(_insert_terminal_run())

        # Hitting the stream endpoint for a terminal run with no buffer
        # must return a synthesised done event and close.
        with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
        assert "done" in body


# ── evict_expired ────────────────────────────────────────────────────────────

def test_evict_expired_removes_stale_buffer(hub):
    asyncio.get_event_loop().run_until_complete(_test_evict(hub))


async def _test_evict(hub):
    import time
    await hub.publish("run_ev", "done", {"status": "succeeded"})
    buf = hub._buffers["run_ev"]
    buf._expires_at = time.monotonic() - 1  # force expired
    hub.evict_expired()
    assert "run_ev" not in hub._buffers
