"""Stable JSON and Markdown rendering for evaluator reports."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import EvaluationReport, Finding


def write_report(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    """Atomically write machine-readable and human-readable report artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"

    json_content = (
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    _atomic_write(json_path, json_content)
    _atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path


def render_markdown(report: EvaluationReport) -> str:
    """Render the report's canonical ordering as readable Markdown."""
    lines = [
        "# eqlib Dependency Evaluator Report",
        "",
        f"- Profile: `{report.profile}`",
        f"- Started at: `{report.started_at}`",
        "",
        "## Environment",
        "",
    ]
    lines.extend(
        f"- `{name}`: `{value}`" for name, value in sorted(report.environment.items())
    )
    lines.extend(["", "## Findings", ""])

    findings = report.ordered_findings()
    if not findings:
        lines.append("No findings.")

    for finding in findings:
        lines.extend(
            [
                f"### {finding.id}: {finding.title}",
                "",
                f"- Severity: `{finding.severity.value}`",
                f"- Status: `{finding.status}`",
                f"- Detail: {finding.detail}",
                "- Evidence: "
                + json.dumps(finding.evidence, ensure_ascii=False, sort_keys=True),
            ]
        )
        if finding.remediation is not None:
            lines.append(f"- Remediation: {finding.remediation}")
        lines.append("")

    return "\n".join(lines) + "\n"


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    """Return the JSON-compatible representation shared by both artifacts."""
    return {
        "profile": report.profile,
        "started_at": report.started_at,
        "environment": report.environment,
        "findings": [finding_to_dict(item) for item in report.ordered_findings()],
    }


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Return a JSON-compatible representation of a finding."""
    return {
        "id": finding.id,
        "severity": finding.severity.value,
        "title": finding.title,
        "detail": finding.detail,
        "evidence": finding.evidence,
        "remediation": finding.remediation,
        "status": finding.status,
    }


def _atomic_write(path: Path, content: str) -> None:
    """Replace *path* only after its complete UTF-8 content reaches disk."""
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
