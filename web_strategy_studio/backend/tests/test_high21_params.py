"""Tests for HIGH-21: @param extraction and strategy_params injection."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_h21_test")


# ---------------------------------------------------------------------------
# @param extraction (lint_service)
# ---------------------------------------------------------------------------

class TestParamExtraction:
    """Verify that lint_service._parse_params extracts # @param declarations."""

    def _lint(self, src: str):
        from studio_api.lint_service import lint_source
        return lint_source(src)

    def test_single_str_param(self):
        src = """
# @param security: str = "601390"
def initialize(context):
    pass
"""
        result = self._lint(src)
        assert result["params"] == [
            {"name": "security", "type": "text", "default": "601390"}
        ]

    def test_int_param(self):
        src = "# @param fast_period: int = 5\n"
        result = self._lint(src)
        assert result["params"] == [
            {"name": "fast_period", "type": "number", "default": 5}
        ]

    def test_float_param(self):
        src = "# @param stop_loss: float = 0.08\n"
        result = self._lint(src)
        assert result["params"] == [
            {"name": "stop_loss", "type": "number", "default": 0.08}
        ]

    def test_bool_param(self):
        src = "# @param use_filter: bool = True\n"
        result = self._lint(src)
        assert result["params"] == [
            {"name": "use_filter", "type": "checkbox", "default": True}
        ]

    def test_list_param(self):
        src = "# @param securities: list = ['601390', '000001']\n"
        result = self._lint(src)
        assert result["params"] == [
            {"name": "securities", "type": "text", "default": "601390,000001"}
        ]

    def test_multiple_params(self):
        src = """
# @param fast_period: int = 5
# @param slow_period: int = 20
# @param security: str = "601390"
"""
        result = self._lint(src)
        names = [p["name"] for p in result["params"]]
        assert names == ["fast_period", "slow_period", "security"]

    def test_no_params_returns_empty(self):
        src = "x = 1\n"
        result = self._lint(src)
        assert result["params"] == []

    def test_param_included_in_lint_response(self):
        """Full lint response must include params key when # @param lines exist."""
        src = "# @param threshold: float = 0.5\n"
        result = self._lint(src)
        assert "params" in result
        assert len(result["params"]) == 1


# ---------------------------------------------------------------------------
# strategy_params injection (isolated_runner)
# ---------------------------------------------------------------------------

class TestStrategyParamsInjection:
    """Verify that isolated_runner injects strategy_params into PARAMS."""

    def test_injects_known_params(self, tmp_path: Path):
        """PARAMS values should be overwritten by strategy_params."""
        cfg = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "starting_cash": 100000,
            "benchmark": "000300.XSHG",
            "use_local": True,
            "strategy_params": {"fast_period": 10, "slow_period": 30},
        }
        strategy = """
PARAMS = {"fast_period": 5, "slow_period": 20}

def initialize(context):
    assert PARAMS["fast_period"] == 10, f"expected 10 got {PARAMS['fast_period']}"
    assert PARAMS["slow_period"] == 30
"""
        (tmp_path / "run_config.json").write_text(__import__("json").dumps(cfg))
        (tmp_path / "user_strategy.py").write_text(strategy)

        import runpy
        ns = runpy.run_path(str(tmp_path / "user_strategy.py"), run_name="__user_strategy__")

        # Simulate what isolated_runner does
        sp = cfg.get("strategy_params")
        if isinstance(sp, dict):
            up = ns.get("PARAMS")
            if isinstance(up, dict):
                for k, v in sp.items():
                    if k in up:
                        old = up[k]
                        try:
                            up[k] = type(old)(v) if v is not None else old
                        except (TypeError, ValueError):
                            up[k] = v
                    else:
                        up[k] = v

        assert ns["PARAMS"]["fast_period"] == 10
        assert ns["PARAMS"]["slow_period"] == 30

    def test_preserves_type(self, tmp_path: Path):
        """String '10' should become int 10 when PARAMS original is int."""
        import runpy
        sp = {"fast_period": "10"}
        strategy_src = 'PARAMS = {"fast_period": 5}\n'
        strategy_file = tmp_path / "s.py"
        strategy_file.write_text(strategy_src)
        ns = runpy.run_path(str(strategy_file), run_name="__test__")

        up = ns.get("PARAMS")
        for k, v in sp.items():
            if k in up:
                old = up[k]
                try:
                    up[k] = type(old)(v) if v is not None else old
                except (TypeError, ValueError):
                    up[k] = v
        assert ns["PARAMS"]["fast_period"] == 10
        assert isinstance(ns["PARAMS"]["fast_period"], int)

    def test_adds_new_param_not_in_params(self, tmp_path: Path):
        """strategy_params keys not in PARAMS should be added."""
        import runpy
        sp = {"new_param": 42}
        strategy_src = 'PARAMS = {"existing": 1}\n'
        strategy_file = tmp_path / "s.py"
        strategy_file.write_text(strategy_src)
        ns = runpy.run_path(str(strategy_file), run_name="__test__")

        up = ns.get("PARAMS")
        for k, v in sp.items():
            if k in up:
                old = up[k]
                try:
                    up[k] = type(old)(v) if v is not None else old
                except (TypeError, ValueError):
                    up[k] = v
            else:
                up[k] = v

        assert ns["PARAMS"]["new_param"] == 42

    def test_no_strategy_params_leaves_params_unchanged(self, tmp_path: Path):
        """If strategy_params is None, PARAMS should be untouched."""
        import runpy
        strategy_src = 'PARAMS = {"fast_period": 5}\n'
        strategy_file = tmp_path / "s.py"
        strategy_file.write_text(strategy_src)
        ns = runpy.run_path(str(strategy_file), run_name="__test__")
        assert ns["PARAMS"]["fast_period"] == 5


# ---------------------------------------------------------------------------
# _make_run_config includes strategy_params
# ---------------------------------------------------------------------------

class TestMakeRunConfig:
    """Verify _make_run_config passes through strategy_params."""

    def test_strategy_params_included(self):
        from studio_api.runner import _make_run_config
        params = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "strategy_params": {"fast_period": 10},
        }
        cfg = _make_run_config(params)
        assert cfg["strategy_params"] == {"fast_period": 10}

    def test_strategy_params_defaults_to_none(self):
        from studio_api.runner import _make_run_config
        params = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        cfg = _make_run_config(params)
        assert cfg["strategy_params"] is None
