"""Tests for strategy PATCH versioning behaviour (Phase 0).

B4 (always bumping version on every PATCH) is intentionally NOT fixed in Phase 0.
The test_patch_always_bumps_version test is expected to FAIL until Phase 2.
"""

from __future__ import annotations

import os

import pytest

# Point at an in-memory DB before importing any studio_api module.
os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test_artifacts")


@pytest.fixture(scope="module")
def client():
    """Synchronous TestClient — triggers FastAPI lifespan (DB init)."""
    from fastapi.testclient import TestClient
    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_patch_always_bumps_version():
    """B4 — PATCH with source_code must NOT always bump version (Phase 2 fix).

    This test is EXPECTED TO FAIL in Phase 0.  Rapid debounced saves currently
    create a new StrategyVersion row on every PATCH, regardless of whether the
    content changed.  Phase 2 will deduplicate identical-content versions.
    """
    pytest.xfail(
        "B4 not fixed yet — PATCH always creates a new version row. "
        "Fixed in Phase 2 by content-hash deduplication."
    )


def test_patch_updates_source_code(client):
    """PATCH with source_code updates the strategy's code."""
    tpl = client.get("/api/v1/strategies/_new/template")
    assert tpl.status_code == 200

    create_resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "test strategy",
            "description": "phase-0 test",
            "source_code": tpl.json()["source_code"],
        },
    )
    assert create_resp.status_code in (200, 201)
    strategy_id = create_resp.json()["id"]

    # PATCH with new source code
    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    patch_resp = client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={"source_code": new_code},
    )
    assert patch_resp.status_code == 200

    # GET should return updated code
    get_resp = client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["source_code"] == new_code


def test_patch_name_only_no_version_bump(client):
    """PATCH with only name change must NOT create a new version row."""
    tpl = client.get("/api/v1/strategies/_new/template")
    create_resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "original name",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
    )
    assert create_resp.status_code in (200, 201)
    sid = create_resp.json()["id"]
    v_before = create_resp.json()["version"]

    # PATCH name only
    patch_resp = client.patch(
        f"/api/v1/strategies/{sid}",
        json={"name": "updated name"},
    )
    assert patch_resp.status_code == 200
    v_after = patch_resp.json()["version"]

    # Version must NOT have changed
    assert v_after == v_before, (
        f"Name-only PATCH should not bump version: {v_before} → {v_after}"
    )
