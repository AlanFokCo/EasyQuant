"""
Tests for HIGH-15: auth-gated report routes.

Verifies that:
- The old unauthenticated /static/reports/ mount is gone (returns 404).
- GET /api/v1/reports/{run_id}/report.html and report.json require auth.
- A different user cannot access another user's report (404).
- The owner receives the file (200) or a legitimate 404 when not yet generated.
- CSP headers are set on authenticated responses.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault(
    "EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_report_access_ctrl_test"
)


@pytest.fixture(scope="module")
def client():
    # test_auth.py modifies db_mod.engine to a temp file-based DB.
    # Reset to a fresh in-memory DB so our tests are isolated from that.
    import studio_api.db as db_mod
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    new_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    db_mod.engine = new_engine
    db_mod.SessionLocal = async_sessionmaker(
        new_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Reset the in-process rate limiter so previous test modules' run creations
    # don't exhaust our limit and cause 429 responses.
    from studio_api.run_queue import rate_limiter
    rate_limiter._hits.clear()

    from fastapi.testclient import TestClient
    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _register_or_login(client, username: str, password: str) -> str:
    """Register a user (or login if already exists) and return the JWT token."""
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


@pytest.fixture(scope="module")
def token_user_a(client):
    return _register_or_login(client, "test_high15_user_a", "pass_a_1234")


@pytest.fixture(scope="module")
def token_user_b(client):
    return _register_or_login(client, "test_high15_user_b", "pass_b_5678")


@pytest.fixture(scope="module")
def run_id_user_a(client, token_user_a):
    """Create a strategy + run owned by user A and return the run_id."""
    headers = {"Authorization": f"Bearer {token_user_a}"}

    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "high15_access_ctrl_strat",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    r = client.post(
        "/api/v1/runs",
        json={
            "strategy_id": sid,
            "params": {"start_date": "2024-01-01", "end_date": "2024-01-05"},
        },
        headers=headers,
    )
    assert r.status_code in (200, 201, 202)
    run_data = r.json()
    return run_data.get("run_id") or run_data["id"]


# ---------------------------------------------------------------------------
# HIGH-15: Static mount must be removed
# ---------------------------------------------------------------------------


def test_high15_static_reports_mount_is_gone(client):
    """/static/reports/ must be inaccessible even when the file exists on disk."""
    # Plant a real file so a static mount would serve 200 if still present.
    from studio_api.app import reports_root

    probe_dir = reports_root / "probe_run_id"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "report.html").write_text("<html>probe</html>")

    r = client.get("/static/reports/probe_run_id/report.html")
    assert r.status_code == 404, (
        "The /static/reports/ mount should be removed (unauthenticated access "
        f"must not be possible). Got {r.status_code} — is the mount still active?"
    )


def test_high15_static_reports_json_is_gone(client):
    """/static/reports/ JSON must also be inaccessible even when the file exists."""
    from studio_api.app import reports_root

    probe_dir = reports_root / "probe_run_id"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "report.json").write_text('{"probe": true}')

    r = client.get("/static/reports/probe_run_id/report.json")
    assert r.status_code == 404, (
        "The /static/reports/ mount should be removed. "
        f"Got {r.status_code} instead of 404."
    )


# ---------------------------------------------------------------------------
# HIGH-15: Authenticated HTML endpoint
# ---------------------------------------------------------------------------


def test_high15_html_no_token_returns_401(client):
    """/api/v1/reports/{run_id}/report.html without token returns 401."""
    r = client.get("/api/v1/reports/any_run_id/report.html")
    assert r.status_code == 401


def test_high15_html_invalid_token_returns_401(client):
    """/api/v1/reports/{run_id}/report.html with invalid token returns 401."""
    r = client.get(
        "/api/v1/reports/any_run_id/report.html",
        headers={"Authorization": "Bearer this_is_not_a_valid_token"},
    )
    assert r.status_code == 401


def test_high15_html_other_user_returns_404(client, run_id_user_a, token_user_b):
    """User B cannot read user A's report — must get 404 (not 200 or 403)."""
    r = client.get(
        f"/api/v1/reports/{run_id_user_a}/report.html",
        headers={"Authorization": f"Bearer {token_user_b}"},
    )
    assert r.status_code == 404


def test_high15_html_owner_gets_200_or_404_not_401(client, run_id_user_a, token_user_a):
    """Owner can access report — response is 200 (file exists) or 404 (not yet generated), never 401."""
    r = client.get(
        f"/api/v1/reports/{run_id_user_a}/report.html",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert r.status_code in (200, 404), (
        f"Owner should get 200 or 404, not {r.status_code}"
    )


def test_high15_html_owner_200_has_csp(client, token_user_a):
    """When report.html exists, the response must include a CSP header."""
    # Create a fresh strategy and run within this test to avoid DB isolation issues
    headers = {"Authorization": f"Bearer {token_user_a}"}

    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "high15_csp_html_strat",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    r = client.post(
        "/api/v1/runs",
        json={
            "strategy_id": sid,
            "params": {"start_date": "2024-01-01", "end_date": "2024-01-05"},
        },
        headers=headers,
    )
    assert r.status_code in (200, 201, 202)
    run_id = r.json().get("run_id") or r.json()["id"]

    # Plant a dummy report file so the endpoint returns 200
    from studio_api.app import reports_root

    report_dir = reports_root / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.html").write_text("<html><body>test</body></html>")

    r = client.get(
        f"/api/v1/reports/{run_id}/report.html",
        headers=headers,
    )
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp, "200 response must include Content-Security-Policy header"
    assert "default-src" in csp


# ---------------------------------------------------------------------------
# HIGH-15: Authenticated JSON endpoint
# ---------------------------------------------------------------------------


def test_high15_json_no_token_returns_401(client):
    """/api/v1/reports/{run_id}/report.json without token returns 401."""
    r = client.get("/api/v1/reports/any_run_id/report.json")
    assert r.status_code == 401


def test_high15_json_invalid_token_returns_401(client):
    """/api/v1/reports/{run_id}/report.json with invalid token returns 401."""
    r = client.get(
        "/api/v1/reports/any_run_id/report.json",
        headers={"Authorization": "Bearer bad_token_here"},
    )
    assert r.status_code == 401


def test_high15_json_other_user_returns_404(client, run_id_user_a, token_user_b):
    """User B cannot read user A's report.json — must get 404."""
    r = client.get(
        f"/api/v1/reports/{run_id_user_a}/report.json",
        headers={"Authorization": f"Bearer {token_user_b}"},
    )
    assert r.status_code == 404


def test_high15_json_owner_gets_200_or_404_not_401(client, run_id_user_a, token_user_a):
    """Owner can access report.json — response is 200 or 404, never 401."""
    r = client.get(
        f"/api/v1/reports/{run_id_user_a}/report.json",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert r.status_code in (200, 404)


def test_high15_json_owner_200_has_csp(client, token_user_a):
    """When report.json exists, the response must include a CSP header."""
    headers = {"Authorization": f"Bearer {token_user_a}"}

    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "high15_csp_json_strat",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    r = client.post(
        "/api/v1/runs",
        json={
            "strategy_id": sid,
            "params": {"start_date": "2024-01-01", "end_date": "2024-01-05"},
        },
        headers=headers,
    )
    assert r.status_code in (200, 201, 202)
    run_id = r.json().get("run_id") or r.json()["id"]

    from studio_api.app import reports_root

    report_dir = reports_root / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text('{"summary": {}}')

    r = client.get(
        f"/api/v1/reports/{run_id}/report.json",
        headers=headers,
    )
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp, "200 response must include Content-Security-Policy header"
    assert "default-src" in csp


# ---------------------------------------------------------------------------
# HIGH-15: Backend API returns /api/v1/reports/ URLs, not /static/reports/
# ---------------------------------------------------------------------------


def test_high15_artifacts_response_uses_api_path(client, run_id_user_a, token_user_a):
    """After a succeeded run, the artifacts URLs must use /api/v1/reports/, not /static/reports/."""
    r = client.get(
        f"/api/v1/runs/{run_id_user_a}",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert r.status_code == 200
    data = r.json()
    html_url = data.get("html_report_url") or ""
    json_url = data.get("json_report_url") or ""

    if html_url:
        assert "/api/v1/reports/" in html_url, (
            f"html_report_url should use /api/v1/reports/, got: {html_url}"
        )
        assert "/static/reports/" not in html_url

    if json_url:
        assert "/api/v1/reports/" in json_url, (
            f"json_report_url should use /api/v1/reports/, got: {json_url}"
        )
        assert "/static/reports/" not in json_url
