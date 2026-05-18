"""Tests for HIGH-11: buy cash check must cover worst-case slippage.

The engine's buy-order cash check previously computed the maximum affordable
shares using only _COMMISSION_BUFFER (1.001), ignoring slippage.  If a
FixedSlippage(pct=0.005) is configured the true cost is ~0.5% higher,
potentially causing the portfolio to exceed its available cash.

The fix uses base_price * (1 + slippage_max_pct + commission_rate) as the
denominator, giving a conservative upper-bound per share.
"""

from __future__ import annotations

import datetime
import math
import pytest


def _make_minimal_session_and_portfolio(cash: float):
    """Create a minimal BacktestSession + portfolio with the given cash."""
    from eqlib._state import BacktestSession, _set_session
    from eqlib.context import Context
    from eqlib.context import Portfolio

    sess = BacktestSession()
    _set_session(sess)

    day = datetime.date(2024, 1, 4)
    ctx = Context(day, day, "daily", cash)
    sess._context = ctx
    return sess, ctx.portfolio, day


def _make_preloaded_one_bar(security, day, open_px, volume):
    import pandas as pd
    from eqlib.data_cache import PreloadedData
    import eqlib.engine as eng

    pre = PreloadedData()
    ts = pd.Timestamp(day)
    pre._bar_cache[security] = {
        ts: {"open": open_px, "high": open_px, "low": open_px,
             "close": open_px, "volume": volume},
    }
    pre._close_dict[security] = {ts: open_px}
    pre._field_series[security] = {
        "close": pd.Series([open_px], index=[ts]),
        "volume": pd.Series([float(volume)], index=[ts]),
    }
    pre._securities = [security]
    pre._dates = pd.DatetimeIndex([ts])

    from eqlib._state import get_session
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    eng._preloaded = pre
    return pre


class TestHigh11CashBuffer:
    def setup_method(self):
        from eqlib._state import BacktestSession, _set_session
        from eqlib.context import Context
        import eqlib.engine as eng
        _set_session(BacktestSession())
        eng._preloaded = eng._preloaded_fallback

    def teardown_method(self):
        from eqlib._state import _clear_session
        import eqlib.engine as eng
        _clear_session()
        eng._preloaded = eng._preloaded_fallback

    def test_no_slippage_cash_never_goes_negative(self):
        """Without slippage, buying at the cash boundary must not overdraft."""
        from eqlib.trade import order
        from eqlib._state import get_session
        import eqlib.engine as eng

        cash = 10_000.0
        price = 10.0
        day = datetime.date(2024, 1, 4)

        sess, portfolio, day = _make_minimal_session_and_portfolio(cash)
        _make_preloaded_one_bar("600519", day, price, 1_000_000)

        order("600519", 1000)  # Request 1000 shares = 10,000 cash (tight)
        eng._fill_pending_orders(sess, day)

        assert portfolio.available_cash >= 0, (
            f"Portfolio went negative: {portfolio.available_cash:.2f}"
        )

    def test_fixed_slippage_cash_never_goes_negative(self):
        """With FixedSlippage(0.005), affordable shares must account for slippage."""
        from eqlib.trade import order
        from eqlib._state import get_session
        from eqlib.slippage import FixedSlippage
        import eqlib.engine as eng

        cash = 10_000.0
        price = 10.0
        day = datetime.date(2024, 1, 4)

        sess, portfolio, day = _make_minimal_session_and_portfolio(cash)
        sess._slippage_model = FixedSlippage(pct=0.005)
        _make_preloaded_one_bar("600519", day, price, 1_000_000)

        order("600519", 1000)  # Try to buy 1000 shares
        eng._fill_pending_orders(sess, day)

        assert portfolio.available_cash >= 0, (
            f"Portfolio went negative with slippage: {portfolio.available_cash:.2f}"
        )

    def test_slippage_model_max_pct_used_when_available(self):
        """Engine uses slippage_model.max_pct instead of fallback when present."""
        from eqlib.trade import order
        from eqlib.slippage import FixedSlippage
        import eqlib.engine as eng

        # Use a very large slippage so the engine should buy fewer shares
        cash = 10_000.0
        price = 10.0
        day = datetime.date(2024, 1, 4)

        sess, portfolio, day = _make_minimal_session_and_portfolio(cash)
        sess._slippage_model = FixedSlippage(pct=0.02)  # 2% slippage
        _make_preloaded_one_bar("600519", day, price, 1_000_000)

        order("600519", 1000)
        eng._fill_pending_orders(sess, day)

        assert portfolio.available_cash >= 0
        # Should have bought fewer than 1000 shares due to large slippage
        pos = portfolio.positions.get("600519")
        if pos is not None:
            # 1000 shares at 10.0 × 1.02 = 10,200 > 10,000, so must be < 1000
            assert pos.amount < 1000, (
                f"Expected fewer than 1000 shares with 2% slippage, got {pos.amount}"
            )
