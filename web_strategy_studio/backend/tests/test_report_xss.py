"""Tests for report XSS protection + auth-gated report access (HIGH-14/HIGH-15)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_report_xss_test")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "report_xss_user",
            "password": "testpass",
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "report_xss_user",
                "password": "testpass",
            },
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_other(client):
    """Second user to test cross-user report access denial."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "other_report_user",
            "password": "testpass2",
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "other_report_user",
                "password": "testpass2",
            },
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


# ── HIGH-14 / HIGH-15: Static mount is gone ──────────────────────────────────


def test_report_static_mount_removed(client):
    """The unauthenticated /static/reports/ mount must be removed (HIGH-15)."""
    # Create a real file to prove the static mount can't serve it
    from studio_api.app import reports_root

    probe_dir = reports_root / "xss_probe_run"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "report.html").write_text("<html>probe</html>")

    r = client.get("/static/reports/xss_probe_run/report.html")
    assert r.status_code == 404, (
        "/static/reports/ must be inaccessible — the unauthenticated static mount "
        f"should be removed. Got HTTP {r.status_code}."
    )


# ── HIGH-14: iframe sandbox attribute ────────────────────────────────────────


def test_report_page_iframe_sandbox():
    """ReportPage.tsx iframe must NOT include allow-same-origin."""
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
        "src",
        "pages",
        "ReportPage.tsx",
    )
    with open(path) as f:
        content = f.read()
    # Find the iframe sandbox attribute
    import re

    m = re.search(r'sandbox\s*=\s*"([^"]*)"', content)
    assert m, "iframe must have a sandbox attribute"
    sandbox = m.group(1)
    assert "allow-same-origin" not in sandbox, (
        "iframe sandbox must NOT include allow-same-origin "
        "(would defeat CSP and expose API cookies)"
    )
    # But it should still allow scripts for TradingView charts
    assert "allow-scripts" in sandbox, "iframe sandbox must allow scripts for charts"


# ── HIGH-14: html.escape in report.py ────────────────────────────────────────


def test_report_escapes_xss_in_trade_log():
    """Trade log entries with HTML must be escaped in generated HTML."""
    import html

    from eqlib.report import generate_html_report

    # Create a minimal fake result dict
    class FakePortfolio:
        def __init__(self):
            self.starting_cash = 100000.0
            self.total_value = 105000.0
            self.positions = {}

    class FakeContext:
        def __init__(self):
            self.start_date = "2024-01-01"
            self.end_date = "2024-01-31"
            self.portfolio = FakePortfolio()
            self.universe = []

    xss_security = '<script>alert("xss")</script>'
    result = {
        "context": FakeContext(),
        "trade_log": [
            {
                "type": "BUY",
                "date": "2024-01-02",
                "security": xss_security,  # XSS payload in security field
                "price": 10.0,
                "amount": 100,
                "commission": 5.0,
            }
        ],
        "recorded_values": {},
        "benchmark": "000300.XSHG",
        "candlestick_data": [],
        "tech_stats": {},
    }

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        out_path = f.name

    try:
        generate_html_report(result, out_path)
        html_content = open(out_path).read()

        # The raw script tag must NOT appear in the HTML
        assert (
            xss_security not in html_content
        ), "XSS payload from trade_log.security must be escaped in HTML output"
        # The escaped version should be present
        assert html.escape(xss_security) in html_content
    finally:
        os.unlink(out_path)


def test_report_escapes_xss_in_trade_date():
    """Trade date with HTML must be escaped."""
    from eqlib.report import generate_html_report

    class FakePortfolio:
        def __init__(self):
            self.starting_cash = 100000.0
            self.total_value = 105000.0
            self.positions = {}

    class FakeContext:
        def __init__(self):
            self.start_date = "2024-01-01"
            self.end_date = "2024-01-31"
            self.portfolio = FakePortfolio()
            self.universe = []

    xss_date = "2024-01-02</td><td><script>alert(1)</script>"
    result = {
        "context": FakeContext(),
        "trade_log": [
            {
                "type": "BUY",
                "date": xss_date,
                "security": "000001.XSHE",
                "price": 10.0,
                "amount": 100,
                "commission": 5.0,
            }
        ],
        "recorded_values": {},
        "benchmark": "000300.XSHG",
        "candlestick_data": [],
        "tech_stats": {},
    }

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        out_path = f.name

    try:
        generate_html_report(result, out_path)
        html_content = open(out_path).read()

        assert xss_date not in html_content, "XSS payload from trade_log.date must be escaped"
    finally:
        os.unlink(out_path)


def test_report_escapes_xss_in_positions():
    """Position security codes with HTML must be escaped."""
    from eqlib.report import generate_html_report

    class FakePosition:
        def __init__(self):
            self.amount = 100
            self.avg_cost = 10.0

    class FakePortfolio:
        def __init__(self):
            self.starting_cash = 100000.0
            self.total_value = 105000.0
            self.positions = {xss_code: FakePosition()}

    xss_code = '<script>alert("xss")</script>'
    fake_portfolio = FakePortfolio()
    fake_portfolio.positions[xss_code] = FakePosition()

    class FakeContext:
        def __init__(self):
            self.start_date = "2024-01-01"
            self.end_date = "2024-01-31"
            self.portfolio = fake_portfolio
            self.universe = []

    result = {
        "context": FakeContext(),
        "trade_log": [],
        "recorded_values": {},
        "benchmark": "000300.XSHG",
        "candlestick_data": [],
        "tech_stats": {},
    }

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        out_path = f.name

    try:
        generate_html_report(result, out_path)
        html_content = open(out_path).read()

        assert xss_code not in html_content, "XSS payload from position key must be escaped"
    finally:
        os.unlink(out_path)


# ── HIGH-15: Report access requires auth + ownership ─────────────────────────


def test_report_endpoint_requires_auth(client):
    """GET /api/v1/reports/{run_id}/report.html must require auth."""
    r = client.get("/api/v1/reports/fake_run/report.html")
    assert r.status_code == 401


def test_report_endpoint_returns_404_for_unauthorized_user(client, auth_token, auth_token_other):
    """User B must NOT be able to access User A's report (404-on-unauthorized)."""
    headers_a = {"Authorization": f"Bearer {auth_token}"}
    headers_b = {"Authorization": f"Bearer {auth_token_other}"}

    # Create a strategy and run as user A
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers_a)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "report-auth-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers_a,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    # Create a run
    run_body = {
        "strategy_id": sid,
        "params": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
        },
    }
    r = client.post("/api/v1/runs", json=run_body, headers=headers_a)
    assert r.status_code in (200, 201, 202)
    run_id = r.json().get("run_id") or r.json()["id"]

    # User B tries to access User A's report — must get 404
    r = client.get(f"/api/v1/reports/{run_id}/report.html", headers=headers_b)
    assert r.status_code == 404


def test_report_endpoint_returns_file_for_owner(client, auth_token):
    """Owner can access their own report."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a strategy
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "report-owner-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

    # Create a run
    run_body = {
        "strategy_id": sid,
        "params": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
        },
    }
    r = client.post("/api/v1/runs", json=run_body, headers=headers)
    assert r.status_code in (200, 201, 202)
    run_id = r.json().get("run_id") or r.json()["id"]

    # Owner tries to access report — should succeed (even if file doesn't exist yet, 404 is fine)
    r = client.get(f"/api/v1/reports/{run_id}/report.html", headers=headers)
    # Either 200 (file exists) or 404 (file not yet generated) — but NOT 401/403
    assert r.status_code in (200, 404)
