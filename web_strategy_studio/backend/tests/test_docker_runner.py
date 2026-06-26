"""Tests for Docker Runner environment variable passing and command construction."""

from __future__ import annotations

import pytest

pytest_plugins = ("anyio",)


@pytest.fixture
def docker_runner():
    """Create a DockerRunner instance for testing."""
    from studio_api.runner import DockerRunner

    return DockerRunner()


class TestDockerRunnerBuildCmd:
    """Test DockerRunner._build_cmd method."""

    def test_build_cmd_includes_eq_artifact_dir(self, docker_runner):
        """Docker command should include EQ_ARTIFACT_DIR env var."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        # Find the -e flag followed by EQ_ARTIFACT_DIR
        found = False
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                if cmd[i + 1].startswith("EQ_ARTIFACT_DIR="):
                    found = True
                    assert "/tmp/artifacts" in cmd[i + 1]
                    break
        assert found, "EQ_ARTIFACT_DIR not found in docker command"

    def test_build_cmd_includes_eq_repo_root(self, docker_runner):
        """Docker command should include EQ_REPO_ROOT env var."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        found = False
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                if cmd[i + 1].startswith("EQ_REPO_ROOT="):
                    found = True
                    break
        assert found, "EQ_REPO_ROOT not found in docker command"

    def test_build_cmd_includes_eq_run_id(self, docker_runner):
        """Docker command should include EQ_RUN_ID env var."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        found = False
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                if cmd[i + 1] == "EQ_RUN_ID=test-run-123":
                    found = True
                    break
        assert found, "EQ_RUN_ID not found in docker command"

    def test_build_cmd_includes_pythonunbuffered(self, docker_runner):
        """Docker command should include PYTHONUNBUFFERED=1."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        found = False
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                if cmd[i + 1] == "PYTHONUNBUFFERED=1":
                    found = True
                    break
        assert found, "PYTHONUNBUFFERED=1 not found in docker command"

    def test_build_cmd_includes_volume_mounts(self, docker_runner):
        """Docker command should include volume mounts for work and artifact dirs."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        # Check for work volume
        assert "--volume" in cmd or "-v" in cmd
        assert "/tmp/work:/work:ro" in cmd
        assert "/tmp/artifacts:/out:rw" in cmd

    def test_build_cmd_includes_security_flags(self, docker_runner):
        """Docker command should include security-related flags."""
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        assert "--rm" in cmd
        assert "--network" in cmd
        assert "none" in cmd
        assert "--read-only" in cmd
        assert "--pids-limit" in cmd
        assert "64" in cmd
        assert "--security-opt" in cmd
        assert "no-new-privileges" in cmd

    def test_build_cmd_uses_custom_image(self, docker_runner, monkeypatch):
        """Docker command should use custom image from EQ_STUDIO_RUNNER_IMAGE."""
        monkeypatch.setenv("EQ_STUDIO_RUNNER_IMAGE", "my-custom-runner:1.0")

        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run-123",
        )

        assert "my-custom-runner:1.0" in cmd

    def test_build_cmd_enable_network(self, docker_runner, monkeypatch):
        """When enable_network is True, network should be 'bridge' instead of 'none'."""
        from studio_api.config import settings

        original = settings.enable_network
        try:
            settings.enable_network = True
            cmd = docker_runner._build_cmd(
                work_dir="/tmp/work",
                artifact_dir="/tmp/artifacts",
                run_id="test-run-123",
            )
            # 'none' should have been replaced with 'bridge'
            assert "none" not in cmd
            assert "bridge" in cmd
        finally:
            settings.enable_network = original

    def test_build_cmd_passes_run_id_correctly(self, docker_runner):
        """Run ID should be passed correctly to the docker command."""
        specific_run_id = "run_abc123def"
        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id=specific_run_id,
        )

        # Find EQ_RUN_ID
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                if cmd[i + 1].startswith("EQ_RUN_ID="):
                    assert cmd[i + 1] == f"EQ_RUN_ID={specific_run_id}"
                    break


class TestDockerRunnerEnvVarIsolation:
    """Test that Docker runner properly isolates environment variables."""

    def test_does_not_pass_sensitive_env_vars(self, docker_runner, monkeypatch):
        """Sensitive env vars like JWT_SECRET should not be passed to container."""
        monkeypatch.setenv("EQ_JWT_SECRET", "super-secret-value")

        cmd = docker_runner._build_cmd(
            work_dir="/tmp/work",
            artifact_dir="/tmp/artifacts",
            run_id="test-run",
        )

        # The command should not contain the secret value
        cmd_str = " ".join(cmd)
        assert "super-secret-value" not in cmd_str
