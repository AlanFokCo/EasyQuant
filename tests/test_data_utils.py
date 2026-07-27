"""Tests for pure data-utility functions (no network required)."""

import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from eqlib.data import (
    _code_to_akshare,
    _compact_date_to_iso,
    _get_trading_days_range,
    _is_ashare_holiday,
    _is_etf,
    _is_index,
    _iter_days,
)


class TestIsIndex:
    def test_shanghai_index_with_xshg_suffix(self):
        """000xxx codes are Shanghai indices only when .XSHG is present."""
        assert _is_index("000300.XSHG") is True   # 沪深300
        assert _is_index("000001.XSHG") is True   # 上证综指
        assert _is_index("000905.XSHG") is True   # 中证500
        assert _is_index("000016.XSHG") is True   # 上证50

    def test_shenzhen_index_with_or_without_suffix(self):
        """399xxx codes are always Shenzhen indices."""
        assert _is_index("399001.XSHE") is True   # 深证成指
        assert _is_index("399006.XSHE") is True   # 创业板指
        assert _is_index("399001") is True         # suffix optional for 399xxx

    def test_shenzhen_stock_000xxx_not_index(self):
        """000xxx Shenzhen stocks must NOT be misclassified as indices."""
        assert _is_index("000858.XSHE") is False  # 五粮液
        assert _is_index("000858") is False        # no suffix → treat as stock
        assert _is_index("000001.XSHE") is False  # 平安银行
        assert _is_index("000002.XSHE") is False  # 万科A

    def test_shanghai_stock_not_index(self):
        assert _is_index("600519") is False        # 贵州茅台
        assert _is_index("601390") is False        # 中国中铁
        assert _is_index("600519.XSHG") is False  # with suffix (starts with 6)


class TestIsEtf:
    def test_etf_codes(self):
        assert _is_etf("510300") is True   # 沪深300 ETF (Shanghai)
        assert _is_etf("159919") is True   # 嘉实沪深300ETF (Shenzhen)
        assert _is_etf("161725") is True   # 招商中证白酒ETF

    def test_non_etf_codes(self):
        assert _is_etf("601390") is False
        assert _is_etf("000858") is False
        assert _is_etf("600519") is False


class TestCodeNormalization:
    def test_strip_exchange_suffix(self):
        assert _code_to_akshare("601390.XSHG") == "601390"
        assert _code_to_akshare("000858.XSHE") == "000858"
        assert _code_to_akshare("000858") == "000858"
        assert _code_to_akshare("000300.XSHG") == "000300"


class TestDateNormalization:
    def test_compact_date_to_iso_for_baostock(self):
        assert _compact_date_to_iso("20200102") == "2020-01-02"
        assert _compact_date_to_iso("2020-01-02") == "2020-01-02"


class TestTradingDayFallback:
    def test_cached_trading_day_range_matches_iter_days_filter(self):
        start = datetime.date(2024, 1, 1)
        end = datetime.date(2024, 1, 15)
        expected = tuple(
            d for d in _iter_days(start, end)
            if d.weekday() < 5 and not _is_ashare_holiday(d)
        )
        assert _get_trading_days_range(start, end) == expected


def _sample_ohlcv(start, periods):
    dates = pd.bdate_range(start, periods=periods, freq="B")
    return pd.DataFrame({
        "open": [10.0] * periods,
        "high": [10.5] * periods,
        "low": [9.8] * periods,
        "close": [10.2] * periods,
        "volume": [1000.0] * periods,
        "money": [10000.0] * periods,
        "pct_change": [0.0] * periods,
        "price_change": [0.0] * periods,
        "turnover": [0.0] * periods,
    }, index=dates)


class TestLongRangeSourceCoverage:
    def test_attribute_history_missing_preloaded_security_does_not_fetch_network(self, monkeypatch):
        """Backtest mode should treat preload misses as empty history."""
        import eqlib._state as state_mod
        import eqlib.data as data_mod
        import eqlib.engine as engine_mod
        from eqlib.data_cache import PreloadedData

        preloaded = PreloadedData()
        dates = pd.bdate_range("2020-01-01", periods=3)
        preloaded._field_series = {
            "600519": {
                "close": pd.Series([10.0, 10.1, 10.2], index=dates),
            }
        }
        preloaded.panel = None

        def fail_fetch(*args, **kwargs):
            raise AssertionError("attribute_history should not fetch network data in backtest mode")

        monkeypatch.setattr(engine_mod, "_get_preloaded", lambda: preloaded)
        monkeypatch.setattr(data_mod, "fetch_stock_data", fail_fetch)
        monkeypatch.setattr(
            state_mod,
            "_context",
            SimpleNamespace(current_dt=datetime.datetime(2020, 1, 6, 9, 30)),
        )

        result = data_mod.attribute_history("600941", 5, fields=["close"])

        assert result.empty

    def test_fetch_stock_data_skips_truncated_source_when_fuller_source_exists(self, monkeypatch):
        """Long backtests should not silently accept a recent truncated slice."""
        import eqlib.data as data_mod

        data_mod._cache.clear()
        truncated = _sample_ohlcv("2023-11-15", 20)
        full = _sample_ohlcv("2020-01-02", 60)
        monkeypatch.setattr(data_mod, "_DATA_FETCHERS", [
            ("tencent", lambda *args, **kwargs: truncated),
            ("sina", lambda *args, **kwargs: full),
        ])

        result = data_mod.fetch_stock_data("002594", "2020-01-01", "2026-07-08")

        assert result.index.min() == pd.Timestamp("2020-01-02")
        assert len(result) == len(full)

    def test_fetch_stock_data_returns_short_candidate_when_no_fuller_source(self, monkeypatch):
        """A truncated but valid candidate is still better than no data."""
        import eqlib.data as data_mod

        data_mod._cache.clear()
        truncated = _sample_ohlcv("2023-11-15", 20)
        monkeypatch.setattr(data_mod, "_DATA_FETCHERS", [
            ("tencent", lambda *args, **kwargs: truncated),
            ("sina", lambda *args, **kwargs: pd.DataFrame()),
        ])

        result = data_mod.fetch_stock_data("002594", "2020-01-01", "2026-07-08")

        assert result.index.min() == pd.Timestamp("2023-11-15")
        assert len(result) == len(truncated)

    @pytest.mark.parametrize("invalid", [float("inf"), float("-inf")])
    def test_validate_ohlcv_rejects_nonfinite_values(self, invalid):
        import eqlib.data as data_mod

        frame = _sample_ohlcv("2020-01-02", 10)
        frame.loc[frame.index[-1], "volume"] = invalid

        assert not data_mod._validate_ohlcv(frame, "test")

    def test_disk_cache_falls_back_to_pickle_without_parquet(self, monkeypatch, tmp_path):
        """Disk cache should still work when optional parquet engines are absent."""
        import eqlib.data_cache as cache_mod

        monkeypatch.setattr(cache_mod, "_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(cache_mod, "_parquet_engine", lambda: None)
        df = _sample_ohlcv("2020-01-02", 10)

        cache_mod._save_to_disk(df, "002594", "qfq")
        loaded = cache_mod._load_from_disk("002594", "20200101", "20200131", "qfq")

        assert cache_mod._pickle_cache_path("002594", "qfq").exists()
        assert loaded is not None
        assert loaded.index.min() == pd.Timestamp("2020-01-02")
        assert len(loaded) == len(df)
