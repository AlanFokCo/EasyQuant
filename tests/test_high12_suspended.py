"""Tests for HIGH-12: suspended detection distinguishes "missing bar" from "volume=0".

Previously _get_volume_fast returned 0.0 for both missing bars and zero-volume
bars; the suspension check could not tell them apart.

After the fix:
- _get_volume_fast returns None when the bar is absent (no entry in _bar_cache).
- _get_volume_fast returns 0.0 when the bar exists but volume is 0.
- Both skip the order by default (treat_missing_bar_as_suspended=True).
- Setting treat_missing_bar_as_suspended=False lets zero-volume bars through
  (fills at price with no volume impact) while still blocking missing bars
  when treat_missing_bar_as_suspended=True.
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


def _set_preloaded_with_bar(security, day, volume):
    """Install a bar with the given volume (may be 0)."""
    import pandas as pd
    from eqlib.data_cache import PreloadedData
    import eqlib.engine as eng
    from eqlib._state import get_session

    price = 10.0
    pre = PreloadedData()
    ts = pd.Timestamp(day)
    pre._bar_cache[security] = {
        ts: {"open": price, "high": price, "low": price, "close": price, "volume": volume},
    }
    pre._close_dict[security] = {ts: price}
    pre._field_series[security] = {
        "close": pd.Series([price], index=[ts]),
        "volume": pd.Series([float(volume)], index=[ts]),
    }
    pre._securities = [security]
    pre._dates = pd.DatetimeIndex([ts])
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    eng._preloaded = pre


def _set_preloaded_no_bar(security, day):
    """Install a PreloadedData with NO bar for the given security+day."""
    import pandas as pd
    from eqlib.data_cache import PreloadedData
    import eqlib.engine as eng
    from eqlib._state import get_session

    pre = PreloadedData()
    ts = pd.Timestamp(day)
    pre._bar_cache = {}  # empty — no bar for security
    pre._close_dict = {}
    pre._field_series = {}
    pre._securities = []
    pre._dates = pd.DatetimeIndex([ts])
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    eng._preloaded = pre


class TestHigh12Suspended:
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

    def test_missing_bar_skips_order_by_default(self, caplog):
        """No bar for security → order skipped (treat_missing_bar_as_suspended default True)."""
        from eqlib.trade import order
        import eqlib.engine as eng

        sess, portfolio, day = _make_session()
        _set_preloaded_no_bar("600519", day)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order("600519", 100)
            eng._fill_pending_orders(sess, day)

        assert "600519" not in portfolio.positions
        assert any(
            "no open price" in m.lower() or "no bar" in m.lower() or "suspended" in m.lower()
            for m in caplog.messages
        ), (
            "Expected a warning about no open price or suspension\n"
            f"Messages: {caplog.messages}"
        )

    def test_zero_volume_bar_skips_order_by_default(self, caplog):
        """Bar exists but volume=0 → order skipped by default."""
        from eqlib.trade import order
        import eqlib.engine as eng

        sess, portfolio, day = _make_session()
        _set_preloaded_with_bar("600519", day, volume=0)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order("600519", 100)
            eng._fill_pending_orders(sess, day)

        assert "600519" not in portfolio.positions

    def test_positive_volume_fills_order(self):
        """Normal bar with positive volume → order is filled."""
        from eqlib.trade import order
        import eqlib.engine as eng

        sess, portfolio, day = _make_session()
        _set_preloaded_with_bar("600519", day, volume=1_000_000)

        order("600519", 100)
        eng._fill_pending_orders(sess, day)

        assert "600519" in portfolio.positions
        assert portfolio.positions["600519"].amount == 100

    def test_treat_missing_bar_as_suspended_false_allows_zero_volume(self):
        """With treat_missing_bar_as_suspended=False, zero-volume bars are not suspended."""
        from eqlib.trade import order
        from eqlib._state import get_session
        import eqlib.engine as eng

        sess, portfolio, day = _make_session()
        sess._options["treat_missing_bar_as_suspended"] = False
        _set_preloaded_with_bar("600519", day, volume=0)

        order("600519", 100)
        eng._fill_pending_orders(sess, day)

        # With volume=0 and option=False, the order should be filled (no suspension)
        assert "600519" in portfolio.positions

    def test_missing_bar_still_skipped_when_option_false(self, caplog):
        """Even with treat_missing_bar_as_suspended=False, missing bar skips order."""
        from eqlib.trade import order
        from eqlib._state import get_session
        import eqlib.engine as eng

        sess, portfolio, day = _make_session()
        sess._options["treat_missing_bar_as_suspended"] = False
        _set_preloaded_no_bar("600519", day)

        with caplog.at_level(logging.WARNING, logger="eqlib"):
            order("600519", 100)
            eng._fill_pending_orders(sess, day)

        # No bar → no open price → order skipped before suspension check
        assert "600519" not in portfolio.positions

    def test_missing_bar_option_false_skips_and_warns(self):
        """option=False + missing bar: order must be skipped and a warning must be logged.

        vol is None always means 'no bar' and must unconditionally skip the order
        (regardless of treat_missing_bar_as_suspended).  This test patches the
        underlying Python logger directly to verify the warning is emitted even
        though eqlib's logger has propagate=False by default.
        """
        from unittest.mock import patch
        from eqlib.trade import order
        import eqlib.engine as eng
        import logging

        sess, portfolio, day = _make_session()
        sess._options["treat_missing_bar_as_suspended"] = False
        _set_preloaded_no_bar("600519", day)

        _eqlib_logger = logging.getLogger("eqlib")
        with patch.object(_eqlib_logger, "warning") as mock_warn:
            order("600519", 100)
            eng._fill_pending_orders(sess, day)

        # Order must be skipped regardless of the option
        assert "600519" not in portfolio.positions

        # A warning must have been emitted mentioning the security — either the
        # "no open price" guard (which fires first when the bar is absent) or
        # the "has no bar" suspension check.
        warning_calls = [str(call) for call in mock_warn.call_args_list]
        assert any(
            "600519" in c and ("no bar" in c or "no open price" in c)
            for c in warning_calls
        ), f"Expected a skip warning for 600519 (no bar / no open price), got: {warning_calls}"
