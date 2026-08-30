"""Performance evaluator contracts."""

from __future__ import annotations

from pathlib import Path

from evaluator.benchmarks import (
    BenchmarkSample,
    _parse_time_output,
    evaluate_benchmarks,
)
from evaluator.models import Severity


ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_marks_twofold_regression_as_p2(monkeypatch):
    monkeypatch.setattr(
        "evaluator.benchmarks._samples",
        lambda *args: [
            BenchmarkSample(seconds=2.1, max_rss_mb=101.0),
            BenchmarkSample(seconds=2.2, max_rss_mb=102.0),
            BenchmarkSample(seconds=2.3, max_rss_mb=103.0),
        ],
    )
    baseline = {"import_eqlib": {"seconds": 1.0, "max_rss_mb": 100.0}}

    findings = evaluate_benchmarks(ROOT, baseline)

    assert any(
        item.id == "PERF-301" and item.severity is Severity.P2 for item in findings
    )


def test_benchmark_without_measurement_tool_is_unavailable(monkeypatch):
    monkeypatch.setattr("evaluator.benchmarks._samples", lambda *args: None)
    baseline = {"import_eqlib": {"seconds": 1.0, "max_rss_mb": 100.0}}

    findings = evaluate_benchmarks(ROOT, baseline)

    assert [(item.id, item.status) for item in findings] == [
        ("PERF-302", "unavailable")
    ]


def test_macos_time_parser_accepts_aligned_resource_output():
    sample = _parse_time_output(
        "        0.71 real         0.56 user\n"
        "           126124032  maximum resident set size\n"
    )

    assert sample == BenchmarkSample(seconds=0.71, max_rss_mb=120.28125)
