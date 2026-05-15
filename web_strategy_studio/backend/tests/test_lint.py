"""Tests for studio_api.lint_service (Phase 0)."""

from __future__ import annotations

import pytest

from studio_api.lint_service import lint_source


class TestSyntaxErrors:
    def test_valid_python_passes(self):
        src = "x = 1 + 2\nprint(x)\n"
        result = lint_source(src)
        assert result["syntax_errors"] == []

    def test_syntax_error_detected(self):
        src = "def foo(\n"  # unclosed paren
        result = lint_source(src)
        assert len(result["syntax_errors"]) > 0
        assert result["ok"] is False

    def test_ok_false_on_syntax_error(self):
        src = "class (\n"
        result = lint_source(src)
        assert result["ok"] is False


class TestSecurityScanner:
    def test_banned_import_exec_blocked(self):
        src = "import os\nexec('rm -rf /')\n"
        result = lint_source(src)
        # exec() is banned — should make ok=False
        assert result["ok"] is False
        codes = [n["code"] for n in result["security_notes"]]
        assert any("EQ-BANNED" in c for c in codes)

    def test_clean_strategy_passes(self):
        src = (
            "from eqlib import *\n"
            "\n"
            "def initialize(context):\n"
            "    g.security = '601390'\n"
            "    set_benchmark('000300.XSHG')\n"
            "    run_daily(market_open, time='every_bar')\n"
            "\n"
            "def market_open(context):\n"
            "    pass\n"
        )
        result = lint_source(src)
        assert result["ok"] is True
        assert result["syntax_errors"] == []

    def test_missing_initialize_noted(self):
        src = "x = 1\n"
        result = lint_source(src)
        # require_initialize_function raises a security note
        assert any("initialize" in n["message"].lower() for n in result["security_notes"])


class TestReturnShape:
    def test_result_has_all_keys(self):
        result = lint_source("x = 1\n")
        assert "ok" in result
        assert "syntax_errors" in result
        assert "lint_issues" in result
        assert "security_notes" in result
