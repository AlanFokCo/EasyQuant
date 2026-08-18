"""Tests for evaluator report rendering and persistence."""

import json
from pathlib import Path

from evaluator.models import EvaluationReport, Finding, Severity
from evaluator.report import render_markdown, write_report


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


def test_write_report_normalizes_nonfinite_evidence_for_strict_json(tmp_path):
    report = EvaluationReport.create(
        profile="offline",
        findings=[
            Finding(
                "DATA-101",
                Severity.P0,
                "nonfinite evidence",
                "details",
                evidence={
                    "infinite": float("inf"),
                    "nan": float("nan"),
                    "negative_infinite": float("-inf"),
                },
            )
        ],
    )

    json_path, _ = write_report(report, tmp_path)

    def reject_nonstandard_constant(value):
        raise ValueError(f"non-standard JSON constant: {value}")

    payload = json.loads(
        json_path.read_text(encoding="utf-8"),
        parse_constant=reject_nonstandard_constant,
    )
    assert payload["findings"][0]["evidence"] == {
        "infinite": {"$type": "nonfinite_float", "value": "Infinity"},
        "nan": {"$type": "nonfinite_float", "value": "NaN"},
        "negative_infinite": {"$type": "nonfinite_float", "value": "-Infinity"},
    }


def test_write_report_normalizes_non_json_evidence(tmp_path):
    report = EvaluationReport.create(
        profile="offline",
        findings=[
            Finding(
                "DEP-003",
                Severity.P1,
                "path evidence",
                "details",
                evidence={"artifact": Path("fixtures/raw-payload.json")},
            )
        ],
    )

    json_path, _ = write_report(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["findings"][0]["evidence"] == {
        "artifact": {
            "$type": "path",
            "value": "fixtures/raw-payload.json",
        }
    }


def test_write_report_marks_cyclic_evidence_explicitly(tmp_path):
    evidence = {}
    evidence["self"] = evidence
    report = EvaluationReport.create(
        profile="offline",
        findings=[
            Finding(
                "DEP-005",
                Severity.P1,
                "cyclic evidence",
                "details",
                evidence=evidence,
            )
        ],
    )

    json_path, _ = write_report(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["findings"][0]["evidence"] == {
        "self": {
            "$type": "cycle",
            "python_type": "builtins.dict",
        }
    }


def test_write_report_marks_lone_unicode_surrogates_explicitly(tmp_path):
    report = EvaluationReport.create(
        profile="offline",
        findings=[
            Finding(
                "DEP-006",
                Severity.P1,
                "invalid unicode evidence",
                "details",
                evidence={"bad": "prefix\ud800suffix"},
            )
        ],
    )

    json_path, markdown_path = write_report(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["findings"][0]["evidence"] == {
        "bad": {
            "$type": "invalid_unicode",
            "value": "prefix\\ud800suffix",
        }
    }
    assert "invalid_unicode" in markdown_path.read_text(encoding="utf-8")


def test_render_markdown_bounds_untrusted_finding_content():
    report = EvaluationReport(
        profile="offline",
        started_at="2026-08-18T00:00:00+00:00",
        environment={"python": "3.10"},
        findings=[
            Finding(
                "DEP-004",
                Severity.P1,
                "title\n### injected title\n<script>alert(1)</script>",
                "detail\n## injected detail\n<div>unsafe detail</div>",
                evidence={
                    "html": "<img src=x onerror=alert(1)>",
                    "heading": "# injected evidence",
                },
            )
        ],
    )

    markdown = render_markdown(report)

    assert [line for line in markdown.splitlines() if line.startswith("#")] == [
        "# eqlib Dependency Evaluator Report",
        "## Run",
        "## Environment",
        "## Findings",
        "### Finding 1",
    ]
    assert all(not line.startswith("<") for line in markdown.splitlines())
    assert "    ### injected title" in markdown
    assert "    <script>alert(1)</script>" in markdown
    assert "    ## injected detail" in markdown
    assert "    <div>unsafe detail</div>" in markdown
    assert '      "html": "<img src=x onerror=alert(1)>"' in markdown
