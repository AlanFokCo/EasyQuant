"""Tests for dimension 1 backtest credibility fixes.

1.1 _get_price_limit_ratio() uses session-level cache and skips network
    calls (akshare/get_extras) in backtest mode.
1.2 BacktestSession includes _after_trading_end_done in __slots__ and reset().
1.3 _compute_chart_data returns multi-stock K-line data (symbols_data dict)
    with per-symbol markers filtered correctly.
"""

import datetime
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# 1.1 Price-limit ratio caching
# ---------------------------------------------------------------------------

class TestPriceLimitCaching:
    """_get_price_limit_ratio must use session cache and classify boards."""

    def test_star_market_20pct(self):
        """STAR Market (688xxx) → 20%."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("688001.XSHG") == 0.20

    def test_chinext_20pct(self):
        """ChiNext (300xxx) → 20%."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("300001.XSHE") == 0.20

    def test_main_board_10pct(self):
        """Main board (601xxx) → 10% (no network calls in backtest)."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("601390.XSHG") == 0.10

    def test_session_cache_stores_result(self):
        """After first call, the ratio is cached in session._options."""
        from eqlib._state import BacktestSession
        from eqlib.engine import _get_price_limit_ratio

        sess = BacktestSession()
        ratio = _get_price_limit_ratio("688001.XSHG", session=sess)
        assert ratio == 0.20
        cache = sess._options.get("_price_limit_cache")
        assert cache is not None
        assert cache["688001.XSHG"] == 0.20

    def test_session_cache_returns_cached_value(self):
        """Second call returns the cached value without recomputation."""
        from eqlib._state import BacktestSession
        from eqlib.engine import _get_price_limit_ratio

        sess = BacktestSession()
        # Pre-populate cache with a custom value
        sess._options["_price_limit_cache"] = {"000001.XSHE": 0.42}
        assert _get_price_limit_ratio("000001.XSHE", session=sess) == 0.42

    def test_no_session_skips_network(self):
        """session=None → skip_network_calls=True, returns 10% for main board."""
        from eqlib.engine import _get_price_limit_ratio
        # Should NOT attempt network calls and should return 10%
        assert _get_price_limit_ratio("601390.XSHG", session=None) == 0.10

    def test_backtest_session_skips_network(self):
        """Backtest session (no _is_paper_trading flag) skips network calls."""
        from eqlib._state import BacktestSession
        from eqlib.engine import _get_price_limit_ratio

        sess = BacktestSession()
        # No _is_paper_trading → skip_network_calls = True
        assert _get_price_limit_ratio("601390.XSHG", session=sess) == 0.10

    def test_cache_price_limit_helper(self):
        """_cache_price_limit stores ratio in session options dict."""
        from eqlib._state import BacktestSession
        from eqlib.engine import _cache_price_limit

        sess = BacktestSession()
        _cache_price_limit(sess, "300100.XSHE", 0.20)
        assert sess._options["_price_limit_cache"]["300100.XSHE"] == 0.20

    def test_cache_price_limit_no_session(self):
        """_cache_price_limit with session=None does not raise."""
        from eqlib.engine import _cache_price_limit
        _cache_price_limit(None, "601390.XSHG", 0.10)  # should not raise


# ---------------------------------------------------------------------------
# 1.2 BacktestSession _after_trading_end_done slot
# ---------------------------------------------------------------------------

class TestAfterTradingEndDoneSlot:
    """_after_trading_end_done must be in __slots__ and reset to False."""

    def test_slot_exists(self):
        """BacktestSession.__slots__ includes _after_trading_end_done."""
        from eqlib._state import BacktestSession
        assert "_after_trading_end_done" in BacktestSession.__slots__

    def test_default_false(self):
        """A fresh session has _after_trading_end_done = False."""
        from eqlib._state import BacktestSession
        sess = BacktestSession()
        assert sess._after_trading_end_done is False

    def test_reset_clears_flag(self):
        """reset() sets _after_trading_end_done back to False."""
        from eqlib._state import BacktestSession
        sess = BacktestSession()
        sess._after_trading_end_done = True
        sess.reset()
        assert sess._after_trading_end_done is False


# ---------------------------------------------------------------------------
# 1.3 Multi-stock K-line chart data
# ---------------------------------------------------------------------------

def _make_ohlcv(symbol, n_days=30, start_date="2024-01-02"):
    """Build a simple OHLCV DataFrame for testing."""
    import numpy as np
    dates = pd.bdate_range(start_date, periods=n_days, freq="B")
    rng = np.random.RandomState(42)
    base = 10.0 + rng.randn(n_days).cumsum() * 0.5
    df = pd.DataFrame({
        "open": base,
        "high": base + 0.3,
        "low": base - 0.3,
        "close": base + 0.1,
        "volume": rng.randint(1000, 5000, n_days).astype(float),
    }, index=dates)
    return df


def _make_result_for_chart(symbols, ohlcv_data=None, trade_log=None):
    """Build a minimal backtest result dict for _compute_chart_data."""
    start = datetime.date(2024, 1, 2)
    end = datetime.date(2024, 2, 15)
    dates = pd.bdate_range(start, end, freq="B")

    entries = [
        {"date": d.date(), "total_value": 100000.0 + i * 10}
        for i, d in enumerate(dates)
    ]

    class FakePortfolio:
        starting_cash = 100000.0
        total_value = entries[-1]["total_value"]
        positions = {}

    class FakeContext:
        portfolio = FakePortfolio()
        start_date = start
        end_date = end
        universe = list(symbols)

    if ohlcv_data is None:
        ohlcv_data = {s: _make_ohlcv(s) for s in symbols}

    if trade_log is None:
        trade_log = []

    return {
        "context": FakeContext(),
        "trade_log": trade_log,
        "recorded_values": entries,
        "ohlcv_data": ohlcv_data,
    }


class TestMultiStockKline:
    """_compute_chart_data produces per-symbol K-line data."""

    def test_symbols_data_populated(self):
        """symbols_data dict has entries for all traded symbols."""
        from eqlib.report import _compute_chart_data
        trade_log = [
            {"date": datetime.date(2024, 1, 5), "security": "601390",
             "type": "BUY", "amount": 100, "price": 10.0, "commission": 5.0},
            {"date": datetime.date(2024, 1, 8), "security": "000001",
             "type": "BUY", "amount": 200, "price": 15.0, "commission": 5.0},
        ]
        result = _make_result_for_chart(["601390", "000001"], trade_log=trade_log)
        chart = _compute_chart_data(result)

        assert "symbols_data" in chart
        assert "601390" in chart["symbols_data"]
        assert "000001" in chart["symbols_data"]

    def test_symbols_list_sorted(self):
        """symbols_list is sorted alphabetically."""
        from eqlib.report import _compute_chart_data
        trade_log = [
            {"date": datetime.date(2024, 1, 5), "security": "601390",
             "type": "BUY", "amount": 100, "price": 10.0, "commission": 5.0},
            {"date": datetime.date(2024, 1, 8), "security": "000001",
             "type": "BUY", "amount": 200, "price": 15.0, "commission": 5.0},
        ]
        result = _make_result_for_chart(["601390", "000001"], trade_log=trade_log)
        chart = _compute_chart_data(result)

        assert chart["symbols_list"] == ["000001", "601390"]

    def test_markers_filtered_per_symbol(self):
        """Each symbol's markers only include trades for that symbol."""
        from eqlib.report import _compute_chart_data
        trade_log = [
            {"date": datetime.date(2024, 1, 5), "security": "601390",
             "type": "BUY", "amount": 100, "price": 10.0, "commission": 5.0},
            {"date": datetime.date(2024, 1, 8), "security": "000001",
             "type": "BUY", "amount": 200, "price": 15.0, "commission": 5.0},
            {"date": datetime.date(2024, 1, 10), "security": "601390",
             "type": "SELL", "amount": 100, "price": 11.0, "commission": 5.0},
        ]
        result = _make_result_for_chart(["601390", "000001"], trade_log=trade_log)
        chart = _compute_chart_data(result)

        markers_601390 = chart["symbols_data"]["601390"]["markers"]
        markers_000001 = chart["symbols_data"]["000001"]["markers"]

        # 601390 has 2 trades, 000001 has 1
        assert len(markers_601390) == 2
        assert len(markers_000001) == 1

    def test_single_symbol_no_selector_needed(self):
        """With one symbol, symbols_list has length 1."""
        from eqlib.report import _compute_chart_data
        trade_log = [
            {"date": datetime.date(2024, 1, 5), "security": "601390",
             "type": "BUY", "amount": 100, "price": 10.0, "commission": 5.0},
        ]
        result = _make_result_for_chart(["601390"], trade_log=trade_log)
        chart = _compute_chart_data(result)

        assert chart["symbols_list"] == ["601390"]
        assert len(chart["symbols_data"]) == 1

    def test_primary_symbol_backward_compat(self):
        """Top-level chart keys (candlestick_data etc.) come from primary symbol."""
        from eqlib.report import _compute_chart_data
        trade_log = [
            {"date": datetime.date(2024, 1, 5), "security": "601390",
             "type": "BUY", "amount": 100, "price": 10.0, "commission": 5.0},
        ]
        result = _make_result_for_chart(["601390"], trade_log=trade_log)
        chart = _compute_chart_data(result)

        primary = chart["symbols_data"][chart["symbol"]]
        assert chart["candlestick_data"] == primary["candlestick_data"]
        assert chart["markers"] == primary["markers"]

    def test_compute_symbol_kline_returns_tech_stats(self):
        """_compute_symbol_kline includes tech_stats dict."""
        from eqlib.report import _compute_symbol_kline
        ohlcv = _make_ohlcv("601390", n_days=30)
        start = datetime.date(2024, 1, 2)
        end = datetime.date(2024, 2, 15)
        data = _compute_symbol_kline("601390", start, end,
                                     {"601390": ohlcv}, [])
        assert "tech_stats" in data
        assert isinstance(data["tech_stats"], dict)

    def test_empty_ohlcv_does_not_crash(self):
        """Missing OHLCV data for a symbol doesn't crash."""
        from eqlib.report import _compute_symbol_kline
        start = datetime.date(2024, 1, 2)
        end = datetime.date(2024, 2, 15)
        # Empty ohlcv_data dict — should handle gracefully
        data = _compute_symbol_kline("999999", start, end, {}, [])
        assert data["candlestick_data"] == []
        assert data["markers"] == []
