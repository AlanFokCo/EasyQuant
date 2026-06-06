"""Tests for strategy versioning (B4/B15) — Phase 2."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    # Disable draft-mode coalescing: each PATCH with changed content → new version
    import studio_api.config as _cfg
    from studio_api.app import app

    _cfg.settings.version_coalesce_sec = 0
    # Module E: enable registration for backward-compat tests
    _cfg.settings.allow_registration = True
    _cfg.settings.require_invite_code = False

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    pw = "TestPass1!"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "version_user",
            "password": pw,
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "version_user",
                "password": pw,
            },
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]
    # Registration may fail with 422 if password policy changed or 201 on success
    if reg.status_code in (200, 201):
        return reg.json()["access_token"]
    # If registration fails, try login as fallback
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": "version_user",
            "password": pw,
        },
    )
    assert resp.status_code == 200, f"Register: {reg.status_code} {reg.text}; Login: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


def _create(client, auth_token, name="test"):
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "description": "", "source_code": tpl.json()["source_code"]},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ── B4: identical content must NOT create a new version ─────────────────────


def test_identical_patch_does_not_bump_version(client, auth_token):
    """PATCH with unchanged source_code must not increment version (B4 fix)."""
    created = _create(client, auth_token, "dedup-test")
    sid = created["id"]
    v0 = created["version"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    same_code = client.get(f"/api/v1/strategies/{sid}", headers=headers).json()["source_code"]

    r1 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code}, headers=headers)
    assert r1.status_code == 200
    r2 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code}, headers=headers)
    assert r2.status_code == 200

    assert (
        r2.json()["version"] == v0
    ), f"Identical-content PATCH must not bump version: {v0} → {r2.json()['version']}"


def test_different_content_bumps_version(client, auth_token):
    """PATCH with different source_code must create a new version (coalesce disabled)."""
    created = _create(client, auth_token, "bump-test")
    sid = created["id"]
    v0 = created["version"]
    headers = {"Authorization": f"Bearer {auth_token}"}

    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    r = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": new_code}, headers=headers)
    assert r.status_code == 200
    assert r.json()["version"] > v0


# ── B15: GET must return current_version, not max version ───────────────────


def test_get_returns_current_version_code(client, auth_token):
    """GET /strategies/{id} returns source at current_version."""
    created = _create(client, auth_token, "current-ver-test")
    sid = created["id"]
    headers = {"Authorization": f"Bearer {auth_token}"}

    v2_code = "from eqlib import *\n\ndef initialize(context):\n    g.x = 2\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": v2_code}, headers=headers)

    detail = client.get(f"/api/v1/strategies/{sid}", headers=headers).json()
    assert detail["source_code"] == v2_code


# ── Versions list ────────────────────────────────────────────────────────────


def test_list_versions(client, auth_token):
    """GET /strategies/{id}/versions returns ordered list with at least 2 entries."""
    created = _create(client, auth_token, "versions-list-test")
    sid = created["id"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2}, headers=headers)

    r = client.get(f"/api/v1/strategies/{sid}/versions", headers=headers)
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) >= 2, f"Expected >=2 versions, got: {versions}"
    assert versions[0]["version"] == 1
    nums = [v["version"] for v in versions]
    assert nums == sorted(nums)


def test_get_specific_version(client, auth_token):
    """GET /strategies/{id}/versions/{version} returns that version's source."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    orig = tpl.json()["source_code"]
    # Create a brand-new strategy (fresh v1 with orig code)
    resp = client.post(
        "/api/v1/strategies",
        json={"name": "specific-ver-test", "description": "", "source_code": orig},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2}, headers=headers)

    r = client.get(f"/api/v1/strategies/{sid}/versions/1", headers=headers)
    assert r.status_code == 200
    assert r.json()["source_code"] == orig

    r2 = client.get(f"/api/v1/strategies/{sid}/versions/2", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["source_code"] == code_v2


def test_get_nonexistent_version_404(client, auth_token):
    created = _create(client, auth_token, "not-found-ver-test")
    sid = created["id"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = client.get(f"/api/v1/strategies/{sid}/versions/999", headers=headers)
    assert r.status_code == 404


# ── Snapshot ─────────────────────────────────────────────────────────────────


def test_snapshot_creates_new_version(client, auth_token):
    """POST /strategies/{id}/snapshot always creates a new version."""
    created = _create(client, auth_token, "snapshot-test")
    sid = created["id"]
    v0 = created["version"]
    headers = {"Authorization": f"Bearer {auth_token}"}

    r = client.post(
        f"/api/v1/strategies/{sid}/snapshot", json={"label": "release-1.0"}, headers=headers
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["version"] > v0

    versions = client.get(f"/api/v1/strategies/{sid}/versions", headers=headers).json()
    labeled = [v for v in versions if v.get("label") == "release-1.0"]
    assert labeled, "Snapshot label not found in versions list"


# ── Restore ──────────────────────────────────────────────────────────────────


def test_restore_version(client, auth_token):
    """POST /strategies/{id}/versions/{v}/restore creates a new version with old code."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    orig = tpl.json()["source_code"]
    resp = client.post(
        "/api/v1/strategies",
        json={"name": "restore-test", "description": "", "source_code": orig},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2}, headers=headers)

    r = client.post(f"/api/v1/strategies/{sid}/versions/1/restore", headers=headers)
    assert r.status_code in (200, 201), r.text
    new_ver = r.json()["version"]

    detail = client.get(f"/api/v1/strategies/{sid}", headers=headers).json()
    assert detail["source_code"] == orig
    assert detail["version"] == new_ver


# ── Name-only PATCH still does not bump version ──────────────────────────────


def test_name_patch_no_version_bump(client, auth_token):
    created = _create(client, auth_token, "name-bump-test")
    sid = created["id"]
    v0 = created["version"]
    headers = {"Authorization": f"Bearer {auth_token}"}

    r = client.patch(f"/api/v1/strategies/{sid}", json={"name": "renamed"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["version"] == v0
