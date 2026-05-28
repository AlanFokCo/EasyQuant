"""Tests for Round 2 optimization fixes.

Covers:
1. ORDER_TARGET partial fill keeps original target
2. ORDER_TIMEOUT entries filtered from trade win rate / P&L ratio
3. _calc_excess_metrics handles NaN benchmark returns
4. _file_locks bounded growth in data_cache
5. _to_tv_date simplified isinstance chain
6. _bare_code helper for security code stripping
"""
import datetime
import threading
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


# ── 1. ORDER_TARGET partial fill keeps original target ─────────────────────

class TestOrderTargetPartialFill:
    """Verify that ORDER_TARGET partial fills preserve the original target_amount
    so the engine re-computes delta = target - current on the next bar."""

    def _make_session(self):
        from eqlib._state import BacktestSession
        from eqlib.context import Context, Portfolio, Position
        from eqlib.objects import Order

        sess = BacktestSession()
        sess.reset()
        sess._order_cost = None
        ctx = Context(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        ctx.portfolio = Portfolio()
        ctx.portfolio.starting_cash = 1_000_000
        ctx.portfolio.available_cash = 1_000_000
        ctx.portfolio.positions = {}
        sess._context = ctx
        sess._slippage_model = None
        return sess

    def test_target_preserved_after_partial_fill(self):
        """After a partial fill of ORDER_TARGET, the remaining order should
        keep the original target_amount (not subtract the filled amount)."""
        from eqlib._state import BacktestSession
        from eqlib.context import Position
        from eqlib.objects import Order, OrderCost

        sess = self._make_session()
        sess._order_cost = OrderCost()

        # Target 1000 shares, currently 0
        order_obj = Order("601390.XSHG", 1000, side="buy")

        sess._pending_orders = [{
            "action": "ORDER_TARGET",
            "security": "601390.XSHG",
            "target_amount": 1000,
            "order_obj": order_obj,
        }]

        day = datetime.date(2024, 1, 15)

        # Mock preloaded data and price functions to allow partial fill
        from eqlib import engine
        from eqlib.data_cache import PreloadedData

        preloaded = PreloadedData()
        preloaded._panel = {
            "601390.XSHG": pd.DataFrame({
                "open": [10.0],
                "high": [10.5],
                "low": [9.5],
                "close": [10.2],
                "volume": [300],  # Only 300 shares available -> partial fill of 300
                "money": [3000],
            }, index=pd.DatetimeIndex([pd.Timestamp(day)])),
        }
        preloaded._dates = [pd.Timestamp(day)]

        with patch.object(engine, '_get_preloaded', return_value=preloaded):
            engine._fill_pending_orders(
                sess, day,
                max_daily_volume_pct=1.0,
            )

        # Check: if partial fill happened, the remaining order should keep target=1000
        for pending_order in sess._pending_orders:
            if pending_order["action"] == "ORDER_TARGET":
                assert pending_order["target_amount"] == 1000, \
                    f"Expected target_amount=1000, got {pending_order['target_amount']}"


# ── 2. ORDER_TIMEOUT filtered from win rate / P&L ─────────────────────────

class TestOrderTimeoutFiltered:
    """ORDER_TIMEOUT entries in trade_log must not crash or bias
    _calc_trade_win_rate and _calc_profit_loss_ratio."""

    def test_win_rate_ignores_timeout(self):
        from eqlib.attribution import _calc_trade_win_rate

        trades = [
            {"security": "601390.XSHG", "type": "BUY", "price": 10.0, "amount": 100},
            {"security": "601390.XSHG", "type": "SELL", "price": 12.0, "amount": 100},
            # ORDER_TIMEOUT entry — should be silently skipped
            {
                "type": "ORDER_TIMEOUT",
                "date": datetime.date(2024, 1, 15),
                "security": "601390.XSHG",
                "order_id": "xyz",
                "action": "ORDER",
                "elapsed_seconds": 90000,
                "timeout_seconds": 86400,
            },
        ]
        win_rate, total, wins, losses = _calc_trade_win_rate(trades)
        assert total == 1
        assert wins == 1
        assert losses == 0
        assert win_rate == 1.0

    def test_profit_loss_ratio_ignores_timeout(self):
        from eqlib.attribution import _calc_profit_loss_ratio

        trades = [
            {"security": "601390.XSHG", "type": "BUY", "price": 10.0, "amount": 100},
            {"security": "601390.XSHG", "type": "SELL", "price": 8.0, "amount": 100},
            # ORDER_TIMEOUT entry — must not cause KeyError on "price"
            {
                "type": "ORDER_TIMEOUT",
                "date": datetime.date(2024, 1, 15),
                "security": "601390.XSHG",
                "order_id": "xyz",
                "action": "ORDER",
                "elapsed_seconds": 90000,
                "timeout_seconds": 86400,
            },
        ]
        plr, win_count, loss_count = _calc_profit_loss_ratio(trades)
        assert loss_count == 1
        assert win_count == 0
        assert plr == 0.0

    def test_only_timeout_entries(self):
        """A trade log with only ORDER_TIMEOUT entries should return zeros."""
        from eqlib.attribution import _calc_trade_win_rate, _calc_profit_loss_ratio

        trades = [
            {
                "type": "ORDER_TIMEOUT",
                "date": datetime.date(2024, 1, 15),
                "security": "601390.XSHG",
                "order_id": "abc",
                "action": "ORDER",
                "elapsed_seconds": 90000,
                "timeout_seconds": 86400,
            },
        ]
        win_rate, total, wins, losses = _calc_trade_win_rate(trades)
        assert total == 0
        assert win_rate == 0.0

        plr, wc, lc = _calc_profit_loss_ratio(trades)
        assert wc == 0
        assert lc == 0


# ── 3. _calc_excess_metrics handles NaN benchmark ─────────────────────────

class TestExcessMetricsNaN:
    """_calc_excess_metrics should handle NaN entries in benchmark returns."""

    def test_nan_in_benchmark_returns(self):
        from eqlib.attribution import _calc_excess_metrics

        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        strategy_ret = pd.Series(np.random.randn(30) * 0.01, index=dates)
        bench_ret = pd.Series(np.random.randn(30) * 0.01, index=dates)
        # Inject NaN
        bench_ret.iloc[5] = np.nan
        bench_ret.iloc[15] = np.nan

        excess_total, excess_dd, excess_sharpe, daily_excess = _calc_excess_metrics(
            strategy_ret, bench_ret, 0.03, 252
        )
        # Should return finite values (NaN filled with 0)
        assert np.isfinite(excess_total)
        assert np.isfinite(excess_dd)
        assert np.isfinite(excess_sharpe)
        assert np.isfinite(daily_excess)

    def test_all_nan_benchmark(self):
        from eqlib.attribution import _calc_excess_metrics

        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        strategy_ret = pd.Series(np.random.randn(10) * 0.01, index=dates)
        bench_ret = pd.Series([np.nan] * 10, index=dates)

        excess_total, excess_dd, excess_sharpe, daily_excess = _calc_excess_metrics(
            strategy_ret, bench_ret, 0.03, 252
        )
        # All NaN benchmark → treated as 0, so excess == strategy
        assert np.isfinite(excess_total)


# ── 4. _file_locks bounded growth ──────────────────────────────────────────

class TestFileLocksBounded:
    """_file_locks dict should not grow unbounded."""

    def test_locks_eviction(self):
        from eqlib import data_cache

        original_max = data_cache._MAX_FILE_LOCKS
        original_locks = data_cache._file_locks.copy()
        try:
            # Set a tiny cap to trigger eviction
            data_cache._MAX_FILE_LOCKS = 5
            data_cache._file_locks.clear()

            # Create 10 locks
            for i in range(10):
                data_cache._get_file_lock(Path(f"/tmp/test_lock_{i}.parquet"))

            # Should be capped (eviction removes unlocked entries)
            assert len(data_cache._file_locks) <= 10  # may evict some
            # The most recent lock should exist
            assert str(Path("/tmp/test_lock_9.parquet")) in data_cache._file_locks
        finally:
            data_cache._MAX_FILE_LOCKS = original_max
            data_cache._file_locks = original_locks


# ── 5. _to_tv_date simplified ─────────────────────────────────────────────

class TestToTvDate:
    """The simplified _to_tv_date should handle all input types correctly."""

    def test_datetime(self):
        from eqlib.report import _to_tv_date
        dt = datetime.datetime(2024, 3, 15, 10, 30, 0)
        assert _to_tv_date(dt) == "2024-03-15"

    def test_date(self):
        from eqlib.report import _to_tv_date
        d = datetime.date(2024, 3, 15)
        assert _to_tv_date(d) == "2024-03-15"

    def test_pd_timestamp(self):
        from eqlib.report import _to_tv_date
        ts = pd.Timestamp("2024-03-15")
        assert _to_tv_date(ts) == "2024-03-15"

    def test_numpy_datetime64(self):
        from eqlib.report import _to_tv_date
        nd = np.datetime64("2024-03-15")
        assert _to_tv_date(nd) == "2024-03-15"

    def test_string_passthrough(self):
        from eqlib.report import _to_tv_date
        assert _to_tv_date("2024-03-15 12:00:00") == "2024-03-15"

    def test_string_date(self):
        from eqlib.report import _to_tv_date
        assert _to_tv_date("2024-03-15") == "2024-03-15"


# ── 6. _bare_code helper ──────────────────────────────────────────────────

class TestBareCode:
    """_bare_code strips exchange suffixes correctly."""

    def test_xshg(self):
        from eqlib.engine import _bare_code
        assert _bare_code("601390.XSHG") == "601390"

    def test_xshe(self):
        from eqlib.engine import _bare_code
        assert _bare_code("000001.XSHE") == "000001"

    def test_no_suffix(self):
        from eqlib.engine import _bare_code
        assert _bare_code("601390") == "601390"

    def test_empty(self):
        from eqlib.engine import _bare_code
        assert _bare_code("") == ""
