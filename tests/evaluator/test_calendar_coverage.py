"""Bundled A-share calendar freshness contracts."""

from __future__ import annotations

from datetime import date
import json

from evaluator.calendar import evaluate_calendar_coverage
from evaluator.models import Severity


def _write_calendar(root, end: str) -> None:
    resource = root / "eqlib" / "static" / "ashare_trading_days.json"
    resource.parent.mkdir(parents=True)
    resource.write_text(json.dumps({"coverage": {"end": end}}), encoding="utf-8")


def test_calendar_coverage_warns_before_the_release_horizon(tmp_path):
    _write_calendar(tmp_path, "2026-12-31")

    findings = evaluate_calendar_coverage(
        tmp_path, today=date(2026, 9, 3), warning_days=120
    )

    assert [(item.id, item.severity) for item in findings] == [
        ("DATA-192", Severity.P2)
    ]


def test_calendar_coverage_escalates_when_coverage_has_expired(tmp_path):
    _write_calendar(tmp_path, "2026-09-02")

    findings = evaluate_calendar_coverage(
        tmp_path, today=date(2026, 9, 3), warning_days=120
    )

    assert [(item.id, item.severity) for item in findings] == [
        ("DATA-192", Severity.P1)
    ]
    assert "expired" in findings[0].title.lower()
    assert "expired" in findings[0].detail.lower()


def test_calendar_coverage_ending_today_is_not_yet_expired(tmp_path):
    _write_calendar(tmp_path, "2026-09-03")

    findings = evaluate_calendar_coverage(
        tmp_path, today=date(2026, 9, 3), warning_days=120
    )

    assert [(item.id, item.severity) for item in findings] == [
        ("DATA-192", Severity.P2)
    ]


def test_invalid_calendar_metadata_is_blocking(tmp_path):
    _write_calendar(tmp_path, "not-a-date")

    findings = evaluate_calendar_coverage(tmp_path, today=date(2026, 9, 2))

    assert [(item.id, item.severity) for item in findings] == [
        ("DATA-191", Severity.P1)
    ]
