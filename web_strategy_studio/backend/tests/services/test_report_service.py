"""Tests for ReportService — comparison, export, and single-report helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio_api.services.report_service import ReportService


@pytest.fixture
def svc(tmp_path: Path) -> ReportService:
    """Create a ReportService backed by a temp artifact dir."""
    return ReportService(artifact_dir=tmp_path)


def _create_report(svc: ReportService, run_id: str, data: dict) -> Path:
    """Helper: write a report.json into the service's artifact dir."""
    report_dir = svc.artifact_dir / "reports" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(data))
    (report_dir / "report.html").write_text("<html>report</html>")
    return report_dir


# ------------------------------------------------------------------
# Single-report helpers
# ------------------------------------------------------------------


class TestLoadReportJson:
    def test_load_existing_report(self, svc: ReportService):
        _create_report(svc, "run-1", {"metrics": {"total_return": 0.15}})
        data = svc.load_report_json("run-1")
        assert data is not None
        assert data["metrics"]["total_return"] == 0.15

    def test_load_missing_report(self, svc: ReportService):
        assert svc.load_report_json("nonexistent") is None

    def test_load_corrupt_json(self, svc: ReportService):
        report_dir = svc.artifact_dir / "reports" / "bad"
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text("not valid json {")
        with pytest.raises(json.JSONDecodeError):
            svc.load_report_json("bad")


class TestGetReportPath:
    def test_existing_file(self, svc: ReportService):
        _create_report(svc, "run-a", {})
        path = svc.get_report_path("run-a", "report.html")
        assert path is not None
        assert path.name == "report.html"

    def test_missing_file(self, svc: ReportService):
        assert svc.get_report_path("run-a", "report.html") is None


# ------------------------------------------------------------------
# Comparison
# ------------------------------------------------------------------


class TestCompareReports:
    def test_basic_comparison(self, svc: ReportService):
        _create_report(svc, "r1", {"metrics": {"total_return": 0.10, "sharpe_ratio": 1.2}})
        _create_report(svc, "r2", {"metrics": {"total_return": 0.20, "sharpe_ratio": 1.8}})
        result = svc.compare_reports(["r1", "r2"])

        assert "reports" in result
        assert "differences" in result
        assert len(result["reports"]) == 2

        diff = result["differences"]
        assert diff["total_return"]["max"] == 0.20
        assert diff["total_return"]["min"] == 0.10
        assert abs(diff["total_return"]["diff"] - 0.10) < 1e-6

    def test_comparison_requires_two_reports(self, svc: ReportService):
        result = svc.compare_reports(["single-run"])
        assert "error" in result

    def test_comparison_with_missing_reports(self, svc: ReportService):
        _create_report(svc, "r1", {"metrics": {"total_return": 0.10}})
        result = svc.compare_reports(["r1", "nonexistent"])
        assert "error" in result
        assert result["loaded"] == 1

    def test_comparison_includes_run_id(self, svc: ReportService):
        _create_report(svc, "r1", {"metrics": {}})
        _create_report(svc, "r2", {"metrics": {}})
        result = svc.compare_reports(["r1", "r2"])
        run_ids = [r["run_id"] for r in result["reports"]]
        assert "r1" in run_ids
        assert "r2" in run_ids

    def test_differences_calculation(self, svc: ReportService):
        _create_report(svc, "a", {"metrics": {"max_drawdown": -0.05, "annual_return": 0.12}})
        _create_report(svc, "b", {"metrics": {"max_drawdown": -0.15, "annual_return": 0.25}})
        result = svc.compare_reports(["a", "b"])
        diff = result["differences"]

        assert diff["max_drawdown"]["max"] == -0.05
        assert diff["max_drawdown"]["min"] == -0.15
        assert abs(diff["annual_return"]["diff"] - 0.13) < 1e-6

    def test_comparison_handles_top_level_metrics(self, svc: ReportService):
        """Reports may store metrics at the top level (no 'metrics' key)."""
        _create_report(svc, "x", {"total_return": 0.08})
        _create_report(svc, "y", {"total_return": 0.12})
        result = svc.compare_reports(["x", "y"])
        assert "total_return" in result["differences"]


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------


class TestExport:
    def test_export_html(self, svc: ReportService):
        _create_report(svc, "run-exp", {"metrics": {}})
        path = svc.get_export_path("run-exp", "html")
        assert path is not None
        assert path.suffix == ".html"
        assert path.is_file()

    def test_export_json(self, svc: ReportService):
        _create_report(svc, "run-exp", {"metrics": {}})
        path = svc.get_export_path("run-exp", "json")
        assert path is not None
        assert path.suffix == ".json"

    def test_export_unsupported_format(self, svc: ReportService):
        _create_report(svc, "run-exp", {"metrics": {}})
        assert svc.get_export_path("run-exp", "docx") is None

    def test_export_missing_run(self, svc: ReportService):
        assert svc.get_export_path("missing", "html") is None

    def test_export_pdf_not_generated(self, svc: ReportService):
        """PDF is not yet auto-generated, so path should be None."""
        _create_report(svc, "run-exp", {"metrics": {}})
        assert svc.get_export_path("run-exp", "pdf") is None


# ------------------------------------------------------------------
# List available runs
# ------------------------------------------------------------------


class TestListAvailableRuns:
    def test_list_runs(self, svc: ReportService):
        _create_report(svc, "run-b", {})
        _create_report(svc, "run-a", {})
        runs = svc.list_available_runs()
        assert runs == ["run-a", "run-b"]  # sorted

    def test_empty_list(self, svc: ReportService):
        assert svc.list_available_runs() == []

    def test_ignores_runs_without_html(self, svc: ReportService):
        """Runs with only report.json but no report.html should not appear."""
        report_dir = svc.artifact_dir / "reports" / "incomplete"
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text("{}")
        assert svc.list_available_runs() == []
