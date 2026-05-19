"""Tests for per-IP rate limiting on POST /runs (B18)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_ratelimit_test")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """Register and login to get an auth token."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ratelimit_user",
            "password": "testpass",
        },
    )
    if reg.status_code == 409:
        # Already registered, login instead
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "ratelimit_user",
                "password": "testpass",
            },
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


@pytest.fixture(scope="module")
def strategy_id(client, auth_token):
    """Create a strategy to use for run requests."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    assert tpl.status_code == 200
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "rate-limit-strategy",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def test_rate_limiter_unit():
    """Unit test for the _RateLimiter class."""
    from studio_api.run_queue import _RateLimiter

    rl = _RateLimiter(limit=3, window_sec=60)

    # First 3 allowed
    for i in range(3):
        allowed, remaining = rl.is_allowed("1.2.3.4")
        assert allowed, f"Request {i+1} should be allowed"

    # 4th denied
    allowed, remaining = rl.is_allowed("1.2.3.4")
    assert not allowed
    assert remaining == 0


def test_rate_limiter_window_expiry():
    """Hits outside the window are not counted."""
    import time

    from studio_api.run_queue import _RateLimiter

    rl = _RateLimiter(limit=2, window_sec=1)  # 1-second window

    rl.is_allowed("5.5.5.5")
    rl.is_allowed("5.5.5.5")
    # Should be rate-limited now
    allowed, _ = rl.is_allowed("5.5.5.5")
    assert not allowed

    # Wait for window to expire
    time.sleep(1.05)

    # Window has reset — first request allowed again
    allowed, _ = rl.is_allowed("5.5.5.5")
    assert allowed


def test_429_response_has_correct_envelope(client, strategy_id, auth_token):
    """When rate-limited, the response must follow the error envelope format."""
    from studio_api.run_queue import rate_limiter

    headers = {"Authorization": f"Bearer {auth_token}"}

    # Directly exhaust the rate limit for testclient's IP
    for _ in range(100):
        rate_limiter.is_allowed("testclient")

    run_body = {
        "strategy_id": strategy_id,
        "params": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    }
    resp = client.post("/api/v1/runs", json=run_body, headers=headers)
    assert resp.status_code == 429
    body = resp.json()
    # FastAPI wraps HTTPException detail under "detail" key
    detail = body.get("detail") or body
    err = detail.get("error") if isinstance(detail, dict) else None
    assert err is not None, f"Expected error envelope, got: {body}"
    assert err["code"] == "RATE_LIMITED"
    assert "message" in err

    # Reset for other tests
    rate_limiter._hits.clear()


def test_different_ips_have_independent_limits():
    """Each IP has its own independent bucket."""
    from studio_api.run_queue import _RateLimiter

    rl = _RateLimiter(limit=1, window_sec=60)

    allowed_a, _ = rl.is_allowed("10.0.0.1")
    assert allowed_a

    allowed_a2, _ = rl.is_allowed("10.0.0.1")
    assert not allowed_a2  # exhausted

    allowed_b, _ = rl.is_allowed("10.0.0.2")
    assert allowed_b  # fresh bucket
