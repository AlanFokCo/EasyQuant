"""Tests for evaluator report rendering and persistence."""

import json

from evaluator.models import EvaluationReport, Finding, Severity
from evaluator.report import write_report


def test_write_report_orders_findings_and_keeps_same_ids(tmp_path):
    report = EvaluationReport.create(
        profile="offline",
        findings=[
            Finding("DEP-002", Severity.P2, "secondary", "details"),
            Finding("DATA-101", Severity.P0, "critical", "details"),
        ],
    )

    json_path, markdown_path = write_report(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert [item["id"] for item in payload["findings"]] == ["DATA-101", "DEP-002"]
    assert "# eqlib Dependency Evaluator Report" in markdown_path.read_text(
        encoding="utf-8"
    )
