"""Smoke tests for all example files.

Validates:
1. Syntax: every .py file compiles without errors
2. Imports: every module can be imported without ImportError
3. Standards: no star imports, no private API usage, docstrings, __main__ guards
"""

import importlib.util
import py_compile
import re
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _get_example_files():
    """Return all .py files in examples/ (excluding _defaults and __init__)."""
    files = []
    for f in EXAMPLES_DIR.rglob("*.py"):
        name = f.name
        if name.startswith("_") or name == "__init__.py":
            continue
        files.append(f)
    return sorted(files)


# ============================================================
# 1. Syntax checks
# ============================================================

class TestSyntax:
    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_compiles(self, filepath):
        """Every example file must compile without syntax errors."""
        try:
            py_compile.compile(str(filepath), doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"{filepath.name} has syntax error: {e}")


# ============================================================
# 2. Import checks
# ============================================================

class TestImports:
    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_importable(self, filepath):
        """Every example file must be importable (all deps resolve)."""
        spec = importlib.util.spec_from_file_location(
            f"example_{filepath.stem}", str(filepath))
        if spec is None:
            pytest.fail(f"Cannot create import spec for {filepath.name}")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            # Some examples call sys.exit in __main__ — that's OK during import
            pass
        except Exception as e:
            pytest.fail(f"{filepath.name} failed to import: {e}")


# ============================================================
# 3. Code standards checks
# ============================================================

class TestStandards:
    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_no_star_imports(self, filepath):
        """Examples must use explicit imports, not 'from eqlib import *'."""
        content = filepath.read_text()
        if re.search(r"from\s+eqlib\s+import\s+\*", content):
            pytest.fail(f"{filepath.name} uses 'from eqlib import *'")

    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_no_private_apis(self, filepath):
        """Examples must not import private (underscore-prefixed) APIs."""
        content = filepath.read_text()
        private_patterns = [
            r"from\s+eqlib\.\w+\s+import\s+_\w+",
            r"from\s+eqlib\s+import\s+_\w+",
            r"eqlib\._\w+",
        ]
        for pattern in private_patterns:
            match = re.search(pattern, content)
            if match:
                pytest.fail(
                    f"{filepath.name} uses private API: {match.group()}")

    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_has_docstring(self, filepath):
        """Every example must have a module-level docstring."""
        content = filepath.read_text().strip()
        if not content.startswith(('"""', "'''", 'r"""', "r'''")):
            pytest.fail(f"{filepath.name} missing module docstring")

    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_has_main_guard(self, filepath):
        """Every example must have an if __name__ == '__main__' guard."""
        content = filepath.read_text()
        if 'if __name__' not in content:
            pytest.fail(f"{filepath.name} missing __main__ guard")

    @pytest.mark.parametrize("filepath", _get_example_files(),
                             ids=lambda p: p.name)
    def test_uses_defaults(self, filepath):
        """Strategy examples should import from _defaults for consistency."""
        content = filepath.read_text()
        # Check if file has a backtest (uses run_strategy or run_backtest)
        has_backtest = any(kw in content for kw in
                           ["run_strategy", "run_backtest",
                            "run_portfolio_backtest"])
        if has_backtest and "_defaults" not in content:
            pytest.fail(
                f"{filepath.name} has backtest but doesn't import _defaults")
