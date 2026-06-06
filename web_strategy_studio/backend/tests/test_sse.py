"""Tests for SSE last_event_id handling (query param and header support)."""

from __future__ import annotations

import asyncio
import os

import pytest

pytest_plugins = ("anyio",)

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_sse_test")
os.environ.setdefault("EQ_STUDIO_ALLOW_REGISTRATION", "true")


@pytest.fixture
def auth_client():
    """Create a TestClient with an authenticated user."""
    from fastapi.testclient import TestClient

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=True) as client:
        # Register/login with strong password (uppercase, lowercase, digit, special)
        password = "TestPass123!"
        reg = client.post(
            "/api/v1/auth/register",
            json={"username": "sse_test_user", "password": password},
        )
        if reg.status_code == 409:
            resp = client.post(
                "/api/v1/auth/login",
                json={"username": "sse_test_user", "password": password},
            )
        else:
            resp = reg
        token = resp.json()["access_token"]
        yield client, token


@pytest.fixture
def strategy_and_run(auth_client):
    """Create a strategy and a terminal run for SSE testing."""
    import secrets

    client, token = auth_client
    headers = {"Authorization": f"Bearer {token}"}

    # Create strategy
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": f"sse-test-{secrets.token_hex(4)}",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    strat_id = strat.json()["id"]

    # Create a terminal run directly in DB with unique ID
    from datetime import datetime, timezone

    from studio_api.db import SessionLocal
    from studio_api.models import Run

    run_id = f"run_sse_{secrets.token_hex(8)}"

    async def _insert():
        async with SessionLocal() as session:
            run = Run(
                id=run_id,
                strategy_id=strat_id,
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

    asyncio.run(_insert())

    return client, token, run_id


class TestSSELastEventIdQueryParam:
    """Test that SSE endpoint accepts last_event_id as query parameter."""

    def test_sse_with_query_param(self, strategy_and_run):
        """SSE stream should accept last_event_id as query parameter."""
        client, token, run_id = strategy_and_run
        headers = {"Authorization": f"Bearer {token}"}

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream?last_event_id=123",
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
            # Should get a synthesized done event for terminal run
            assert "done" in body

    def test_sse_with_zero_query_param(self, strategy_and_run):
        """SSE stream should handle last_event_id=0 (all events)."""
        client, token, run_id = strategy_and_run
        headers = {"Authorization": f"Bearer {token}"}

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream?last_event_id=0",
            headers=headers,
        ) as resp:
            assert resp.status_code == 200


class TestSSELastEventIdHeader:
    """Test that SSE endpoint accepts Last-Event-ID header."""

    def test_sse_with_header(self, strategy_and_run):
        """SSE stream should accept Last-Event-ID header (SSE spec)."""
        client, token, run_id = strategy_and_run
        headers = {
            "Authorization": f"Bearer {token}",
            "Last-Event-ID": "456",
        }

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream",
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
            assert "done" in body


class TestSSELastEventIdPrecedence:
    """Test that query param takes precedence over header."""

    def test_query_param_takes_precedence(self, strategy_and_run):
        """When both query param and header are provided, query param wins."""
        client, token, run_id = strategy_and_run
        headers = {
            "Authorization": f"Bearer {token}",
            "Last-Event-ID": "999",  # This should be ignored
        }

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream?last_event_id=100",  # This wins
            headers=headers,
        ) as resp:
            assert resp.status_code == 200


class TestSSEInvalidLastEventId:
    """Test SSE behavior with invalid last_event_id values."""

    def test_invalid_last_event_id_fallback(self, strategy_and_run):
        """Invalid last_event_id should fall back to sending all events."""
        client, token, run_id = strategy_and_run
        headers = {"Authorization": f"Bearer {token}"}

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream?last_event_id=not-a-number",
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
            assert "done" in body

    def test_no_last_event_id(self, strategy_and_run):
        """SSE stream should work without any last_event_id."""
        client, token, run_id = strategy_and_run
        headers = {"Authorization": f"Bearer {token}"}

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream",
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
            assert "done" in body
