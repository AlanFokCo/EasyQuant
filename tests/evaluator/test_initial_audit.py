"""The published initial audit must not assert unresolved blocking findings."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_initial_audit_has_no_open_blocking_findings():
    report = ROOT / "reports" / "evaluator" / "2026-08-30-initial-audit.json"
    findings = json.loads(report.read_text(encoding="utf-8"))["findings"]

    assert not [
        finding
        for finding in findings
        if finding["severity"] in {"P0", "P1"} and finding["status"] == "open"
    ]
