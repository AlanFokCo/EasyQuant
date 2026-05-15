"""Lint: syntax, ruff, security scanner."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from studio_api.security_scanner import SecurityScanner, require_initialize_function

PROFILE_FAST = "fast"
PROFILE_STRICT = "strict"


def _syntax_errors(source: str) -> list[dict]:
    out: list[dict] = []
    try:
        compile(source, "<strategy>", "exec", ast.PyCF_ONLY_AST)
    except SyntaxError as e:
        out.append(
            {
                "line": e.lineno or 1,
                "col": e.offset or 0,
                "message": e.msg or "invalid syntax",
                "severity": "error",
            }
        )
    return out


def _ruff_issues(source: str, timeout: float = 15.0) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(source)
        tmp = f.name
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", tmp, "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    finally:
        Path(tmp).unlink(missing_ok=True)
    if not proc.stdout.strip():
        return []
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    issues = []
    for item in raw:
        code = item.get("code", "RUFF")
        issues.append(
            {
                "code": code,
                "line": item.get("location", {}).get("row", 1),
                "col": item.get("location", {}).get("column", 1),
                "message": item.get("message", ""),
                # B23: ruff F/W codes are warnings, not errors.
                "severity": "warning",
            }
        )
    return issues


def lint_source(source: str, profile: str = PROFILE_FAST) -> dict:
    syntax_errors = _syntax_errors(source)
    scanner = SecurityScanner()
    sec = scanner.scan(source)
    sec.extend(require_initialize_function(source))

    security_notes = [{"code": n.code, "line": n.line, "message": n.message} for n in sec]

    lint_issues: list[dict] = []
    if not syntax_errors:
        lint_issues = _ruff_issues(source)

    # B23: ok=False only for syntax errors and EQ-BANNED-* security notes.
    # EQ-IMPORT-WARN and ruff codes are warnings: ok stays True but they
    # appear in lint_issues / security_notes for the frontend to display.
    blocking_security = any(n["code"].startswith("EQ-BANNED") for n in security_notes)
    ok = not syntax_errors and not blocking_security

    return {
        "ok": ok,
        "syntax_errors": syntax_errors,
        "lint_issues": lint_issues,
        "security_notes": security_notes,
    }
