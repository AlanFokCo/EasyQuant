"""Stable JSON and Markdown rendering for evaluator reports."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
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

    json_content = _json_dump(report_to_dict(report), indent=2) + "\n"
    _atomic_write(json_path, json_content)
    _atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path


def render_markdown(report: EvaluationReport) -> str:
    """Render the report's canonical ordering as readable Markdown."""
    lines = ["# eqlib Dependency Evaluator Report", "", "## Run", ""]
    _append_field(lines, "Profile", report.profile)
    _append_field(lines, "Started at", report.started_at)
    lines.extend(["## Environment", ""])
    _append_code_block(lines, _json_dump(_json_safe(report.environment), indent=2))
    lines.extend(["", "## Findings", ""])

    findings = report.ordered_findings()
    if not findings:
        lines.append("No findings.")

    for index, finding in enumerate(findings, start=1):
        payload = finding_to_dict(finding)
        lines.extend([f"### Finding {index}", ""])
        _append_field(lines, "ID", payload["id"])
        _append_field(lines, "Severity", payload["severity"])
        _append_field(lines, "Status", payload["status"])
        _append_field(lines, "Title", payload["title"])
        _append_field(lines, "Detail", payload["detail"])
        _append_field(lines, "Evidence", _json_dump(payload["evidence"], indent=2))
        _append_field(lines, "Remediation", payload["remediation"])

    return "\n".join(lines) + "\n"


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    """Return the JSON-compatible representation shared by both artifacts."""
    return {
        "profile": _json_safe(report.profile),
        "started_at": _json_safe(report.started_at),
        "environment": _json_safe(report.environment),
        "findings": [finding_to_dict(item) for item in report.ordered_findings()],
    }


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Return a JSON-compatible representation of a finding."""
    return {
        "id": _json_safe(finding.id),
        "severity": finding.severity.value,
        "title": _json_safe(finding.title),
        "detail": _json_safe(finding.detail),
        "evidence": _json_safe(finding.evidence),
        "remediation": _json_safe(finding.remediation),
        "status": _json_safe(finding.status),
    }


def _json_safe(value: Any, active_ids: set[int] | None = None) -> Any:
    """Normalize arbitrary evidence into a deterministic, strict JSON value."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return _json_safe_string(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"$type": "nonfinite_float", "value": _nonfinite_float_label(value)}
    if isinstance(value, Path):
        return {"$type": "path", "value": _json_safe_string(value.as_posix())}
    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        active_ids = active_ids if active_ids is not None else set()
        value_id = id(value)
        if value_id in active_ids:
            return {"$type": "cycle", "python_type": _python_type_name(value)}

        active_ids.add(value_id)
        try:
            if isinstance(value, Mapping):
                return _json_safe_mapping(value, active_ids)
            if isinstance(value, list):
                return [_json_safe(item, active_ids) for item in value]
            if isinstance(value, tuple):
                return {
                    "$type": "tuple",
                    "items": [_json_safe(item, active_ids) for item in value],
                }
            return {
                "$type": "set",
                "items": _sorted_json_values(
                    [_json_safe(item, active_ids) for item in value]
                ),
            }
        finally:
            active_ids.remove(value_id)
    if isinstance(value, bytes):
        return {"$type": "bytes", "hex": value.hex()}
    return {"$type": "unsupported", "python_type": _python_type_name(value)}


def _json_safe_mapping(mapping: Mapping[Any, Any], active_ids: set[int]) -> Any:
    """Normalize mappings without silently coercing non-string JSON keys."""
    if all(isinstance(key, str) and not _contains_surrogate(key) for key in mapping):
        return {key: _json_safe(value, active_ids) for key, value in mapping.items()}

    items = [
        {"key": _json_safe(key, active_ids), "value": _json_safe(value, active_ids)}
        for key, value in mapping.items()
    ]
    return {"$type": "mapping", "items": _sorted_json_values(items)}


def _json_safe_string(value: str) -> Any:
    """Represent lone Unicode surrogates explicitly instead of emitting invalid UTF-8."""
    if not _contains_surrogate(value):
        return value
    return {
        "$type": "invalid_unicode",
        "value": _utf8_safe_text(value),
    }


def _contains_surrogate(value: str) -> bool:
    """Return whether *value* contains a Unicode surrogate code point."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _utf8_safe_text(value: str) -> str:
    """Escape invalid Unicode code points while preserving readable text."""
    return value.encode("utf-8", errors="backslashreplace").decode("utf-8")


def _nonfinite_float_label(value: float) -> str:
    """Return an explicit label without substituting an invented number."""
    if math.isnan(value):
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"


def _python_type_name(value: Any) -> str:
    """Return a stable type label without relying on arbitrary object reprs."""
    value_type = type(value)
    return _utf8_safe_text(f"{value_type.__module__}.{value_type.__qualname__}")


def _sorted_json_values(values: list[Any]) -> list[Any]:
    """Sort JSON-safe values so unordered evidence serializes deterministically."""
    return sorted(values, key=_json_dump)


def _json_dump(value: Any, *, indent: int | None = None) -> str:
    """Encode a normalized JSON value with no non-standard numeric literals."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    )


def _append_field(lines: list[str], label: str, value: Any) -> None:
    """Render a controlled label followed by an indented literal value block."""
    lines.extend([label, ""])
    _append_code_block(lines, _code_block_text(value))
    lines.append("")


def _append_code_block(lines: list[str], content: str) -> None:
    """Append a Markdown code block that input text cannot escape."""
    content_lines = content.splitlines() or [""]
    lines.extend(f"    {line}" for line in content_lines)


def _code_block_text(value: Any) -> str:
    """Keep text readable while rendering non-text values as strict JSON."""
    safe_value = _json_safe(value)
    if isinstance(safe_value, str):
        return safe_value
    return _json_dump(safe_value, indent=2)


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
