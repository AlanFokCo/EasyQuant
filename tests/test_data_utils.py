"""Tests for pure data-utility functions (no network required)."""

import datetime
from eqlib.data import _is_index, _is_etf, _code_to_akshare, _get_trading_days_range, _iter_days, _is_ashare_holiday


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


class TestTradingDayFallback:
    def test_cached_trading_day_range_matches_iter_days_filter(self):
        start = datetime.date(2024, 1, 1)
        end = datetime.date(2024, 1, 15)
        expected = tuple(
            d for d in _iter_days(start, end)
            if d.weekday() < 5 and not _is_ashare_holiday(d)
        )
        assert _get_trading_days_range(start, end) == expected
