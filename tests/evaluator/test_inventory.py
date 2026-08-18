"""Tests for release dependency inventory and AST-only import auditing."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evaluator.inventory import (
    evaluate_inventory,
    normalize_distribution_name,
    read_project_dependencies,
    scan_runtime_imports,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_project(
    root: Path,
    dependencies: list[str],
    optional_dependencies: dict[str, list[str]] | None = None,
) -> None:
    lines = [
        "[project]",
        'name = "inventory-fixture"',
        'version = "0.0.0"',
        'requires-python = ">=3.10"',
        "dependencies = [",
    ]
    lines.extend(f"  {json.dumps(requirement)}," for requirement in dependencies)
    lines.append("]")
    if optional_dependencies:
        lines.extend(["", "[project.optional-dependencies]"])
        for extra, requirements in optional_dependencies.items():
            lines.append(
                f"{extra} = [{', '.join(json.dumps(item) for item in requirements)}]"
            )
    (root / "pyproject.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_runtime_module(root: Path, contents: str) -> None:
    package = root / "eqlib"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "runtime.py").write_text(contents, encoding="utf-8")


def _finding(findings, finding_id: str):
    return next(item for item in findings if item.id == finding_id)


def _pinned_names(lock_text: str) -> set[str]:
    names = set()
    for line in lock_text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==[^\\\s]+", line)
        if match:
            names.add(normalize_distribution_name(match.group(1)))
    return names


def _lock_hashes(lock_text: str) -> dict[str, set[str]]:
    hashes = {}
    current_name = None
    for line in lock_text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==[^\\\s]+", line)
        if match:
            current_name = normalize_distribution_name(match.group(1))
            hashes.setdefault(current_name, set())
        hash_match = re.search(r"--hash=sha256:([0-9a-f]{64})", line)
        if current_name is not None and hash_match:
            hashes[current_name].add(hash_match.group(1))
    return hashes


def test_inventory_reports_direct_runtime_import_missing_from_metadata(tmp_path):
    _write_project(tmp_path, dependencies=["numpy>=1.23"])
    _write_runtime_module(tmp_path, "import requests\n")

    findings = evaluate_inventory(tmp_path)

    assert "requests" in _finding(findings, "DEP-001").detail


def test_inventory_reports_stale_requirements_file(tmp_path):
    _write_project(tmp_path, dependencies=["numpy>=1.23", "requests>=2.0"])
    (tmp_path / "requirements.txt").write_text("numpy>=1.23\n", encoding="utf-8")

    findings = evaluate_inventory(tmp_path)

    assert _finding(findings, "DEP-002").severity.value == "P1"


def test_ast_scan_never_imports_target_code_and_skips_non_third_party_imports(tmp_path):
    _write_project(tmp_path, dependencies=[])
    _write_runtime_module(
        tmp_path,
        "\n".join(
            [
                "import sys",
                "from urllib.parse import quote",
                "import eqlib.trap",
                "from . import trap",
                "import Fancy_Package.client",
                "from sklearn.linear_model import LinearRegression",
                "import chinese_calendar",
            ]
        )
        + "\n",
    )
    (tmp_path / "eqlib" / "trap.py").write_text(
        "raise AssertionError('AST scanning must not execute target code')\n",
        encoding="utf-8",
    )

    imports = scan_runtime_imports(tmp_path)

    assert imports == {"chinese-calendar", "fancy-package", "scikit-learn"}


def test_inventory_recognizes_declared_optional_imports_without_hiding_real_ones(
    tmp_path,
):
    _write_project(
        tmp_path,
        dependencies=["numpy>=1.23"],
        optional_dependencies={"models": ["fastparquet>=2023.0", "XGBoost>=2.0"]},
    )
    _write_runtime_module(
        tmp_path,
        "import fastparquet\nimport xgboost\nimport unlisted_vendor\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-001")

    assert finding.detail == "unlisted-vendor"


def test_inventory_reports_missing_hash_lock(tmp_path):
    _write_project(tmp_path, dependencies=["numpy>=1.23"])
    _write_runtime_module(tmp_path, "import numpy\n")

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "constraints-py310.txt" in finding.detail


def test_inventory_reports_hashless_or_stale_hash_lock(tmp_path):
    _write_project(tmp_path, dependencies=["numpy>=1.23", "requests>=2.0"])
    _write_runtime_module(tmp_path, "import numpy\nimport requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    lock_path = requirements_dir / "constraints-py310.txt"
    lock_path.write_text("numpy==1.26.4\n", encoding="utf-8")

    malformed = _finding(evaluate_inventory(tmp_path), "DEP-005")
    assert "hash" in malformed.detail.lower()

    lock_path.write_text(
        "numpy==1.26.4 --hash=sha256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )
    stale = _finding(evaluate_inventory(tmp_path), "DEP-005")
    assert "requests" in stale.detail


def test_inventory_detects_hashless_lock_entry_with_extras(tmp_path):
    _write_project(tmp_path, dependencies=[])
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        "coverage[toml]==7.15.4\n",
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert finding.evidence["hashless"] == ["coverage"]


def test_inventory_rejects_lock_pin_below_metadata_specifier(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        "requests==1.0.0 --hash=sha256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "requests==1.0.0" in finding.detail


def test_repository_metadata_requirements_and_hash_lock_are_consistent():
    findings = evaluate_inventory(ROOT)
    lock_text = (ROOT / "requirements" / "constraints-py310.txt").read_text(
        encoding="utf-8"
    )

    assert not [
        finding
        for finding in findings
        if finding.id in {"DEP-001", "DEP-002", "DEP-005"}
    ]
    assert "--hash=sha256:" in lock_text
    assert read_project_dependencies(ROOT) <= _pinned_names(lock_text)


def test_repository_hash_lock_covers_multiple_platform_artifacts():
    lock_text = (ROOT / "requirements" / "constraints-py310.txt").read_text(
        encoding="utf-8"
    )
    hashes = _lock_hashes(lock_text)

    for package in ("numpy", "pandas", "matplotlib", "scipy"):
        assert len(hashes[package]) > 1, package


def test_lock_readme_records_reproducible_python310_installation():
    readme = (ROOT / "requirements" / "README.md").read_text(encoding="utf-8")

    assert "Python 3.10" in readme
    assert (
        "pip-compile --generate-hashes --extra dev --output-file "
        "requirements/constraints-py310.txt pyproject.toml"
    ) in readme
    assert (
        "pip install --require-hashes -r requirements/constraints-py310.txt" in readme
    )
    assert 'pip install --no-deps -e ".[dev]"' in readme
    assert "official PyPI release hashes" in readme
