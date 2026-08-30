"""Contract-runner evidence and profile semantics regression tests."""

from __future__ import annotations

from pathlib import Path
import subprocess

from evaluator.contracts import run_live_contracts, run_offline_contracts
from evaluator.models import Severity


ROOT = Path(__file__).resolve().parents[2]


def test_live_profile_reports_missing_network_contracts_as_visible_advisory(
    monkeypatch,
):
    monkeypatch.setattr(
        "evaluator.contracts.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=5,
            stdout="no tests collected (10 deselected)\n",
            stderr="",
        ),
    )

    findings = run_live_contracts(ROOT)

    assert [(item.id, item.severity) for item in findings] == [("CON-002", Severity.P1)]
    assert findings[0].evidence["selector"] == ["-m", "network"]


def test_contract_failure_keeps_failed_node_ids_when_stdout_is_truncated(monkeypatch):
    failure_node = "tests/test_data_utils.py::TestDataUtils::test_contract_failure"
    output = ("x" * 5_000) + f"\nFAILED {failure_node} - expected failure\n"
    monkeypatch.setattr(
        "evaluator.contracts.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout=output, stderr=""
        ),
    )

    finding = run_offline_contracts(ROOT)[0]

    assert finding.id == "CON-001"
    assert finding.evidence["failed_node_ids"] == [failure_node]
    assert "FAILED " + failure_node in finding.evidence["stdout"]


def test_live_timeout_is_unavailable_and_sets_live_environment(monkeypatch):
    captured = {}

    def expire(*args, **kwargs):
        captured.update(kwargs)
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("evaluator.contracts.subprocess.run", expire)

    finding = run_live_contracts(ROOT)[0]

    assert (finding.id, finding.status) == ("DATA-190", "unavailable")
    assert captured["timeout"] == 90
    assert captured["env"]["EQLIB_EVALUATOR_LIVE"] == "1"


def test_offline_contracts_exclude_network_marked_tests(monkeypatch):
    captured = {}

    def successful(*args, **kwargs):
        captured["command"] = args[0]
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("evaluator.contracts.subprocess.run", successful)

    assert run_offline_contracts(ROOT) == []
    assert "not network" in captured["command"]
