"""Integration tests for the reports router.

Verifies auth-gating, ownership checks, comparison, export, and listing.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault(
    "EQ_STUDIO_ARTIFACT_DIR",
    os.path.join(tempfile.gettempdir(), "eq_studio_reports_test"),
)


@pytest.fixture(scope="module")
def client():
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    import studio_api.db as db_mod

    new_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    db_mod.engine = new_engine
    db_mod.SessionLocal = async_sessionmaker(
        new_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    import asyncio

    asyncio.run(db_mod.init_db())

    # Enable registration for tests
    import studio_api.config as cfg

    cfg.settings.allow_registration = True

    from studio_api.run_queue import rate_limiter

    rate_limiter._hits.clear()

    from fastapi.testclient import TestClient

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _register_or_login(client, username: str, password: str) -> str:
    # Clear rate limiter to avoid 429 during test setup
    from studio_api.run_queue import rate_limiter

    rate_limiter._hits.clear()

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
    assert reg.status_code in (200, 201), f"register failed: {reg.status_code} {reg.text}"
    return reg.json()["access_token"]


@pytest.fixture(scope="module")
def token_a(client):
    return _register_or_login(client, "rpt_user_a", "Rpt_pass_a_1234!")


@pytest.fixture(scope="module")
def run_id_a(client, token_a):
    """Create a strategy + run owned by user A."""
    headers = {"Authorization": f"Bearer {token_a}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "rpt_test_strat_a",
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
    return r.json().get("run_id") or r.json()["id"]


def _plant_report_files(run_id: str, data: dict | None = None):
    """Write report.html and report.json into the artifact dir."""
    from studio_api.app import reports_root

    report_dir = reports_root / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.html").write_text("<html><body>report</body></html>")
    (report_dir / "report.json").write_text(
        json.dumps(data or {"metrics": {"total_return": 0.15, "sharpe_ratio": 1.2}})
    )


# ------------------------------------------------------------------
# Auth gating
# ------------------------------------------------------------------


class TestAuthGating:
    def test_html_no_token_401(self, client):
        r = client.get("/api/v1/reports/any-run/report.html")
        assert r.status_code == 401

    def test_json_no_token_401(self, client):
        r = client.get("/api/v1/reports/any-run/report.json")
        assert r.status_code == 401

    def test_metrics_no_token_401(self, client):
        r = client.get("/api/v1/reports/any-run/metrics")
        assert r.status_code == 401

    def test_compare_no_token_401(self, client):
        r = client.post("/api/v1/reports/compare", json={"run_ids": ["a", "b"]})
        assert r.status_code == 401

    def test_export_no_token_401(self, client):
        r = client.get("/api/v1/reports/any-run/export/html")
        assert r.status_code == 401

    def test_list_no_token_401(self, client):
        r = client.get("/api/v1/reports")
        assert r.status_code == 401


# ------------------------------------------------------------------
# Ownership checks
# ------------------------------------------------------------------


class TestOwnership:
    def test_nonexistent_run_returns_404_html(self, client, token_a):
        """Accessing a non-existent run returns 404 (not 403)."""
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            "/api/v1/reports/nonexistent-run-id/report.html",
            headers=headers,
        )
        assert r.status_code == 404

    def test_nonexistent_run_returns_404_json(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            "/api/v1/reports/nonexistent-run-id/report.json",
            headers=headers,
        )
        assert r.status_code == 404

    def test_nonexistent_run_returns_404_metrics(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            "/api/v1/reports/nonexistent-run-id/metrics",
            headers=headers,
        )
        assert r.status_code == 404

    def test_nonexistent_run_returns_404_export(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            "/api/v1/reports/nonexistent-run-id/export/html",
            headers=headers,
        )
        assert r.status_code == 404


# ------------------------------------------------------------------
# Owner access
# ------------------------------------------------------------------


class TestOwnerAccess:
    def test_owner_gets_html(self, client, run_id_a, token_a):
        _plant_report_files(run_id_a)
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(f"/api/v1/reports/{run_id_a}/report.html", headers=headers)
        assert r.status_code == 200
        assert "Content-Security-Policy" in r.headers

    def test_owner_gets_json(self, client, run_id_a, token_a):
        _plant_report_files(run_id_a)
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(f"/api/v1/reports/{run_id_a}/report.json", headers=headers)
        assert r.status_code == 200
        assert "Content-Security-Policy" in r.headers

    def test_owner_gets_metrics(self, client, run_id_a, token_a):
        _plant_report_files(run_id_a, {"metrics": {"total_return": 0.15}})
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(f"/api/v1/reports/{run_id_a}/metrics", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["metrics"]["total_return"] == 0.15

    def test_missing_report_returns_404(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            "/api/v1/reports/nonexistent-run-999/metrics",
            headers=headers,
        )
        # Will get 404 from ownership check since run doesn't exist
        assert r.status_code == 404


# ------------------------------------------------------------------
# Comparison
# ------------------------------------------------------------------


class TestCompareEndpoint:
    def test_compare_requires_two_ids(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.post(
            "/api/v1/reports/compare",
            json={"run_ids": ["single"]},
            headers=headers,
        )
        assert r.status_code == 400

    def test_compare_two_reports(self, client, run_id_a, token_a):
        """Compare two reports owned by user A."""
        _plant_report_files(run_id_a, {"metrics": {"total_return": 0.15}})

        # Create a second strategy + run for user A
        headers = {"Authorization": f"Bearer {token_a}"}
        tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
        strat = client.post(
            "/api/v1/strategies",
            json={
                "name": "rpt_compare_second",
                "description": "",
                "source_code": tpl.json()["source_code"],
            },
            headers=headers,
        )
        sid2 = strat.json()["id"]
        r2 = client.post(
            "/api/v1/runs",
            json={
                "strategy_id": sid2,
                "params": {"start_date": "2024-01-01", "end_date": "2024-01-05"},
            },
            headers=headers,
        )
        run_id_2 = r2.json().get("run_id") or r2.json()["id"]
        _plant_report_files(run_id_2, {"metrics": {"total_return": 0.25}})

        r = client.post(
            "/api/v1/reports/compare",
            json={"run_ids": [run_id_a, run_id_2]},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "reports" in body
        assert "differences" in body


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------


class TestExportEndpoint:
    def test_export_html(self, client, run_id_a, token_a):
        _plant_report_files(run_id_a)
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            f"/api/v1/reports/{run_id_a}/export/html",
            headers=headers,
        )
        assert r.status_code == 200

    def test_export_json(self, client, run_id_a, token_a):
        _plant_report_files(run_id_a)
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            f"/api/v1/reports/{run_id_a}/export/json",
            headers=headers,
        )
        assert r.status_code == 200

    def test_export_unsupported_format(self, client, run_id_a, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            f"/api/v1/reports/{run_id_a}/export/docx",
            headers=headers,
        )
        assert r.status_code == 400

    def test_export_missing_file(self, client, run_id_a, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get(
            f"/api/v1/reports/{run_id_a}/export/pdf",
            headers=headers,
        )
        assert r.status_code == 404


# ------------------------------------------------------------------
# Listing
# ------------------------------------------------------------------


class TestListReports:
    def test_list_reports(self, client, token_a):
        headers = {"Authorization": f"Bearer {token_a}"}
        r = client.get("/api/v1/reports", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "runs" in body
        assert isinstance(body["runs"], list)
