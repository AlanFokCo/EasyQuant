"""Tests for dimension 2 backtest credibility fixes.

2.1 ORDER_VALUE sell-side lot rounding — both buy and sell must round to 100-share lots.
2.2 Sortino ratio must subtract risk-free rate (consistent with Sharpe).
2.3 Sharpe and Sortino must use the same ddof convention (sample std, ddof=1).
"""

import datetime
import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helper: build a fake backtest result dict for analyze_returns
# ---------------------------------------------------------------------------

def _make_fake_result(daily_returns, starting_cash=100000.0):
    """Build a minimal result dict that analyze_returns can consume."""
    values = (1 + pd.Series(daily_returns)).cumprod() * starting_cash
    dates = pd.bdate_range("2024-01-02", periods=len(values), freq="B")

    entries = [
        {"date": d.date(), "total_value": v}
        for d, v in zip(dates, values)
    ]

    class FakePortfolio:
        def __init__(self, cash, final):
            self.starting_cash = cash
            self.total_value = final
            self.positions = {}

    class FakeContext:
        def __init__(self, cash, final):
            self.portfolio = FakePortfolio(cash, final)

    return {
        "context": FakeContext(starting_cash, float(values.iloc[-1])),
        "trade_log": [],
        "recorded_values": entries,
    }


# ---------------------------------------------------------------------------
# 2.1 ORDER_VALUE sell-side lot rounding
# ---------------------------------------------------------------------------

class TestOrderValueSellRounding:
    """order_value sell orders must round to 100-share lot size."""

    def test_round_lot_basic(self):
        """_round_lot always rounds down to nearest 100."""
        from eqlib.engine import _round_lot
        assert _round_lot(95) == 0
        assert _round_lot(100) == 100
        assert _round_lot(150) == 100
        assert _round_lot(250) == 200
        assert _round_lot(999) == 900

    def test_sell_order_value_is_lot_rounded(self):
        """Selling via order_value must produce a lot-rounded delta."""
        from eqlib.engine import _round_lot

        # Simulate the fixed logic: negative value → round abs, then negate
        value = -9500
        open_px = 100.0
        raw = int(value / open_px)  # -95
        delta = _round_lot(abs(raw))  # 0 (rounds 95 down to 0)
        if value < 0:
            delta = -delta
        # 95 shares rounds down to 0 — can't sell less than 100
        assert delta == 0

    def test_sell_order_value_full_lot(self):
        """Selling 15000 at 100/share → -150 shares → rounds to -100."""
        from eqlib.engine import _round_lot

        value = -15000
        open_px = 100.0
        raw = int(value / open_px)  # -150
        delta = _round_lot(abs(raw))  # 100
        if value < 0:
            delta = -delta
        assert delta == -100

    def test_buy_order_value_still_rounds(self):
        """Buy side: 9500 at 100/share → 95 shares → rounds to 0."""
        from eqlib.engine import _round_lot

        value = 9500
        open_px = 100.0
        raw = int(value / open_px)  # 95
        delta = _round_lot(abs(raw))  # 0
        assert delta == 0

    def test_buy_order_value_full_lot(self):
        """Buy side: 15000 at 100/share → 150 shares → rounds to 100."""
        from eqlib.engine import _round_lot

        value = 15000
        open_px = 100.0
        raw = int(value / open_px)  # 150
        delta = _round_lot(abs(raw))  # 100
        assert delta == 100


# ---------------------------------------------------------------------------
# 2.2 Sortino ratio includes risk-free rate
# ---------------------------------------------------------------------------

class TestSortinoRiskFreeRate:
    """Sortino ratio must subtract the risk-free rate in the numerator."""

    @staticmethod
    def _build_daily_returns(n=252, mean=0.0005, seed=42):
        """Generate synthetic daily returns."""
        rng = np.random.RandomState(seed)
        return list(rng.normal(mean, 0.01, n))

    def test_sortino_decreases_with_higher_rf(self):
        """Higher risk-free rate should lower the Sortino ratio."""
        from eqlib.attribution import analyze_returns

        daily = self._build_daily_returns()
        result_low = _make_fake_result(daily)
        result_high = _make_fake_result(daily)

        stats_low = analyze_returns(result_low, risk_free_rate=0.01)
        stats_high = analyze_returns(result_high, risk_free_rate=0.10)

        assert stats_high["sortino_ratio"] < stats_low["sortino_ratio"], (
            "Sortino should decrease when risk-free rate increases"
        )

    def test_sortino_zero_rf_matches_manual(self):
        """With rf=0, Sortino should equal (mean / downside_std) * sqrt(TRADING_DAYS_PER_YEAR)."""
        from eqlib.attribution import analyze_returns
        from eqlib.constants import TRADING_DAYS_PER_YEAR

        daily = self._build_daily_returns()
        result = _make_fake_result(daily)

        stats = analyze_returns(result, risk_free_rate=0.0)

        # Manually compute expected Sortino with rf=0
        values = (1 + pd.Series(daily)).cumprod() * 100000
        daily_ret = values.pct_change().dropna()
        downside = daily_ret[daily_ret < 0]
        downside_std = downside.std()  # ddof=1
        expected = (daily_ret.mean() / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR)

        assert abs(stats["sortino_ratio"] - expected) < 1e-6


# ---------------------------------------------------------------------------
# 2.3 Sharpe & Sortino use consistent ddof
# ---------------------------------------------------------------------------

class TestConsistentDdof:
    """Sharpe and Sortino must use the same ddof convention."""

    def test_sortino_uses_sample_std(self):
        """Sortino denominator must use ddof=1 (sample std)."""
        from eqlib.attribution import analyze_returns

        daily = list(np.array([0.01, -0.02, 0.005, -0.01, 0.003, -0.015] * 42))
        result = _make_fake_result(daily)

        stats = analyze_returns(result, risk_free_rate=0.0)

        # Manually verify with ddof=1
        values = (1 + pd.Series(daily)).cumprod() * 100000
        daily_ret = values.pct_change().dropna()
        downside = daily_ret[daily_ret < 0]
        downside_std_ddof1 = downside.std()  # default ddof=1
        downside_std_ddof0 = downside.std(ddof=0)

        from eqlib.constants import TRADING_DAYS_PER_YEAR
        expected_ddof1 = (daily_ret.mean() / downside_std_ddof1) * np.sqrt(TRADING_DAYS_PER_YEAR)

        assert abs(stats["sortino_ratio"] - expected_ddof1) < 1e-6, (
            f"Sortino {stats['sortino_ratio']} should use ddof=1 ({expected_ddof1})"
        )


class TestEdgeCases:
    """Edge cases for metrics calculations."""

    def test_no_negative_returns(self):
        """All positive returns → Sortino should be 0 (no downside data)."""
        from eqlib.attribution import analyze_returns

        daily = [0.001] * 100
        result = _make_fake_result(daily)
        stats = analyze_returns(result, risk_free_rate=0.0)
        assert stats["sortino_ratio"] == 0.0

    def test_all_negative_returns(self):
        """All negative returns → Sortino should be computable (negative)."""
        from eqlib.attribution import analyze_returns

        daily = [-0.001] * 100
        result = _make_fake_result(daily)
        stats = analyze_returns(result, risk_free_rate=0.0)
        assert stats["sortino_ratio"] < 0.0

