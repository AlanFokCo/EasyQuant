"""Tests for the runner._enrich_result URL generation fix.

Verifies that:
- html_report_url and json_report_url use /api/v1/reports/ (not /static/reports/)
- run_id is included in the enriched payload
- Failed results still get null URLs
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio_api.runner import _enrich_result


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """Create a temporary artifact directory with report files."""
    run_dir = tmp_path / "reports" / "test-run-123"
    run_dir.mkdir(parents=True)
    (run_dir / "report.html").write_text("<html><body>test report</body></html>")
    (run_dir / "report.json").write_text('{"metrics": {"total_return": 0.15}}')
    return tmp_path / "reports" / "test-run-123"


class TestEnrichResultUrls:
    """URL generation must use /api/v1/reports/ path."""

    def test_html_report_url_uses_api_path(self, artifact_dir: Path):
        """html_report_url must use /api/v1/reports/ prefix."""
        result = _enrich_result({"ok": True}, artifact_dir, "test-run-123")
        assert result["html_report_url"] == "/api/v1/reports/test-run-123/report.html"

    def test_json_report_url_uses_api_path(self, artifact_dir: Path):
        """json_report_url must use /api/v1/reports/ prefix."""
        result = _enrich_result({"ok": True}, artifact_dir, "test-run-123")
        assert result["json_report_url"] == "/api/v1/reports/test-run-123/report.json"

    def test_no_static_path_in_urls(self, artifact_dir: Path):
        """URLs must never contain /static/reports/."""
        result = _enrich_result({"ok": True}, artifact_dir, "test-run-123")
        assert "/static/" not in (result.get("html_report_url") or "")
        assert "/static/" not in (result.get("json_report_url") or "")

    def test_run_id_included_in_payload(self, artifact_dir: Path):
        """run_id must be present in the enriched result."""
        result = _enrich_result({"ok": True}, artifact_dir, "test-run-123")
        assert result["run_id"] == "test-run-123"

    def test_missing_report_html_sets_error(self, tmp_path: Path):
        """When report.html doesn't exist, ok=False and error is set."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = _enrich_result({"ok": True}, empty_dir, "no-report-run")
        assert result["ok"] is False
        assert result["error_code"] == "REPORT_MISSING"
        assert result["html_report_url"] is None

    def test_missing_report_json_url_is_null(self, tmp_path: Path):
        """When only report.html exists (no json), json_report_url is None."""
        run_dir = tmp_path / "html-only"
        run_dir.mkdir()
        (run_dir / "report.html").write_text("<html></html>")
        result = _enrich_result({"ok": True}, run_dir, "html-only-run")
        assert result["html_report_url"] is not None
        assert result["json_report_url"] is None

    def test_failed_result_gets_null_urls(self, tmp_path: Path):
        """When ok=False, URLs default to None."""
        result = _enrich_result({"ok": False, "error": "some error"}, tmp_path, "failed-run")
        assert result["html_report_url"] is None
        assert result["json_report_url"] is None
        assert result["run_id"] == "failed-run"

    def test_run_id_always_set(self, tmp_path: Path):
        """run_id must be set regardless of ok status."""
        for ok_val in [True, False]:
            result = _enrich_result({"ok": ok_val}, tmp_path, "run-abc")
            assert result["run_id"] == "run-abc"
