"""Tests for asyncio run queue, concurrency cap, and queue endpoint (B17/B18)."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_queue_test")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── queue module unit tests ───────────────────────────────────────────────────


def test_enqueue_adds_to_pending():
    from studio_api.run_queue import _pending, enqueue, pending_run_ids

    _pending.clear()

    async def _run():
        await enqueue("run_unit_1", lambda: asyncio.sleep(0))
        assert "run_unit_1" in pending_run_ids()

    asyncio.get_event_loop().run_until_complete(_run())
    _pending.clear()


def test_queue_position():
    from studio_api.run_queue import _pending, enqueue, queue_position

    _pending.clear()

    async def _run():
        await enqueue("run_pos_a", lambda: asyncio.sleep(0))
        await enqueue("run_pos_b", lambda: asyncio.sleep(0))
        assert queue_position("run_pos_a") == 1
        assert queue_position("run_pos_b") == 2
        assert queue_position("nonexistent") is None

    asyncio.get_event_loop().run_until_complete(_run())
    _pending.clear()


def test_rate_limiter_allows_under_limit():
    from studio_api.run_queue import _RateLimiter

    rl = _RateLimiter(limit=5, window_sec=60)
    for i in range(5):
        allowed, remaining = rl.is_allowed("test_ip")
        assert allowed, f"Request {i+1} should be allowed"
    # 6th request should be denied
    allowed, _ = rl.is_allowed("test_ip")
    assert not allowed


def test_rate_limiter_different_ips_independent():
    from studio_api.run_queue import _RateLimiter

    rl = _RateLimiter(limit=2, window_sec=60)
    rl.is_allowed("ip_a")
    rl.is_allowed("ip_a")
    # ip_a is now exhausted
    allowed_a, _ = rl.is_allowed("ip_a")
    assert not allowed_a
    # ip_b is a fresh counter
    allowed_b, _ = rl.is_allowed("ip_b")
    assert allowed_b


# ── GET /api/v1/queue endpoint ────────────────────────────────────────────────


def test_queue_endpoint_returns_structure(client):
    r = client.get("/api/v1/queue")
    assert r.status_code == 200
    body = r.json()
    assert "queue_length" in body
    assert "active_count" in body
    assert "max_concurrent" in body
    assert "queued_runs" in body
    assert isinstance(body["queued_runs"], list)


def test_queue_max_concurrent_from_settings(client):
    from studio_api.config import settings

    r = client.get("/api/v1/queue")
    assert r.json()["max_concurrent"] == settings.max_concurrent_runs


# ── Rate limit response ───────────────────────────────────────────────────────


def test_rate_limit_endpoint_returns_429(client):
    """Exhaust the per-IP rate limit and verify 429 is returned."""
    from studio_api.config import settings
    from studio_api.run_queue import rate_limiter

    # Create a strategy first
    tpl = client.get("/api/v1/strategies/_new/template")
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "rate-limit-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    _run_body = {
        "strategy_id": sid,
        "params": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    }

    # Exhaust the rate limit for testclient's IP
    test_ip = "testclient"
    rate_limiter._hits[test_ip] = []  # clear any residual hits

    # Fill up the bucket
    for _ in range(settings.rate_limit_runs_per_window):
        allowed, _ = rate_limiter.is_allowed(test_ip)
        assert allowed

    # Next call from rate_limiter should be denied
    allowed, _ = rate_limiter.is_allowed(test_ip)
    assert not allowed
