"""Fresh-wheel build and isolated-install evidence for dependency evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from email import message_from_bytes, policy
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Sequence
from zipfile import BadZipFile, ZipFile

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from .inventory import (
    normalize_distribution_name,
    read_optional_dependency_declarations,
    read_project_dependency_declarations,
    read_project_requires_python,
)
from .models import Finding, Severity


_COMMAND_TIMEOUT_SECONDS = 180
_MAX_EVIDENCE_CHARS = 4_000
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_INDEX_UNAVAILABLE_MARKERS = (
    "could not fetch url",
    "connection broken",
    "connection refused",
    "connection timed out",
    "network is unreachable",
    "proxyerror",
    "read timed out",
    "temporary failure in name resolution",
    "timed out",
    "too many requests",
    "certificate verify failed",
    "sslerror",
)


@dataclass(frozen=True)
class _CommandResult:
    """Bounded evidence from an evaluator-owned subprocess."""

    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    index_unavailable: bool = False


def build_and_audit_wheel(
    root: Path, work_dir: Path
) -> tuple[dict[str, Any], list[Finding]]:
    """Build a wheel, inspect its embedded METADATA, and audit an isolated install."""
    root = Path(root).resolve()
    work_dir = Path(work_dir).resolve()
    _ensure_work_dir_is_external(root, work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = Path(tempfile.mkdtemp(prefix="eqlib-wheel-audit-", dir=work_dir))
    dist_dir = audit_dir / "dist"
    dist_dir.mkdir()

    build = _run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=root,
        check=False,
    )
    if build.returncode != 0:
        return _empty_evidence(audit_dir, build=build), [_build_failure(build)]

    wheel_paths = sorted(dist_dir.glob("*.whl"))
    if len(wheel_paths) != 1:
        finding = Finding(
            "DEP-003",
            Severity.P0,
            "Wheel build did not produce exactly one artifact",
            f"Expected one wheel in {dist_dir}, found {len(wheel_paths)}",
            evidence={
                "build": _command_evidence(build),
                "wheel_paths": [str(item) for item in wheel_paths],
            },
            remediation="Fix the build configuration so it emits one wheel artifact.",
        )
        return _empty_evidence(audit_dir, build=build), [finding]

    wheel_path = wheel_paths[0]
    try:
        metadata = _read_wheel_metadata(wheel_path)
    except (BadZipFile, OSError, ValueError) as exc:
        finding = Finding(
            "DEP-003",
            Severity.P0,
            "Wheel METADATA is unreadable",
            _bounded_text(str(exc)),
            evidence={"wheel_path": str(wheel_path), "build": _command_evidence(build)},
            remediation="Build a valid wheel containing one dist-info/METADATA file.",
        )
        return _empty_evidence(audit_dir, build=build, wheel_path=wheel_path), [finding]

    venv_dir = audit_dir / "venv"
    venv = _run([sys.executable, "-m", "venv", str(venv_dir)], check=False)
    if venv.returncode != 0:
        finding = Finding(
            "DEP-003",
            Severity.P0,
            "Isolated wheel environment could not be created",
            _command_detail(venv),
            evidence={"venv": _command_evidence(venv)},
            remediation="Repair the Python venv tooling used by the evaluator.",
        )
        return _evidence(wheel_path, metadata, build=build, venv=venv), [finding]

    try:
        venv_python = _venv_python(venv_dir)
    except ValueError as exc:
        finding = Finding(
            "DEP-003",
            Severity.P0,
            "Isolated wheel environment is incomplete",
            _bounded_text(str(exc)),
            evidence={"venv": _command_evidence(venv)},
            remediation="Repair the Python venv tooling used by the evaluator.",
        )
        return _evidence(wheel_path, metadata, build=build, venv=venv), [finding]

    install = _run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--isolated",
            "--no-cache-dir",
            "--disable-pip-version-check",
            str(wheel_path),
        ],
        check=False,
    )
    pip_check = _run(
        [str(venv_python), "-m", "pip", "check", "--isolated"],
        check=False,
    )
    findings = _metadata_findings(root, metadata)
    findings.extend(_installation_findings(install, pip_check))
    return (
        _evidence(
            wheel_path,
            metadata,
            build=build,
            venv=venv,
            venv_python=venv_python,
            install=install,
            pip_check=pip_check,
            installed_metadata=_read_installed_metadata(venv_dir, metadata["name"]),
        ),
        findings,
    )


def requirement_name(requirement: str) -> str:
    """Return the normalized distribution name encoded in a Requires-Dist field."""
    match = _REQUIREMENT_NAME.match(requirement)
    if match is None:
        raise ValueError(f"invalid requirement: {requirement!r}")
    return normalize_distribution_name(match.group(1))


def _read_wheel_metadata(wheel_path: Path) -> dict[str, Any]:
    """Read the sole METADATA member embedded in a freshly built wheel."""
    with ZipFile(wheel_path) as archive:
        metadata_members = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA") and "/" in name
        ]
        if len(metadata_members) != 1:
            raise ValueError(
                f"wheel must contain exactly one dist-info/METADATA file, found {len(metadata_members)}"
            )
        message = message_from_bytes(
            archive.read(metadata_members[0]), policy=policy.default
        )

    name = message.get("Name")
    version = message.get("Version")
    if not name or not version:
        raise ValueError("wheel METADATA is missing Name or Version")
    return {
        "name": name,
        "version": version,
        "requires_python": message.get("Requires-Python"),
        "requires_dist": list(message.get_all("Requires-Dist", [])),
    }


def _metadata_findings(root: Path, metadata: dict[str, Any]) -> list[Finding]:
    try:
        declared = _expected_wheel_requirements(root)
        wheel_dependencies = {
            _canonical_requirement(requirement)
            for requirement in metadata["requires_dist"]
        }
        declared_python = _canonical_requires_python(read_project_requires_python(root))
        wheel_python = _canonical_requires_python(metadata.get("requires_python"))
    except (InvalidRequirement, InvalidSpecifier, ValueError) as exc:
        return [
            Finding(
                "DEP-003",
                Severity.P0,
                "Wheel metadata requirement is invalid",
                _bounded_text(str(exc)),
                evidence={"metadata": metadata},
                remediation="Use valid PEP 508 requirements and Requires-Python metadata.",
            )
        ]

    missing = sorted(declared - wheel_dependencies)
    unexpected = sorted(wheel_dependencies - declared)
    if not (missing or unexpected or declared_python != wheel_python):
        return []
    return [
        Finding(
            "DEP-003",
            Severity.P0,
            "Wheel metadata differs from release metadata",
            _metadata_difference_detail(
                missing, unexpected, declared_python, wheel_python
            ),
            evidence={
                "declared_requires_python": declared_python,
                "wheel_requires_python": wheel_python,
                "declared_requires_dist": sorted(declared),
                "wheel_requires_dist": sorted(wheel_dependencies),
            },
            remediation="Rebuild after aligning pyproject.toml release dependencies.",
        )
    ]


def _expected_wheel_requirements(root: Path) -> set[str]:
    """Return canonical wheel Requires-Dist declarations implied by pyproject."""
    expected = {
        _canonical_requirement(requirement)
        for requirement in read_project_dependency_declarations(root)
    }
    for extra, requirements in read_optional_dependency_declarations(root).items():
        expected.update(
            _canonical_requirement(_with_extra_marker(requirement, extra))
            for requirement in requirements
        )
    return expected


def _with_extra_marker(requirement: str, extra: str) -> str:
    parsed = Requirement(requirement)
    base = requirement.split(";", 1)[0].strip()
    marker = str(parsed.marker) if parsed.marker else ""
    extra_marker = f'extra == "{extra}"'
    if marker:
        return f"{base}; ({marker}) and {extra_marker}"
    return f"{base}; {extra_marker}"


def _canonical_requirement(requirement: str) -> str:
    """Normalize the complete PEP 508 requirement, not merely its name."""
    parsed = Requirement(requirement)
    name = normalize_distribution_name(parsed.name)
    if parsed.extras:
        normalized_extras = sorted(
            normalize_distribution_name(extra) for extra in parsed.extras
        )
        name += "[" + ",".join(normalized_extras) + "]"
    if parsed.url:
        name += f" @ {parsed.url}"
    else:
        name += str(parsed.specifier)
    if parsed.marker:
        name += f"; {parsed.marker}"
    return name


def _canonical_requires_python(value: str | None) -> str | None:
    if value is None:
        return None
    return str(SpecifierSet(value))


def _metadata_difference_detail(
    missing: list[str],
    unexpected: list[str],
    declared_python: str | None,
    wheel_python: str | None,
) -> str:
    parts = []
    if declared_python != wheel_python:
        parts.append(
            "requires-python differs: expected "
            f"{declared_python or '<unset>'}, wheel has {wheel_python or '<unset>'}"
        )
    if missing:
        parts.append("missing from wheel: " + ", ".join(missing))
    if unexpected:
        parts.append("unexpected in wheel: " + ", ".join(unexpected))
    return "; ".join(parts)


def _installation_findings(
    install: _CommandResult, pip_check: _CommandResult
) -> list[Finding]:
    """Turn isolated installation outcomes into bounded, explicit findings."""
    if _is_index_unavailable(install):
        return [
            Finding(
                "DEP-004",
                Severity.P1,
                "Package index unavailable during wheel installation",
                _bounded_text(_command_detail(install, pip_check)),
                evidence={
                    "install": _command_evidence(install),
                    "pip_check": _command_evidence(pip_check),
                },
                remediation="Restore package-index access and rerun the isolated wheel audit.",
                status="unavailable",
            )
        ]
    if install.returncode == 0 and pip_check.returncode == 0:
        return []
    return [
        Finding(
            "DEP-003",
            Severity.P0,
            "Wheel dependency installation is inconsistent",
            _bounded_text(_command_detail(install, pip_check)),
            evidence={
                "install": _command_evidence(install),
                "pip_check": _command_evidence(pip_check),
            },
            remediation="Repair wheel dependency declarations and rerun pip check in a clean environment.",
        )
    ]


def _build_failure(build: _CommandResult) -> Finding:
    if _is_index_unavailable(build):
        return Finding(
            "DEP-004",
            Severity.P1,
            "Package index unavailable while building the wheel",
            _command_detail(build),
            evidence={"build": _command_evidence(build)},
            remediation="Restore package-index access and rerun the wheel audit.",
            status="unavailable",
        )
    return Finding(
        "DEP-003",
        Severity.P0,
        "Wheel build failed",
        _command_detail(build),
        evidence={"build": _command_evidence(build)},
        remediation="Repair the wheel build before evaluating dependency installation.",
    )


def _is_index_unavailable(result: _CommandResult) -> bool:
    if result.timed_out or result.index_unavailable:
        return True
    return _output_indicates_index_unavailable(result.stdout, result.stderr)


def _output_indicates_index_unavailable(stdout: str, stderr: str) -> bool:
    output = f"{stdout}\n{stderr}".lower()
    return any(marker in output for marker in _INDEX_UNAVAILABLE_MARKERS)


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
    timeout: int = _COMMAND_TIMEOUT_SECONDS,
) -> _CommandResult:
    """Run a bounded subprocess and retain only bounded, UTF-8-safe evidence."""
    del check  # Evaluation failures are findings rather than subprocess exceptions.
    command_tuple = tuple(str(part) for part in command)
    try:
        completed = subprocess.run(
            command_tuple,
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_text(exc.stdout)
        stderr = _coerce_text(exc.stderr)
        return _CommandResult(
            command_tuple,
            None,
            _bounded_text(stdout),
            _bounded_text(stderr),
            timed_out=True,
            index_unavailable=_output_indicates_index_unavailable(stdout, stderr),
        )
    stdout = completed.stdout
    stderr = completed.stderr
    return _CommandResult(
        command_tuple,
        completed.returncode,
        _bounded_text(stdout),
        _bounded_text(stderr),
        index_unavailable=_output_indicates_index_unavailable(stdout, stderr),
    )


def _venv_python(venv_dir: Path) -> Path:
    """Return the platform-specific Python executable within an evaluator venv."""
    candidate = venv_dir / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    if not candidate.is_file():
        raise ValueError(f"venv did not create a Python executable at {candidate}")
    return candidate


def _evidence(
    wheel_path: Path,
    metadata: dict[str, Any],
    *,
    build: _CommandResult,
    venv: _CommandResult | None = None,
    venv_python: Path | None = None,
    install: _CommandResult | None = None,
    pip_check: _CommandResult | None = None,
    installed_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "wheel_path": str(wheel_path),
        "wheel_sha256": _file_sha256(wheel_path),
        "metadata": metadata,
        "requires_python": metadata["requires_python"],
        "requires_dist": metadata["requires_dist"],
        "build": _command_evidence(build),
        "venv": _command_evidence(venv),
        "venv_python": str(venv_python) if venv_python is not None else None,
        "install": _command_evidence(install),
        "pip_check": _command_evidence(pip_check),
        "installed_metadata": installed_metadata,
    }


def _empty_evidence(
    audit_dir: Path, *, build: _CommandResult, wheel_path: Path | None = None
) -> dict[str, Any]:
    return {
        "audit_dir": str(audit_dir),
        "wheel_path": str(wheel_path) if wheel_path is not None else None,
        "wheel_sha256": _file_sha256(wheel_path) if wheel_path is not None else None,
        "metadata": None,
        "requires_python": None,
        "requires_dist": [],
        "build": _command_evidence(build),
        "venv": None,
        "venv_python": None,
        "install": None,
        "pip_check": None,
        "installed_metadata": None,
    }


def _read_installed_metadata(
    venv_dir: Path, expected_name: str
) -> dict[str, Any] | None:
    expected = normalize_distribution_name(expected_name)
    for metadata_path in venv_dir.rglob("*.dist-info/METADATA"):
        try:
            message = message_from_bytes(
                metadata_path.read_bytes(), policy=policy.default
            )
        except OSError:
            continue
        name = message.get("Name")
        if name and normalize_distribution_name(name) == expected:
            return {
                "name": name,
                "version": message.get("Version"),
                "requires_python": message.get("Requires-Python"),
                "requires_dist": list(message.get_all("Requires-Dist", [])),
            }
    return None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_evidence(result: _CommandResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "command": list(result.command),
        "returncode": result.returncode,
        "stdout": _bounded_text(result.stdout),
        "stderr": _bounded_text(result.stderr),
        "timed_out": result.timed_out,
        "index_unavailable": result.index_unavailable,
    }


def _command_detail(*results: _CommandResult) -> str:
    sections = []
    for result in results:
        command = " ".join(result.command)
        status = "timed out" if result.timed_out else f"exit {result.returncode}"
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        sections.append(f"{command} ({status})" + (f"\n{output}" if output else ""))
    return _bounded_text("\n\n".join(sections))


def _bounded_text(value: str) -> str:
    if len(value) <= _MAX_EVIDENCE_CHARS:
        return value
    half = (_MAX_EVIDENCE_CHARS - 80) // 2
    omitted = len(value) - (half * 2)
    return f"{value[:half]}\n... [{omitted} characters truncated] ...\n{value[-half:]}"


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _ensure_work_dir_is_external(root: Path, work_dir: Path) -> None:
    try:
        work_dir.relative_to(root)
    except ValueError:
        return
    raise ValueError("wheel audit work_dir must be outside the repository")
