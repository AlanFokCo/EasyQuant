"""Tests for new strategy API endpoints: templates, diff.

Covers:
- GET /api/v1/templates — list templates
- GET /api/v1/templates/{id} — get template detail
- GET /api/v1/strategies/{id}/versions/{from}/diff/{to} — version diff
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import studio_api.config as _cfg
    from studio_api.app import app

    _cfg.settings.version_coalesce_sec = 0
    _cfg.settings.allow_registration = True
    _cfg.settings.require_invite_code = False

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    pw = "TestPass1!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "strat_api_user", "password": pw},
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "strat_api_user", "password": pw},
        )
        return resp.json()["access_token"]
    assert reg.status_code in (200, 201), f"Register failed: {reg.text}"
    return reg.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_strategy(client, auth_token, name="test", code=None):
    headers = _headers(auth_token)
    if code is None:
        tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
        code = tpl.json()["source_code"]
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "description": "", "source_code": code},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /api/v1/templates
# ---------------------------------------------------------------------------


class TestListTemplates:
    def test_returns_list(self, client, auth_token):
        r = client.get("/api/v1/templates", headers=_headers(auth_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_each_has_required_fields(self, client, auth_token):
        r = client.get("/api/v1/templates", headers=_headers(auth_token))
        for t in r.json():
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "category" in t

    def test_does_not_include_code(self, client, auth_token):
        r = client.get("/api/v1/templates", headers=_headers(auth_token))
        for t in r.json():
            assert "code" not in t

    def test_requires_auth(self, client):
        r = client.get("/api/v1/templates")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/templates/{template_id}
# ---------------------------------------------------------------------------


class TestGetTemplate:
    def test_returns_template_with_code(self, client, auth_token):
        r = client.get("/api/v1/templates/double_ma", headers=_headers(auth_token))
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "double_ma"
        assert "code" in data
        assert "def initialize" in data["code"]

    def test_returns_404_for_missing(self, client, auth_token):
        r = client.get("/api/v1/templates/nonexistent_xyz", headers=_headers(auth_token))
        assert r.status_code == 404

    def test_all_builtin_templates_accessible(self, client, auth_token):
        # Get list first
        listing = client.get("/api/v1/templates", headers=_headers(auth_token)).json()
        for t in listing:
            r = client.get(f"/api/v1/templates/{t['id']}", headers=_headers(auth_token))
            assert r.status_code == 200
            assert "code" in r.json()


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{id}/versions/{from}/diff/{to}
# ---------------------------------------------------------------------------


class TestVersionDiff:
    def test_diff_between_versions(self, client, auth_token):
        headers = _headers(auth_token)
        created = _create_strategy(client, auth_token, "diff-test")
        sid = created["id"]

        # Create v2 with different code
        new_code = "from eqlib import *\n\ndef initialize(context):\n    g.x = 2\n"
        client.patch(
            f"/api/v1/strategies/{sid}",
            json={"source_code": new_code},
            headers=headers,
        )

        # Diff v1 → v2
        r = client.get(
            f"/api/v1/strategies/{sid}/versions/1/diff/2",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert "from_code" in data
        assert "to_code" in data
        assert isinstance(data["diff"], list)

    def test_diff_404_for_missing_version(self, client, auth_token):
        headers = _headers(auth_token)
        created = _create_strategy(client, auth_token, "diff-404-test")
        sid = created["id"]

        r = client.get(
            f"/api/v1/strategies/{sid}/versions/1/diff/99",
            headers=headers,
        )
        assert r.status_code == 404

    def test_diff_404_for_missing_strategy(self, client, auth_token):
        headers = _headers(auth_token)
        r = client.get(
            "/api/v1/strategies/nonexistent/versions/1/diff/2",
            headers=headers,
        )
        assert r.status_code == 404
