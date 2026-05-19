"""Tests for PR-9: cancel button (HIGH-18), optimistic lock (HIGH-19), per-tab runId (HIGH-20)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_pr9_test")


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
            "username": "pr9_user",
            "password": "testpass",
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "pr9_user",
                "password": "testpass",
            },
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


# ── HIGH-18: Cancel endpoint requires auth + ownership ───────────────────────


def test_cancel_requires_auth(client):
    """POST /runs/{id}/cancel must require auth."""
    r = client.post("/api/v1/runs/fake_run/cancel")
    assert r.status_code == 401


def test_cancel_returns_404_for_unauthorized_user(client, auth_token):
    """User B must NOT be able to cancel User A's run."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a strategy and run
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "cancel-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

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

    # Register another user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "other_cancel_user",
            "password": "testpass2",
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "other_cancel_user",
                "password": "testpass2",
            },
        )
    else:
        resp = reg
    other_token = resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Other user tries to cancel — must get 404
    r = client.post(f"/api/v1/runs/{run_id}/cancel", headers=other_headers)
    assert r.status_code == 404


def test_cancel_owner_can_cancel(client, auth_token):
    """Run owner can cancel their own run."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a strategy
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "self-cancel-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

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

    # Owner cancels
    r = client.post(f"/api/v1/runs/{run_id}/cancel", headers=headers)
    assert r.status_code in (200, 201)
    assert r.json()["status"] == "cancelled"


def test_cancel_idempotent_for_terminal_run(client, auth_token):
    """Cancelling an already-failed/succeeded run returns ok."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create a strategy
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    strat = client.post(
        "/api/v1/strategies",
        json={
            "name": "idempotent-cancel-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert strat.status_code in (200, 201)
    sid = strat.json()["id"]

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

    # Wait for run to complete
    import time

    for _ in range(30):
        time.sleep(0.5)
        status_resp = client.get(f"/api/v1/runs/{run_id}", headers=headers)
        if status_resp.status_code == 200:
            status = status_resp.json()["status"]
            if status in ("succeeded", "failed", "cancelled"):
                break

    # Try to cancel — should return ok with current status
    r = client.post(f"/api/v1/runs/{run_id}/cancel", headers=headers)
    assert r.status_code in (200, 201)
    assert r.json()["ok"] is True


# ── HIGH-19: Frontend optimistic lock detection ──────────────────────────────


def test_frontend_optimistic_lock_file_checks():
    """StrategyLayout.tsx must include version conflict detection."""
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
        "src",
        "components",
        "StrategyLayout.tsx",
    )
    with open(path) as f:
        content = f.read()

    # Must track serverVersion
    assert "serverVersion" in content, "StrategyLayout must track serverVersion for optimistic lock"

    # Must check version before saving
    assert "version" in content.lower(), "Must check version before PATCH"

    # Must show conflict message
    assert (
        "版本冲突" in content or "conflict" in content.lower()
    ), "Must show version conflict message"


def test_strategy_version_returned_on_patch(client, auth_token):
    """PATCH /strategies/{id} must return updated version number."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "version-patch-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    v0 = resp.json()["version"]

    # Patch with new code
    new_code = "from eqlib import *\n\ndef initialize(context):\n    pass\n"
    r = client.patch(
        f"/api/v1/strategies/{resp.json()['id']}",
        json={"source_code": new_code},
        headers=headers,
    )
    assert r.status_code == 200
    assert "version" in r.json()
    assert r.json()["version"] >= v0


# ── HIGH-20: Frontend per-tab runId ─────────────────────────────────────────


def test_frontend_uses_sessionStorage_for_runid():
    """useRunStream.ts must use sessionStorage (not localStorage) for runId."""
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
        "src",
        "hooks",
        "useRunStream.ts",
    )
    with open(path) as f:
        content = f.read()

    # Must use sessionStorage
    assert (
        "sessionStorage" in content
    ), "useRunStream must use sessionStorage for per-tab runId (HIGH-20)"

    # Must NOT use localStorage for runId
    # The old code had localStorage.getItem/setItem for runId
    import re

    run_id_ls = re.findall(r"localStorage\.(?:get|set|remove)Item\(.*run_id", content)
    assert not run_id_ls, f"useRunStream must not use localStorage for runId, found: {run_id_ls}"


def test_editorStore_uses_sessionStorage_for_runid():
    """editorStore.ts must use sessionStorage (not localStorage) for runId."""
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
        "src",
        "store",
        "editorStore.ts",
    )
    with open(path) as f:
        content = f.read()

    # Must use sessionStorage for runId
    assert (
        "sessionStorage" in content
    ), "editorStore must use sessionStorage for per-tab runId (HIGH-20)"

    # Must NOT use localStorage for runId key
    import re

    run_id_ls = re.findall(r"localStorage\.(?:get|set|remove)Item\(.*run_id", content)
    assert not run_id_ls, f"editorStore must not use localStorage for runId, found: {run_id_ls}"
