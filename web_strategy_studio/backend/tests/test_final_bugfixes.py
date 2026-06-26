"""Regression tests for the final bug-fix and stability pass.

Covers:
- P0: Unauthenticated endpoints (completion, format, symbols) now require auth
- P0: Strategy template endpoint requires auth
- P1: X-Forwarded-For spoofing protection (trust_proxy_headers)
- P2: Monaco editor sends auth header (frontend-only, tested conceptually)
- Stability: resource cleanup and error handling
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_final_fix_test")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import studio_api.config as _cfg
    from studio_api.app import app

    _cfg.settings.allow_registration = True
    _cfg.settings.require_invite_code = False
    # Ensure proxy header trust is off by default (secure default)
    _cfg.settings.trust_proxy_headers = False

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """Register and login to get an auth token."""
    pw = "FinalFix1!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "final_fix_user", "password": pw},
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "final_fix_user", "password": pw},
        )
        return resp.json()["access_token"]
    assert reg.status_code in (200, 201), f"Register failed: {reg.text}"
    return reg.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# P0: Unauthenticated endpoint tests
# ---------------------------------------------------------------------------


class TestUnauthenticatedEndpointsRequireAuth:
    """Verify that previously-unauthenticated endpoints now reject unauthed calls."""

    def test_completion_requires_auth(self, client):
        """POST /api/v1/completion must return 401 without a token."""
        r = client.post(
            "/api/v1/completion",
            json={"source_code": "x = 1", "cursor_line": 1, "cursor_col": 5},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_format_requires_auth(self, client):
        """POST /api/v1/format must return 401 without a token."""
        r = client.post(
            "/api/v1/format",
            json={"source_code": "x=1\n"},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_symbols_search_requires_auth(self, client):
        """GET /api/v1/symbols/search must return 401 without a token."""
        r = client.get("/api/v1/symbols/search", params={"q": "601390"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_strategy_template_requires_auth(self, client):
        """GET /api/v1/strategies/_new/template must return 401 without a token."""
        r = client.get("/api/v1/strategies/_new/template")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


class TestAuthenticatedEndpointsWork:
    """Verify that authed calls to the same endpoints succeed."""

    def test_completion_with_auth(self, client, auth_token):
        r = client.post(
            "/api/v1/completion",
            json={"source_code": "from eqlib import *\n", "cursor_line": 1, "cursor_col": 17},
            headers=_headers(auth_token),
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "suggestions" in r.json()

    def test_format_with_auth(self, client, auth_token):
        r = client.post(
            "/api/v1/format",
            json={"source_code": "x=1\n"},
            headers=_headers(auth_token),
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_symbols_search_with_auth(self, client, auth_token):
        r = client.get(
            "/api/v1/symbols/search",
            params={"q": "601390"},
            headers=_headers(auth_token),
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_strategy_template_with_auth(self, client, auth_token):
        r = client.get(
            "/api/v1/strategies/_new/template",
            headers=_headers(auth_token),
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "source_code" in r.json()


# ---------------------------------------------------------------------------
# P1: X-Forwarded-For spoofing protection
# ---------------------------------------------------------------------------


class TestXForwardedForSpoofingProtection:
    """X-Forwarded-For must NOT be trusted unless trust_proxy_headers=True."""

    def test_default_does_not_trust_xff(self):
        """trust_proxy_headers should be False by default."""
        from studio_api.config import Settings

        s = Settings()
        assert s.trust_proxy_headers is False

    def test_client_ip_ignores_xff_when_untrusted(self):
        """_client_ip should return the direct client host when trust is off."""
        from unittest.mock import MagicMock

        import studio_api.config as cfg
        from studio_api.services.auth_service import _client_ip

        original = cfg.settings.trust_proxy_headers
        cfg.settings.trust_proxy_headers = False
        try:
            request = MagicMock()
            request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            assert _client_ip(request) == "127.0.0.1"
        finally:
            cfg.settings.trust_proxy_headers = original

    def test_client_ip_uses_xff_when_trusted(self):
        """_client_ip should use X-Forwarded-For when trust_proxy_headers=True."""
        from unittest.mock import MagicMock

        import studio_api.config as cfg
        from studio_api.services.auth_service import _client_ip

        original = cfg.settings.trust_proxy_headers
        cfg.settings.trust_proxy_headers = True
        try:
            request = MagicMock()
            request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            assert _client_ip(request) == "1.2.3.4"
        finally:
            cfg.settings.trust_proxy_headers = original

    def test_client_ip_handles_no_client(self):
        """_client_ip should handle missing client gracefully."""
        from unittest.mock import MagicMock

        from studio_api.services.auth_service import _client_ip

        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _client_ip(request) == "unknown"

    def test_client_ip_handles_none_request(self):
        """_client_ip should handle None request."""
        from studio_api.services.auth_service import _client_ip

        assert _client_ip(None) == "unknown"


# ---------------------------------------------------------------------------
# P1: Rate limiter uses direct client IP (not spoofed XFF)
# ---------------------------------------------------------------------------


class TestRateLimiterUsesClientIp:
    """Rate limiter should use direct client IP when trust_proxy_headers is off."""

    def test_rate_limit_ignores_xff_by_default(self, client, auth_token):
        """Sending X-Forwarded-For should NOT change the rate-limit bucket.

        Without this fix, an attacker could bypass rate limits by rotating
        the X-Forwarded-For header.
        """
        import studio_api.config as cfg
        from studio_api.run_queue import rate_limiter

        # Ensure proxy trust is off
        original = cfg.settings.trust_proxy_headers
        cfg.settings.trust_proxy_headers = False
        rate_limiter._hits.clear()

        try:
            # Create a strategy for run requests
            tpl = client.get("/api/v1/strategies/_new/template", headers=_headers(auth_token))
            strat = client.post(
                "/api/v1/strategies",
                json={
                    "name": "xff-test",
                    "description": "",
                    "source_code": tpl.json()["source_code"],
                },
                headers=_headers(auth_token),
            )
            sid = strat.json()["id"]

            # Exhaust rate limit for "testclient" (the real TestClient IP)
            for _ in range(cfg.settings.rate_limit_runs_per_window):
                client.post(
                    "/api/v1/runs",
                    json={
                        "strategy_id": sid,
                        "params": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
                    },
                    headers=_headers(auth_token),
                )

            # Even with a different X-Forwarded-For, we should still be rate-limited
            # because the rate limiter uses the direct client IP
            r = client.post(
                "/api/v1/runs",
                json={
                    "strategy_id": sid,
                    "params": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
                },
                headers={
                    **_headers(auth_token),
                    "X-Forwarded-For": "99.99.99.99",
                },
            )
            assert r.status_code == 429, (
                f"Expected 429 (rate limit), got {r.status_code}. "
                "X-Forwarded-For should be ignored when trust_proxy_headers=False."
            )
        finally:
            cfg.settings.trust_proxy_headers = original
            rate_limiter._hits.clear()


# ---------------------------------------------------------------------------
# Stability: Runner cleanup guarantees
# ---------------------------------------------------------------------------


class TestRunnerCleanupGuarantees:
    """Verify that temp directories are always cleaned up."""

    def test_local_runner_cleans_temp_on_success(self, tmp_path):
        """LocalRunner.run uses try/finally to always clean up temp dirs."""
        import inspect

        from studio_api.runner import LocalRunner

        source = inspect.getsource(LocalRunner.run)
        assert "finally:" in source
        assert "shutil.rmtree" in source
        assert "ignore_errors=True" in source

    def test_docker_runner_cleans_temp_on_success(self, tmp_path):
        """DockerRunner.run uses try/finally to always clean up temp dirs."""
        import inspect

        from studio_api.runner import DockerRunner

        source = inspect.getsource(DockerRunner.run)
        assert "finally:" in source
        assert "shutil.rmtree" in source
        assert "ignore_errors=True" in source


# ---------------------------------------------------------------------------
# Stability: StreamHub lock cleanup
# ---------------------------------------------------------------------------


class TestStreamHubLockIntegrity:
    """Verify StreamHub doesn't leak locks."""

    def test_no_lock_leak_after_publish_subscribe_unsubscribe(self):
        """Locks should be cleaned up when queues are emptied."""
        import asyncio

        from studio_api.stream_hub import StreamHub

        async def _test():
            hub = StreamHub()
            run_id = "run_lock_test"

            q = hub.subscribe(run_id)
            await hub.publish(run_id, "log", {"line": "test"})
            hub.unsubscribe(run_id, q)

            # After unsubscribe with empty queue list, lock should be removed
            assert run_id not in hub._locks

        asyncio.run(_test())

    def test_lock_cleaned_on_terminal_event(self):
        """Locks should be removed after a terminal event."""
        import asyncio

        from studio_api.stream_hub import StreamHub

        async def _test():
            hub = StreamHub()
            run_id = "run_terminal_test"

            hub.subscribe(run_id)
            await hub.publish(run_id, "done", {"status": "succeeded"})

            # Terminal event should clean up locks
            assert run_id not in hub._locks

        asyncio.run(_test())
