"""Tests for BLOCKER-9 (data_mgmt path traversal) and
BLOCKER-10 (delete_run rmtree validation).
"""

import datetime
import os
import pathlib
import tempfile
import uuid

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-9: _normalize_code strict validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker9NormalizeCode:
    """_normalize_code must reject anything that is not exactly 6 digits."""

    def _get_normalize(self):
        from studio_api.routers.data_mgmt import _normalize_code
        return _normalize_code

    def test_valid_six_digits(self):
        nc = self._get_normalize()
        assert nc("601390") == "601390"
        assert nc("000001") == "000001"

    def test_reject_path_traversal_dotdot(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):  # HTTPException
            nc("../etc/passwd")

    def test_reject_url_encoded_traversal(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("..%2F..%2Ftmp%2Fpoc")

    def test_reject_absolute_path(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("/tmp/poc")

    def test_reject_windows_backslash(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("..\\..\\tmp\\poc")

    def test_reject_double_dot_percent(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("..%2f")

    def test_reject_too_short(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("60139")

    def test_reject_too_long(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("6013901")

    def test_reject_letters(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("ABCDEF")

    def test_reject_exchange_suffix_stripped_valid(self):
        nc = self._get_normalize()
        assert nc("601390.XSHG") == "601390"

    def test_reject_mixed_case_with_traversal(self):
        nc = self._get_normalize()
        with pytest.raises(Exception):
            nc("601390/../../tmp")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-9: _local_csv_path path traversal defense-in-depth
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker9LocalCsvPath:
    """_local_csv_path must raise if the resolved path escapes the data dir."""

    def _make_sandbox(self, monkeypatch, tmp_path):
        """Create a sandboxed data_dir and patch _get_local_data_dir."""
        import eqlib.data_cache as dc
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setattr(dc, "_LOCAL_DATA_DIR", str(data_dir), raising=False)
        return data_dir

    def test_normal_code_returns_path_in_data_dir(self, monkeypatch, tmp_path):
        dc = self._make_sandbox(monkeypatch, tmp_path)
        from eqlib.data_cache import _local_csv_path
        p = _local_csv_path("601390")
        assert p.resolve().is_relative_to(dc.resolve())

    def test_dotdot_raises_valueerror(self, monkeypatch, tmp_path):
        self._make_sandbox(monkeypatch, tmp_path)
        from eqlib.data_cache import _local_csv_path
        with pytest.raises(ValueError, match="outside of data directory"):
            _local_csv_path("../../tmp/poc")

    def test_absolute_code_raises(self, monkeypatch, tmp_path):
        self._make_sandbox(monkeypatch, tmp_path)
        from eqlib.data_cache import _local_csv_path
        with pytest.raises(ValueError, match="outside of data directory"):
            _local_csv_path("/etc/passwd")

    def test_embedded_slash_raises(self, monkeypatch, tmp_path):
        self._make_sandbox(monkeypatch, tmp_path)
        from eqlib.data_cache import _local_csv_path
        with pytest.raises(ValueError, match="outside of data directory"):
            _local_csv_path("601390/../../evil")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-10: delete_run rmtree validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker10DeleteRunRmtreeValidation:
    """delete_run must only delete artifacts under the reports directory."""

    @pytest.fixture
    def app_setup(self, tmp_path):
        """Set up a minimal test environment with settings pointing to tmp."""
        import studio_api.config as cfg
        cfg.settings.artifact_dir = tmp_path / "artifacts"
        cfg.settings.artifact_dir.mkdir(parents=True, exist_ok=True)
        (cfg.settings.artifact_dir / "reports").mkdir(exist_ok=True)

    @pytest.mark.asyncio
    async def test_delete_run_only_deletes_within_reports(self, tmp_path, app_setup):
        """If html_path is poisoned to point outside reports, deletion is skipped."""
        from unittest.mock import AsyncMock, patch, MagicMock
        from pathlib import Path

        import studio_api.config as cfg
        import studio_api.routers.runs as runs_router

        reports_root = cfg.settings.artifact_dir / "reports"
        # Create a decoy directory outside reports
        decoy = tmp_path / "decoy"
        decoy.mkdir()
        (decoy / "secret.txt").write_text("sensitive")

        # Create a fake run with poisoned html_path
        run_id = str(uuid.uuid4())
        run = MagicMock()
        run.id = run_id
        run.status = "failed"
        run.html_path = str(decoy / "report.html")

        mock_session = AsyncMock()
        mock_session.get.return_value = run

        # Run the delete
        result = await runs_router.delete_run(run_id, session=mock_session)

        # Verify decoy directory was NOT deleted
        assert (decoy / "secret.txt").exists(), (
            "delete_run should NOT have deleted files outside reports directory"
        )

    @pytest.mark.asyncio
    async def test_delete_run_deletes_valid_reports_dir(self, tmp_path, app_setup):
        """Valid html_path should have its artifacts deleted normally."""
        from unittest.mock import AsyncMock, MagicMock
        from pathlib import Path
        import shutil

        import studio_api.config as cfg
        import studio_api.routers.runs as runs_router

        reports_root = cfg.settings.artifact_dir / "reports"
        run_id = str(uuid.uuid4())
        report_dir = reports_root / run_id
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.html").write_text("<html></html>")

        run = MagicMock()
        run.id = run_id
        run.status = "succeeded"
        run.html_path = f"/static/reports/{run_id}/report.html"

        mock_session = AsyncMock()
        mock_session.get.return_value = run

        result = await runs_router.delete_run(run_id, session=mock_session)

        # The report directory should have been deleted
        assert not report_dir.exists(), (
            "delete_run should have deleted the valid reports directory"
        )
