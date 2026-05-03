"""Test statistical utility functions."""

import numpy as np
import pandas as pd
from eqlib.utils.stats import (
    rolling_corr, rolling_beta, rolling_sharpe,
    zscore, percentile_rank,
    linear_regression,
    downside_deviation, value_at_risk, conditional_var,
    drawdown, max_drawdown,
    consecutive_wins, consecutive_losses,
    fibonacci, comb, perm,
    compound_return, cagr, log_return,
)


class TestRolling:
    def test_rolling_corr(self):
        np.random.seed(42)
        x = pd.Series(np.random.randn(100))
        y = pd.Series(np.random.randn(100))
        result = rolling_corr(x, y, window=20)
        assert len(result) == 100

    def test_rolling_beta(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.02)
        benchmark = pd.Series(np.random.randn(100) * 0.015)
        result = rolling_beta(returns, benchmark, window=20)
        assert len(result) == 100

    def test_rolling_sharpe(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.01)
        result = rolling_sharpe(returns, window=20, risk_free=0.03)
        assert len(result) == 100


class TestZScore:
    def test_zscore_mean_zero_std_one(self):
        np.random.seed(42)
        data = pd.Series(np.random.randn(500))
        result = zscore(data, window=50)
        valid = result.dropna()
        assert len(valid) > 0
        # Rolling z-score values should be roughly centered around 0
        assert abs(valid.mean()) < 0.5

    def test_zscore_rolling(self):
        data = pd.Series(np.random.randn(100))
        result = zscore(data, window=20)
        assert len(result) == 100


class TestPercentileRank:
    def test_percentile_rank(self):
        data = pd.Series([10, 20, 30, 40, 50])
        result = percentile_rank(data)
        assert len(result) == 5
        assert result.iloc[-1] == 100.0  # max = 100th percentile


class TestLinearRegression:
    def test_linear_regression(self):
        x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        y = pd.Series([3.0, 5.0, 7.0, 9.0, 11.0])  # y = 2x + 1
        result = linear_regression(x, y)
        assert result is not None
        assert abs(result["beta"] - 2.0) < 1e-10
        assert abs(result["alpha"] - 1.0) < 1e-10
        assert result["r_squared"] == 1.0


class TestRisk:
    def test_downside_deviation(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.02)
        result = downside_deviation(returns, target=0.0)
        assert result > 0

    def test_value_at_risk(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(1000) * 0.02)
        result = value_at_risk(returns, confidence=0.05)
        assert result > 0

    def test_conditional_var(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(1000) * 0.02)
        result = conditional_var(returns, confidence=0.05)
        assert result > 0


class TestDrawdown:
    def test_drawdown(self):
        values = pd.Series([100.0, 110, 105, 120, 115, 130])
        result = drawdown(values)
        assert len(result) == 6
        assert (result <= 0).all()

    def test_max_drawdown(self):
        values = pd.Series([100.0, 110, 105, 120, 115, 130])
        dd_val, start, end = max_drawdown(values)
        assert dd_val < 0
        assert dd_val > -1


class TestStreaks:
    def test_consecutive_wins(self):
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.01])
        streaks = consecutive_wins(returns)
        assert isinstance(streaks, pd.Series)
        assert len(streaks) == 5
        assert streaks.iloc[-1] == 2  # last two are wins

    def test_consecutive_losses(self):
        returns = pd.Series([-0.01, -0.02, 0.01, -0.03, -0.01])
        streaks = consecutive_losses(returns)
        assert isinstance(streaks, pd.Series)
        assert streaks.iloc[-1] == 2  # last two are losses


class TestMath:
    def test_fibonacci(self):
        assert fibonacci(1) == [1]
        assert fibonacci(2) == [1, 1]
        assert fibonacci(6) == [1, 1, 2, 3, 5, 8]
        assert fibonacci(0) == []

    def test_comb(self):
        assert comb(5, 2) == 10
        assert comb(10, 0) == 1

    def test_perm(self):
        assert perm(5, 2) == 20
        assert perm(3, 3) == 6


class TestReturns:
    def test_compound_return(self):
        returns = pd.Series([0.01, 0.02, -0.01, 0.03])
        result = compound_return(returns)
        expected = (1.01 * 1.02 * 0.99 * 1.03) - 1
        assert abs(result - expected) < 1e-10

    def test_cagr(self):
        result = cagr(start_value=100, end_value=150, years=3)
        expected = (150 / 100) ** (1 / 3) - 1
        assert abs(result - expected) < 1e-10

    def test_log_return(self):
        prices = pd.Series([100.0, 101, 102, 103])
        result = log_return(prices)
        assert len(result) == 4
        assert pd.isna(result.iloc[0])  # first is NaN
