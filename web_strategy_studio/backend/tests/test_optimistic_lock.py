"""Tests for HIGH-19: optimistic locking on PATCH /strategies/{id}.

Verifies that:
- PATCH without expected_version → 200 (backward-compatible)
- PATCH with expected_version == current_version → 200
- PATCH with expected_version < current_version → 409 VERSION_CONFLICT
- Two concurrent PATCHes with the same expected_version: first 200, second 409
- Inside the version_coalesce_sec window, a PATCH with stale expected_version → 409
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_optlock")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import studio_api.config as _cfg
    from studio_api.app import app

    # Use a short coalesce window so we can also test the coalesce path
    _cfg.settings.version_coalesce_sec = 30

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    reg = client.post("/api/v1/auth/register", json={"username": "optlock_user", "password": "testpass"})
    if reg.status_code == 409:
        resp = client.post("/api/v1/auth/login", json={"username": "optlock_user", "password": "testpass"})
        token = resp.json()["access_token"]
    else:
        token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_strategy(client, headers, name="optlock-test"):
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "description": "", "source_code": tpl.json()["source_code"]},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    return resp.json()


def test_patch_no_expected_version_is_200(client, auth_headers):
    """PATCH without expected_version must succeed (backward compatibility)."""
    strat = _create_strategy(client, auth_headers, "no-ev-test")
    resp = client.patch(
        f"/api/v1/strategies/{strat['id']}",
        json={"source_code": "# changed\n"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_patch_correct_expected_version_is_200(client, auth_headers):
    """PATCH with expected_version == current_version must succeed."""
    strat = _create_strategy(client, auth_headers, "ev-match-test")
    resp = client.patch(
        f"/api/v1/strategies/{strat['id']}",
        json={"source_code": "# v2\n", "expected_version": strat["version"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_patch_stale_expected_version_is_409(client, auth_headers):
    """PATCH with expected_version < current_version must return 409."""
    import studio_api.config as _cfg
    # Disable coalesce so the first PATCH creates a real new version
    original = _cfg.settings.version_coalesce_sec
    _cfg.settings.version_coalesce_sec = 0
    try:
        strat = _create_strategy(client, auth_headers, "ev-stale-test")
        v0 = strat["version"]
        # Advance to v0+1 without expected_version (force-write)
        advance = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# v2 forced\n"},
            headers=auth_headers,
        )
        assert advance.status_code == 200
        assert advance.json()["version"] == v0 + 1

        # Now PATCH with the old expected_version → 409
        resp = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# v3 stale\n", "expected_version": v0},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]["error"]
        assert detail["code"] == "VERSION_CONFLICT"
    finally:
        _cfg.settings.version_coalesce_sec = original


def test_concurrent_patch_same_expected_version(client, auth_headers):
    """Two PATCHes with the same expected_version: first 200, second 409."""
    import studio_api.config as _cfg
    original = _cfg.settings.version_coalesce_sec
    _cfg.settings.version_coalesce_sec = 0
    try:
        strat = _create_strategy(client, auth_headers, "concurrent-test")
        v0 = strat["version"]

        resp1 = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# first writer\n", "expected_version": v0},
            headers=auth_headers,
        )
        assert resp1.status_code == 200

        resp2 = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# second writer\n", "expected_version": v0},
            headers=auth_headers,
        )
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["error"]["code"] == "VERSION_CONFLICT"
    finally:
        _cfg.settings.version_coalesce_sec = original


def test_coalesce_window_still_rejects_stale_expected_version(client, auth_headers):
    """Inside the coalesce window, a second PATCH with stale expected_version must be 409.

    When expected_version is provided, the coalesce path is bypassed so that two
    concurrent writers both arriving with expected_version=v0 will each attempt to
    create a new version: the first succeeds (v0→v1), the second hits the
    top-level check (expected v0, server is v1) → 409.
    """
    import studio_api.config as _cfg
    original = _cfg.settings.version_coalesce_sec
    _cfg.settings.version_coalesce_sec = 60  # generous window
    try:
        strat = _create_strategy(client, auth_headers, "coalesce-lock-test")
        v0 = strat["version"]

        # First PATCH with expected_version=v0 — coalesce is skipped when
        # expected_version is provided, so a proper v1 is created.
        resp1 = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# writer A\n", "expected_version": v0},
            headers=auth_headers,
        )
        assert resp1.status_code == 200
        v1 = resp1.json()["version"]
        assert v1 == v0 + 1, "expected_version bypasses coalesce, must create new version"

        # Second PATCH with the stale expected_version=v0 → 409
        resp2 = client.patch(
            f"/api/v1/strategies/{strat['id']}",
            json={"source_code": "# writer B — should conflict\n", "expected_version": v0},
            headers=auth_headers,
        )
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["error"]["code"] == "VERSION_CONFLICT"
    finally:
        _cfg.settings.version_coalesce_sec = original
