"""Pytest contract execution for evaluator profiles."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Sequence

from .models import Finding, Severity


_CONTRACT_TIMEOUT_SECONDS = 180
_OFFLINE_NODE_IDS = ("tests/test_imports.py", "tests/test_data_utils.py")
_LIVE_MARKER = "network"


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
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout": _bounded_text(stdout),
        "stderr": _bounded_text(stderr),
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


def _bounded_text(value: str | bytes | None, limit: int = 4_000) -> str:
    """Retain actionable failure evidence without unbounded report artifacts."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if len(value) <= limit:
        return value
    omitted = len(value) - limit
    return f"{value[:limit]}\n... [{omitted} characters truncated] ..."
