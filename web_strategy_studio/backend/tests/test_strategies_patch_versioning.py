"""Tests for strategy PATCH versioning behaviour (Phase 0 → Phase 2).

B4 is fixed in Phase 2 — the xfail mark is removed.
"""

from __future__ import annotations

import os

import pytest

# Point at an in-memory DB before importing any studio_api module.
os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")
# Disable coalescing so tests see true dedup behaviour without draft-mode noise
os.environ.setdefault("EQ_STUDIO_VERSION_COALESCE_SEC", "0")


@pytest.fixture(scope="module")
def client():
    """Synchronous TestClient — triggers FastAPI lifespan (DB init)."""
    from fastapi.testclient import TestClient

    import studio_api.config as _cfg
    from studio_api.app import app

    _cfg.settings.version_coalesce_sec = 0

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """Register and login to get an auth token."""
    reg = client.post("/api/v1/auth/register", json={
        "username": "patch_user",
        "password": "testpass",
    })
    if reg.status_code == 409:
        resp = client.post("/api/v1/auth/login", json={
            "username": "patch_user",
            "password": "testpass",
        })
        return resp.json()["access_token"]
    return reg.json()["access_token"]


def test_patch_same_code_no_version_bump(client, auth_token):
    """B4 — PATCH with the same source_code must NOT create a duplicate version."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    create_resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "version-bump test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert create_resp.status_code in (200, 201)
    sid = create_resp.json()["id"]
    v0 = create_resp.json()["version"]

    # PATCH with identical source code twice — version must stay the same
    same_code = tpl.json()["source_code"]
    client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code}, headers=headers)
    resp2 = client.patch(f"/api/v1/strategies/{sid}", json={"source_code": same_code}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["version"] == v0, "Identical-content PATCH must not increment version (B4)"


def test_patch_updates_source_code(client, auth_token):
    """PATCH with source_code updates the strategy's code."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    assert tpl.status_code == 200

    create_resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "test strategy",
            "description": "phase-0 test",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert create_resp.status_code in (200, 201)
    strategy_id = create_resp.json()["id"]

    # PATCH with new source code
    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    patch_resp = client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={"source_code": new_code},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # GET should return updated code
    get_resp = client.get(f"/api/v1/strategies/{strategy_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["source_code"] == new_code


def test_patch_name_only_no_version_bump(client, auth_token):
    """PATCH with only name change must NOT create a new version row."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    create_resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "original name",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert create_resp.status_code in (200, 201)
    sid = create_resp.json()["id"]
    v_before = create_resp.json()["version"]

    # PATCH name only
    patch_resp = client.patch(
        f"/api/v1/strategies/{sid}",
        json={"name": "updated name"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    v_after = patch_resp.json()["version"]

    # Version must NOT have changed
    assert v_after == v_before, f"Name-only PATCH should not bump version: {v_before} → {v_after}"
