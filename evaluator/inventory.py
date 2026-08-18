"""Static release-dependency inventory checks for the evaluator."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path
import re
import sys
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

try:  # pragma: no cover - the fallback is exercised on Python 3.10 only.
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the declared tomli fallback.
    import tomli as tomllib

from .models import Finding, Severity


_IMPORT_NAME_TO_DISTRIBUTION = {
    "chinese_calendar": "chinese-calendar",
    "sklearn": "scikit-learn",
}
_NORMALIZE_NAME = re.compile(r"[-_.]+")
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_LOCK_PIN = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9._,-]+\])?\s*==\s*([^\s\\]+)"
)
_SHA256_HASH = re.compile(r"--hash=sha256:[0-9a-fA-F]{64}\b")
_STDLIB_FALLBACK = frozenset(
    {
        "__future__",
        "abc",
        "argparse",
        "ast",
        "base64",
        "builtins",
        "calendar",
        "collections",
        "concurrent",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "hmac",
        "html",
        "importlib",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "numbers",
        "os",
        "pathlib",
        "pickle",
        "random",
        "re",
        "statistics",
        "sys",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "urllib",
        "uuid",
        "warnings",
        "zoneinfo",
    }
)


def normalize_distribution_name(name: str) -> str:
    """Return a PEP 503-style distribution name without importing packages."""
    return _NORMALIZE_NAME.sub("-", name.strip()).lower()


def read_project_dependencies(root: Path) -> set[str]:
    """Return normalized runtime distribution names from release metadata."""
    return {
        _requirement_name(dependency)
        for dependency in read_project_dependency_declarations(root)
    }


def read_project_dependency_declarations(root: Path) -> list[str]:
    """Return raw runtime PEP 508 declarations from release metadata."""
    dependencies = _read_project(root).get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(dependency, str) for dependency in dependencies
    ):
        raise ValueError("[project].dependencies must be a list of strings")
    return dependencies


def read_project_requires_python(root: Path) -> str | None:
    """Return the release Python requirement as written in project metadata."""
    requires_python = _read_project(root).get("requires-python")
    if requires_python is not None and not isinstance(requires_python, str):
        raise ValueError("[project].requires-python must be a string")
    return requires_python


def read_optional_dependencies(root: Path) -> set[str]:
    """Return normalized distributions intentionally supplied by project extras."""
    optional = _optional_dependencies_by_extra(root)
    return {
        dependency for dependencies in optional.values() for dependency in dependencies
    }


def read_optional_dependency_declarations(root: Path) -> dict[str, list[str]]:
    """Return raw PEP 508 declarations grouped by their declared extra."""
    optional = _read_project(root).get("optional-dependencies", {})
    if not isinstance(optional, Mapping):
        raise ValueError("[project.optional-dependencies] must be a table")

    result = {}
    for extra, requirements in optional.items():
        if not isinstance(extra, str) or not isinstance(requirements, list):
            raise ValueError("optional dependency extras must map to requirement lists")
        if not all(isinstance(requirement, str) for requirement in requirements):
            raise ValueError("optional dependency declarations must be strings")
        result[extra] = requirements
    return result


def read_requirements(path: Path) -> set[str]:
    """Return normalized requirement names from a flat requirements file."""
    return set(_read_requirement_signatures(path))


def scan_runtime_imports(root: Path) -> set[str]:
    """Find third-party imports through AST parsing only, never target imports."""
    package_dir = Path(root) / "eqlib"
    if not package_dir.is_dir():
        return set()

    stdlib = _stdlib_module_names()
    first_party = _first_party_module_names(root)
    imported = set()
    for path in sorted(package_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for name in _imported_top_level_names(node):
                if name in stdlib or name in first_party:
                    continue
                distribution = _IMPORT_NAME_TO_DISTRIBUTION.get(name, name)
                imported.add(normalize_distribution_name(distribution))
    return imported


def evaluate_inventory(root: Path) -> list[Finding]:
    """Compare imports, release metadata, requirements, and the Python 3.10 lock."""
    root = Path(root)
    declared = read_project_dependencies(root)
    optional = read_optional_dependencies(root)
    runtime_imports = scan_runtime_imports(root)
    findings = []

    missing = sorted(runtime_imports - declared - optional)
    if missing:
        findings.append(
            Finding(
                "DEP-001",
                Severity.P1,
                "Undeclared runtime dependency",
                ", ".join(missing),
                evidence={
                    "declared": sorted(declared),
                    "optional": sorted(optional),
                    "runtime_imports": sorted(runtime_imports),
                },
                remediation="Declare each direct runtime import in project metadata or an explicit extra.",
            )
        )

    requirements_path = root / "requirements.txt"
    if requirements_path.exists() and _read_requirement_signatures(
        requirements_path
    ) != _project_requirement_signatures(root):
        findings.append(
            Finding(
                "DEP-002",
                Severity.P1,
                "requirements.txt differs from project metadata",
                "Regenerate or remove requirements.txt",
                evidence={
                    "metadata": _project_requirement_signatures(root),
                    "requirements": _read_requirement_signatures(requirements_path),
                },
                remediation="Keep requirements.txt aligned with [project].dependencies.",
            )
        )

    lock_finding = _validate_py310_hash_lock(root)
    if lock_finding is not None:
        findings.append(lock_finding)
    return findings


def _read_project(root: Path) -> Mapping[str, Any]:
    metadata_path = Path(root) / "pyproject.toml"
    with metadata_path.open("rb") as stream:
        parsed = tomllib.load(stream)
    project = parsed.get("project")
    if not isinstance(project, Mapping):
        raise ValueError("pyproject.toml must contain a [project] table")
    return project


def _optional_dependencies_by_extra(root: Path) -> dict[str, set[str]]:
    return {
        extra: {_requirement_name(requirement) for requirement in requirements}
        for extra, requirements in read_optional_dependency_declarations(root).items()
    }


def _project_requirement_signatures(root: Path) -> dict[str, str]:
    return _requirement_signatures(read_project_dependency_declarations(root))


def _read_requirement_signatures(path: Path) -> dict[str, str]:
    requirements = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "--")):
            raise ValueError(f"unsupported requirement directive in {path}: {line}")
        requirements.append(line)
    return _requirement_signatures(requirements)


def _requirement_signatures(requirements: Iterable[object]) -> dict[str, str]:
    signatures = {}
    for requirement in requirements:
        if not isinstance(requirement, str):
            raise ValueError("dependency declarations must be strings")
        name = _requirement_name(requirement)
        match = _REQUIREMENT_NAME.match(requirement)
        assert match is not None
        signatures[name] = re.sub(r"\s+", "", requirement[match.end() :])
    return signatures


def _requirement_name(requirement: object) -> str:
    if not isinstance(requirement, str):
        raise ValueError("dependency declarations must be strings")
    match = _REQUIREMENT_NAME.match(requirement)
    if match is None:
        raise ValueError(f"invalid requirement declaration: {requirement!r}")
    return normalize_distribution_name(match.group(1))


def _imported_top_level_names(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Import):
        return (alias.name.split(".", 1)[0] for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        if node.level or not node.module:
            return ()
        return (node.module.split(".", 1)[0],)
    return ()


def _stdlib_module_names() -> frozenset[str]:
    names = getattr(sys, "stdlib_module_names", ())
    return frozenset(names) | _STDLIB_FALLBACK


def _first_party_module_names(root: Path) -> frozenset[str]:
    root = Path(root)
    names = set()
    for child in root.iterdir():
        if child.is_file() and child.suffix == ".py":
            names.add(child.stem)
        elif child.is_dir() and (child / "__init__.py").is_file():
            names.add(child.name)
    return frozenset(names)


def _validate_py310_hash_lock(root: Path) -> Finding | None:
    lock_path = Path(root) / "requirements" / "constraints-py310.txt"
    if not lock_path.is_file():
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is missing",
            f"{lock_path.relative_to(root)} is missing",
            evidence={"lock_path": str(lock_path)},
            remediation="Generate the Python 3.10 lock with pip-compile --generate-hashes.",
        )

    pins, hashless = _read_hash_lock(lock_path)
    if not pins:
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is malformed",
            "constraints-py310.txt contains no pinned requirements",
            evidence={"lock_path": str(lock_path)},
            remediation="Regenerate the lock with pip-compile --generate-hashes.",
        )
    if hashless:
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is malformed",
            "constraints-py310.txt has pinned requirements without SHA-256 hashes",
            evidence={"lock_path": str(lock_path), "hashless": hashless},
            remediation="Regenerate the lock with pip-compile --generate-hashes.",
        )

    direct_requirements = _direct_lock_requirements(root)
    missing = sorted(set(direct_requirements) - set(pins))
    invalid_pins = _invalid_direct_pins(direct_requirements, pins)
    if missing or invalid_pins:
        details = []
        if missing:
            details.append("Missing direct pins: " + ", ".join(missing))
        if invalid_pins:
            details.append("Incompatible direct pins: " + "; ".join(invalid_pins))
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is stale",
            " ".join(details),
            evidence={
                "lock_path": str(lock_path),
                "missing_direct_pins": missing,
                "invalid_direct_pins": invalid_pins,
                "pinned": sorted(pins),
            },
            remediation="Regenerate the lock after changing release or dev metadata.",
        )
    return None


def _direct_lock_requirements(root: Path) -> dict[str, Requirement]:
    declarations = read_project_dependency_declarations(root)
    declarations.extend(read_optional_dependency_declarations(root).get("dev", []))
    direct = {}
    for declaration in declarations:
        try:
            parsed = Requirement(declaration)
        except InvalidRequirement as exc:
            raise ValueError(
                f"invalid dependency declaration: {declaration!r}"
            ) from exc
        direct[normalize_distribution_name(parsed.name)] = parsed
    return direct


def _invalid_direct_pins(
    direct_requirements: Mapping[str, Requirement], pins: Mapping[str, str]
) -> list[str]:
    invalid = []
    for name, requirement in direct_requirements.items():
        pinned = pins.get(name)
        if pinned is None or not requirement.specifier:
            continue
        try:
            satisfies = Version(pinned) in requirement.specifier
        except InvalidVersion:
            satisfies = False
        if not satisfies:
            invalid.append(f"{name}=={pinned} does not satisfy {requirement.specifier}")
    return sorted(invalid)


def _read_hash_lock(path: Path) -> tuple[dict[str, str], list[str]]:
    pins = {}
    hashless = []
    for line in _logical_lock_lines(path.read_text(encoding="utf-8")):
        match = _LOCK_PIN.match(line)
        if match is None:
            continue
        name = normalize_distribution_name(match.group(1))
        pins[name] = match.group(2)
        if _SHA256_HASH.search(line) is None:
            hashless.append(name)
    return pins, sorted(hashless)


def _logical_lock_lines(text: str) -> Iterable[str]:
    parts = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.endswith("\\"):
            parts.append(stripped[:-1].rstrip())
            continue
        parts.append(stripped)
        if parts:
            yield " ".join(part for part in parts if part)
        parts = []
    if parts:
        yield " ".join(part for part in parts if part)
