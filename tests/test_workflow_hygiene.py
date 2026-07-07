"""Regression tests for GitHub Actions workflow hygiene."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_hygiene_script_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_workflows.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
