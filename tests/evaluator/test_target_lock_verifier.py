"""Tests for marker-aware comparison of a target resolver result and lock."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "requirements" / "verify_target_lock.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("target_lock_verifier", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifier_matches_linux_active_markers_and_exact_pins(tmp_path):
    verifier = _load_verifier()
    lock = tmp_path / "constraints-py310.txt"
    resolved = tmp_path / "resolved-linux.txt"
    lock.write_text(
        "common==1.0.0 \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n"
        "linux-only==2.0.0 ; sys_platform == 'linux' \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n"
        "mac-only==3.0.0 ; sys_platform == 'darwin' \\\n"
        "    --hash=sha256:" + "c" * 64 + "\n",
        encoding="utf-8",
    )
    resolved.write_text("common==1.0.0\nlinux-only==2.0.0\n", encoding="utf-8")

    comparison = verifier.compare(lock, resolved, platform="linux")

    assert comparison == {"missing": [], "extra": [], "version_mismatch": []}


def test_verifier_detects_omitted_linux_marker_transitive_pin(tmp_path):
    verifier = _load_verifier()
    lock = tmp_path / "constraints-py310.txt"
    resolved = tmp_path / "resolved-linux.txt"
    lock.write_text(
        "pytest==9.1.1 \\\n" "    --hash=sha256:" + "a" * 64 + "\n",
        encoding="utf-8",
    )
    resolved.write_text(
        "pytest==9.1.1\nexceptiongroup==1.3.1\n",
        encoding="utf-8",
    )

    comparison = verifier.compare(lock, resolved, platform="linux")

    assert comparison["missing"] == ["exceptiongroup"]
