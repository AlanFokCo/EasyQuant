"""Tests for HIGH-13: order_value / order_target_value emit a warning on large price gaps.

When today's open price is more than 10% above or below yesterday's close,
the engine logs a warning suggesting the caller use order() with explicit
share counts instead of value-based orders.
"""

from __future__ import annotations

import datetime
import logging
import pytest


@pytest.fixture(autouse=True)
def _propagate_eqlib_log():
    """Enable log propagation on the 'eqlib' logger during each test so that
    pytest's caplog fixture can capture messages."""
    import logging
    eqlib_log = logging.getLogger("eqlib")
    old = eqlib_log.propagate
    eqlib_log.propagate = True
    yield
    eqlib_log.propagate = old


def _make_session(cash: float = 1_000_000.0):
    from eqlib._state import BacktestSession, _set_session
    from eqlib.context import Context
    import eqlib.engine as eng

    sess = BacktestSession()
    _set_session(sess)
    day = datetime.date(2024, 1, 4)
    ctx = Context(day, day, "daily", cash)
    sess._context = ctx
    eng._preloaded = eng._preloaded_fallback
    return sess, ctx.portfolio, day


def _set_preloaded_two_days(security, yesterday, prev_close, today, today_open):
    """Install preloaded data with a yesterday and today bar."""
    import pandas as pd
    from eqlib.data_cache import PreloadedData
    import eqlib.engine as eng
    from eqlib._state import get_session

    pre = PreloadedData()
    ts_y = pd.Timestamp(yesterday)
    ts_t = pd.Timestamp(today)
    pre._bar_cache[security] = {
        ts_y: {"open": prev_close, "high": prev_close, "low": prev_close,
               "close": prev_close, "volume": 1_000_000},
        ts_t: {"open": today_open, "high": today_open, "low": today_open,
               "close": today_open, "volume": 1_000_000},
    }
    pre._close_dict[security] = {ts_y: prev_close, ts_t: today_open}
    pre._field_series[security] = {
        "close": pd.Series([prev_close, today_open], index=[ts_y, ts_t]),
        "volume": pd.Series([1_000_000.0, 1_000_000.0], index=[ts_y, ts_t]),
    }
    pre._securities = [security]
    pre._dates = pd.DatetimeIndex([ts_y, ts_t])
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    eng._preloaded = pre


class TestHigh13OrderValueGap:
    def setup_method(self):
        from eqlib._state import BacktestSession, _set_session
        import eqlib.engine as eng
        _set_session(BacktestSession())
        eng._preloaded = eng._preloaded_fallback

    def teardown_method(self):
        from eqlib._state import _clear_session
        import eqlib.engine as eng
        _clear_session()
        eng._preloaded = eng._preloaded_fallback

    def test_order_value_gap_up_emits_warning(self, caplog):
        """order_value on a stock that gapped up >10% emits a warning."""
        from eqlib.trade import order_value
        import eqlib.engine as eng

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)
        prev_close = 10.0
        today_open = 11.1  # +11% gap

        sess, _, _ = _make_session()
        _set_preloaded_two_days("600519", yesterday, prev_close, today, today_open)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order_value("600519", 10_000)
            eng._fill_pending_orders(sess, today)

        gap_warnings = [m for m in caplog.messages
                        if "gap" in m.lower() and "600519" in m]
        assert gap_warnings, (
            "Expected a gap warning for order_value with >10% price gap, got none.\n"
            f"All warnings: {caplog.messages}"
        )

    def test_order_value_gap_down_emits_warning(self, caplog):
        """order_value on a stock that gapped down >10% emits a warning."""
        from eqlib.trade import order_value
        import eqlib.engine as eng

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)
        prev_close = 10.0
        today_open = 8.9  # -11% gap

        sess, _, _ = _make_session()
        _set_preloaded_two_days("600519", yesterday, prev_close, today, today_open)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order_value("600519", 10_000)
            eng._fill_pending_orders(sess, today)

        gap_warnings = [m for m in caplog.messages
                        if "gap" in m.lower() and "600519" in m]
        assert gap_warnings, "Expected a gap warning for order_value with >10% gap down"

    def test_order_target_value_gap_emits_warning(self, caplog):
        """order_target_value also emits a warning on a large gap."""
        from eqlib.trade import order_target_value
        import eqlib.engine as eng

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)

        sess, _, _ = _make_session()
        _set_preloaded_two_days("600519", yesterday, 10.0, today, 11.5)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order_target_value("600519", 50_000)
            eng._fill_pending_orders(sess, today)

        gap_warnings = [m for m in caplog.messages if "gap" in m.lower()]
        assert gap_warnings, "Expected gap warning for order_target_value"

    def test_order_value_small_gap_no_warning(self, caplog):
        """order_value with a small price move (<10%) must NOT emit a gap warning."""
        from eqlib.trade import order_value
        import eqlib.engine as eng

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)

        sess, _, _ = _make_session()
        _set_preloaded_two_days("600519", yesterday, 10.0, today, 10.5)  # +5%

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order_value("600519", 10_000)
            eng._fill_pending_orders(sess, today)

        gap_warnings = [m for m in caplog.messages
                        if "gap" in m.lower() and "600519" in m]
        assert not gap_warnings, f"Unexpected gap warning for small move: {gap_warnings}"

    def test_plain_order_no_gap_warning(self, caplog):
        """Plain order() must never emit a gap warning (not a value-based order)."""
        from eqlib.trade import order
        import eqlib.engine as eng

        yesterday = datetime.date(2024, 1, 3)
        today = datetime.date(2024, 1, 4)

        sess, _, _ = _make_session()
        _set_preloaded_two_days("600519", yesterday, 10.0, today, 12.0)  # +20%

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order("600519", 100)
            eng._fill_pending_orders(sess, today)

        gap_warnings = [m for m in caplog.messages if "gap" in m.lower()]
        assert not gap_warnings, (
            f"order() should not emit gap warnings, got: {gap_warnings}"
        )
