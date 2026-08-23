"""Static release-dependency inventory checks for the evaluator."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
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
_LOCK_PIN = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9._,-]+\])?\s*==\s*([^\s\\]+)"
)
_SHA256_HASH = re.compile(r"--hash=sha256:[0-9a-fA-F]{64}\b")
_LOCK_INPUT_FINGERPRINT_PREFIX = "# eqlib-lock-input-sha256: v1:"
_LOCK_INPUT_FINGERPRINT = re.compile(
    r"^\s*#\s*eqlib-lock-input-sha256:\s*v1:([0-9a-fA-F]{64})\s*$"
)
_LOCK_INPUT_SCHEMA = "eqlib-lock-input-v1"
_LOCK_RESOLVER_SCHEMA = {
    "input_groups": ["project.dependencies", "project.optional-dependencies.dev"],
    "pipeline": [
        {
            "tool": "pip-tools-pip-compile",
            "schema": "py310-base-v1",
        },
        {
            "tool": "uv-pip-compile",
            "version": "0.12.5",
            "schema": "universal-generate-hashes-no-strip-markers-v1",
        },
        {
            "tool": "eqlib-select-py310-targets",
            "schema": "macos-arm64-manylinux-x86_64-v1",
        },
        {
            "tool": "eqlib-enrich-pypi-hashes",
            "schema": "all-release-sha256-v1",
        },
    ],
}
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


def _marker_environment(
    *,
    platform_machine: str,
    platform_system: str,
    sys_platform: str,
) -> dict[str, str]:
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "implementation_version": "3.10.0",
            "os_name": "posix",
            "platform_machine": platform_machine,
            "platform_python_implementation": "CPython",
            "platform_release": "",
            "platform_system": platform_system,
            "platform_version": "",
            "python_full_version": "3.10.0",
            "python_version": "3.10",
            "sys_platform": sys_platform,
            "extra": "",
        }
    )
    return {key: str(value) for key, value in environment.items()}


_LOCK_TARGET_MATRIX = (
    {
        "id": "cpython-3.10-macos-arm64",
        "marker_environment": _marker_environment(
            platform_machine="arm64",
            platform_system="Darwin",
            sys_platform="darwin",
        ),
    },
    {
        "id": "cpython-3.10-manylinux-x86_64",
        "marker_environment": _marker_environment(
            platform_machine="x86_64",
            platform_system="Linux",
            sys_platform="linux",
        ),
    },
)


@dataclass(frozen=True)
class _HashLockPin:
    """A pinned lock requirement, including its platform marker."""

    version: str
    requirement: Requirement


def normalize_distribution_name(name: str) -> str:
    """Return a PEP 503-style distribution name without importing packages."""
    return _NORMALIZE_NAME.sub("-", name.strip()).lower()


def lock_input_fingerprint(root: Path) -> str:
    """Hash canonical lock inputs, not the mutable upstream resolution result."""
    payload = {
        "schema": _LOCK_INPUT_SCHEMA,
        "resolver": _LOCK_RESOLVER_SCHEMA,
        "requires_python": _canonical_requires_python(
            read_project_requires_python(root)
        ),
        "primary": sorted(
            _canonical_pep508_requirement(requirement)
            for requirement in read_project_dependency_declarations(root)
        ),
        "dev": sorted(
            _canonical_pep508_requirement(requirement)
            for requirement in read_optional_dependency_declarations(root).get(
                "dev", []
            )
        ),
        "target_matrix": _LOCK_TARGET_MATRIX,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def lock_input_fingerprint_header(root: Path) -> str:
    """Return the deterministic lock-header line for the current project inputs."""
    return _LOCK_INPUT_FINGERPRINT_PREFIX + lock_input_fingerprint(root) + "\n"


def _canonical_pep508_requirement(declaration: str) -> str:
    """Render a parsed requirement in a deterministic, PEP 508-aware form."""
    requirement = _parse_pep508_requirement(declaration)

    name = normalize_distribution_name(requirement.name)
    if requirement.extras:
        name += (
            "["
            + ",".join(
                sorted(
                    normalize_distribution_name(extra) for extra in requirement.extras
                )
            )
            + "]"
        )
    if requirement.url:
        result = f"{name} @ {requirement.url}"
    else:
        specifiers = ",".join(
            sorted(str(specifier) for specifier in requirement.specifier)
        )
        result = name + specifiers
    if requirement.marker:
        result += f"; {_canonical_marker(requirement.marker)}"
    return result


def _canonical_marker(marker: Any) -> str:
    """Render a packaging-parsed marker with stable boolean-clause ordering."""
    markers = getattr(marker, "_markers", None)
    if not isinstance(markers, list):
        raise ValueError("packaging marker has no parse tree")
    return _render_marker_tree(_marker_tree(markers))


def _marker_tree(value: object) -> tuple[Any, ...]:
    if isinstance(value, tuple) and len(value) == 3:
        variable, operator, marker_value = value
        return ("comparison", str(variable), str(operator), str(marker_value))
    if not isinstance(value, list) or not value:
        raise ValueError("invalid packaging marker tree")

    operands: list[tuple[Any, ...]] = []
    operators: list[str] = []
    expecting_operand = True
    for item in value:
        if isinstance(item, str):
            if expecting_operand or item not in {"and", "or"}:
                raise ValueError("invalid packaging marker operator")
            while operators and _marker_precedence(operators[-1]) >= _marker_precedence(
                item
            ):
                _reduce_marker_tree(operands, operators.pop())
            operators.append(item)
            expecting_operand = True
            continue
        if not expecting_operand:
            raise ValueError("invalid packaging marker expression")
        operands.append(_marker_tree(item))
        expecting_operand = False

    if expecting_operand:
        raise ValueError("invalid packaging marker expression")
    while operators:
        _reduce_marker_tree(operands, operators.pop())
    if len(operands) != 1:
        raise ValueError("invalid packaging marker expression")
    return operands[0]


def _marker_precedence(operator: str) -> int:
    return 2 if operator == "and" else 1


def _reduce_marker_tree(operands: list[tuple[Any, ...]], operator: str) -> None:
    if len(operands) < 2:
        raise ValueError("invalid packaging marker expression")
    right = operands.pop()
    left = operands.pop()
    children: list[tuple[Any, ...]] = []
    for node in (left, right):
        if node[0] == operator:
            children.extend(node[1])
        else:
            children.append(node)
    operands.append((operator, tuple(sorted(children, key=_render_marker_tree))))


def _render_marker_tree(tree: tuple[Any, ...]) -> str:
    if tree[0] == "comparison":
        _, variable, operator, value = tree
        return f"{variable} {operator} {json.dumps(value)}"
    operator, children = tree
    return (
        "("
        + f" {operator} ".join(_render_marker_tree(child) for child in children)
        + ")"
    )


def _parse_pep508_requirement(declaration: object) -> Requirement:
    if not isinstance(declaration, str):
        raise ValueError("dependency declarations must be strings")
    try:
        return Requirement(declaration)
    except InvalidRequirement as exc:
        raise ValueError(f"invalid dependency declaration: {declaration!r}") from exc


def _canonical_requires_python(value: str | None) -> str | None:
    if value is None:
        return None
    return str(SpecifierSet(value))


def read_project_dependencies(root: Path) -> set[str]:
    """Return normalized runtime distribution names from release metadata."""
    return {
        normalize_distribution_name(_parse_pep508_requirement(dependency).name)
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
        visitor = _RuntimeImportVisitor()
        visitor.visit(tree)
        for name in visitor.imported_top_level_names:
            if name in stdlib or name in first_party:
                continue
            distribution = _IMPORT_NAME_TO_DISTRIBUTION.get(name, name)
            imported.add(normalize_distribution_name(distribution))
    return imported


def evaluate_inventory(root: Path) -> list[Finding]:
    """Compare imports, release metadata, requirements, and the Python 3.10 lock."""
    root = Path(root)
    try:
        _validate_project_dependency_declarations(root)
        declared = read_project_dependencies(root)
        optional = read_optional_dependencies(root)
    except ValueError as exc:
        return [
            Finding(
                "DEP-002",
                Severity.P1,
                "Project dependency declarations are invalid",
                str(exc),
                evidence={"project_path": str(root / "pyproject.toml")},
                remediation="Use valid, non-duplicate PEP 508 declarations in project metadata.",
            )
        ]
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
    if requirements_path.exists():
        try:
            metadata_signatures = _project_requirement_signatures(root)
            requirements_signatures = _read_requirement_signatures(requirements_path)
        except ValueError as exc:
            findings.append(
                Finding(
                    "DEP-002",
                    Severity.P1,
                    "requirements.txt contains invalid dependency declarations",
                    str(exc),
                    evidence={"requirements_path": str(requirements_path)},
                    remediation="Use one valid, non-duplicate PEP 508 declaration per distribution.",
                )
            )
        else:
            if requirements_signatures != metadata_signatures:
                findings.append(
                    Finding(
                        "DEP-002",
                        Severity.P1,
                        "requirements.txt differs from project metadata",
                        "Regenerate or remove requirements.txt",
                        evidence={
                            "metadata": metadata_signatures,
                            "requirements": requirements_signatures,
                        },
                        remediation="Keep requirements.txt aligned with [project].dependencies.",
                    )
                )

    lock_finding = _validate_py310_hash_lock(root)
    if lock_finding is not None:
        findings.append(lock_finding)
    return findings


def _read_project(root: Path) -> Mapping[str, Any]:
    parsed = _read_pyproject(root)
    project = parsed.get("project")
    if not isinstance(project, Mapping):
        raise ValueError("pyproject.toml must contain a [project] table")
    return project


def _read_pyproject(root: Path) -> Mapping[str, Any]:
    metadata_path = Path(root) / "pyproject.toml"
    with metadata_path.open("rb") as stream:
        parsed = tomllib.load(stream)
    if not isinstance(parsed, Mapping):
        raise ValueError("pyproject.toml must contain a table")
    return parsed


def _optional_dependencies_by_extra(root: Path) -> dict[str, set[str]]:
    return {
        extra: {
            normalize_distribution_name(_parse_pep508_requirement(requirement).name)
            for requirement in requirements
        }
        for extra, requirements in read_optional_dependency_declarations(root).items()
    }


def _project_requirement_signatures(root: Path) -> tuple[str, ...]:
    return _requirement_signatures(read_project_dependency_declarations(root))


def _read_requirement_signatures(path: Path) -> tuple[str, ...]:
    requirements = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "--")):
            raise ValueError(f"unsupported requirement directive in {path}: {line}")
        requirements.append(line)
    return _requirement_signatures(requirements)


def _requirement_signatures(requirements: Iterable[object]) -> tuple[str, ...]:
    signatures = []
    duplicate_keys = set()
    for requirement in requirements:
        parsed = _parse_pep508_requirement(requirement)
        name = normalize_distribution_name(parsed.name)
        marker = _canonical_marker(parsed.marker) if parsed.marker else None
        duplicate_key = (name, marker)
        if duplicate_key in duplicate_keys:
            raise ValueError(f"duplicate dependency declaration for {name}")
        duplicate_keys.add(duplicate_key)
        signatures.append(_canonical_pep508_requirement(requirement))
    return tuple(sorted(signatures))


def _validate_project_dependency_declarations(root: Path) -> None:
    """Reject malformed metadata before emitting partial inventory findings."""
    primary = read_project_dependency_declarations(root)
    optional = read_optional_dependency_declarations(root)
    _requirement_signatures(primary)
    for declarations in optional.values():
        _requirement_signatures(declarations)
    _requirement_signatures([*primary, *optional.get("dev", [])])


def _requirement_name(requirement: object) -> str:
    return normalize_distribution_name(_parse_pep508_requirement(requirement).name)


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


class _RuntimeImportVisitor(ast.NodeVisitor):
    """Collect imports that can execute under normal runtime control flow."""

    def __init__(self) -> None:
        self.imported_top_level_names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        self.imported_top_level_names.update(
            alias.name.split(".", 1)[0] for alias in node.names
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.level and node.module:
            self.imported_top_level_names.add(node.module.split(".", 1)[0])

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_test(node.test):
            self._visit_statements(node.orelse)
            return
        truth = _constant_truth_value(node.test)
        if truth is True:
            self._visit_statements(node.body)
        elif truth is False:
            self._visit_statements(node.orelse)
        else:
            self._visit_statements(node.body)
            self._visit_statements(node.orelse)

    def visit_While(self, node: ast.While) -> None:
        truth = _constant_truth_value(node.test)
        if truth is False:
            self._visit_statements(node.orelse)
        else:
            self._visit_statements(node.body)
            self._visit_statements(node.orelse)

    def _visit_statements(self, statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            self.visit(statement)


def _is_type_checking_test(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr == "TYPE_CHECKING"
    )


def _constant_truth_value(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(
        node.value, (bool, int, float, complex, str, bytes, type(None))
    ):
        return bool(node.value)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
        return False
    if isinstance(node, ast.Dict) and not node.keys:
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _constant_truth_value(node.operand)
        return None if value is None else not value
    return None


def _first_party_module_names(root: Path) -> frozenset[str]:
    """Return only top-level packages selected for setuptools distribution."""
    root = Path(root)
    names: set[str] = set()
    configuration = _read_pyproject(root)
    tool = configuration.get("tool", {})
    setuptools = tool.get("setuptools", {}) if isinstance(tool, Mapping) else {}
    if not isinstance(setuptools, Mapping):
        return frozenset(names)

    explicit_packages = setuptools.get("packages")
    if isinstance(explicit_packages, list):
        names.update(_top_level_package_names(explicit_packages))
    elif isinstance(explicit_packages, Mapping):
        find_configuration = explicit_packages.get("find")
        if isinstance(find_configuration, Mapping):
            names.update(
                _find_setuptools_package_names(root, setuptools, find_configuration)
            )
    elif "py-modules" not in setuptools:
        # Setuptools' default package discovery applies only when package/module
        # selection was not explicitly configured.
        names.update(_find_setuptools_package_names(root, setuptools, {}))

    py_modules = setuptools.get("py-modules", [])
    if isinstance(py_modules, list):
        names.update(
            module.split(".", 1)[0]
            for module in py_modules
            if isinstance(module, str) and module
        )
    return frozenset(names)


def _top_level_package_names(packages: Iterable[object]) -> set[str]:
    return {
        package.split(".", 1)[0]
        for package in packages
        if isinstance(package, str) and package
    }


def _find_setuptools_package_names(
    root: Path,
    setuptools: Mapping[str, Any],
    find_configuration: Mapping[str, Any],
) -> set[str]:
    include = _string_list(find_configuration.get("include", ["*"]))
    exclude = _string_list(find_configuration.get("exclude", []))
    package_dir = setuptools.get("package-dir", {})
    default_where = "."
    if isinstance(package_dir, Mapping) and isinstance(package_dir.get(""), str):
        default_where = package_dir[""]
    where = _string_list(find_configuration.get("where", [default_where]))

    package_names = set()
    for directory in where:
        source_root = root / directory
        if not source_root.is_dir():
            continue
        for initializer in source_root.rglob("__init__.py"):
            relative = initializer.parent.relative_to(source_root)
            if not relative.parts:
                continue
            package = ".".join(relative.parts)
            if not any(fnmatchcase(package, pattern) for pattern in include):
                continue
            if any(fnmatchcase(package, pattern) for pattern in exclude):
                continue
            package_names.add(package.split(".", 1)[0])
    return package_names


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            "setuptools package discovery options must be lists of strings"
        )
    return value


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

    try:
        direct_requirements = _direct_lock_requirements(root)
    except ValueError as exc:
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock cannot be validated",
            str(exc),
            evidence={"lock_path": str(lock_path)},
            remediation="Use valid, non-duplicate primary and dev dependency declarations.",
        )
    missing, inactive_pins, invalid_pins, duplicate_pins = _validate_direct_lock_pins(
        direct_requirements, pins
    )
    if missing or inactive_pins or invalid_pins or duplicate_pins:
        details = []
        if missing:
            details.append("Missing direct pins: " + ", ".join(missing))
        if inactive_pins:
            details.append("Inactive direct pins: " + "; ".join(inactive_pins))
        if invalid_pins:
            details.append("Incompatible direct pins: " + "; ".join(invalid_pins))
        if duplicate_pins:
            details.append("Duplicate direct pins: " + "; ".join(duplicate_pins))
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is stale",
            " ".join(details),
            evidence={
                "lock_path": str(lock_path),
                "missing_direct_pins": missing,
                "inactive_direct_pins": inactive_pins,
                "invalid_direct_pins": invalid_pins,
                "duplicate_direct_pins": duplicate_pins,
                "pinned": sorted(pins),
            },
            remediation="Regenerate the lock after changing release or dev metadata.",
        )

    expected_fingerprint = lock_input_fingerprint(root)
    fingerprint_state, actual_fingerprint = _read_lock_input_fingerprint(lock_path)
    if fingerprint_state != "valid" or actual_fingerprint != expected_fingerprint:
        if fingerprint_state == "missing":
            detail = "constraints-py310.txt is missing its lock-input fingerprint"
        elif fingerprint_state == "malformed":
            detail = "constraints-py310.txt has a malformed or duplicate lock-input fingerprint"
        else:
            detail = "constraints-py310.txt lock-input fingerprint does not match project metadata"
        return Finding(
            "DEP-005",
            Severity.P1,
            "Python 3.10 hash lock is stale",
            detail,
            evidence={
                "lock_path": str(lock_path),
                "fingerprint_state": fingerprint_state,
                "expected_lock_input_fingerprint": expected_fingerprint,
                "actual_lock_input_fingerprint": actual_fingerprint,
            },
            remediation="Regenerate the Python 3.10 lock after changing its inputs.",
        )
    return None


def _direct_lock_requirements(root: Path) -> list[Requirement]:
    declarations = read_project_dependency_declarations(root)
    declarations.extend(read_optional_dependency_declarations(root).get("dev", []))
    return [
        parsed
        for declaration in declarations
        if _is_active_for_lock_targets(parsed := _parse_pep508_requirement(declaration))
    ]


def _is_active_for_lock_targets(requirement: Requirement) -> bool:
    if requirement.marker is None:
        return True
    return any(
        requirement.marker.evaluate(target["marker_environment"])
        for target in _LOCK_TARGET_MATRIX
    )


def _validate_direct_lock_pins(
    direct_requirements: Iterable[Requirement],
    pins: Mapping[str, list[_HashLockPin]],
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Check pins per explicit Python 3.10 target, not on the host platform."""
    missing: set[str] = set()
    inactive: set[str] = set()
    invalid: set[str] = set()
    duplicates: set[str] = set()
    for target in _LOCK_TARGET_MATRIX:
        environment = target["marker_environment"]
        active_requirements: dict[str, list[Requirement]] = {}
        for requirement in direct_requirements:
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            name = normalize_distribution_name(requirement.name)
            active_requirements.setdefault(name, []).append(requirement)

        for name, requirements in active_requirements.items():
            if len(requirements) > 1:
                duplicates.add(f"{name} for {target['id']}")
                continue
            direct_requirement = requirements[0]
            known_pins = pins.get(name, [])
            if not known_pins:
                missing.add(name)
                continue
            active_pins = [
                pin
                for pin in known_pins
                if pin.requirement.marker is None
                or pin.requirement.marker.evaluate(environment)
            ]
            if not active_pins:
                inactive.add(f"{name} for {target['id']}")
                continue
            if not direct_requirement.specifier:
                continue
            compatible = False
            for pin in active_pins:
                try:
                    compatible = Version(pin.version) in direct_requirement.specifier
                except InvalidVersion:
                    compatible = False
                if compatible:
                    break
            if not compatible:
                pinned_versions = ", ".join(
                    f"{name}=={pin.version}" for pin in active_pins
                )
                invalid.add(
                    f"{pinned_versions} does not satisfy "
                    f"{direct_requirement.specifier} for {target['id']}"
                )
    return (
        sorted(missing),
        sorted(inactive),
        sorted(invalid),
        sorted(duplicates),
    )


def _read_hash_lock(path: Path) -> tuple[dict[str, list[_HashLockPin]], list[str]]:
    pins: dict[str, list[_HashLockPin]] = {}
    hashless = []
    for line in _logical_lock_lines(path.read_text(encoding="utf-8")):
        match = _LOCK_PIN.match(line)
        if match is None:
            continue
        name = normalize_distribution_name(match.group(1))
        requirement_text = line.split(" --hash=", 1)[0].strip()
        try:
            requirement = _parse_pep508_requirement(requirement_text)
        except ValueError:
            hashless.append(name)
            continue
        pins.setdefault(name, []).append(
            _HashLockPin(version=match.group(2), requirement=requirement)
        )
        if _SHA256_HASH.search(line) is None:
            hashless.append(name)
    return pins, sorted(hashless)


def _read_lock_input_fingerprint(lock_path: Path) -> tuple[str, str | None]:
    matching = []
    malformed = []
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        if "eqlib-lock-input-sha256:" not in raw_line:
            continue
        match = _LOCK_INPUT_FINGERPRINT.match(raw_line)
        if match is None:
            malformed.append(raw_line)
        else:
            matching.append(match.group(1).lower())
    if malformed or len(matching) > 1:
        return "malformed", None
    if not matching:
        return "missing", None
    return "valid", matching[0]


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
