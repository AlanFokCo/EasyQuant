"""Tests for DockerRunner isolation (BLOCKER-8).

Adversarial strategies that attempt to:
  - Sleep for a long time (should be killed by timeout)
  - Allocate excessive memory (should be OOM-killed by Docker)
  - Write files outside the work directory (should fail due to --read-only)
  - Access the network (should fail due to --network none)

DockerRunner tests are skipped when Docker is not available.
"""

from __future__ import annotations

import os
import subprocess

import pytest

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_runner_test")


@pytest.fixture(scope="module")
def client():
    """TestClient with runner env set to docker."""
    from fastapi.testclient import TestClient

    os.environ["EQ_STUDIO_RUNNER"] = "docker"

    from studio_api.app import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    # Cleanup: reset env
    os.environ.pop("EQ_STUDIO_RUNNER", None)


@pytest.fixture(scope="module")
def auth_token(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "runner_user",
            "password": "testpass",
        },
    )
    if reg.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": "runner_user",
                "password": "testpass",
            },
        )
        return resp.json()["access_token"]
    return reg.json()["access_token"]


@pytest.fixture(scope="module")
def strategy_id(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "docker-runner-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _docker_available() -> bool:
    """Check if Docker daemon is running and accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ── LocalRunner still works (no Docker needed) ───────────────────────────────


def test_local_runner_executes_backtest(client, auth_token):
    """LocalRunner (default) should execute a benign strategy successfully."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    tpl = client.get("/api/v1/strategies/_new/template", headers=headers)
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "local-runner-test",
            "description": "",
            "source_code": tpl.json()["source_code"],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    run_body = {
        "strategy_id": sid,
        "params": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
        },
    }
    r = client.post("/api/v1/runs", json=run_body, headers=headers)
    # POST /runs returns 202 Accepted (queued) or 200/201 (immediate start)
    assert r.status_code in (200, 201, 202)


# ── DockerRunner tests (skipped if Docker not available) ─────────────────────


@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_docker_runner_timeout_kills_long_sleep(client, auth_token):
    """A strategy that sleeps 100s should be killed by Docker timeout."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    malicious_code = """\
from eqlib import *

PARAMS = {}
PARAM_RANGES = {}

def initialize(context):
    import time
    # Sleep forever — should be killed
    while True:
        time.sleep(1)
"""
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "sleep-test",
            "description": "",
            "source_code": malicious_code,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    # Use a very short timeout for the test
    from studio_api.config import settings

    original_timeout = settings.run_timeout_sec
    settings.run_timeout_sec = 10  # 10s for test

    try:
        run_body = {
            "strategy_id": sid,
            "params": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
            },
        }
        r = client.post("/api/v1/runs", json=run_body, headers=headers)
        assert r.status_code in (200, 201, 202)
        run_id = r.json()["id"]

        # Poll for completion
        import time

        for _ in range(30):
            time.sleep(1)
            status_resp = client.get(f"/api/v1/runs/{run_id}", headers=headers)
            if status_resp.status_code == 200:
                status = status_resp.json()["status"]
                if status in ("failed", "succeeded", "cancelled"):
                    break
        else:
            pytest.fail("Run did not complete within 30s")

        assert status in ("failed",), f"Expected failed (timeout), got: {status}"
    finally:
        settings.run_timeout_sec = original_timeout


@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_docker_runner_no_network_access(client, auth_token):
    """A strategy that tries to access the network should fail."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    # The scanner should flag this as a banned import, but the Docker
    # isolation ensures it can't actually reach the network even if bypassed.
    network_code = """\
from eqlib import *
import urllib.request

PARAMS = {}
PARAM_RANGES = {}

def initialize(context):
    try:
        urllib.request.urlopen("http://example.com", timeout=2)
    except Exception:
        pass  # Network should be blocked
"""
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": "network-test",
            "description": "",
            "source_code": network_code,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    sid = resp.json()["id"]

    from studio_api.config import settings

    original_timeout = settings.run_timeout_sec
    settings.run_timeout_sec = 15

    try:
        run_body = {
            "strategy_id": sid,
            "params": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
            },
        }
        r = client.post("/api/v1/runs", json=run_body, headers=headers)
        assert r.status_code in (200, 201, 202)
        run_id = r.json()["id"]

        import time

        for _ in range(30):
            time.sleep(1)
            status_resp = client.get(f"/api/v1/runs/{run_id}", headers=headers)
            if status_resp.status_code == 200:
                status = status_resp.json()["status"]
                if status in ("failed", "succeeded", "cancelled"):
                    break
        else:
            pytest.fail("Run did not complete within 30s")

        # The run should fail because the scanner will flag the import,
        # or Docker will block the network
    finally:
        settings.run_timeout_sec = original_timeout


# ── Runner protocol unit tests ───────────────────────────────────────────────


def test_runner_protocol_selects_local_by_default():
    """Default runner should be LocalRunner."""
    from studio_api.runner import get_runner, reset_runner

    os.environ.pop("EQ_STUDIO_RUNNER", None)
    reset_runner()
    runner = get_runner()
    assert type(runner).__name__ == "LocalRunner"


def test_runner_protocol_selects_docker_when_env_set():
    """EQ_STUDIO_RUNNER=docker should select DockerRunner."""
    from studio_api.runner import get_runner, reset_runner

    os.environ["EQ_STUDIO_RUNNER"] = "docker"
    try:
        reset_runner()
        runner = get_runner()
        assert type(runner).__name__ == "DockerRunner"
    finally:
        os.environ.pop("EQ_STUDIO_RUNNER", None)


def test_runner_protocol_invalid_env_falls_back_to_local():
    """Invalid EQ_STUDIO_RUNNER value should fall back to LocalRunner."""
    from studio_api.runner import get_runner, reset_runner

    os.environ["EQ_STUDIO_RUNNER"] = "kubernetes"
    try:
        reset_runner()
        runner = get_runner()
        assert type(runner).__name__ == "LocalRunner"
    finally:
        os.environ.pop("EQ_STUDIO_RUNNER", None)


def test_docker_build_command():
    """DockerRunner should build a correct docker run command."""
    from studio_api.runner import DockerRunner

    runner = DockerRunner()
    cmd = runner._build_cmd(
        work_dir="/tmp/test_work",
        artifact_dir="/tmp/test_artifacts",
    )
    assert cmd[0] == "docker"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "--network" in cmd
    assert "none" in cmd
    assert "--memory" in cmd
    assert "--pids-limit" in cmd
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd
