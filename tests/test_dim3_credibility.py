"""Tests for dimension 3 backtest credibility fixes.

3.1 Calmar ratio must use a threshold guard (abs(max_dd) >= 1e-6) to avoid
    explosive ratios when drawdown is near-zero.
3.2 Annual turnover uses the average of total_buy_value and total_sell_value
    (not min) to avoid underestimation when buy/sell values diverge.
3.3 Profit/loss ratio returns inf when all trades are winners (loss_count == 0),
    and 0.0 only when win_count == 0.
"""

import math
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

    ctx_stub = type("Ctx", (), {
        "portfolio": FakePortfolio(starting_cash, float(values.iloc[-1])),
        "start_date": dates[0].date(),
        "end_date": dates[-1].date(),
    })()

    return {
        "context": ctx_stub,
        "recorded_values": entries,
        "trade_log": [],
    }


# ---------------------------------------------------------------------------
# 3.1  Calmar ratio threshold guard
# ---------------------------------------------------------------------------

class TestCalmarThreshold:
    """Calmar must be 0.0 when max drawdown is negligibly small."""

    def test_near_zero_drawdown_returns_zero(self):
        """A monotonically rising portfolio has ~0 drawdown → Calmar = 0."""
        from eqlib.attribution import analyze_returns

        # Create a series with tiny drawdowns (< 1e-6)
        n = 60
        daily_ret = [0.001] * n  # purely positive returns, no drawdown
        result = _make_fake_result(daily_ret)
        analytics = analyze_returns(result)

        # Max drawdown should be 0 or negligible
        assert abs(analytics["max_drawdown"]) < 1e-6
        # Calmar should be 0, not an explosive number
        assert analytics["calmar_ratio"] == 0.0

    def test_real_drawdown_gives_normal_calmar(self):
        """A portfolio with a real drawdown should produce a finite Calmar."""
        from eqlib.attribution import analyze_returns

        daily_ret = [0.01] * 20 + [-0.05] * 5 + [0.01] * 20
        result = _make_fake_result(daily_ret)
        analytics = analyze_returns(result)

        assert abs(analytics["max_drawdown"]) >= 1e-6
        assert 0 < analytics["calmar_ratio"] < 1000  # reasonable value


# ---------------------------------------------------------------------------
# 3.2  Turnover uses average of buy+sell, not min
# ---------------------------------------------------------------------------

class TestTurnoverAverage:
    """Annual turnover should use (buy + sell) / 2 / avg_value / years."""

    def test_asymmetric_buy_sell(self):
        from eqlib.attribution import analyze_returns

        daily_ret = [0.001] * 60
        result = _make_fake_result(daily_ret)

        # Simulate asymmetric trades: more buys than sells
        result["trade_log"] = [
            {"type": "BUY", "security": "000001.XSHE", "price": 10.0, "amount": 1000,
             "commission": 5.0, "date": datetime.date(2024, 1, 3)},
            {"type": "BUY", "security": "000001.XSHE", "price": 11.0, "amount": 500,
             "commission": 5.0, "date": datetime.date(2024, 1, 10)},
            {"type": "SELL", "security": "000001.XSHE", "price": 12.0, "amount": 800,
             "commission": 5.0, "date": datetime.date(2024, 2, 1)},
        ]

        analytics = analyze_returns(result)

        total_buy = 10.0 * 1000 + 11.0 * 500  # 15,500
        total_sell = 12.0 * 800  # 9,600
        # With average: (15500 + 9600) / 2 = 12,550
        # With min:     min(15500, 9600) = 9,600

        # The turnover should reflect the average, not the min
        # We verify by checking the turnover is strictly greater than what
        # min-based would yield (since avg > min when values differ).
        avg_val = analytics.get("avg_portfolio_value")
        if avg_val is None:
            # Reconstruct from known starting cash and returns
            values = (1 + pd.Series(daily_ret)).cumprod() * 100000.0
            avg_val = float(values.mean())

        n_days = analytics["trading_days"]
        years = n_days / 252.0

        min_based = min(total_buy, total_sell) / avg_val / years
        avg_based = (total_buy + total_sell) / 2.0 / avg_val / years

        # Actual turnover should match avg-based calculation
        assert analytics["annual_turnover"] == pytest.approx(avg_based, rel=1e-6)
        assert analytics["annual_turnover"] > min_based


# ---------------------------------------------------------------------------
# 3.3  Profit/loss ratio edge cases
# ---------------------------------------------------------------------------

class TestProfitLossRatioEdgeCases:
    """P/L ratio: inf when all wins, 0.0 when all losses, normal otherwise."""

    def test_all_winners_returns_inf(self):
        from eqlib.attribution import _calc_profit_loss_ratio

        trades = [
            {"type": "BUY", "security": "A", "price": 10.0, "amount": 100},
            {"type": "SELL", "security": "A", "price": 15.0, "amount": 100},
            {"type": "BUY", "security": "B", "price": 20.0, "amount": 100},
            {"type": "SELL", "security": "B", "price": 25.0, "amount": 100},
        ]
        plr, wins, losses = _calc_profit_loss_ratio(trades)
        assert wins == 2
        assert losses == 0
        assert plr == float("inf")

    def test_all_losers_returns_zero(self):
        from eqlib.attribution import _calc_profit_loss_ratio

        trades = [
            {"type": "BUY", "security": "A", "price": 15.0, "amount": 100},
            {"type": "SELL", "security": "A", "price": 10.0, "amount": 100},
        ]
        plr, wins, losses = _calc_profit_loss_ratio(trades)
        assert wins == 0
        assert losses == 1
        assert plr == 0.0

    def test_no_trades_returns_zero(self):
        from eqlib.attribution import _calc_profit_loss_ratio

        plr, wins, losses = _calc_profit_loss_ratio([])
        assert plr == 0.0
        assert wins == 0
        assert losses == 0

    def test_mixed_returns_finite_ratio(self):
        from eqlib.attribution import _calc_profit_loss_ratio

        trades = [
            {"type": "BUY", "security": "A", "price": 10.0, "amount": 100},
            {"type": "SELL", "security": "A", "price": 15.0, "amount": 100},  # win: 500
            {"type": "BUY", "security": "B", "price": 20.0, "amount": 100},
            {"type": "SELL", "security": "B", "price": 18.0, "amount": 100},  # loss: -200
        ]
        plr, wins, losses = _calc_profit_loss_ratio(trades)
        assert wins == 1
        assert losses == 1
        assert plr == pytest.approx(500.0 / 200.0)
        assert math.isfinite(plr)
