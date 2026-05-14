"""Tests for P1, P2, P3, P4 fixes.

Coverage:
- H3: simple_factor_analysis rename + deprecated fama_french_analysis alias
- H5: attribute_history fq validation in backtest mode
- H7: _get_trading_days prefers sina calendar
- M3: Thread-safe data._cache
- M7: walk_forward framework
- M8: StrategyConfig.use_local field
- S1: CORS configuration via settings
- S4: StreamHub cleanup on done/error
- S6: Idempotency TTL format in runs.py
- E7: API stability markers in __init__.py
"""

from __future__ import annotations

import asyncio
import threading
import warnings
from datetime import date
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────────────────────────────────────
# H3: simple_factor_analysis rename + deprecated alias
# ──────────────────────────────────────────────────────────────────────────────

class TestH3SimpleFactorAnalysisRename:
    """H3: fama_french_analysis → simple_factor_analysis."""

    def _make_minimal_result(self):
        """Build a minimal backtest result dict for attribution tests."""
        import pandas as pd
        import datetime as dt

        ctx = MagicMock()
        ctx.portfolio.total_value = 110000.0
        ctx.portfolio.starting_cash = 100000.0
        ctx.portfolio.positions = {}
        ctx.benchmark = "000300.XSHG"
        ctx.current_dt = dt.datetime(2024, 12, 31)

        dates = pd.date_range("2024-01-02", "2024-12-31", freq="B")
        strategy_values = [100000 * (1 + 0.0003) ** i for i in range(len(dates))]
        bench_values = [100000 * (1 + 0.0002) ** i for i in range(len(dates))]

        # recorded_values format: {date: {"date": date, "total_value": ..., "bench_value": ...}}
        recorded = {}
        for d, sv, bv in zip(dates, strategy_values, bench_values):
            key = d.date()
            recorded[key] = {
                "date": key,
                "total_value": sv,
                "bench_value": bv,
            }

        return {
            "context": ctx,
            "trade_log": [],
            "recorded_values": recorded,
            "benchmark": "000300.XSHG",
        }

    def test_simple_factor_analysis_callable(self):
        from eqlib.attribution import simple_factor_analysis
        result = self._make_minimal_result()
        out = simple_factor_analysis(result)
        # Should return a dict (or None if insufficient data)
        assert out is None or isinstance(out, dict)

    def test_simple_factor_analysis_exported_from_eqlib(self):
        import eqlib
        assert hasattr(eqlib, "simple_factor_analysis")
        assert callable(eqlib.simple_factor_analysis)

    def test_fama_french_analysis_is_deprecated_alias(self):
        from eqlib.attribution import fama_french_analysis
        result = self._make_minimal_result()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            fama_french_analysis(result)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 1
            assert "simple_factor_analysis" in str(deprecation_warnings[0].message)

    def test_deprecated_alias_exported_from_eqlib(self):
        import eqlib
        assert hasattr(eqlib, "fama_french_analysis")
        # Should still be callable (for backward compat)
        assert callable(eqlib.fama_french_analysis)


# ──────────────────────────────────────────────────────────────────────────────
# H5: attribute_history fq validation
# ──────────────────────────────────────────────────────────────────────────────

class TestH5AttributeHistoryFqValidation:
    """H5: attribute_history should reject fq != 'pre' when preloaded panel is present."""

    def _make_preloaded(self, sec="601390"):
        """Build a minimal PreloadedData-like object."""
        import pandas as pd

        dates = pd.date_range("2023-01-03", periods=30, freq="B")
        frame = pd.DataFrame({
            "open": [10.0] * 30,
            "high": [11.0] * 30,
            "low": [9.5] * 30,
            "close": [10.0 + i * 0.01 for i in range(30)],
            "volume": [1e6] * 30,
        }, index=dates)

        preloaded = MagicMock()
        preloaded._field_series = {
            sec: {
                "open": frame["open"],
                "close": frame["close"],
                "volume": frame["volume"],
            }
        }
        preloaded.panel = None
        return preloaded

    def test_fq_post_raises_in_backtest(self):
        """fq='post' should raise ValueError when preloaded data is available."""
        import datetime as dt
        import pytest
        from eqlib.data import attribute_history
        from eqlib._state import BacktestSession, _set_session, get_session

        session = BacktestSession()
        _set_session(session)

        preloaded = self._make_preloaded()
        context_dt = dt.datetime(2023, 2, 15)

        # Use MagicMock for context — only current_dt is needed
        ctx = MagicMock()
        ctx.current_dt = context_dt
        session._context = ctx

        with patch("eqlib.engine._get_preloaded", return_value=preloaded):
            with pytest.raises(ValueError, match="fq='post'"):
                attribute_history("601390", 10, fields=["close"], fq="post")

    def test_fq_none_is_allowed_in_backtest(self):
        """fq=None (no adjustment) is permitted in backtest mode and returns data."""
        import datetime as dt
        from eqlib.data import attribute_history
        from eqlib._state import BacktestSession, _set_session

        session = BacktestSession()
        _set_session(session)

        preloaded = self._make_preloaded()
        context_dt = dt.datetime(2023, 2, 15)

        ctx = MagicMock()
        ctx.current_dt = context_dt
        session._context = ctx

        with patch("eqlib.engine._get_preloaded", return_value=preloaded):
            # fq=None means "no adjustment" — should not raise, uses qfq preloaded data
            result = attribute_history("601390", 10, fields=["close"], fq=None)
            assert not result.empty

    def test_fq_pre_works_in_backtest(self):
        """fq='pre' (default) should work fine in backtest mode."""
        import datetime as dt
        from eqlib.data import attribute_history
        from eqlib._state import BacktestSession, _set_session

        session = BacktestSession()
        _set_session(session)

        preloaded = self._make_preloaded()
        context_dt = dt.datetime(2023, 2, 15)

        ctx = MagicMock()
        ctx.current_dt = context_dt
        session._context = ctx

        with patch("eqlib.engine._get_preloaded", return_value=preloaded):
            result = attribute_history("601390", 10, fields=["close"], fq="pre")
            assert not result.empty


# ──────────────────────────────────────────────────────────────────────────────
# M3: Thread-safe _cache
# ──────────────────────────────────────────────────────────────────────────────

class TestM3ThreadSafeCache:
    """M3: data._cache must be guarded by a threading.Lock."""

    def test_cache_lock_exists(self):
        import eqlib.data as data_mod
        import threading
        assert hasattr(data_mod, "_cache_lock")
        assert isinstance(data_mod._cache_lock, type(threading.Lock()))

    def test_spot_lock_exists(self):
        import eqlib.data as data_mod
        import threading
        assert hasattr(data_mod, "_spot_lock")
        assert isinstance(data_mod._spot_lock, type(threading.Lock()))

    def test_concurrent_cache_reads_dont_raise(self):
        """Multiple threads reading from the cache simultaneously should not crash."""
        import eqlib.data as data_mod

        errors = []

        def read_cache():
            try:
                with data_mod._cache_lock:
                    _ = dict(data_mod._cache)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_cache) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent cache reads: {errors}"


# ──────────────────────────────────────────────────────────────────────────────
# M7: Walk-forward framework
# ──────────────────────────────────────────────────────────────────────────────

class TestM7WalkForward:
    """M7: walk_forward() basic functionality."""

    def test_walk_forward_importable(self):
        from eqlib.wfa import walk_forward, WFAResult
        assert callable(walk_forward)
        assert WFAResult is not None

    def test_wfa_exported_from_eqlib(self):
        import eqlib
        assert hasattr(eqlib, "walk_forward")
        assert hasattr(eqlib, "WFAResult")

    def test_add_months_helper(self):
        from eqlib.wfa import _add_months
        assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # 2024 is leap year
        assert _add_months(date(2024, 1, 15), 3) == date(2024, 4, 15)
        assert _add_months(date(2023, 12, 1), 1) == date(2024, 1, 1)

    def test_stitch_equity_chains_correctly(self):
        import pandas as pd
        from eqlib.wfa import _stitch_equity

        # Two windows, each starting at 1.0 and ending at 1.1 (10% gain)
        idx1 = pd.date_range("2023-01-03", periods=5, freq="B")
        idx2 = pd.date_range("2023-02-01", periods=5, freq="B")
        s1 = pd.Series([1.0, 1.02, 1.04, 1.07, 1.10], index=idx1)
        s2 = pd.Series([1.0, 1.02, 1.04, 1.07, 1.10], index=idx2)

        equity = _stitch_equity([s1, s2], starting_cash=100_000)
        assert len(equity) == 10
        # First window: 100000 * 1.10 = 110000; second window should start at 110000
        assert abs(equity.iloc[-1] - 100_000 * 1.10 * 1.10) < 1.0

    def test_wfa_result_repr(self):
        import pandas as pd
        from eqlib.wfa import WFAResult

        r = WFAResult(windows=[], oos_equity=pd.Series(dtype=float), summary={
            "total_oos_return": 0.15,
            "oos_sharpe": 1.2,
        })
        assert "0" in repr(r)

    def test_walk_forward_no_data_returns_empty(self):
        """walk_forward with empty date range should produce WFAResult with 0 windows."""
        from eqlib.wfa import walk_forward

        # Arrange: make_initialize returns something, but date range is invalid
        # (end before start → 0 OOS windows)
        def make_init():
            def initialize(context):
                pass
            return initialize

        # Mock run_backtest to do nothing (no network) — patch the name inside wfa module
        with patch("eqlib.engine.run_backtest", return_value=None):
            result = walk_forward(
                make_init,
                start_date="2024-06-01",
                end_date="2024-07-01",  # only 1 month — too short for 12-mo train + 3-mo test
                train_months=12,
                test_months=3,
            )
        assert result.windows == []


# ──────────────────────────────────────────────────────────────────────────────
# M8: StrategyConfig.use_local
# ──────────────────────────────────────────────────────────────────────────────

class TestM8StrategyConfigUseLocal:
    """M8: use_local should be a proper StrategyConfig field."""

    def test_default_use_local_is_false(self):
        from eqlib.portfolio import StrategyConfig
        cfg = StrategyConfig(
            securities=["601390"],
            start_date="2024-01-01",
            end_date="2024-03-31",
        )
        assert cfg.use_local is False

    def test_use_local_can_be_set_to_true(self):
        from eqlib.portfolio import StrategyConfig
        cfg = StrategyConfig(
            securities=["601390"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            use_local=True,
        )
        assert cfg.use_local is True

    def test_run_portfolio_backtest_passes_use_local(self):
        """run_portfolio_backtest should forward config.use_local to run_backtest."""
        from eqlib.portfolio import StrategyConfig

        captured_kwargs = {}

        def mock_run_backtest(init_fn, start, end, **kwargs):
            captured_kwargs.update(kwargs)
            return None  # simulate no result

        def my_strategy(context):
            pass

        cfg = StrategyConfig(
            securities=["601390"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            use_local=True,
        )

        with patch("eqlib.engine.run_backtest", side_effect=mock_run_backtest):
            from eqlib.portfolio import run_portfolio_backtest
            run_portfolio_backtest(cfg, my_strategy, generate_reports=False)

        assert captured_kwargs.get("use_local") is True


# ──────────────────────────────────────────────────────────────────────────────
# S1: CORS configuration
# ──────────────────────────────────────────────────────────────────────────────

class TestS1CORSConfig:
    """S1: CORS should use configurable origins, not ['*'] + allow_credentials."""

    def test_settings_has_cors_allowed_origins(self):
        from studio_api.config import settings
        assert hasattr(settings, "cors_allowed_origins")
        assert isinstance(settings.cors_allowed_origins, list)

    def test_default_cors_does_not_contain_wildcard(self):
        from studio_api.config import settings
        assert "*" not in settings.cors_allowed_origins

    def test_default_cors_contains_localhost(self):
        from studio_api.config import settings
        origins = settings.cors_allowed_origins
        has_localhost = any("localhost" in o or "127.0.0.1" in o for o in origins)
        assert has_localhost


# ──────────────────────────────────────────────────────────────────────────────
# S4: StreamHub cleanup
# ──────────────────────────────────────────────────────────────────────────────

class TestS4StreamHubCleanup:
    """S4: StreamHub should clean up empty run_id entries after terminal events."""

    def test_unsubscribe_removes_empty_entry(self):
        from studio_api.stream_hub import StreamHub

        hub = StreamHub()
        q = hub.subscribe("run_abc")
        assert "run_abc" in hub._queues

        hub.unsubscribe("run_abc", q)
        # After unsubscribe and list becomes empty, the key should be removed
        assert "run_abc" not in hub._queues

    def test_done_event_cleans_up_run_id(self):
        """Publishing 'done' should remove the run_id from _queues."""
        from studio_api.stream_hub import StreamHub

        async def _run():
            hub = StreamHub()
            hub.subscribe("run_xyz")
            assert "run_xyz" in hub._queues
            await hub.publish("run_xyz", "done", {"status": "succeeded"})
            assert "run_xyz" not in hub._queues

        asyncio.get_event_loop().run_until_complete(_run())

    def test_error_event_cleans_up_run_id(self):
        """Publishing 'error' should also remove the run_id."""
        from studio_api.stream_hub import StreamHub

        async def _run():
            hub = StreamHub()
            hub.subscribe("run_err")
            await hub.publish("run_err", "error", {"message": "something failed"})
            assert "run_err" not in hub._queues

        asyncio.get_event_loop().run_until_complete(_run())

    def test_non_terminal_events_do_not_clean_up(self):
        """Progress and log events should NOT remove the run_id."""
        from studio_api.stream_hub import StreamHub

        async def _run():
            hub = StreamHub()
            hub.subscribe("run_prog")
            await hub.publish("run_prog", "progress", {"progress": 0.5})
            assert "run_prog" in hub._queues

        asyncio.get_event_loop().run_until_complete(_run())


# ──────────────────────────────────────────────────────────────────────────────
# S6: Idempotency TTL
# ──────────────────────────────────────────────────────────────────────────────

class TestS6IdempotencyTTL:
    """S6: idempotency_ttl_sec should be a Settings field."""

    def test_settings_has_idempotency_ttl(self):
        from studio_api.config import settings
        assert hasattr(settings, "idempotency_ttl_sec")
        assert settings.idempotency_ttl_sec > 0

    def test_default_ttl_is_24_hours(self):
        from studio_api.config import settings
        assert settings.idempotency_ttl_sec == 86400


# ──────────────────────────────────────────────────────────────────────────────
# E7: API stability markers
# ──────────────────────────────────────────────────────────────────────────────

class TestE7ApiStabilityMarkers:
    """E7: __init__.py should contain API stability marker comments."""

    def test_stable_marker_present_in_init(self):
        import eqlib
        import inspect
        source = inspect.getsource(eqlib)
        assert "STABLE" in source

    def test_experimental_marker_present_in_init(self):
        import eqlib
        import inspect
        source = inspect.getsource(eqlib)
        assert "EXPERIMENTAL" in source

    def test_deprecated_marker_present_in_init(self):
        import eqlib
        import inspect
        source = inspect.getsource(eqlib)
        assert "DEPRECATED" in source


# ──────────────────────────────────────────────────────────────────────────────
# H7: _get_trading_days uses sina calendar
# ──────────────────────────────────────────────────────────────────────────────

class TestH7TradingDays:
    """H7: _get_trading_days should prefer sina calendar over stock history."""

    def test_preloaded_dates_take_priority(self):
        """When preloaded._dates is available, skip all network calls."""
        import pandas as pd
        from eqlib.engine import _get_trading_days

        preloaded = MagicMock()
        preloaded._dates = pd.date_range("2024-01-01", "2024-03-31", freq="B").tolist()

        start = date(2024, 1, 2)
        end = date(2024, 1, 31)

        # Should not call akshare at all
        with patch("akshare.tool_trade_date_hist_sina") as mock_sina, \
             patch("akshare.stock_zh_a_hist") as mock_stock:
            result = _get_trading_days(start, end, preloaded=preloaded)
            mock_sina.assert_not_called()
            mock_stock.assert_not_called()

        assert len(result) > 0
        assert all(start <= d <= end for d in result)

    def test_falls_back_to_sina_when_no_preloaded(self):
        """Without preloaded data, should attempt sina calendar."""
        import pandas as pd
        from eqlib.engine import _get_trading_days

        mock_df = pd.DataFrame({"trade_date": pd.date_range("2024-01-02", "2024-01-31", freq="B")})

        with patch("akshare.tool_trade_date_hist_sina", return_value=mock_df) as mock_sina:
            result = _get_trading_days(date(2024, 1, 2), date(2024, 1, 31), preloaded=None)
            mock_sina.assert_called_once()

        assert len(result) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Security scanner documentation
# ──────────────────────────────────────────────────────────────────────────────

class TestS2SecurityScannerDocumented:
    """S2: security_scanner.py should document its limitations."""

    def test_module_docstring_warns_about_limitations(self):
        from studio_api import security_scanner
        doc = security_scanner.__doc__ or ""
        assert "NOT a security sandbox" in doc or "friendly lint" in doc

    def test_scanner_still_catches_banned_imports(self):
        """The scanner should still catch obvious banned imports."""
        from studio_api.security_scanner import SecurityScanner
        scanner = SecurityScanner()
        notes = scanner.scan("import os\nprint('hello')")
        codes = [n.code for n in notes]
        assert "EQ-BANNED-IMPORT" in codes
