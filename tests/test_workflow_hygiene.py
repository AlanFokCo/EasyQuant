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


def test_python310_workflows_install_the_hash_locked_dependency_closure():
    for workflow_name in ("test.yml", "eqlib-evaluator.yml"):
        workflow = (ROOT / ".github" / "workflows" / workflow_name).read_text()

        assert "pip install --require-hashes -r requirements/constraints-py310.txt" in workflow
        assert 'pip install --no-deps -e ".[dev]"' in workflow
