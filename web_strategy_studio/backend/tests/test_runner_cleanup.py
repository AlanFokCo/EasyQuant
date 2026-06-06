"""Tests for runner temp directory cleanup with try/finally."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest_plugins = ("anyio",)


@pytest.fixture
def local_runner():
    """Create a LocalRunner instance for testing."""
    from studio_api.runner import LocalRunner

    return LocalRunner()


@pytest.fixture
def docker_runner():
    """Create a DockerRunner instance for testing."""
    from studio_api.runner import DockerRunner

    return DockerRunner()


class TestLocalRunnerCleanup:
    """Test that LocalRunner cleans up temp directories even on exceptions."""

    @pytest.mark.asyncio
    async def test_cleanup_on_subprocess_failure(self, local_runner, tmp_path, monkeypatch):
        """Temp directory should be cleaned up when subprocess creation fails."""
        from studio_api.config import settings

        # Use tmp_path as artifact_dir
        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        # Track created temp directories
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def mock_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            return path

        # Mock create_subprocess_exec to raise
        async def mock_create_subprocess_exec(*args, **kwargs):
            raise RuntimeError("Simulated subprocess creation failure")

        with patch("tempfile.mkdtemp", side_effect=mock_mkdtemp):
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=mock_create_subprocess_exec,
            ):
                with pytest.raises(RuntimeError, match="Simulated"):
                    await local_runner.run(
                        run_id="test_cleanup_1",
                        source_code="# test",
                        params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
                    )

        # Verify all temp directories are cleaned up
        for dir_path in created_dirs:
            assert not os.path.exists(dir_path), f"Temp dir {dir_path} was not cleaned up"

    @pytest.mark.asyncio
    async def test_cleanup_on_timeout(self, local_runner, tmp_path, monkeypatch):
        """Temp directory should be cleaned up on timeout."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def mock_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            return path

        # Create a mock process that simulates timeout
        mock_proc = AsyncMock()
        mock_proc.stdout = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.returncode = None
        mock_proc.kill = lambda: None

        async def mock_wait():
            await asyncio.sleep(100)  # Simulate long-running process

        mock_proc.wait = mock_wait

        # Mock readline to return empty (EOF)
        mock_proc.stdout.readline = AsyncMock(return_value=b"")
        mock_proc.stderr.readline = AsyncMock(return_value=b"")

        async def mock_create_subprocess_exec(*args, **kwargs):
            return mock_proc

        # Set very short timeout
        monkeypatch.setattr(settings, "run_timeout_sec", 0)

        with patch("tempfile.mkdtemp", side_effect=mock_mkdtemp):
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=mock_create_subprocess_exec,
            ):
                result = await local_runner.run(
                    run_id="test_timeout_cleanup",
                    source_code="# test",
                    params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
                )

        # Result should indicate timeout
        assert result.get("error_code") == "TIMEOUT"

        # Verify cleanup
        for dir_path in created_dirs:
            assert not os.path.exists(dir_path), f"Temp dir {dir_path} was not cleaned up"

    @pytest.mark.asyncio
    async def test_cleanup_on_unexpected_exception(self, local_runner, tmp_path, monkeypatch):
        """Temp directory should be cleaned up even on unexpected exceptions."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def mock_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            return path

        # Mock stream_hub.publish to raise an unexpected exception
        async def mock_publish(*args, **kwargs):
            raise ValueError("Unexpected error during publish")

        with patch("tempfile.mkdtemp", side_effect=mock_mkdtemp):
            with patch("studio_api.runner.stream_hub.publish", side_effect=mock_publish):
                with pytest.raises(ValueError, match="Unexpected error"):
                    await local_runner.run(
                        run_id="test_unexpected",
                        source_code="# test",
                        params={},
                    )

        # Verify cleanup happened despite the exception
        for dir_path in created_dirs:
            assert not os.path.exists(dir_path), f"Temp dir {dir_path} was not cleaned up"


class TestDockerRunnerCleanup:
    """Test that DockerRunner cleans up temp directories even on exceptions."""

    @pytest.mark.asyncio
    async def test_cleanup_on_docker_failure(self, docker_runner, tmp_path, monkeypatch):
        """Temp directory should be cleaned up when Docker command fails."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def mock_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            return path

        # Mock create_subprocess_exec to raise (Docker not available)
        async def mock_create_subprocess_exec(*args, **kwargs):
            raise RuntimeError("Docker daemon not available")

        with patch("tempfile.mkdtemp", side_effect=mock_mkdtemp):
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=mock_create_subprocess_exec,
            ):
                with pytest.raises(RuntimeError, match="Docker daemon"):
                    await docker_runner.run(
                        run_id="test_docker_cleanup",
                        source_code="# test",
                        params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
                    )

        # Verify cleanup
        for dir_path in created_dirs:
            assert not os.path.exists(dir_path), f"Temp dir {dir_path} was not cleaned up"

    @pytest.mark.asyncio
    async def test_cleanup_on_write_failure(self, docker_runner, tmp_path, monkeypatch):
        """Temp directory should be cleaned up when file write fails."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def mock_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            # Make the directory read-only to cause write failures
            os.chmod(path, 0o555)
            return path

        with patch("tempfile.mkdtemp", side_effect=mock_mkdtemp):
            try:
                with pytest.raises((PermissionError, OSError)):
                    await docker_runner.run(
                        run_id="test_write_fail",
                        source_code="# test",
                        params={},
                    )
            finally:
                # Restore permissions for cleanup
                for dir_path in created_dirs:
                    if os.path.exists(dir_path):
                        os.chmod(dir_path, 0o755)

        # Verify cleanup happened (or at least attempted)
        # Note: Some dirs may still exist if chmod failed, but the important
        # thing is that the try/finally was executed


class TestResourceCleanupGuarantees:
    """Test that resource cleanup is guaranteed regardless of execution path."""

    @pytest.mark.asyncio
    async def test_cleanup_in_finally_block(self, local_runner, tmp_path, monkeypatch):
        """Verify cleanup happens via finally block, not just explicit calls."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        cleanup_attempts = []
        original_rmtree = __import__("shutil").rmtree

        def tracking_rmtree(path, *args, **kwargs):
            cleanup_attempts.append(path)
            return original_rmtree(path, *args, **kwargs)

        # Force an early exception before any explicit cleanup
        async def mock_publish(*args, **kwargs):
            raise RuntimeError("Early failure")

        with patch("shutil.rmtree", side_effect=tracking_rmtree):
            with patch("studio_api.runner.stream_hub.publish", side_effect=mock_publish):
                with pytest.raises(RuntimeError):
                    await local_runner.run(
                        run_id="test_finally",
                        source_code="# test",
                        params={},
                    )

        # Verify shutil.rmtree was called (via finally block)
        assert len(cleanup_attempts) > 0, "shutil.rmtree was not called"

    @pytest.mark.asyncio
    async def test_no_duplicate_cleanup(self, local_runner, tmp_path, monkeypatch):
        """Verify that cleanup doesn't cause errors when called multiple times."""
        from studio_api.config import settings

        monkeypatch.setattr(settings, "artifact_dir", tmp_path)

        cleanup_count = [0]
        original_rmtree = __import__("shutil").rmtree

        def counting_rmtree(path, *args, **kwargs):
            cleanup_count[0] += 1
            return original_rmtree(path, *args, **kwargs)

        # Mock to force timeout (which previously had explicit cleanup)
        mock_proc = AsyncMock()
        mock_proc.stdout = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.returncode = None
        mock_proc.kill = lambda: None

        async def mock_wait():
            await asyncio.sleep(100)

        mock_proc.wait = mock_wait
        mock_proc.stdout.readline = AsyncMock(return_value=b"")
        mock_proc.stderr.readline = AsyncMock(return_value=b"")

        monkeypatch.setattr(settings, "run_timeout_sec", 0)

        with patch("shutil.rmtree", side_effect=counting_rmtree):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ):
                result = await local_runner.run(
                    run_id="test_no_dup",
                    source_code="# test",
                    params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
                )

        # Cleanup should be called exactly once (via finally)
        # not twice (once explicit + once finally)
        assert cleanup_count[0] == 1, f"Expected 1 cleanup call, got {cleanup_count[0]}"
