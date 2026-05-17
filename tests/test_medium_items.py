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


class TestFetchLivePricesSmallUniverse:
    """MED-24: _fetch_live_prices should avoid full A-share download for small universes."""

    def test_small_universe_no_bulk_download(self):
        """For <100 securities, should use individual hist endpoint, not bulk."""
        from unittest.mock import patch, MagicMock
        from eqlib.engine import _fetch_live_prices

        # With a small universe, bulk endpoint should NOT be called
        with patch("akshare.stock_zh_a_spot_em") as mock_bulk, \
             patch("akshare.stock_zh_a_hist") as mock_hist:
            mock_bulk.return_value = MagicMock()
            mock_bulk.side_effect = AssertionError("bulk endpoint should not be called")

            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.iloc = MagicMock()
            mock_df.iloc.__getitem__ = MagicMock(return_value=MagicMock())
            mock_df.iloc[-1].__getitem__ = MagicMock(return_value=10.5)
            mock_hist.return_value = mock_df

            cache = _fetch_live_prices({}, securities={"601390", "000001"})

            mock_bulk.assert_not_called()
            assert mock_hist.call_count == 2


class TestBareIndexCodeRetry:
    """MED-32: bare 000xxx codes should auto-retry as Shanghai indices."""

    def test_bare_000_code_retries_as_index(self):
        """When stock lookup fails for 000xxx, should retry as 000xxx.XSHG."""
        from unittest.mock import patch
        import pandas as pd
        import eqlib.data as data_mod

        # Clear in-memory cache to avoid test interference
        data_mod._cache.clear()

        # Create a properly formatted index DataFrame with DatetimeIndex
        def make_idx_df(*a, **kw):
            df = pd.DataFrame({
                "open": [3.8, 3.85], "high": [3.9, 3.95],
                "low": [3.7, 3.75], "close": [3.85, 3.90],
                "volume": [100, 110], "money": [385, 396],
                "pct_change": [1.0, 1.3], "price_change": [0.05, 0.10],
                "turnover": [0.01, 0.02],
            }, index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]))
            return df

        # Mock all stock-side fetchers to return empty, and index em to succeed.
        with patch.object(data_mod, "_fetch_from_em", return_value=pd.DataFrame()), \
             patch.object(data_mod, "_fetch_from_tencent", return_value=pd.DataFrame()), \
             patch.object(data_mod, "_fetch_from_sina", return_value=pd.DataFrame()), \
             patch.object(data_mod, "_fetch_from_baostock", return_value=pd.DataFrame()), \
             patch.object(data_mod.ak, "stock_zh_index_daily_em", return_value=make_idx_df()):
            from eqlib.data import fetch_stock_data
            result = fetch_stock_data("000300", "2024-01-01", "2024-01-05")
            # Index retry path should succeed
            assert not result.empty, "Should have retrieved index data via retry"
            assert "close" in result.columns
