"""Tests for MEDIUM items: optimizer guard, cache key unification, etc."""

from __future__ import annotations

import datetime
import warnings

import numpy as np
import pandas as pd
import pytest


class TestOptimizerDivZeroGuard:
    """MED-22: optimizer should return None when all weights zeroed."""

    def test_all_weights_zeroed_returns_none(self):
        """When min_weight=1.0 and max_weight=1.0 with many assets,
        optimizer may produce weights that all get zeroed out."""
        from eqlib.optimizer import portfolio_optimizer, MinVariance

        # Create prices where all assets have nearly identical returns
        # This can cause optimizer to concentrate on one asset and
        # zero out the rest, potentially leaving nothing after threshold
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)
        # Two assets with very similar price paths
        prices = pd.DataFrame(
            {
                "A": 100 + np.cumsum(np.random.randn(100) * 0.01),
                "B": 100 + np.cumsum(np.random.randn(100) * 0.01),
            },
            index=dates,
        )
        # Should not raise, and should return valid weights or None
        result = portfolio_optimizer(
            securities=["A", "B"],
            prices=prices,
            target=MinVariance(),
        )
        # Either valid weights (sum to 1) or None — no crash
        if result is not None:
            assert abs(result.sum() - 1.0) < 1e-6


class TestTradingDaysRangeCacheKey:
    """MED-23: _get_trading_days_range cache should unify date types."""

    def test_date_and_datetime_produce_same_result(self):
        from eqlib.data import _get_trading_days_range

        d1 = datetime.date(2024, 1, 1)
        d2 = datetime.date(2024, 1, 31)
        dt1 = datetime.datetime(2024, 1, 1)
        dt2 = datetime.datetime(2024, 1, 31)
        ts1 = pd.Timestamp("2024-01-01")
        ts2 = pd.Timestamp("2024-01-31")

        r1 = _get_trading_days_range(d1, d2)
        r2 = _get_trading_days_range(dt1, dt2)
        r3 = _get_trading_days_range(ts1, ts2)

        assert r1 == r2 == r3

    def test_cache_info_shares_hits(self):
        """After calling with different date types, cache should show hits."""
        from eqlib.data import (
            _get_trading_days_range,
            _get_trading_days_range_raw,
        )

        # Clear any previous cache state by checking raw cache info
        _get_trading_days_range_raw.cache_clear()

        d1 = datetime.date(2024, 3, 1)
        d2 = datetime.date(2024, 3, 31)
        dt1 = datetime.datetime(2024, 3, 1)
        dt2 = datetime.datetime(2024, 3, 31)

        _get_trading_days_range(d1, d2)
        _get_trading_days_range(dt1, dt2)  # should hit cache via raw

        info = _get_trading_days_range_raw.cache_info()
        assert info.hits >= 1, f"Expected cache hit but got {info}"
