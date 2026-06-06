"""Report service — report retrieval, comparison, and export.

Encapsulates all report-related business logic so that the router stays thin.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReportService:
    """Service for report operations.

    Parameters
    ----------
    artifact_dir:
        Root artifact directory (``settings.artifact_dir``).  Reports live
        under ``<artifact_dir>/reports/<run_id>/``.
    """

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir

    # ------------------------------------------------------------------
    # Single-report helpers
    # ------------------------------------------------------------------

    def _report_dir(self, run_id: str) -> Path:
        return self.artifact_dir / "reports" / run_id

    def get_report_path(self, run_id: str, filename: str) -> Optional[Path]:
        """Return the absolute path to a report file, or *None* if missing."""
        path = self._report_dir(run_id) / filename
        if path.is_file():
            return path
        return None

    def load_report_json(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load and parse ``report.json`` for *run_id*."""
        path = self.get_report_path(run_id, "report.json")
        if path is None:
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_reports(self, run_ids: List[str]) -> Dict[str, Any]:
        """Compare metrics across multiple runs.

        Returns a dict with ``reports`` (list of per-run data) and
        ``differences`` (per-metric max / min / diff).
        """
        if len(run_ids) < 2:
            return {"error": "At least 2 reports required for comparison"}

        reports: List[Dict[str, Any]] = []
        for run_id in run_ids:
            data = self.load_report_json(run_id)
            if data is not None:
                reports.append({"run_id": run_id, **data})

        if len(reports) < 2:
            return {
                "error": "Could not load enough reports for comparison",
                "loaded": len(reports),
            }

        return {
            "reports": reports,
            "differences": self._calculate_differences(reports),
        }

    @staticmethod
    def _calculate_differences(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute per-metric statistics across reports."""
        metric_keys = [
            "total_return",
            "annual_return",
            "annualized_return",
            "sharpe_ratio",
            "max_drawdown",
            "sortino_ratio",
            "calmar_ratio",
            "win_rate",
        ]
        differences: Dict[str, Any] = {}
        for key in metric_keys:
            values: List[float] = []
            for report in reports:
                # metrics may live under report["metrics"] or at the top level
                metrics = report.get("metrics", report)
                val = metrics.get(key)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (TypeError, ValueError):
                        pass
            if values:
                differences[key] = {
                    "values": values,
                    "max": max(values),
                    "min": min(values),
                    "diff": round(max(values) - min(values), 6),
                }
        return differences

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_export_path(self, run_id: str, fmt: str) -> Optional[Path]:
        """Return the file path for an export, or *None* if unavailable.

        Currently supported formats: ``html``, ``json``.
        PDF / PNG generation can be added later (ReportLab, Pillow).
        """
        filename_map = {
            "html": "report.html",
            "json": "report.json",
            "pdf": "report.pdf",
            "png": "report.png",
        }
        filename = filename_map.get(fmt)
        if filename is None:
            return None
        return self.get_report_path(run_id, filename)

    def list_available_runs(self) -> List[str]:
        """Return run IDs that have a report directory."""
        reports_root = self.artifact_dir / "reports"
        if not reports_root.is_dir():
            return []
        return sorted(
            d.name
            for d in reports_root.iterdir()
            if d.is_dir() and (d / "report.html").is_file()
        )
