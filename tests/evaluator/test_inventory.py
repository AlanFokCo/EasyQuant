"""Tests for release dependency inventory and AST-only import auditing."""

from __future__ import annotations

import json
from hashlib import sha256
import re
from pathlib import Path

from evaluator.inventory import (
    _LOCK_TARGET_MATRIX,
    _active_hash_lock_pins,
    _read_hash_lock,
    _resolver_evidence_resolver,
    evaluate_inventory,
    lock_input_fingerprint,
    lock_input_fingerprint_header,
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


def _write_valid_requests_hash_lock(root: Path, suffix: str = "") -> None:
    requirements_dir = root / "requirements"
    requirements_dir.mkdir(exist_ok=True)
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(root)
        + "requests==2.34.2 \\\n"
        + "    --hash=sha256:"
        + "0" * 64
        + "\n"
        + suffix,
        encoding="utf-8",
    )


def _hash_lock_pin(requirement: str, digest: str = "0") -> str:
    return f"{requirement} \\\n    --hash=sha256:{digest * 64}\n"


def _write_matching_resolver_evidence(root: Path) -> None:
    lock_path = root / "requirements" / "constraints-py310.txt"
    pins = _read_hash_lock(lock_path)
    payload = {
        "schema": "eqlib-py310-resolver-evidence-v1",
        "lock_sha256": sha256(lock_path.read_bytes()).hexdigest(),
        "lock_input_fingerprint": "v1:" + lock_input_fingerprint(root),
        "resolver": _resolver_evidence_resolver(),
        "targets": {
            target["id"]: {
                "platform": target["platform"],
                "python_full_version": target["python_full_version"],
                "pins": _active_hash_lock_pins(pins, target),
            }
            for target in _LOCK_TARGET_MATRIX
        },
    }
    lock_path.with_name("constraints-py310-resolver-evidence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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


def test_inventory_compares_pep508_requirements_semantically(tmp_path):
    _write_project(
        tmp_path,
        dependencies=['Requests[socks] >= 2.28 ; python_version < "3.11"'],
    )
    _write_runtime_module(tmp_path, "import requests\n")
    (tmp_path / "requirements.txt").write_text(
        "requests[socks]>=2.28; python_version < '3.11'\n",
        encoding="utf-8",
    )

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-002"]


def test_inventory_normalizes_equivalent_pep508_marker_order(tmp_path):
    _write_project(
        tmp_path,
        dependencies=[
            'requests>=2.28; python_version < "3.11" and sys_platform == "darwin"'
        ],
    )
    _write_runtime_module(tmp_path, "import requests\n")
    (tmp_path / "requirements.txt").write_text(
        'requests>=2.28; sys_platform == "darwin" and python_version < "3.11"\n',
        encoding="utf-8",
    )

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-002"]


def test_inventory_rejects_duplicate_canonical_requirement_names(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.0"])
    _write_runtime_module(tmp_path, "import requests\n")
    (tmp_path / "requirements.txt").write_text(
        "requests>=2.0\nRequests>=2.0\n",
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-002")

    assert "duplicate" in finding.detail.lower()


def test_inventory_reports_invalid_project_pep508_declaration(tmp_path):
    _write_project(tmp_path, dependencies=["requests @"])
    _write_runtime_module(tmp_path, "import requests\n")

    finding = _finding(evaluate_inventory(tmp_path), "DEP-002")

    assert "invalid" in finding.detail.lower()
    assert "project" in finding.title.lower()


def test_inventory_rejects_duplicate_inactive_direct_declarations(tmp_path):
    _write_project(
        tmp_path,
        dependencies=[
            'requests>=2 ; sys_platform == "win32"',
            'Requests>=2 ; sys_platform == "win32"',
        ],
    )
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path)
        + "tomli==2.0.0 --hash=sha256:"
        + "0" * 64
        + "\n",
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-002")

    assert "duplicate" in finding.detail.lower()


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


def test_ast_scan_skips_type_checking_and_provably_dead_import_branches(tmp_path):
    _write_project(tmp_path, dependencies=[])
    _write_runtime_module(
        tmp_path,
        "\n".join(
            [
                "import typing",
                "from typing import TYPE_CHECKING",
                "if TYPE_CHECKING:",
                "    import type_only",
                "else:",
                "    import type_checked_else",
                "if typing.TYPE_CHECKING:",
                "    import typing_type_only",
                "if False:",
                "    import false_only",
                "if 0:",
                "    import zero_only",
                "if []:",
                "    import empty_only",
                "if True:",
                "    import always_runtime",
                "else:",
                "    import true_else_only",
                "if runtime_condition:",
                "    import conditional_runtime",
            ]
        )
        + "\n",
    )

    imports = scan_runtime_imports(tmp_path)

    assert imports == {
        "always-runtime",
        "conditional-runtime",
        "type-checked-else",
    }


def test_ast_scan_skips_only_setuptools_shipped_root_packages(tmp_path):
    _write_project(tmp_path, dependencies=[])
    (tmp_path / "pyproject.toml").write_text(
        (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
        + '\n[tool.setuptools.packages.find]\ninclude = ["eqlib*", "published*"]\n',
        encoding="utf-8",
    )
    _write_runtime_module(
        tmp_path,
        "import published.module\nimport local_only.module\n",
    )
    for package in ("published", "local_only"):
        package_dir = tmp_path / package
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    imports = scan_runtime_imports(tmp_path)

    assert imports == {"local-only"}


def test_ast_scan_does_not_hide_scanned_root_excluded_by_setuptools(tmp_path):
    _write_project(tmp_path, dependencies=[])
    (tmp_path / "pyproject.toml").write_text(
        (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
        + '\n[tool.setuptools.packages.find]\ninclude = ["published*"]\n',
        encoding="utf-8",
    )
    _write_runtime_module(tmp_path, "import eqlib.external\n")

    imports = scan_runtime_imports(tmp_path)

    assert imports == {"eqlib"}


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


def test_inventory_rejects_unknown_hash_lock_directive(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(
        tmp_path,
        "--extra-index-url https://example.invalid/simple\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "extra-index-url" in finding.detail


def test_inventory_rejects_unpinned_hash_lock_requirement(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(
        tmp_path,
        "urllib3>=2.0 \\\n" + "    --hash=sha256:" + "1" * 64 + "\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "exact == pin" in finding.detail


def test_inventory_rejects_garbage_hash_lock_line(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(tmp_path, "this is not a lock requirement\n")

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "invalid requirement" in finding.detail


def test_inventory_rejects_orphan_hash_lock_continuation(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(
        tmp_path,
        "    --hash=sha256:" + "1" * 64 + "\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "orphan" in finding.detail


def test_inventory_rejects_direct_url_hash_lock_requirement(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(
        tmp_path,
        "other @ https://example.invalid/other.whl \\\n"
        + "    --hash=sha256:"
        + "1" * 64
        + "\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "direct URL" in finding.detail


def test_inventory_rejects_duplicate_active_hash_lock_pin(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(
        tmp_path,
        "urllib3==2.7.0 ; sys_platform == 'linux' \\\n"
        + "    --hash=sha256:"
        + "1" * 64
        + "\n"
        + "urllib3==2.7.0 ; sys_platform == 'linux' \\\n"
        + "    --hash=sha256:"
        + "2" * 64
        + "\n",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "malformed" in finding.title.lower()
    assert "duplicate active pin" in finding.detail


def test_inventory_accepts_documented_via_comment_in_hash_lock(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_valid_requests_hash_lock(tmp_path, "# via project\n")
    _write_matching_resolver_evidence(tmp_path)

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-005"]


def test_inventory_rejects_hash_lock_without_lock_input_fingerprint(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        _hash_lock_pin("requests==2.34.2"),
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "fingerprint" in finding.detail.lower()


def test_lock_input_fingerprint_is_stable_for_equivalent_metadata_order(tmp_path):
    _write_project(
        tmp_path,
        dependencies=["Requests >= 2.28", "numpy>=1.23"],
        optional_dependencies={"dev": ["pytest >= 7", "coverage[toml]>=7"]},
    )

    initial = lock_input_fingerprint(tmp_path)

    _write_project(
        tmp_path,
        dependencies=["numpy >= 1.23", "requests>=2.28"],
        optional_dependencies={"dev": ["coverage[toml] >= 7", "pytest>=7"]},
    )

    assert lock_input_fingerprint(tmp_path) == initial


def test_inventory_rejects_lock_when_input_fingerprint_drifts_despite_valid_pin(
    tmp_path,
):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    lock_path = requirements_dir / "constraints-py310.txt"
    lock_path.write_text(
        lock_input_fingerprint_header(tmp_path) + _hash_lock_pin("requests==2.34.2"),
        encoding="utf-8",
    )

    _write_project(tmp_path, dependencies=["requests>=2.29"])

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "fingerprint" in finding.detail.lower()
    assert finding.evidence["fingerprint_state"] == "valid"
    assert (
        finding.evidence["actual_lock_input_fingerprint"]
        != finding.evidence["expected_lock_input_fingerprint"]
    )


def test_inventory_rejects_multiple_lock_input_fingerprints(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path)
        + lock_input_fingerprint_header(tmp_path)
        + _hash_lock_pin("requests==2.34.2"),
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert finding.evidence["fingerprint_state"] == "malformed"


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
        _hash_lock_pin("numpy==1.26.4"),
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

    assert "exact pin must begin a hash continuation" in finding.detail


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


def test_inventory_evaluates_direct_markers_for_python310_targets(tmp_path):
    _write_project(
        tmp_path,
        dependencies=[
            "requests>=2.28",
            'future-only>=1; python_version >= "3.11"',
        ],
    )
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    lock_path = requirements_dir / "constraints-py310.txt"
    lock_path.write_text(
        lock_input_fingerprint_header(tmp_path) + _hash_lock_pin("requests==2.34.2"),
        encoding="utf-8",
    )
    _write_matching_resolver_evidence(tmp_path)

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-005"]


def test_inventory_rejects_lock_pin_inactive_on_all_python310_targets(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path)
        + _hash_lock_pin('requests==2.34.2 ; sys_platform == "win32"'),
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "active" in finding.detail.lower()
    assert "requests" in finding.detail


def test_inventory_allows_mutually_exclusive_direct_lock_markers(tmp_path):
    _write_project(
        tmp_path,
        dependencies=[
            'platform-demo==1 ; sys_platform == "linux"',
            'platform-demo==2 ; sys_platform == "darwin"',
        ],
    )
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path)
        + _hash_lock_pin('platform-demo==1 ; sys_platform == "linux"')
        + _hash_lock_pin('platform-demo==2 ; sys_platform == "darwin"', "1"),
        encoding="utf-8",
    )
    _write_matching_resolver_evidence(tmp_path)

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-005"]


def test_inventory_uses_python310_full_version_for_direct_lock_markers(tmp_path):
    _write_project(
        tmp_path,
        dependencies=[
            "requests>=2.28",
            'patch-only>=1; python_full_version < "3.10.1"',
        ],
    )
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path) + _hash_lock_pin("requests==2.34.2"),
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-005")

    assert "patch-only" in finding.detail


def test_inventory_reports_duplicate_project_metadata_declarations(tmp_path):
    _write_project(tmp_path, dependencies=["requests>=2.28", "Requests>=2.28"])
    _write_runtime_module(tmp_path, "import requests\n")
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "constraints-py310.txt").write_text(
        lock_input_fingerprint_header(tmp_path)
        + "requests==2.34.2 --hash=sha256:"
        + "0" * 64
        + "\n",
        encoding="utf-8",
    )

    finding = _finding(evaluate_inventory(tmp_path), "DEP-002")

    assert "duplicate" in finding.detail.lower()


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


def test_repository_hash_lock_keeps_explicit_linux_and_macos_branches():
    lock_text = (ROOT / "requirements" / "constraints-py310.txt").read_text(
        encoding="utf-8"
    )

    assert 'akracer==0.0.14 ; sys_platform == "linux"' in lock_text
    assert 'py-mini-racer==0.6.0 ; sys_platform == "linux"' in lock_text
    assert 'mini-racer==0.14.1 ; sys_platform != "linux"' in lock_text


def test_lock_readme_records_reproducible_python310_installation():
    readme = (ROOT / "requirements" / "README.md").read_text(encoding="utf-8")

    assert "Python 3.10" in readme
    assert "pip-compile" in readme
    assert "--allow-unsafe" in readme
    assert "--no-emit-find-links" in readme
    assert "uv 0.12.5" in readme
    assert "--universal --generate-hashes --no-strip-markers" in readme
    assert "select_py310_targets.py" in readme
    assert "verify_target_lock.py" in readme
    assert (
        "pip install --require-hashes -r requirements/constraints-py310.txt" in readme
    )
    assert 'pip install --no-deps -e ".[dev]"' in readme
    assert "official PyPI release hashes" in readme
    assert "pip download --require-hashes --no-deps" not in readme
    assert "does not prove closure" in readme
    assert "does not reproduce a future mutable-index" in readme
    assert "CPython 3.10.0" in readme
    assert "CPython 3.10.20" in readme
    assert "constraints-py310-resolver-evidence.json" in readme
    assert "Task 9" in readme
