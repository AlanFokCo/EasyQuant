"""Regression tests for the 2026-10-12 audit-confirmed engine-semantics fixes.

Covers:
- TOP-1   : price-limit checking is ON by default in backtests
            (buy at limit-up / sell at limit-down are rejected).
- TOP-10  : the limit-ratio table is date- and ST-aware (ChiNext reform
            boundary 2020-08-24; main-board ST 5% via a PIT map channel).
- TOP-5   : suspension semantics are uniform (same-day cancel with reason),
            and delisted positions are force-liquidated instead of silently
            truncating the backtest / haunting the book.
- TOP-2   : paper trading session gating (no matching outside 09:15-15:00;
            first fill after the 09:25 call auction) and empty-quote polls
            keep orders pending instead of cancelling them.
- TOP-8   : paper user-callback circuit breaker (no process kill, no
            exception-triggered re-run).
- GAP-4   : Order.cancel_reason is retained for CANCELLED / EXPIRED.
"""

import datetime

import pandas as pd
import pytest

from eqlib import engine
from eqlib._state import BacktestSession, _set_session, _clear_session
from eqlib.constants import (
    CHINEXT_PRICE_LIMIT_REFORM_DATE,
    DEFAULT_DELIST_GAP_DAYS,
    PAPER_CALLBACK_MAX_FAILURES,
)
from eqlib.context import Context, Position
from eqlib.objects import Order
from eqlib import trade


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_preloaded(bars: dict):
    """Build a minimal PreloadedData from {security: {date: bar_dict}}."""
    from eqlib.data_cache import PreloadedData

    pd_frames = {}
    for sec, day_bars in bars.items():
        rows = []
        for d, bar in sorted(day_bars.items()):
            rows.append({**bar, "date": pd.Timestamp(d)})
        df = pd.DataFrame(rows).set_index("date")
        pd_frames[sec] = df

    pre = PreloadedData()
    if pd_frames:
        pre.panel = pd.concat(pd_frames, axis=1)
        pre._securities = sorted(pd_frames.keys())
        pre._dates = pre.panel.index
        for sec, df in pd_frames.items():
            if "close" in df.columns:
                pre._close_dict[sec] = dict(zip(df.index, df["close"]))
            fields = ["open", "high", "low", "close", "volume"]
            pre._bar_cache[sec] = df.reindex(
                columns=fields, fill_value=0).to_dict("index")
            pre._field_series[sec] = {f: df[f] for f in df.columns if f in df}
    return pre


def _make_session(pre, day, cash: float = 1_000_000.0) -> BacktestSession:
    sess = BacktestSession()
    _set_session(sess)
    ctx = Context(day, day, "daily", cash)
    ctx.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))
    sess._context = ctx
    object.__setattr__(sess, "_preloaded", pre)
    return sess


def _flat_bar(price: float, volume: float = 100_000) -> dict:
    return {"open": price, "high": price, "low": price,
            "close": price, "volume": volume}


def _add_position(sess, security, amount, avg_cost):
    pos = Position(security)
    pos.amount = pos.closeable_amount = amount
    pos.avg_cost = avg_cost
    pos.update(avg_cost)
    sess._context.portfolio.positions[security] = pos
    return pos


@pytest.fixture(autouse=True)
def _clean_session():
    yield
    _clear_session()


# ── TOP-1: price-limit enforcement is the default ───────────────────────────

class TestPriceLimitDefaultOn:
    """check_price_limit defaults to True in backtests (QUANT-P0-01)."""

    def test_buy_at_limit_up_rejected_by_default(self):
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "000001"
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.0),
            fill_day: _flat_bar(11.0),  # exactly +10% limit-up open
        }})
        sess = _make_session(pre, fill_day)

        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, fill_day)

        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-up"
        assert sess._trade_log == []

    def test_sell_at_limit_down_rejected_by_default(self):
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "600519"
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.0),
            fill_day: _flat_bar(9.0),  # exactly -10% limit-down open
        }})
        sess = _make_session(pre, fill_day)
        _add_position(sess, sec, 200, 10.0)

        obj = trade.order(sec, -100)
        engine._fill_pending_orders(sess, fill_day)

        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-down"
        assert sess._context.portfolio.positions[sec].amount == 200

    def test_buy_just_below_limit_up_fills_by_default(self):
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "000001"
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.0),
            fill_day: _flat_bar(10.5),  # +5%, comfortably inside
        }})
        sess = _make_session(pre, fill_day)

        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, fill_day)

        assert obj.status == Order.STATUS_FILLED

    def test_limit_price_rounded_to_fen(self):
        """Exchange rule: limit = round(prev_close * (1 +- ratio), 2)."""
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "000001"
        # 10.03 * 1.10 = 11.033 -> fen-rounded limit-up is 11.03.
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.03),
            fill_day: _flat_bar(11.03),
        }})
        sess = _make_session(pre, fill_day)
        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, fill_day)
        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-up"

    def test_explicit_disable_still_available(self):
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "000001"
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.0),
            fill_day: _flat_bar(11.0),
        }})
        sess = _make_session(pre, fill_day)
        sess._options["check_price_limit"] = False

        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, fill_day)

        assert obj.status == Order.STATUS_FILLED

    def test_prev_close_skips_suspension_gap(self):
        """Limit is computed off the last genuinely traded close."""
        sec = "601398"
        pre = _make_preloaded({sec: {
            datetime.date(2024, 1, 2): _flat_bar(10.0),
            # 2024-01-03 .. 2024-01-04: no bars (suspended)
            datetime.date(2024, 1, 5): _flat_bar(11.0),  # +10% vs 10.0
        }})
        sess = _make_session(pre, datetime.date(2024, 1, 5))
        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, datetime.date(2024, 1, 5))
        # Resume day opens at limit vs the last traded close (10.0) -> reject
        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-up"


# ── TOP-10: date- and ST-aware limit ratios ─────────────────────────────────

class TestPriceLimitRatioTable:
    def test_chinext_before_reform_is_10pct(self):
        ratio = engine._get_price_limit_ratio(
            "300750.XSHE",
            context_dt=CHINEXT_PRICE_LIMIT_REFORM_DATE - datetime.timedelta(days=1),
        )
        assert ratio == 0.10

    def test_chinext_on_reform_date_is_20pct(self):
        ratio = engine._get_price_limit_ratio(
            "300750.XSHE", context_dt=CHINEXT_PRICE_LIMIT_REFORM_DATE)
        assert ratio == 0.20

    def test_chinext_no_date_uses_current_rules(self):
        assert engine._get_price_limit_ratio("300750.XSHE") == 0.20

    def test_star_market_always_20pct(self):
        assert engine._get_price_limit_ratio(
            "688981.XSHG", context_dt=datetime.date(2019, 8, 1)) == 0.20

    def test_bse_30pct(self):
        assert engine._get_price_limit_ratio("830799") == 0.30
        assert engine._get_price_limit_ratio("920001") == 0.30

    def test_st_map_static_bool_gives_5pct(self):
        sess = BacktestSession()
        sess._options["st_status_map"] = {"601398": True}
        assert engine._get_price_limit_ratio(
            "601398.XSHG", context_dt=datetime.date(2024, 1, 2),
            session=sess) == 0.05

    def test_st_map_interval_is_point_in_time(self):
        sess = BacktestSession()
        sess._options["st_status_map"] = {
            "601398": [(datetime.date(2020, 3, 1), datetime.date(2021, 5, 1))],
        }
        assert engine._get_price_limit_ratio(
            "601398.XSHG", context_dt=datetime.date(2020, 6, 1),
            session=sess) == 0.05
        sess2 = BacktestSession()
        sess2._options["st_status_map"] = {
            "601398": [(datetime.date(2020, 3, 1), datetime.date(2021, 5, 1))],
        }
        assert engine._get_price_limit_ratio(
            "601398.XSHG", context_dt=datetime.date(2022, 6, 1),
            session=sess2) == 0.10

    def test_st_map_callable(self):
        sess = BacktestSession()
        sess._options["st_status_map"] = {
            "601398": lambda code, day: day.year == 2021,
        }
        assert engine._get_price_limit_ratio(
            "601398", context_dt=datetime.date(2021, 1, 4), session=sess) == 0.05

    def test_st_does_not_apply_to_chinext(self):
        """ChiNext ST stocks keep the board-wide limit (SZSE rules)."""
        sess = BacktestSession()
        sess._options["st_status_map"] = {"300750": True}
        assert engine._get_price_limit_ratio(
            "300750.XSHE", context_dt=datetime.date(2024, 1, 2),
            session=sess) == 0.20

    def test_st_fill_level_blocks_buy_above_5pct(self):
        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)
        sec = "601398"
        pre = _make_preloaded({sec: {
            prev_day: _flat_bar(10.0),
            fill_day: _flat_bar(10.6),  # +6%: fine for 10%, not for ST 5%
        }})
        sess = _make_session(pre, fill_day)
        sess._options["st_status_map"] = {sec: True}

        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, fill_day)

        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-up"

    def test_chinext_prereform_fill_level(self):
        """300xxx pre-reform (Aug 2020): +15% open is above the 10% limit."""
        sec = "300750"
        pre = _make_preloaded({sec: {
            datetime.date(2020, 8, 20): _flat_bar(10.0),
            datetime.date(2020, 8, 21): _flat_bar(11.5),  # +15%
        }})
        sess = _make_session(pre, datetime.date(2020, 8, 21))
        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, datetime.date(2020, 8, 21))
        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "limit-up"

    def test_chinext_postreform_fill_level(self):
        """300xxx post-reform (Jan 2021): +15% open fills; +20% rejected."""
        sec = "300750"
        pre = _make_preloaded({sec: {
            datetime.date(2020, 12, 31): _flat_bar(10.0),
            datetime.date(2021, 1, 4): _flat_bar(11.5),   # +15% < 20% limit
        }})
        sess = _make_session(pre, datetime.date(2021, 1, 4))
        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, datetime.date(2021, 1, 4))
        assert obj.status == Order.STATUS_FILLED

        _clear_session()
        pre2 = _make_preloaded({sec: {
            datetime.date(2020, 12, 31): _flat_bar(10.0),
            datetime.date(2021, 1, 4): _flat_bar(12.0),   # +20% = limit-up
        }})
        sess2 = _make_session(pre2, datetime.date(2021, 1, 4))
        obj2 = trade.order(sec, 100)
        engine._fill_pending_orders(sess2, datetime.date(2021, 1, 4))
        assert obj2.status == Order.STATUS_CANCELLED
        assert obj2.cancel_reason == "limit-up"


# ── TOP-5: suspension uniformity & delisting ────────────────────────────────

class TestSuspensionUniformity:
    """Same suspension -> same outcome regardless of universe composition."""

    def test_missing_bar_day_cancels_same_day_not_deferred(self):
        sec = "601398"
        suspended_day = datetime.date(2024, 1, 4)
        pre = _make_preloaded({sec: {
            datetime.date(2024, 1, 3): _flat_bar(10.0),
            # 2024-01-04 missing (suspended)
            datetime.date(2024, 1, 5): _flat_bar(10.1),
        }})
        sess = _make_session(pre, suspended_day)

        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, suspended_day)

        assert obj.status == Order.STATUS_CANCELLED
        # A missing bar surfaces at price resolution first.
        assert obj.cancel_reason == "no price data"
        assert not sess._pending_orders, "suspended-day order must not defer"

    def test_calendar_contains_suspension_day(self):
        """The exchange calendar keeps the suspended day (single-stock data)."""
        sec = "601398"
        pre = _make_preloaded({sec: {
            datetime.date(2024, 1, 3): _flat_bar(10.0),
            datetime.date(2024, 1, 5): _flat_bar(10.1),
        }})
        days = engine._get_trading_days(
            datetime.date(2024, 1, 2), datetime.date(2024, 1, 8),
            preloaded=pre)
        assert datetime.date(2024, 1, 4) in days

    def test_zero_volume_bar_cancels_same_day(self):
        sec = "601398"
        day = datetime.date(2024, 1, 4)
        pre = _make_preloaded({sec: {day: _flat_bar(10.0, volume=0)}})
        sess = _make_session(pre, day)
        obj = trade.order(sec, 100)
        engine._fill_pending_orders(sess, day)
        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "suspended"


class TestDelisting:
    """Delisted positions are force-liquidated; the run is not truncated."""

    def _setup_delist(self):
        sec = "601398"
        bars = {sec: {}}
        d = datetime.date(2024, 1, 2)
        while d <= datetime.date(2024, 1, 10):
            if d.weekday() < 5:
                bars[sec][d] = _flat_bar(10.0)
            d += datetime.timedelta(days=1)
        pre = _make_preloaded(bars)
        # Exchange calendar extends far beyond the data end (2024-01-10).
        trading_days = engine._get_trading_days(
            datetime.date(2024, 1, 2), datetime.date(2024, 3, 29))
        assert trading_days[-1] > datetime.date(2024, 1, 10)
        day_pos = {day: i for i, day in enumerate(trading_days)}
        return sec, pre, trading_days, day_pos

    def test_calendar_not_truncated_by_delisted_data(self):
        sec, pre, trading_days, _ = self._setup_delist()
        assert datetime.date(2024, 1, 31) in trading_days
        assert datetime.date(2024, 2, 29) in trading_days

    def test_force_liquidation_after_gap(self):
        sec, pre, trading_days, day_pos = self._setup_delist()
        last_idx = day_pos[datetime.date(2024, 1, 10)]
        liq_day = trading_days[last_idx + DEFAULT_DELIST_GAP_DAYS + 1]
        sess = _make_session(pre, liq_day)
        _add_position(sess, sec, 1000, 10.0)
        cash_before = sess._context.portfolio.available_cash

        engine._handle_delisted_positions(sess, liq_day, day_pos, trading_days)

        portfolio = sess._context.portfolio
        assert sec not in portfolio.positions
        # 1000 @ 10.0 -> proceeds 10000, commission = 5 (min) + 5 (stamp) = 10
        assert portfolio.available_cash == pytest.approx(cash_before + 9990.0)
        entry = sess._trade_log[-1]
        assert entry["type"] == "DELIST_LIQUIDATE"
        assert entry["security"] == sec
        assert entry["amount"] == 1000

    def test_no_liquidation_before_gap(self):
        sec, pre, trading_days, day_pos = self._setup_delist()
        last_idx = day_pos[datetime.date(2024, 1, 10)]
        day = trading_days[last_idx + DEFAULT_DELIST_GAP_DAYS]  # exactly at gap
        sess = _make_session(pre, day)
        _add_position(sess, sec, 1000, 10.0)

        engine._handle_delisted_positions(sess, day, day_pos, trading_days)

        assert sec in sess._context.portfolio.positions
        assert not sess._trade_log

    def test_keep_mode_preserves_position(self):
        sec, pre, trading_days, day_pos = self._setup_delist()
        last_idx = day_pos[datetime.date(2024, 1, 10)]
        day = trading_days[last_idx + DEFAULT_DELIST_GAP_DAYS + 5]
        sess = _make_session(pre, day)
        sess._options["delisted_position_handling"] = "keep"
        _add_position(sess, sec, 1000, 10.0)

        engine._handle_delisted_positions(sess, day, day_pos, trading_days)

        assert sec in sess._context.portfolio.positions

    def test_liquidation_cancels_pending_orders(self):
        sec, pre, trading_days, day_pos = self._setup_delist()
        last_idx = day_pos[datetime.date(2024, 1, 10)]
        liq_day = trading_days[last_idx + DEFAULT_DELIST_GAP_DAYS + 1]
        sess = _make_session(pre, liq_day)
        _add_position(sess, sec, 1000, 10.0)

        obj = trade.order(sec, -100)
        engine._handle_delisted_positions(sess, liq_day, day_pos, trading_days)

        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "delisted"
        assert not sess._pending_orders


# ── TOP-2: paper session gating & empty-quote handling ──────────────────────

class TestPaperMarketPhase:
    @pytest.mark.parametrize("hour,minute,expected", [
        (0, 30, "closed"),
        (9, 14, "closed"),
        (9, 15, "auction"),
        (9, 24, "auction"),
        (9, 25, "continuous"),
        (11, 30, "continuous"),
        (14, 59, "continuous"),
        (15, 0, "after"),
        (23, 30, "after"),
    ])
    def test_phase_boundaries(self, hour, minute, expected):
        now = datetime.datetime(2024, 1, 4, hour, minute)
        assert engine._paper_market_phase(now) == expected


class TestPaperNoPriceKeepsPending:
    """Empty/stale quote polls must not cancel orders (INFRA-P0-01)."""

    def test_empty_exec_prices_keeps_order_pending(self):
        day = datetime.date(2024, 1, 4)
        sess = _make_session(_make_preloaded({}), day)
        sess._options["_is_paper_trading"] = True

        obj = trade.order("601398", 100)
        engine._fill_pending_orders(sess, day, exec_prices={})

        assert obj.status == Order.STATUS_PENDING
        assert len(sess._pending_orders) == 1

    def test_partial_exec_prices_keeps_missing_security_pending(self):
        day = datetime.date(2024, 1, 4)
        sess = _make_session(_make_preloaded({}), day)
        sess._options["_is_paper_trading"] = True

        obj = trade.order("601398", 100)
        engine._fill_pending_orders(sess, day,
                                    exec_prices={"600519": 1700.0})

        assert obj.status == Order.STATUS_PENDING
        assert len(sess._pending_orders) == 1

    def test_order_value_without_price_keeps_pending(self):
        day = datetime.date(2024, 1, 4)
        sess = _make_session(_make_preloaded({}), day)
        sess._options["_is_paper_trading"] = True

        obj = trade.order_value("601398", 10_000)
        engine._fill_pending_orders(sess, day, exec_prices={})

        assert obj.status == Order.STATUS_PENDING
        assert len(sess._pending_orders) == 1

    def test_backtest_still_cancels_on_no_price(self):
        """In backtests (exec_prices=None) no data remains a cancellation."""
        day = datetime.date(2024, 1, 4)
        sess = _make_session(_make_preloaded({}), day)

        obj = trade.order("601398", 100)
        engine._fill_pending_orders(sess, day)

        assert obj.status == Order.STATUS_CANCELLED
        assert obj.cancel_reason == "no price data"


# ── TOP-8: paper callback circuit breaker ───────────────────────────────────

class TestPaperCallbackCircuitBreaker:
    def test_failing_callback_is_contained_then_disabled(self):
        sess = BacktestSession()
        calls = {"n": 0}

        def boom(context):
            calls["n"] += 1
            raise RuntimeError("user bug")

        for _ in range(PAPER_CALLBACK_MAX_FAILURES):
            assert engine._paper_run_callback(sess, boom, None,
                                              label="scheduled") is False
        assert calls["n"] == PAPER_CALLBACK_MAX_FAILURES

        # Disabled: subsequent calls do not invoke the function at all.
        assert engine._paper_run_callback(sess, boom, None,
                                          label="scheduled") is False
        assert calls["n"] == PAPER_CALLBACK_MAX_FAILURES

    def test_success_resets_failure_count(self):
        sess = BacktestSession()
        state = {"fail": True}
        calls = {"n": 0}

        def flaky(context):
            calls["n"] += 1
            if state["fail"]:
                raise RuntimeError("boom")

        assert engine._paper_run_callback(sess, flaky, None) is False
        state["fail"] = False
        assert engine._paper_run_callback(sess, flaky, None) is True
        # Fail again: counter restarted, so one failure must not disable.
        state["fail"] = True
        assert engine._paper_run_callback(sess, flaky, None) is False
        assert engine._paper_run_callback(sess, flaky, None) is False
        assert calls["n"] == 4  # still not disabled (< MAX consecutive)

    def test_user_exception_is_never_raised_to_caller(self):
        sess = BacktestSession()

        def boom(context):
            raise ValueError("must not kill the process")

        # If this raised, the test would fail — the breaker must contain it.
        engine._paper_run_callback(sess, boom, None, label="handle_data")


# ── GAP-4: cancel_reason retained on the Order object ───────────────────────

class TestOrderCancelReason:
    def test_cancelled_keeps_reason(self):
        order = Order("000001.XSHE", 100, side="buy")
        order.transition_to(Order.STATUS_CANCELLED, reason="suspended")
        assert order.cancel_reason == "suspended"
        assert order.reject_reason is None  # unchanged legacy behaviour

    def test_expired_keeps_reason(self):
        order = Order("000001.XSHE", 100, side="buy")
        order.transition_to(Order.STATUS_EXPIRED, reason="timeout")
        assert order.cancel_reason == "timeout"

    def test_rejected_still_uses_reject_reason(self):
        order = Order("000001.XSHE", 100, side="buy")
        order.transition_to(Order.STATUS_SUBMITTED)
        order.transition_to(Order.STATUS_REJECTED, reason="broker reject")
        assert order.reject_reason == "broker reject"
        assert order.cancel_reason is None

    def test_filled_has_no_reasons(self):
        order = Order("000001.XSHE", 100, side="buy")
        order.transition_to(Order.STATUS_SUBMITTED)
        order.add_partial_fill(100, 10.0)
        order.transition_to(Order.STATUS_FILLED)
        assert order.cancel_reason is None
        assert order.reject_reason is None


# ── TOP-2 (loop level): session gate wiring in the real paper loop ──────────

class TestPaperSessionGatedLoop:
    """run_paper_trade must idle completely outside the session window."""

    def test_off_session_never_fills_fetches_or_runs_callbacks(self, monkeypatch):
        import eqlib

        monkeypatch.setattr(engine, "_paper_is_trading_day", lambda day: True)
        monkeypatch.setattr(engine, "_paper_market_phase", lambda now: "closed")

        calls = {"fill": 0, "fetch": 0, "cb": 0}
        monkeypatch.setattr(
            engine, "_fill_pending_orders",
            lambda *a, **k: calls.__setitem__("fill", calls["fill"] + 1))
        monkeypatch.setattr(
            engine, "_fetch_live_prices",
            lambda *a, **k: calls.__setitem__("fetch", calls["fetch"] + 1))

        class _StopLoop(Exception):
            pass

        sleeps = {"n": 0}

        def fake_sleep(seconds):
            sleeps["n"] += 1
            if sleeps["n"] >= 3:
                raise _StopLoop

        monkeypatch.setattr(engine.time, "sleep", fake_sleep)

        def initialize(context):
            def cb(ctx):
                calls["cb"] += 1
            eqlib.run_daily(cb, time="every_bar")

        with pytest.raises(_StopLoop):
            engine.run_paper_trade(initialize, interval=1)

        assert calls == {"fill": 0, "fetch": 0, "cb": 0}
        assert sleeps["n"] == 3  # the loop idled instead of trading

    def test_after_close_hooks_fire_once_after_session_day(self, monkeypatch):
        """continuous -> after: hooks fire exactly once, then the loop idles."""
        import eqlib

        monkeypatch.setattr(engine, "_paper_is_trading_day", lambda day: True)
        phases = iter(["continuous", "continuous", "after", "after", "after"])
        monkeypatch.setattr(
            engine, "_paper_market_phase", lambda now: next(phases, "after"))
        monkeypatch.setattr(engine, "_fetch_live_prices", lambda *a, **k: {})
        monkeypatch.setattr(engine, "_resolve_live_price",
                            lambda cache, sec, default: 10.0)

        hooks = {"n": 0}

        class _StopLoop(Exception):
            pass

        sleeps = {"n": 0}

        def fake_sleep(seconds):
            sleeps["n"] += 1
            if sleeps["n"] >= 5:
                raise _StopLoop

        monkeypatch.setattr(engine.time, "sleep", fake_sleep)

        def initialize(context):
            def hook(context, data):
                hooks["n"] += 1
            from eqlib import _state as _st
            _st.get_session()._after_trading_end_funcs.append(hook)

        with pytest.raises(_StopLoop):
            engine.run_paper_trade(initialize, interval=1)

        assert hooks["n"] == 1, f"after-close hooks must fire once, got {hooks['n']}"


# ── Paper loop: current_dt must be restored after the 09:30 hook block ──────


class _ScriptedDatetime(datetime.datetime):
    """datetime stand-in whose now() follows the test's scripted clock."""

    script: list = []
    idx: int = 0

    @classmethod
    def now(cls, tz=None):
        return cls.script[min(cls.idx, len(cls.script) - 1)]


class _DatetimeModuleShim:
    """Stand-in for the stdlib datetime module inside engine.py only."""

    date = datetime.date
    time = datetime.time
    timedelta = datetime.timedelta
    datetime = _ScriptedDatetime


class TestPaperClockRollover:
    """Day-rollover sets current_dt to 09:30 for the open hooks; it must be
    restored before the ±60s scheduled-time match runs."""

    def test_scheduled_match_uses_real_clock_on_day_rollover(self, monkeypatch):
        import eqlib

        day1 = datetime.date(2024, 1, 2)
        day2 = datetime.date(2024, 1, 3)
        _ScriptedDatetime.script = [
            # setup now() + iteration 1: warmup day (day rollover is a no-op)
            datetime.datetime.combine(day1, datetime.time(9, 31, 30)),
            # iteration 2: first in-market iteration of day2 is at 10:00
            datetime.datetime.combine(day2, datetime.time(10, 0, 0)),
            # iteration 3: settle
            datetime.datetime.combine(day2, datetime.time(10, 0, 30)),
        ]
        _ScriptedDatetime.idx = 0
        monkeypatch.setattr(engine, "datetime", _DatetimeModuleShim)
        monkeypatch.setattr(engine, "_paper_is_trading_day", lambda day: True)
        monkeypatch.setattr(engine, "_paper_market_phase", lambda now: "continuous")
        monkeypatch.setattr(engine, "_fetch_live_prices", lambda *a, **k: {})
        monkeypatch.setattr(engine, "_resolve_live_price",
                            lambda cache, sec, default: 10.0)

        hook_stamps: list = []
        morning_calls: list = []
        ten_calls: list = []

        class _StopLoop(Exception):
            pass

        def fake_sleep(seconds):
            _ScriptedDatetime.idx += 1
            if _ScriptedDatetime.idx >= 3:
                raise _StopLoop

        monkeypatch.setattr(engine.time, "sleep", fake_sleep)

        def initialize(context):
            def hook(context, data):
                hook_stamps.append(context.current_dt)
            eqlib.before_trading_start(hook)

            def morning(ctx):
                morning_calls.append(ctx.current_dt)
            eqlib.run_daily(morning, time="09:30")

            def ten(ctx):
                ten_calls.append((ctx.current_dt, _ScriptedDatetime.idx))
            eqlib.run_daily(ten, time="10:00")

        with pytest.raises(_StopLoop):
            engine.run_paper_trade(initialize, interval=1)

        # The open hook still sees the canonical 09:30 timestamp ...
        assert hook_stamps == [
            datetime.datetime.combine(day2, datetime.time(9, 30))
        ]
        # ... but the ±60s scheduled-time match must use the real clock: a
        # 09:30 schedule must NOT fire when the day's first in-market
        # iteration is actually 10:00.
        assert morning_calls == []
        # Conversely the 10:00 schedule fires on that same rollover iteration
        # (script index 1), not one poll later.
        assert [idx for _, idx in ten_calls] == [1]


# ── FIXGAP-5: auction-phase day rollover must not invert callback order ──────


class TestPaperAuctionHookOrdering:
    """When the loop first wakes during the open call auction (09:15-09:25),
    the day's before_trading_start hooks must still run before any
    handle_data of that day (matching backtest ordering), while order
    matching waits for the continuous phase (09:25+)."""

    def test_hooks_precede_handle_data_and_fill_waits_for_continuous(
        self, monkeypatch
    ):
        import eqlib

        day1 = datetime.date(2024, 1, 2)
        day2 = datetime.date(2024, 1, 3)
        _ScriptedDatetime.script = [
            # iteration 0: warmup day, continuous phase
            datetime.datetime.combine(day1, datetime.time(9, 31)),
            # iteration 1: day2 rolls over during the call auction
            datetime.datetime.combine(day2, datetime.time(9, 20)),
            # iteration 2: continuous trading begins
            datetime.datetime.combine(day2, datetime.time(9, 26)),
            # iteration 3: settle (loop stops after this sleep)
            datetime.datetime.combine(day2, datetime.time(9, 27)),
        ]
        _ScriptedDatetime.idx = 0
        monkeypatch.setattr(engine, "datetime", _DatetimeModuleShim)
        monkeypatch.setattr(engine, "_paper_is_trading_day", lambda day: True)
        # Real phase classification against the scripted clock:
        # 09:20 -> auction, 09:26/09:27 -> continuous.
        monkeypatch.setattr(engine, "_fetch_live_prices", lambda *a, **k: {})
        monkeypatch.setattr(engine, "_resolve_live_price",
                            lambda cache, sec, default: 10.0)

        events: list = []
        fills: list = []
        unlocks: list = []
        monkeypatch.setattr(
            engine, "_fill_pending_orders",
            lambda sess, day, **k: fills.append((day, _ScriptedDatetime.idx)))
        monkeypatch.setattr(
            engine, "_t1_unlock",
            lambda sess: unlocks.append(_ScriptedDatetime.idx))

        class _StopLoop(Exception):
            pass

        def fake_sleep(seconds):
            _ScriptedDatetime.idx += 1
            if _ScriptedDatetime.idx >= 3:
                raise _StopLoop

        monkeypatch.setattr(engine.time, "sleep", fake_sleep)

        def initialize(context):
            def hook(context, data):
                events.append(("hook", _ScriptedDatetime.idx,
                               context.current_dt.time()))
            eqlib.before_trading_start(hook)

            def hd(context, data):
                events.append(("handle_data", _ScriptedDatetime.idx, None))
            engine.set_handle_data(hd)

        with pytest.raises(_StopLoop):
            engine.run_paper_trade(initialize, interval=1)

        # Iteration 0 is the process-start warmup day (no hooks by design).
        # From the auction rollover iteration (idx 1) on, the day's hook must
        # precede every handle_data of day2.
        day2_events = [e for e in events if e[1] >= 1]
        assert day2_events[0][0] == "hook", (
            f"before_trading_start must precede day2's first handle_data, "
            f"got order: {events}"
        )
        hooks = [e for e in day2_events if e[0] == "hook"]
        assert [(idx, t) for _, idx, t in hooks] == [
            (1, datetime.time(9, 30))
        ]
        # handle_data runs during the auction phase too (callbacks are not
        # gated), but only after the hook.
        assert ("handle_data", 1, None) in day2_events
        # No matching during the auction: the day's first fill (and the T+1
        # unlock) happen on the first continuous iteration instead.
        assert fills == [(day2, 2)]
        assert unlocks == [2]
