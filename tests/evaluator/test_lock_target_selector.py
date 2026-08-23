"""Tests for the deterministic Python 3.10 dual-target lock selector."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "requirements" / "select_py310_targets.py"


def _load_selector():
    spec = importlib.util.spec_from_file_location("lock_target_selector", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selector_keeps_exactly_python310_mac_and_linux_active_entries(tmp_path):
    selector = _load_selector()
    source = tmp_path / "universal.txt"
    output = tmp_path / "constraints-py310.txt"
    source.write_text(
        "common==1.0.0 \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n"
        "linux-only==2.0.0 ; sys_platform == 'linux' \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n"
        "mac-only==3.0.0 ; sys_platform == 'darwin' \\\n"
        "    --hash=sha256:" + "c" * 64 + "\n"
        "future-only==4.0.0 ; python_version >= '3.11' \\\n"
        "    --hash=sha256:" + "d" * 64 + "\n",
        encoding="utf-8",
    )

    selected = selector.select(source, output)

    rendered = output.read_text(encoding="utf-8")
    assert selected == 3
    assert "common==1.0.0" in rendered
    assert 'linux-only==2.0.0 ; sys_platform == "linux"' in rendered
    assert 'mac-only==3.0.0 ; sys_platform == "darwin"' in rendered
    assert "future-only" not in rendered
    assert rendered.index("common==") < rendered.index("linux-only==")


def test_selector_keeps_entries_active_only_at_python31020_boundary(tmp_path):
    selector = _load_selector()
    source = tmp_path / "universal.txt"
    output = tmp_path / "constraints-py310.txt"
    source.write_text(
        "runtime-patch-only==1.0.0 ; python_full_version >= '3.10.10' and python_full_version < '3.10.21' \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n",
        encoding="utf-8",
    )

    selected = selector.select(source, output)

    assert selected == 1
    assert "runtime-patch-only==1.0.0" in output.read_text(encoding="utf-8")


def test_selector_fails_closed_for_direct_urls_without_replacing_output(tmp_path):
    selector = _load_selector()
    source = tmp_path / "universal.txt"
    output = tmp_path / "constraints-py310.txt"
    source.write_text(
        "package @ https://example.invalid/package.whl \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n",
        encoding="utf-8",
    )
    output.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match="direct URL"):
        selector.select(source, output)

    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_selector_rejects_overlapping_target_specific_pins(tmp_path):
    selector = _load_selector()
    source = tmp_path / "universal.txt"
    output = tmp_path / "constraints-py310.txt"
    source.write_text(
        "platform-demo==1 ; sys_platform == 'darwin' \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n"
        "platform-demo==2 ; sys_platform != 'linux' \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n",
        encoding="utf-8",
    )
    output.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match="overlapping"):
        selector.select(source, output)

    assert output.read_text(encoding="utf-8") == "sentinel\n"
