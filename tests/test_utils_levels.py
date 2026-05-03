"""Test support/resistance and level utilities."""

import numpy as np
import pandas as pd
from eqlib.utils.levels import (
    pivot_classic, pivot_fibonacci, pivot_woodie,
    pivot_camarilla, pivot_demark,
    support_resistance_levels, fibonacci_retracement,
    donchian, psychological_levels, trailing_stop,
    gap_up_down,
)


def _make_ohlc(n=100, base=100.0):
    np.random.seed(42)
    close = pd.Series(base + np.cumsum(np.random.randn(n) * 2))
    high = pd.Series(close + np.abs(np.random.randn(n) * 1.5))
    low = pd.Series(close - np.abs(np.random.randn(n) * 1.5))
    open_ = pd.Series(base + np.cumsum(np.random.randn(n) * 1.8))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


class TestPivotPoints:
    def test_pivot_classic(self):
        df = _make_ohlc()
        pp, r1, s1, r2, s2, r3, s3 = pivot_classic(df["high"], df["low"], df["close"])
        assert len(pp) == 100
        # At any valid point, r1 > pp > s1
        valid = pp.notna()
        if valid.any():
            assert (r1[valid] > pp[valid]).all()
            assert (pp[valid] > s1[valid]).all()

    def test_pivot_fibonacci(self):
        df = _make_ohlc()
        pp, r1, s1, r2, s2, r3, s3 = pivot_fibonacci(df["high"], df["low"], df["close"])
        assert len(pp) == 100

    def test_pivot_woodie(self):
        df = _make_ohlc()
        pp, r1, s1, r2, s2 = pivot_woodie(df["high"], df["low"], df["close"])
        assert len(pp) == 100

    def test_pivot_camarilla(self):
        df = _make_ohlc()
        r4, r3, r2, r1, s1, s2, s3, s4 = pivot_camarilla(df["high"], df["low"], df["close"])
        assert len(r4) == 100

    def test_pivot_demark(self):
        df = _make_ohlc()
        pp, r1, s1 = pivot_demark(df["high"], df["low"], df["close"], df["open"])
        assert len(pp) == 100


class TestSupportResistance:
    def test_support_resistance_levels(self):
        df = _make_ohlc(200)
        levels = support_resistance_levels(df["high"], df["low"], df["close"])
        assert isinstance(levels, dict)
        assert "resistance" in levels
        assert "support" in levels
        assert isinstance(levels["resistance"], list)
        assert isinstance(levels["support"], list)

    def test_fibonacci_retracement(self):
        df = _make_ohlc(200)
        levels = fibonacci_retracement(df["high"], df["low"], df["close"])
        assert isinstance(levels, dict)
        assert "uptrend" in levels
        assert 0.0 in levels  # 0% level
        assert 1.0 in levels  # 100% level

    def test_donchian(self):
        df = _make_ohlc()
        upper, mid, lower = donchian(df["high"], df["low"], period=20)
        assert len(upper) == 100
        assert len(mid) == 100
        assert len(lower) == 100
        valid = upper.notna() & lower.notna()
        if valid.any():
            assert (upper[valid] >= lower[valid]).all()


class TestPsychologicalLevels:
    def test_psychological_levels(self):
        levels = psychological_levels(price=150.0)
        assert isinstance(levels, list)
        assert len(levels) > 0

    def test_psychological_levels_round_numbers(self):
        levels = psychological_levels(price=100.0)
        assert 100.0 in levels


class TestTrailingStop:
    def test_trailing_stop(self):
        df = _make_ohlc()
        result = trailing_stop(df["close"], high=df["high"], low=df["low"], multiplier=2.0, period=14)
        assert len(result) == 100
        # Trailing stop is cumulative max, so non-NaN values should be non-decreasing
        valid = result.dropna()
        if len(valid) > 1:
            assert (valid.diff().dropna() >= -1e-10).all()


class TestGaps:
    def test_gap_up_down(self):
        df = _make_ohlc()
        gap_up, gap_down = gap_up_down(df["open"], df["high"], df["low"], df["close"])
        assert len(gap_up) == 100
        assert len(gap_down) == 100
        assert isinstance(gap_up, pd.Series)
        assert isinstance(gap_down, pd.Series)
