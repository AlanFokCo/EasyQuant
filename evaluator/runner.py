"""Top-level orchestration for the eqlib dependency evaluator."""

from __future__ import annotations

from pathlib import Path
import tempfile

from .contracts import run_live_contracts, run_offline_contracts
from .inventory import evaluate_inventory
from .models import EvaluationReport, Finding, Severity
from .report import write_report
from .wheel import build_and_audit_wheel


_PROFILES = frozenset(("offline", "live"))
_BLOCKING_SEVERITIES = frozenset((Severity.P0, Severity.P1))


def run_evaluation(
    root: Path, profile: str, output_dir: Path, strict: bool
) -> tuple[EvaluationReport, int]:
    """Collect findings, persist a report, and return the policy exit code."""
    if profile not in _PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")
    report = EvaluationReport.create(
        profile=profile, findings=collect_findings(root, profile)
    )
    write_report(report, output_dir)
    blocking = strict and any(
        finding.severity in _BLOCKING_SEVERITIES for finding in report.findings
    )
    return report, int(blocking)


def collect_findings(root: Path, profile: str) -> list[Finding]:
    """Collect profile-independent evidence before the selected pytest contracts."""
    root = Path(root).resolve()
    findings = list(evaluate_inventory(root))
    with tempfile.TemporaryDirectory(prefix="eqlib-evaluator-wheel-") as work_dir:
        _, wheel_findings = build_and_audit_wheel(root, Path(work_dir))
    findings.extend(wheel_findings)
    findings.extend(run_offline_contracts(root))
    if profile == "live":
        findings.extend(run_live_contracts(root))
    return findings
