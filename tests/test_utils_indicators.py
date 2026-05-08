"""Test technical indicator functions."""

import numpy as np
import pandas as pd
from eqlib.utils.indicators import (
    ma, ema, sma, smma, wma,
    macd, rsi, kdj, boll, atr, cci, wr, roc, obv, adx,
    golden_cross, death_cross,
)


def _make_prices(n=100, base=10.0, trend=0.01, noise=0.02):
    """Generate synthetic price series for testing."""
    np.random.seed(42)
    prices = base * np.exp(np.cumsum(trend + noise * np.random.randn(n)))
    return pd.Series(prices, name="close")


class TestMovingAverages:
    @staticmethod
    def _legacy_smma(series: pd.Series, period: int, weight: float = 1.0) -> pd.Series:
        result = series.rolling(period).mean()
        for i in range(period, len(series)):
            result.iloc[i] = (result.iloc[i - 1] * (period - weight) + series.iloc[i] * weight) / period
        return result

    def test_ma_simple(self):
        prices = _make_prices(50, base=10.0)
        result = ma(prices, period=10)
        assert len(result) == 50
        assert pd.isna(result.iloc[:9]).all()  # first 9 are NaN
        assert result.iloc[9] > 0  # 10th value is valid

    def test_ema(self):
        prices = _make_prices(50, base=10.0)
        result = ema(prices, period=10)
        assert len(result) == 50
        assert result.iloc[-1] > 0

    def test_sma(self):
        prices = _make_prices(50, base=10.0)
        result = sma(prices, period=10)
        assert len(result) == 50
        assert result.iloc[-1] > 0
        # sma is a plain rolling mean — first 9 values should be NaN
        assert pd.isna(result.iloc[:9]).all()
        assert pd.notna(result.iloc[9])

    def test_smma(self):
        prices = _make_prices(50, base=10.0)
        result = smma(prices, period=10)
        assert len(result) == 50
        assert result.iloc[-1] > 0
        # smma and sma should diverge: smma is exponentially smoothed
        sma_result = sma(prices, period=10)
        assert not (result == sma_result).all()

    def test_smma_matches_legacy_formula(self):
        prices = _make_prices(80, base=15.0)
        result = smma(prices, period=14, weight=1.0)
        expected = self._legacy_smma(prices, period=14, weight=1.0)
        pd.testing.assert_series_equal(result, expected)

    def test_smma_matches_legacy_formula_custom_weight(self):
        prices = _make_prices(80, base=15.0)
        result = smma(prices, period=14, weight=2.0)
        expected = self._legacy_smma(prices, period=14, weight=2.0)
        pd.testing.assert_series_equal(result, expected)

    def test_wma(self):
        prices = _make_prices(50, base=10.0)
        result = wma(prices, period=10)
        assert len(result) == 50


class TestMACD:
    def test_macd_returns_three_values(self):
        prices = _make_prices(100)
        diff, dea, macd_vals = macd(prices, fast=12, slow=26, signal=9)
        assert len(diff) == 100
        assert len(dea) == 100
        assert len(macd_vals) == 100

    def test_macd_with_custom_window(self):
        prices = _make_prices(50)
        diff, dea, macd_vals = macd(prices, fast=5, slow=20, signal=5)
        assert len(diff) == 50


class TestRSI:
    def test_rsi_range(self):
        prices = _make_prices(100)
        result = rsi(prices, period=14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_window(self):
        prices = _make_prices(100)
        result = rsi(prices, period=7)
        assert len(result) == 100


class TestKDJ:
    def test_kdj_returns_three_values(self):
        prices = _make_prices(100)
        highs = prices * 1.02
        lows = prices * 0.98
        k, d, j = kdj(highs, lows, prices, period=9)
        assert len(k) == 100
        assert len(d) == 100
        assert len(j) == 100


class TestBollingerBands:
    def test_boll_returns_three_values(self):
        prices = _make_prices(100)
        upper, mid, lower = boll(prices, period=20, num_std=2)
        assert len(upper) == 100
        assert len(mid) == 100
        assert len(lower) == 100
        # Upper should be above lower
        valid_mask = upper.notna() & lower.notna()
        if valid_mask.any():
            assert (upper[valid_mask] > lower[valid_mask]).all()


class TestATR:
    def test_atr_positive(self):
        prices = _make_prices(100)
        highs = prices * 1.02
        lows = prices * 0.98
        result = atr(highs, lows, prices, period=14)
        assert (result.dropna() > 0).all()


class TestCCI:
    def test_cci(self):
        prices = _make_prices(100)
        highs = prices * 1.02
        lows = prices * 0.98
        result = cci(highs, lows, prices, period=14)
        assert len(result) == 100


class TestWR:
    def test_wr_range(self):
        prices = _make_prices(100)
        highs = prices * 1.02
        lows = prices * 0.98
        result = wr(highs, lows, prices, period=14)
        valid = result.dropna()
        assert (valid <= 0).all()
        assert (valid >= -100).all()


class TestROC:
    def test_roc(self):
        prices = _make_prices(100)
        result = roc(prices, period=12)
        assert len(result) == 100


class TestOBV:
    def test_obv(self):
        prices = _make_prices(100)
        volumes = pd.Series(np.random.randint(1000, 10000, size=100))
        result = obv(prices, volumes)
        assert len(result) == 100


class TestADX:
    def test_adx(self):
        prices = _make_prices(100)
        highs = prices * 1.02
        lows = prices * 0.98
        pdi, mdi, adx_val, adxr = adx(highs, lows, prices, period=14)
        assert len(pdi) == 100
        assert len(mdi) == 100
        assert len(adx_val) == 100
        assert len(adxr) == 100


class TestCrossDetection:
    def test_golden_cross_true(self):
        fast = pd.Series([10, 11, 12, 11, 12, 13])
        slow = pd.Series([12, 12, 12, 12, 12, 12])
        result = golden_cross(fast, slow)
        assert isinstance(result, pd.Series)
        # Cross happens at index 4 (fast went from 11<=12 to 12>12 — actually at index where it crosses)
        assert result.any()  # at least one True

    def test_golden_cross_false(self):
        fast = pd.Series([14, 13, 12, 11, 10, 9])
        slow = pd.Series([10, 10, 10, 10, 10, 10])
        result = golden_cross(fast, slow)
        assert not result.any()

    def test_death_cross_true(self):
        fast = pd.Series([10, 11, 12, 11, 10, 9])
        slow = pd.Series([12, 12, 12, 12, 12, 12])
        result = death_cross(fast, slow)
        assert isinstance(result, pd.Series)
        assert result.any()

    def test_death_cross_false(self):
        fast = pd.Series([14, 15, 16, 17, 18, 19])
        slow = pd.Series([12, 12, 12, 12, 12, 12])
        result = death_cross(fast, slow)
        assert not result.any()
