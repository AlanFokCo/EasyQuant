"""Tests for checked dual-target resolver evidence bound to the hash lock."""

from __future__ import annotations

from hashlib import sha256
import json
import importlib.util
from pathlib import Path
import subprocess
import sys

from evaluator.inventory import (
    evaluate_inventory,
    lock_input_fingerprint,
    lock_input_fingerprint_header,
)


_SCHEMA = "eqlib-py310-resolver-evidence-v1"
_MACOS_3100_TARGET = "cpython-3.10.0-macos-arm64"
_MACOS_31020_TARGET = "cpython-3.10.20-macos-arm64"
_LINUX_3100_TARGET = "cpython-3.10.0-manylinux-x86_64"
_LINUX_31020_TARGET = "cpython-3.10.20-manylinux-x86_64"
ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "requirements" / "generate_target_lock_evidence.py"


def _write_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        """[project]
name = "resolver-evidence-fixture"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = ["requests>=2.28"]
""",
        encoding="utf-8",
    )


def _pin(name: str, version: str, marker: str | None, digest: str) -> str:
    requirement = f"{name}=={version}"
    if marker:
        requirement += f" ; {marker}"
    return requirement + " \\\n" + "    --hash=sha256:" + digest * 64 + "\n"


def _write_lock(root: Path) -> Path:
    requirements = root / "requirements"
    requirements.mkdir()
    lock = requirements / "constraints-py310.txt"
    lock.write_text(
        lock_input_fingerprint_header(root)
        + _pin("requests", "2.34.2", None, "a")
        + _pin("linux-only", "1.0.0", 'sys_platform == "linux"', "b")
        + _pin("macos-only", "2.0.0", 'sys_platform == "darwin"', "c")
        + _pin(
            "python-3100-only",
            "3.0.0",
            'python_full_version < "3.10.2"',
            "d",
        ),
        encoding="utf-8",
    )
    return lock


def _commands() -> dict[str, list[str]]:
    base = [
        "uv",
        "pip",
        "compile",
        "pyproject.toml",
        "--extra",
        "dev",
        "--python",
        "python3.10",
    ]
    runtime_suffix = ["--no-header", "--no-annotate", "--no-progress"]
    universal = [
        *base,
        "--python-version",
        "3.10",
        "--universal",
        "--generate-hashes",
        "--no-strip-markers",
        "--no-progress",
    ]
    return {
        _MACOS_3100_TARGET: universal,
        _LINUX_3100_TARGET: universal,
        _MACOS_31020_TARGET: [
            *base,
            "--python-version",
            "3.10.20",
            "--python-platform",
            "aarch64-apple-darwin",
            *runtime_suffix,
        ],
        _LINUX_31020_TARGET: [
            *base,
            "--python-version",
            "3.10.20",
            "--python-platform",
            "x86_64-manylinux_2_17",
            *runtime_suffix,
        ],
    }


def _write_evidence(
    root: Path,
    lock: Path,
    *,
    fingerprint: str | None = None,
    macos_3100_pins: dict[str, str] | None = None,
    macos_31020_pins: dict[str, str] | None = None,
    linux_3100_pins: dict[str, str] | None = None,
    linux_31020_pins: dict[str, str] | None = None,
) -> Path:
    evidence = lock.with_name("constraints-py310-resolver-evidence.json")
    payload = {
        "schema": _SCHEMA,
        "lock_sha256": sha256(lock.read_bytes()).hexdigest(),
        "lock_input_fingerprint": "v1:"
        + (fingerprint if fingerprint is not None else lock_input_fingerprint(root)),
        "resolver": {
            "tool": "uv",
            "version": "0.12.5",
            "commands": _commands(),
        },
        "targets": {
            _MACOS_3100_TARGET: {
                "platform": "macos",
                "python_full_version": "3.10.0",
                "pins": (
                    macos_3100_pins
                    if macos_3100_pins is not None
                    else {
                        "macos-only": "2.0.0",
                        "python-3100-only": "3.0.0",
                        "requests": "2.34.2",
                    }
                ),
            },
            _MACOS_31020_TARGET: {
                "platform": "macos",
                "python_full_version": "3.10.20",
                "pins": (
                    macos_31020_pins
                    if macos_31020_pins is not None
                    else {"macos-only": "2.0.0", "requests": "2.34.2"}
                ),
            },
            _LINUX_3100_TARGET: {
                "platform": "linux",
                "python_full_version": "3.10.0",
                "pins": (
                    linux_3100_pins
                    if linux_3100_pins is not None
                    else {
                        "linux-only": "1.0.0",
                        "python-3100-only": "3.0.0",
                        "requests": "2.34.2",
                    }
                ),
            },
            _LINUX_31020_TARGET: {
                "platform": "linux",
                "python_full_version": "3.10.20",
                "pins": (
                    linux_31020_pins
                    if linux_31020_pins is not None
                    else {"linux-only": "1.0.0", "requests": "2.34.2"}
                ),
            },
        },
    }
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def _finding(root: Path):
    return next(item for item in evaluate_inventory(root) if item.id == "DEP-005")


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "target_resolver_evidence_generator", GENERATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_requires_checked_resolver_evidence(tmp_path):
    _write_project(tmp_path)
    _write_lock(tmp_path)

    finding = _finding(tmp_path)

    assert "resolver evidence" in finding.detail.lower()


def test_inventory_accepts_matching_checked_resolver_evidence(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(tmp_path, lock)

    findings = evaluate_inventory(tmp_path)

    assert not [finding for finding in findings if finding.id == "DEP-005"]


def test_inventory_rejects_evidence_bound_to_changed_lock(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(tmp_path, lock)
    lock.write_text(
        lock.read_text(encoding="utf-8").replace("a" * 64, "d" * 64),
        encoding="utf-8",
    )

    finding = _finding(tmp_path)

    assert "sha256" in finding.detail.lower()


def test_inventory_rejects_evidence_with_altered_fingerprint(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(tmp_path, lock, fingerprint="0" * 64)

    finding = _finding(tmp_path)

    assert "fingerprint" in finding.detail.lower()


def test_inventory_rejects_evidence_missing_linux_only_pin(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(
        tmp_path,
        lock,
        linux_3100_pins={"python-3100-only": "3.0.0", "requests": "2.34.2"},
        linux_31020_pins={"requests": "2.34.2"},
    )

    finding = _finding(tmp_path)

    assert "linux-only" in finding.detail


def test_inventory_rejects_evidence_missing_macos_only_pin(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(
        tmp_path,
        lock,
        macos_3100_pins={"python-3100-only": "3.0.0", "requests": "2.34.2"},
        macos_31020_pins={"requests": "2.34.2"},
    )

    finding = _finding(tmp_path)

    assert "macos-only" in finding.detail


def test_inventory_rejects_evidence_pin_version_drift(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(
        tmp_path,
        lock,
        linux_31020_pins={"linux-only": "1.0.0", "requests": "9.9.9"},
    )

    finding = _finding(tmp_path)

    assert "requests" in finding.detail
    assert "version" in finding.detail.lower()


def test_inventory_rejects_malformed_resolver_evidence(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    evidence = lock.with_name("constraints-py310-resolver-evidence.json")
    evidence.write_text("{not json}\n", encoding="utf-8")

    finding = _finding(tmp_path)

    assert "resolver evidence" in finding.detail.lower()


def test_inventory_requires_python_3100_boundary_evidence(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    _write_evidence(
        tmp_path,
        lock,
        macos_3100_pins={"macos-only": "2.0.0", "requests": "2.34.2"},
    )

    finding = _finding(tmp_path)

    assert "python-3100-only" in finding.detail


def test_generator_writes_deterministic_evidence_for_boundary_and_runtime_targets(
    tmp_path,
):
    generator = _load_generator()
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    universal_resolved = tmp_path / "universal.txt"
    linux_resolved = tmp_path / "linux.txt"
    macos_resolved = tmp_path / "macos.txt"
    output = tmp_path / "evidence.json"
    universal_resolved.write_text(lock.read_text(encoding="utf-8"), encoding="utf-8")
    linux_resolved.write_text("requests==2.34.2\nlinux-only==1.0.0\n", encoding="utf-8")
    macos_resolved.write_text("requests==2.34.2\nmacos-only==2.0.0\n", encoding="utf-8")

    generated = generator.generate(
        lock,
        universal_resolved,
        macos_resolved,
        linux_resolved,
        output,
    )

    assert generated["schema"] == _SCHEMA
    assert generated["lock_sha256"] == sha256(lock.read_bytes()).hexdigest()
    assert generated["lock_input_fingerprint"] == "v1:" + lock_input_fingerprint(
        tmp_path
    )
    assert generated["resolver"]["commands"] == _commands()
    assert generated["targets"][_LINUX_3100_TARGET]["pins"] == {
        "linux-only": "1.0.0",
        "python-3100-only": "3.0.0",
        "requests": "2.34.2",
    }
    assert generated["targets"][_MACOS_3100_TARGET]["pins"] == {
        "macos-only": "2.0.0",
        "python-3100-only": "3.0.0",
        "requests": "2.34.2",
    }
    assert generated["targets"][_LINUX_31020_TARGET]["pins"] == {
        "linux-only": "1.0.0",
        "requests": "2.34.2",
    }
    assert generated["targets"][_MACOS_31020_TARGET]["pins"] == {
        "macos-only": "2.0.0",
        "requests": "2.34.2",
    }
    first = output.read_text(encoding="utf-8")
    generator.generate(lock, universal_resolved, macos_resolved, linux_resolved, output)
    assert output.read_text(encoding="utf-8") == first


def test_generator_cli_runs_from_repository_root(tmp_path):
    _write_project(tmp_path)
    lock = _write_lock(tmp_path)
    universal_resolved = tmp_path / "universal.txt"
    linux_resolved = tmp_path / "linux.txt"
    macos_resolved = tmp_path / "macos.txt"
    output = tmp_path / "evidence.json"
    universal_resolved.write_text(lock.read_text(encoding="utf-8"), encoding="utf-8")
    linux_resolved.write_text("requests==2.34.2\nlinux-only==1.0.0\n", encoding="utf-8")
    macos_resolved.write_text("requests==2.34.2\nmacos-only==2.0.0\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            str(lock),
            str(output),
            "--universal-resolved",
            str(universal_resolved),
            "--macos-resolved",
            str(macos_resolved),
            "--linux-resolved",
            str(linux_resolved),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output.is_file()
