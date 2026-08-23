"""Public evaluator CLI and profile-routing regression tests."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from evaluator.models import Finding, Severity
from evaluator.runner import run_evaluation


ROOT = Path(__file__).resolve().parents[2]


def test_runner_returns_nonzero_for_strict_p0(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "evaluator.runner.collect_findings",
        lambda *args: [Finding("NUM-201", Severity.P0, "bad", "bad")],
    )

    report, exit_code = run_evaluation(ROOT, "offline", tmp_path, strict=True)

    assert exit_code == 1
    assert [finding.id for finding in report.findings] == ["NUM-201"]
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()


def test_runner_keeps_p2_visible_without_non_strict_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "evaluator.runner.collect_findings",
        lambda *args: [Finding("PERF-301", Severity.P2, "slow", "slow")],
    )

    report, exit_code = run_evaluation(ROOT, "offline", tmp_path, strict=False)

    assert exit_code == 0
    assert [finding.id for finding in report.findings] == ["PERF-301"]
    assert (
        json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["findings"][
            0
        ]["id"]
        == "PERF-301"
    )


def test_runner_rejects_unknown_profile(tmp_path):
    with pytest.raises(ValueError, match="Unsupported profile"):
        run_evaluation(ROOT, "unsupported", tmp_path, strict=False)


def test_live_profile_adds_live_contract_findings_only_for_live(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("evaluator.runner.evaluate_inventory", lambda root: [])
    monkeypatch.setattr(
        "evaluator.runner.build_and_audit_wheel", lambda root, work_dir: ({}, [])
    )
    monkeypatch.setattr(
        "evaluator.runner.run_offline_contracts",
        lambda root: calls.append("offline") or [],
    )
    monkeypatch.setattr(
        "evaluator.runner.run_live_contracts", lambda root: calls.append("live") or []
    )

    from evaluator.runner import collect_findings

    assert collect_findings(ROOT, "offline") == []
    assert calls == ["offline"]
    assert collect_findings(ROOT, "live") == []
    assert calls == ["offline", "offline", "live"]


def test_cli_runs_from_repository_root_without_an_editable_install():
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_eqlib_dependencies.py", "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Audit eqlib dependency contracts" in result.stdout
