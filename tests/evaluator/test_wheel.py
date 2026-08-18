"""Tests for freshly built wheel metadata and isolated-install evidence."""

from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from evaluator.wheel import (
    _CommandResult,
    _installation_findings,
    _metadata_findings,
    _read_wheel_metadata,
    _run,
    build_and_audit_wheel,
    requirement_name,
)


ROOT = Path(__file__).resolve().parents[2]


def test_wheel_metadata_parser_reads_metadata_from_wheel_not_egg_info(tmp_path):
    wheel_path = tmp_path / "fixture-0.0.0-py3-none-any.whl"
    with ZipFile(wheel_path, "w") as archive:
        archive.writestr(
            "fixture-0.0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: fixture\nVersion: 0.0.0\n"
            "Requires-Dist: requests (>=2.28)\n",
        )
        archive.writestr("fixture/__init__.py", "")

    metadata = _read_wheel_metadata(wheel_path)

    assert metadata["name"] == "fixture"
    assert metadata["requires_dist"] == ["requests (>=2.28)"]


def test_wheel_metadata_comparison_accepts_declared_extra_requirements(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "wheel-fixture"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = ["requests>=2.28"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
""",
        encoding="utf-8",
    )

    findings = _metadata_findings(
        tmp_path,
        {
            "requires_python": ">=3.10",
            "requires_dist": [
                "requests>=2.28",
                'pytest>=7.0; extra == "dev"',
            ],
        },
    )

    assert findings == []


def test_wheel_metadata_comparison_detects_requirement_and_python_drift(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "wheel-fixture"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = ["requests>=2.28"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
""",
        encoding="utf-8",
    )

    findings = _metadata_findings(
        tmp_path,
        {
            "requires_python": ">=3.9",
            "requires_dist": [
                "requests>=1.0",
                'pytest>=7.0; extra == "cache"',
            ],
        },
    )

    assert [finding.id for finding in findings] == ["DEP-003"]
    assert "requires-python" in findings[0].detail
    assert "requests>=2.28" in findings[0].detail


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="the release wheel declares Python >=3.10",
)
def test_wheel_metadata_contains_declared_runtime_dependencies(tmp_path):
    evidence, findings = build_and_audit_wheel(ROOT, tmp_path)

    names = {requirement_name(item) for item in evidence["requires_dist"]}
    assert {"requests", "scikit-learn"} <= names
    assert evidence["wheel_path"].endswith(".whl")
    assert not any(item.id == "DEP-003" for item in findings)


def test_blocked_package_index_is_unavailable_with_bounded_evidence():
    install = _CommandResult(
        command=("python", "-m", "pip", "install", "fixture.whl"),
        returncode=1,
        stdout="WARNING: Retrying (Retry(total=0)) after connection broken\n"
        + "x" * 20_000,
        stderr="ERROR: Could not fetch URL https://index.example/simple/fixture/\n",
        timed_out=False,
    )
    pip_check = _CommandResult(
        command=("python", "-m", "pip", "check"),
        returncode=1,
        stdout="fixture has not been installed\n",
        stderr="",
        timed_out=False,
    )

    findings = _installation_findings(install, pip_check)

    assert [item.id for item in findings] == ["DEP-004"]
    assert findings[0].status == "unavailable"
    assert len(findings[0].detail) <= 4_500
    assert "x" * 5_000 not in findings[0].detail
    assert len(findings[0].evidence["install"]["stdout"]) <= 4_000
    assert "x" * 5_000 not in findings[0].evidence["install"]["stdout"]


def test_truncated_index_error_remains_an_unavailable_finding():
    install = _run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * 2500 + 'connection broken' + 'x' * 2500); sys.exit(1)",
        ],
        timeout=10,
    )
    pip_check = _CommandResult(
        command=("python", "-m", "pip", "check"),
        returncode=1,
        stdout="",
        stderr="",
    )

    findings = _installation_findings(install, pip_check)

    assert "connection broken" not in install.stdout
    assert [finding.id for finding in findings] == ["DEP-004"]


def test_wheel_audit_install_disables_cache_and_inherited_pip_config(
    monkeypatch, tmp_path
):
    root = tmp_path / "source"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        """[project]
name = "wheel-fixture"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = []
""",
        encoding="utf-8",
    )
    work_dir = tmp_path / "audit"
    calls = []

    def fake_run(command, **_kwargs):
        command = tuple(command)
        calls.append(command)
        if command[1:3] == ("-m", "build"):
            wheel_path = Path(command[-1]) / "wheel_fixture-0.0.0-py3-none-any.whl"
            with ZipFile(wheel_path, "w") as archive:
                archive.writestr(
                    "wheel_fixture-0.0.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: wheel-fixture\nVersion: 0.0.0\n"
                    "Requires-Python: >=3.10\n",
                )
            return _CommandResult(command, 0, "", "")
        if command[1:3] == ("-m", "venv"):
            venv_python = Path(command[-1]) / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.touch()
            return _CommandResult(command, 0, "", "")
        if command[1:4] == ("-m", "pip", "install"):
            assert "--isolated" in command
            assert "--no-cache-dir" in command
            return _CommandResult(command, 1, "", "connection broken")
        return _CommandResult(command, 1, "", "")

    monkeypatch.setattr("evaluator.wheel._run", fake_run)

    _evidence, findings = build_and_audit_wheel(root, work_dir)

    assert any(command[1:4] == ("-m", "pip", "install") for command in calls)
    assert [finding.id for finding in findings] == ["DEP-004"]
