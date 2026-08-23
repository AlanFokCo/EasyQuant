"""Pytest contract execution for evaluator profiles."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence

from .models import Finding, Severity


_CONTRACT_TIMEOUT_SECONDS = 180
_OFFLINE_NODE_IDS = ("tests/test_imports.py", "tests/test_data_utils.py")
_LIVE_MARKER = "network"
_NO_TESTS_COLLECTED_RETURN_CODE = 5
_FAILED_NODE_ID = re.compile(r"^FAILED\s+([^\s]+)", re.MULTILINE)


def run_offline_contracts(root: Path) -> list[Finding]:
    """Run deterministic contracts that are required not to contact providers."""
    return _run_pytest_contract(root, "offline", _OFFLINE_NODE_IDS)


def run_live_contracts(root: Path) -> list[Finding]:
    """Run explicitly marked provider contracts only in the live profile."""
    return _run_pytest_contract(root, "live", ("-m", _LIVE_MARKER))


def _run_pytest_contract(
    root: Path, profile: str, selectors: Sequence[str]
) -> list[Finding]:
    command = (sys.executable, "-m", "pytest", *selectors, "-q")
    try:
        completed = subprocess.run(
            command,
            cwd=Path(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_CONTRACT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return [_contract_failure(profile, command, None, exc.stdout, exc.stderr, True)]

    if completed.returncode == 0:
        return []
    if profile == "live" and completed.returncode == _NO_TESTS_COLLECTED_RETURN_CODE:
        return [
            _missing_live_contracts(
                command, selectors, completed.stdout, completed.stderr
            )
        ]
    return [
        _contract_failure(
            profile,
            command,
            completed.returncode,
            completed.stdout,
            completed.stderr,
            False,
        )
    ]


def _contract_failure(
    profile: str,
    command: Sequence[str],
    returncode: int | None,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    timed_out: bool,
) -> Finding:
    """Convert one bounded pytest failure into a visible evaluator finding."""
    evidence = {
        "profile": profile,
        "command": list(command),
        "selector": list(command[3:-1]),
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout": _bounded_text(stdout),
        "stderr": _bounded_text(stderr),
        "failed_node_ids": _failed_node_ids(stdout, stderr),
    }
    detail = (
        "pytest contract exceeded its total deadline"
        if timed_out
        else "pytest contract failed"
    )
    return Finding(
        "CON-001",
        Severity.P1,
        f"{profile.capitalize()} pytest contract failed",
        detail,
        evidence=evidence,
        remediation="Fix the failing contract before accepting this evaluator run.",
    )


def _missing_live_contracts(
    command: Sequence[str],
    selectors: Sequence[str],
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> Finding:
    """Fail closed when the live profile has no explicitly registered contracts."""
    return Finding(
        "CON-002",
        Severity.P1,
        "No live pytest contracts are registered",
        "pytest selected no tests for the required network marker",
        evidence={
            "command": list(command),
            "selector": list(selectors),
            "returncode": _NO_TESTS_COLLECTED_RETURN_CODE,
            "stdout": _bounded_text(stdout),
            "stderr": _bounded_text(stderr),
            "failed_node_ids": [],
        },
        remediation="Register at least one bounded pytest.mark.network contract before using the live profile.",
    )


def _failed_node_ids(
    stdout: str | bytes | None, stderr: str | bytes | None
) -> list[str]:
    """Extract unique pytest summary node IDs before bounded rendering truncates logs."""
    text = _coerce_text(stdout) + "\n" + _coerce_text(stderr)
    return list(dict.fromkeys(_FAILED_NODE_ID.findall(text)))


def _bounded_text(value: str | bytes | None, limit: int = 4_000) -> str:
    """Retain actionable failure evidence without unbounded report artifacts."""
    value = _coerce_text(value)
    if len(value) <= limit:
        return value
    preserved = (limit - 80) // 2
    omitted = len(value) - (preserved * 2)
    return (
        f"{value[:preserved]}\n"
        f"... [{omitted} characters truncated] ...\n"
        f"{value[-preserved:]}"
    )


def _coerce_text(value: str | bytes | None) -> str:
    """Decode subprocess evidence without allowing an exception to hide a finding."""
    if value is None:
        return ""
    return (
        value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    )
