"""Tests for strategy versioning (B4/B15) — Phase 2."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from studio_api.app import app
    # Disable draft-mode coalescing: each PATCH with changed content → new version
    import studio_api.config as _cfg
    _cfg.settings.version_coalesce_sec = 0

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _create(client, name="test"):
    tpl = client.get("/api/v1/strategies/_new/template")
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "description": "", "source_code": tpl.json()["source_code"]},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ── B4: identical content must NOT create a new version ─────────────────────

def test_identical_patch_does_not_bump_version(client):
    """PATCH with unchanged source_code must not increment version (B4 fix)."""
    created = _create(client, "dedup-test")
    sid = created["id"]
    v0 = created["version"]
    same_code = client.get(f"/api/v1/strategies/{sid}").json()["source_code"]

    r1 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code})
    assert r1.status_code == 200
    r2 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code})
    assert r2.status_code == 200

    assert r2.json()["version"] == v0, (
        f"Identical-content PATCH must not bump version: {v0} → {r2.json()['version']}"
    )


def test_different_content_bumps_version(client):
    """PATCH with different source_code must create a new version (coalesce disabled)."""
    created = _create(client, "bump-test")
    sid = created["id"]
    v0 = created["version"]

    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    r = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": new_code})
    assert r.status_code == 200
    assert r.json()["version"] > v0


# ── B15: GET must return current_version, not max version ───────────────────

def test_get_returns_current_version_code(client):
    """GET /strategies/{id} returns source at current_version."""
    created = _create(client, "current-ver-test")
    sid = created["id"]

    v2_code = "from eqlib import *\n\ndef initialize(context):\n    g.x = 2\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": v2_code})

    detail = client.get(f"/api/v1/strategies/{sid}").json()
    assert detail["source_code"] == v2_code


# ── Versions list ────────────────────────────────────────────────────────────

def test_list_versions(client):
    """GET /strategies/{id}/versions returns ordered list with at least 2 entries."""
    created = _create(client, "versions-list-test")
    sid = created["id"]
    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    r = client.get(f"/api/v1/strategies/{sid}/versions")
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) >= 2, f"Expected >=2 versions, got: {versions}"
    assert versions[0]["version"] == 1
    nums = [v["version"] for v in versions]
    assert nums == sorted(nums)


def test_get_specific_version(client):
    """GET /strategies/{id}/versions/{version} returns that version's source."""
    tpl = client.get("/api/v1/strategies/_new/template")
    orig = tpl.json()["source_code"]
    # Create a brand-new strategy (fresh v1 with orig code)
    resp = client.post(
        "/api/v1/strategies",
        json={"name": "specific-ver-test", "description": "", "source_code": orig},
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    r = client.get(f"/api/v1/strategies/{sid}/versions/1")
    assert r.status_code == 200
    assert r.json()["source_code"] == orig

    r2 = client.get(f"/api/v1/strategies/{sid}/versions/2")
    assert r2.status_code == 200
    assert r2.json()["source_code"] == code_v2


def test_get_nonexistent_version_404(client):
    created = _create(client, "not-found-ver-test")
    sid = created["id"]
    r = client.get(f"/api/v1/strategies/{sid}/versions/999")
    assert r.status_code == 404


# ── Snapshot ─────────────────────────────────────────────────────────────────

def test_snapshot_creates_new_version(client):
    """POST /strategies/{id}/snapshot always creates a new version."""
    created = _create(client, "snapshot-test")
    sid = created["id"]
    v0 = created["version"]

    r = client.post(f"/api/v1/strategies/{sid}/snapshot", json={"label": "release-1.0"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["version"] > v0

    versions = client.get(f"/api/v1/strategies/{sid}/versions").json()
    labeled = [v for v in versions if v.get("label") == "release-1.0"]
    assert labeled, "Snapshot label not found in versions list"


# ── Restore ──────────────────────────────────────────────────────────────────

def test_restore_version(client):
    """POST /strategies/{id}/versions/{v}/restore creates a new version with old code."""
    tpl = client.get("/api/v1/strategies/_new/template")
    orig = tpl.json()["source_code"]
    resp = client.post(
        "/api/v1/strategies",
        json={"name": "restore-test", "description": "", "source_code": orig},
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    r = client.post(f"/api/v1/strategies/{sid}/versions/1/restore")
    assert r.status_code in (200, 201), r.text
    new_ver = r.json()["version"]

    detail = client.get(f"/api/v1/strategies/{sid}").json()
    assert detail["source_code"] == orig
    assert detail["version"] == new_ver


# ── Name-only PATCH still does not bump version ──────────────────────────────

def test_name_patch_no_version_bump(client):
    created = _create(client, "name-bump-test")
    sid = created["id"]
    v0 = created["version"]

    r = client.patch(f"/api/v1/strategies/{sid}", json={"name": "renamed"})
    assert r.status_code == 200
    assert r.json()["version"] == v0



def _create(client, name="test"):
    tpl = client.get("/api/v1/strategies/_new/template")
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "description": "", "source_code": tpl.json()["source_code"]},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ── B4: identical content must NOT create a new version ─────────────────────

def test_identical_patch_does_not_bump_version(client):
    """PATCH with unchanged source_code must not increment version (B4 fix)."""
    created = _create(client, "dedup-test")
    sid = created["id"]
    v0 = created["version"]
    same_code = client.get(f"/api/v1/strategies/{sid}").json()["source_code"]

    # Two PATCH calls with the same code
    r1 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code})
    assert r1.status_code == 200
    r2 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code})
    assert r2.status_code == 200

    assert r2.json()["version"] == v0, (
        f"Identical-content PATCH must not bump version: {v0} → {r2.json()['version']}"
    )


def test_different_content_bumps_version(client):
    """PATCH with different source_code must create a new version."""
    created = _create(client, "bump-test")
    sid = created["id"]
    v0 = created["version"]

    # First patch with different code — with coalesce_sec=0, this always creates a new version
    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    r = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": new_code})
    assert r.status_code == 200
    assert r.json()["version"] > v0


# ── B15: GET must return current_version, not max version ───────────────────

def test_get_returns_current_version_code(client):
    """GET /strategies/{id} returns source at current_version."""
    created = _create(client, "current-ver-test")
    sid = created["id"]

    # Write v2 with new code
    v2_code = "from eqlib import *\n\ndef initialize(context):\n    g.x = 2\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": v2_code})

    # GET should return the latest (v2) code since current_version was updated
    detail = client.get(f"/api/v1/strategies/{sid}").json()
    assert detail["source_code"] == v2_code


# ── Versions list ────────────────────────────────────────────────────────────

def test_list_versions(client):
    """GET /strategies/{id}/versions returns ordered list."""
    created = _create(client, "versions-list-test")
    sid = created["id"]
    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    r = client.get(f"/api/v1/strategies/{sid}/versions")
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) >= 2
    assert versions[0]["version"] == 1
    # Versions come back in ascending order
    nums = [v["version"] for v in versions]
    assert nums == sorted(nums)


def test_get_specific_version(client):
    """GET /strategies/{id}/versions/{version} returns that version's source."""
    tpl = client.get("/api/v1/strategies/_new/template")
    orig = tpl.json()["source_code"]
    created = _create(client, "specific-ver-test")
    sid = created["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    r = client.get(f"/api/v1/strategies/{sid}/versions/1")
    assert r.status_code == 200
    # v1 has the original template code
    assert r.json()["source_code"] == orig

    r2 = client.get(f"/api/v1/strategies/{sid}/versions/2")
    assert r2.status_code == 200
    assert r2.json()["source_code"] == code_v2


def test_get_nonexistent_version_404(client):
    created = _create(client, "not-found-ver-test")
    sid = created["id"]
    r = client.get(f"/api/v1/strategies/{sid}/versions/999")
    assert r.status_code == 404


# ── Snapshot ─────────────────────────────────────────────────────────────────

def test_snapshot_creates_new_version(client):
    """POST /strategies/{id}/snapshot always creates a new version."""
    created = _create(client, "snapshot-test")
    sid = created["id"]
    v0 = created["version"]

    r = client.post(f"/api/v1/strategies/{sid}/snapshot", json={"label": "release-1.0"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["version"] > v0

    # Verify label appears in versions list
    versions = client.get(f"/api/v1/strategies/{sid}/versions").json()
    labeled = [v for v in versions if v.get("label") == "release-1.0"]
    assert labeled, "Snapshot label not found in versions list"


# ── Restore ──────────────────────────────────────────────────────────────────

def test_restore_version(client):
    """POST /strategies/{id}/versions/{v}/restore creates a new version with old code."""
    tpl = client.get("/api/v1/strategies/_new/template")
    orig = tpl.json()["source_code"]
    created = _create(client, "restore-test")
    sid = created["id"]

    code_v2 = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": code_v2})

    # Restore to version 1
    r = client.post(f"/api/v1/strategies/{sid}/versions/1/restore")
    assert r.status_code in (200, 201), r.text
    new_ver = r.json()["version"]

    # The restored version should have the original source code
    detail = client.get(f"/api/v1/strategies/{sid}").json()
    assert detail["source_code"] == orig
    assert detail["version"] == new_ver


# ── Name-only PATCH still does not bump version ──────────────────────────────

def test_name_patch_no_version_bump(client):
    created = _create(client, "name-bump-test")
    sid = created["id"]
    v0 = created["version"]

    r = client.patch(f"/api/v1/strategies/{sid}", json={"name": "renamed"})
    assert r.status_code == 200
    assert r.json()["version"] == v0
