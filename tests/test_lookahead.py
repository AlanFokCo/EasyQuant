"""Tests for BLOCKER-1 (look-ahead bias) and BLOCKER-5 (order mix raise).

BLOCKER-1: attribute_history uses .loc[:ts] (closed interval).  When
context.current_dt = 09:30, the slice includes the current day's OHLCV,
letting strategies "peek" at today's close.  Expected: only data strictly
before today should be returned.

BLOCKER-5: order() and order_target() for the same security within a
single callback silently produce wrong target calculations.  The fix:
detect mixed ORDER vs ORDER_TARGET/ORDER_VALUE/ORDER_TARGET_VALUE actions
for the same security in the pending queue and raise ValueError.
"""

import datetime

import pandas as pd
import pytest


# ── Shared helpers (reuse pattern from test_p0_fixes.py) ────────────────────

def _make_preloaded(bars: dict[str, dict[datetime.date, dict]]) -> "PreloadedData":
    """Build a minimal PreloadedData instance from a nested dict."""
    from eqlib.data_cache import PreloadedData

    pd_frames = {}
    for sec, day_bars in bars.items():
        rows = []
        for d, bar in sorted(day_bars.items()):
            rows.append({**bar, "date": pd.Timestamp(d)})
        df = pd.DataFrame(rows).set_index("date")
        pd_frames[sec] = df

    pre = PreloadedData()
    pre.panel = pd.concat(pd_frames, axis=1)
    pre.panel.columns = pd.MultiIndex.from_tuples(
        [(sec, col) for sec in pd_frames for col in pd_frames[sec].columns],
        names=["security", "field"],
    )
    pre._securities = sorted(pd_frames.keys())
    pre._dates = pre.panel.index

    for sec, df in pd_frames.items():
        if "close" in df.columns:
            pre._close_dict[sec] = dict(zip(df.index, df["close"]))
        fields = ["open", "high", "low", "close", "volume"]
        pre._bar_cache[sec] = df.reindex(columns=fields, fill_value=0).to_dict("index")
        pre._field_series[sec] = {f: df[f] for f in df.columns if f in df}

    return pre


def _activate_preloaded(pre):
    """Install *pre* as the active session's preloaded data."""
    from eqlib._state import get_session
    import eqlib.engine as eng
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    eng._preloaded = pre


def _clear_preloaded():
    """Remove any preloaded data from the active session."""
    from eqlib._state import get_session
    import eqlib.engine as eng
    sess = get_session()
    object.__setattr__(sess, "_preloaded", None)
    eng._preloaded = eng._preloaded_fallback


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-1: attribute_history must NOT include today's bar
# ══════════════════════════════════════════════════════════════════════════════

class TestBlocker1LookAhead:

    def setup_method(self):
        _clear_preloaded()

    def teardown_method(self):
        _clear_preloaded()

    def _make_panel_two_days(self):
        """Panel with yesterday close=100, today close=999."""
        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)
        return {
            "600519": {
                yesterday: {
                    "open": 100, "high": 100, "low": 100,
                    "close": 100, "volume": 1000,
                },
                today: {
                    "open": 105, "high": 110, "low": 98,
                    "close": 999, "volume": 2000,
                },
            }
        }

    def test_attribute_history_closes_yesterday_not_today(self):
        """attribute_history(sec, 1, '1d', ['close']) at 09:30 must return yesterday's close.

        Preloaded panel: yesterday=100, today=999.
        context.current_dt = today 09:30.
        Bug: .loc[:ts] (closed interval) includes today → returns 999.
        Fix: strict < today → returns 100.
        """
        from eqlib._state import BacktestSession, _set_session, _context
        from eqlib.data import attribute_history

        pre = _make_preloaded(self._make_panel_two_days())
        _activate_preloaded(pre)

        today = datetime.date(2024, 1, 4)
        current_dt = datetime.datetime(today.year, today.month, today.day, 9, 30)

        # Set up session context (what engine does before calling market_open)
        sess = BacktestSession()
        _set_session(sess)
        object.__setattr__(sess, "_preloaded", pre)
        sess._context = type("FakeContext", (), {"current_dt": current_dt})()

        result = attribute_history("600519", 1, "1d", ["close"])

        # With the bug, result.iloc[-1]["close"] == 999 (today's close — look-ahead!)
        # After fix, result.iloc[-1]["close"] == 100 (yesterday's close)
        assert not result.empty, "attribute_history should return data"
        assert result.iloc[-1]["close"] == 100, (
            f"attribute_history at 09:30 returned today's close ({result.iloc[-1]['close']}) "
            "instead of yesterday's — look-ahead bias detected"
        )

    def test_attribute_history_multiple_fields_no_today(self):
        """With multiple fields, none should include today's values."""
        from eqlib._state import BacktestSession, _set_session
        from eqlib.data import attribute_history

        pre = _make_preloaded(self._make_panel_two_days())
        _activate_preloaded(pre)

        today = datetime.date(2024, 1, 4)
        current_dt = datetime.datetime(today.year, today.month, today.day, 9, 30)

        sess = BacktestSession()
        _set_session(sess)
        object.__setattr__(sess, "_preloaded", pre)
        sess._context = type("FakeContext", (), {"current_dt": current_dt})()

        result = attribute_history("600519", 2, "1d", ["close", "volume"])

        # Only 1 row available (yesterday); today is excluded
        assert len(result) == 1, f"Expected 1 row (yesterday only), got {len(result)}"
        assert result.iloc[0]["close"] == 100
        assert result.iloc[0]["volume"] == 1000

    def test_attribute_history_returns_empty_on_first_day(self):
        """When there's no historical data before today, return empty DataFrame."""
        from eqlib._state import BacktestSession, _set_session
        from eqlib.data import attribute_history

        first_day = datetime.date(2024, 1, 2)
        bars = {
            "000001": {
                first_day: {
                    "open": 10, "high": 10, "low": 10,
                    "close": 10, "volume": 1000,
                },
            }
        }
        pre = _make_preloaded(bars)
        _activate_preloaded(pre)

        current_dt = datetime.datetime(
            first_day.year, first_day.month, first_day.day, 9, 30
        )

        sess = BacktestSession()
        _set_session(sess)
        object.__setattr__(sess, "_preloaded", pre)
        sess._context = type("FakeContext", (), {"current_dt": current_dt})()

        result = attribute_history("000001", 5, "1d", ["close"])

        # No data strictly before first_day → empty
        assert result.empty, (
            "attribute_history should return empty when no prior data exists"
        )

    def test_attribute_history_legacy_panel_path_no_today(self):
        """The legacy panel fallback path (sec_df[sec_df.index <= current])
        also has look-ahead — it should use strict <."""
        from eqlib._state import BacktestSession, _set_session
        from eqlib.data import attribute_history

        # Build a panel where _field_series is NOT populated (forces fallback path)
        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)
        from eqlib.data_cache import PreloadedData

        sec_df = pd.DataFrame({
            "open": [100, 105],
            "high": [100, 110],
            "low": [100, 98],
            "close": [100, 999],
            "volume": [1000, 2000],
        }, index=pd.DatetimeIndex([yesterday, today]))

        pre = PreloadedData()
        pre.panel = {"600519": sec_df}
        pre._securities = ["600519"]
        pre._dates = sec_df.index
        # Deliberately NOT populate _field_series → forces fallback path
        pre._field_series = {}
        pre._close_dict = {"600519": {yesterday: 100, today: 999}}
        pre._bar_cache = {
            "600519": {
                pd.Timestamp(yesterday): {"open": 100, "high": 100, "low": 100,
                                           "close": 100, "volume": 1000},
                pd.Timestamp(today): {"open": 105, "high": 110, "low": 98,
                                       "close": 999, "volume": 2000},
            }
        }
        _activate_preloaded(pre)

        current_dt = datetime.datetime(today.year, today.month, today.day, 9, 30)

        sess = BacktestSession()
        _set_session(sess)
        object.__setattr__(sess, "_preloaded", pre)
        sess._context = type("FakeContext", (), {"current_dt": current_dt})()

        result = attribute_history("600519", 2, "1d", ["close"])

        assert not result.empty
        assert result.iloc[-1]["close"] == 100, (
            f"Legacy panel path returned today's close ({result.iloc[-1]['close']}) "
            "— look-ahead bias in fallback path"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-5: order + order_target mix for same security must raise
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker5OrderMix:

    def setup_method(self):
        from eqlib._state import BacktestSession, _set_session
        from eqlib.context import Context

        sess = BacktestSession()
        _set_session(sess)
        self._sess = sess

    def teardown_method(self):
        from eqlib._state import _set_session
        _set_session(None)

    def _setup_context_and_pending(self, security: str = "601390"):
        """Set up a session with context and clear pending orders."""
        from eqlib.context import Context
        import datetime as _dt

        day = _dt.date(2024, 1, 4)
        ctx = Context(day, day, "daily", 1_000_000)
        self._sess._context = ctx
        self._sess._pending_orders.clear()

    def test_mix_order_and_order_target_raises(self):
        """Calling order() then order_target() on the same security raises."""
        from eqlib.trade import order, order_target

        self._setup_context_and_pending()
        order("601390", 100)
        with pytest.raises(ValueError, match="Cannot mix"):
            order_target("601390", 200)

    def test_mix_order_and_order_value_raises(self):
        """Calling order() then order_value() on the same security raises."""
        from eqlib.trade import order, order_value

        self._setup_context_and_pending()
        order("601390", 100)
        with pytest.raises(ValueError, match="Cannot mix"):
            order_value("601390", 10000)

    def test_mix_order_target_and_order_raises(self):
        """Calling order_target() then order() on the same security raises."""
        from eqlib.trade import order, order_target

        self._setup_context_and_pending()
        order_target("601390", 200)
        with pytest.raises(ValueError, match="Cannot mix"):
            order("601390", 100)

    def test_same_order_type_same_security_is_fine(self):
        """Multiple order() calls for the same security should still work (queued)."""
        from eqlib.trade import order

        self._setup_context_and_pending()
        oid1 = order("601390", 100)
        oid2 = order("601390", 200)
        assert oid1 is not None
        assert oid2 is not None
        assert len(self._sess._pending_orders) == 2

    def test_different_securities_mix_is_fine(self):
        """order() for A and order_target() for B should not conflict."""
        from eqlib.trade import order, order_target

        self._setup_context_and_pending()
        oid1 = order("601390", 100)
        oid2 = order_target("000001", 200)
        assert oid1 is not None
        assert oid2 is not None
        assert len(self._sess._pending_orders) == 2

    def test_mix_order_value_and_order_target_value_is_fine(self):
        """order_value and order_target_value for same security are both target types — no conflict."""
        from eqlib.trade import order_value, order_target_value

        self._setup_context_and_pending()
        oid1 = order_value("601390", 50000)
        oid2 = order_target_value("601390", 200000)
        assert oid1 is not None
        assert oid2 is not None
        assert len(self._sess._pending_orders) == 2

    def test_all_four_types_together_raises(self):
        """Using all four order types for same security raises."""
        from eqlib.trade import order, order_target, order_value, order_target_value

        self._setup_context_and_pending()
        order("601390", 100)
        with pytest.raises(ValueError, match="Cannot mix"):
            order_target("601390", 200)
        # After exception, the first order should still be in the queue
        assert len(self._sess._pending_orders) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# PR-C: PreloadedData.get_history and get_indicators must not return today's bar
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreloadedDataNoLookahead:
    """Direct tests for PreloadedData.get_history and get_indicators (PR-C).

    These are public methods of PreloadedData.  Previously they used
    loc[:ts] (closed interval) which included today's bar — look-ahead bias.
    The fix uses strict < cutoff consistent with data.py:564-567.
    """

    def _make_pre_with_indicators(self):
        """Return a PreloadedData with 2-day OHLCV + fake indicators."""
        import datetime
        from eqlib.data_cache import PreloadedData

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)

        pre = PreloadedData()
        idx = pd.DatetimeIndex([pd.Timestamp(yesterday), pd.Timestamp(today)])

        # _field_series for get_history
        close_s = pd.Series([100.0, 999.0], index=idx)
        volume_s = pd.Series([1000.0, 9999.0], index=idx)
        pre._field_series["600519"] = {"close": close_s, "volume": volume_s}

        # _indicators for get_indicators
        ind_df = pd.DataFrame(
            {"sma5": [10.0, 99.0], "rsi14": [50.0, 77.0]},
            index=idx,
        )
        pre._indicators["600519"] = ind_df

        return pre, yesterday, today

    def test_get_history_does_not_return_today_bar(self):
        """get_history at 09:30 today must not include today's close."""
        pre, yesterday, today = self._make_pre_with_indicators()
        current_dt = datetime.datetime(today.year, today.month, today.day, 9, 30)

        result = pre.get_history("600519", 5, ["close", "volume"], current_dt)

        assert result is not None
        assert not result.empty
        # Only yesterday should appear; today (close=999) must be excluded
        assert 999.0 not in result["close"].values, (
            "get_history returned today's close (999) — look-ahead bias in get_history"
        )
        assert result.iloc[-1]["close"] == 100.0

    def test_get_history_returns_none_for_unknown_security(self):
        """get_history on an unknown security returns None."""
        pre, _y, today = self._make_pre_with_indicators()
        result = pre.get_history("UNKNOWN", 5, ["close"], today)
        assert result is None

    def test_get_indicators_does_not_return_today_bar(self):
        """get_indicators at 09:30 today must not include today's indicators."""
        pre, yesterday, today = self._make_pre_with_indicators()
        current_dt = datetime.datetime(today.year, today.month, today.day, 9, 30)

        result = pre.get_indicators("600519", 5, current_dt)

        assert result is not None
        assert not result.empty
        # Today's sma5=99 and rsi14=77 must be excluded
        assert 99.0 not in result["sma5"].values, (
            "get_indicators returned today's sma5 (99) — look-ahead bias in get_indicators"
        )
        assert result.iloc[-1]["sma5"] == 10.0

    def test_get_indicators_returns_none_for_unknown_security(self):
        """get_indicators on a security with no indicator data returns None."""
        pre, _y, today = self._make_pre_with_indicators()
        result = pre.get_indicators("UNKNOWN", 5, today)
        assert result is None

    def test_get_history_no_current_dt_returns_all(self):
        """Without a current_dt filter, get_history returns all available bars."""
        pre, _y, _t = self._make_pre_with_indicators()
        result = pre.get_history("600519", 10, ["close"], None)
        assert result is not None
        assert len(result) == 2

    def test_get_indicators_no_current_dt_returns_all(self):
        """Without a current_dt filter, get_indicators returns all available rows."""
        pre, _y, _t = self._make_pre_with_indicators()
        result = pre.get_indicators("600519", 10, None)
        assert result is not None
        assert len(result) == 2
