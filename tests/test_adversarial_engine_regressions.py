"""Executable acceptance cases for audit F01/F02/F05/F06/F11–F14."""
import datetime as dt

import pytest

import eqlib._state as st
from eqlib import engine, trade
from eqlib.context import Context, Position, Portfolio
from eqlib.objects import LimitOrder
from eqlib.slippage import FixedSlippage, VolumeSlippage

DAY = dt.date(2024, 1, 3)
SEC = "601390.XSHG"


@pytest.fixture
def session(monkeypatch):
    sess = st.BacktestSession()
    sess._context = Context(DAY, DAY + dt.timedelta(days=10), starting_cash=1_000_000)
    sess._options["check_price_limit"] = False
    monkeypatch.setattr(st, "get_session", lambda: sess)
    monkeypatch.setattr(engine, "_get_open_fast", lambda *a: 10.0)
    monkeypatch.setattr(engine, "_get_volume_fast", lambda *a: 10_000)
    monkeypatch.setattr(engine, "_get_preloaded", lambda: None)
    return sess


def position(sess, key=SEC, amount=2000):
    p = Position(key)
    p.amount = p.closeable_amount = amount
    p.avg_cost = 10.0
    p.update(10.0)
    sess._context.portfolio.positions[key] = p
    return p


def test_paper_timestamp_and_cross_day_fill(session):
    session._options["_is_paper_trading"] = True
    obj = trade.order_value(SEC, 1000)
    assert isinstance(session._order_timestamps[obj.order_id], dt.datetime)
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1), exec_prices={"601390": 10})
    assert obj.status == "filled"
    assert obj.filled_amount == 100
    assert not session._pending_orders
    assert obj.order_id not in session._order_timestamps


def test_exception_preserves_current_and_unprocessed_orders(session, monkeypatch):
    a = trade.order(SEC, 100)
    b = trade.order("000001", 100)
    class Broken:
        def get_execution_price(self, *a, **kw):
            raise RuntimeError("failed pricing")
    session._slippage_model = Broken()
    with pytest.raises(RuntimeError, match="failed pricing"):
        engine._fill_pending_orders(session, DAY)
    assert [r["order_obj"] for r in session._pending_orders] == [a, b]
    assert not session._trade_log
    session._slippage_model = None
    engine._fill_pending_orders(session, DAY)
    assert a.is_complete() and b.is_complete()
    assert len(session._trade_log) == 2


@pytest.mark.parametrize("price", [None, float("nan"), 0.0])
def test_stale_quote_preserves_last_mark_and_recovers(price):
    pf = Portfolio(1000)
    p = Position(SEC)
    p.amount, p.avg_cost = 100, 10
    pf.positions[SEC] = p
    pf._sync_total_value({SEC: 20})
    assert pf.total_value == 3000
    for _ in range(3):
        pf._sync_total_value({SEC: price})
        assert pf.total_value == 3000 and p.price_stale
    pf._sync_total_value({SEC: 15})
    assert pf.total_value == 2500 and not p.price_stale


@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("slippage", [FixedSlippage(0.01), VolumeSlippage()])
def test_limit_applies_to_final_price(session, side, slippage):
    position(session)
    session._slippage_model = slippage
    obj = trade.order(SEC, side * 100, style=LimitOrder(10))
    engine._fill_pending_orders(session, DAY)
    assert obj.filled_amount == 0
    assert len(session._pending_orders) == 1
    session._slippage_model = None
    engine._fill_pending_orders(session, DAY)
    assert obj.is_complete() and obj.avg_cost == 10


def test_daily_volume_shared_across_orders_calls_aliases_and_sides(session):
    position(session, amount=5000)
    orders = [trade.order("601390", 1000) for _ in range(11)]
    engine._fill_pending_orders(session, DAY)
    assert sum(o.filled_amount for o in orders) == 1000
    engine._fill_pending_orders(session, DAY)
    assert sum(o.filled_amount for o in orders) == 1000
    for obj in orders:
        trade.cancel_order(obj)
    sell = trade.order(SEC, -1000)
    engine._fill_pending_orders(session, DAY)
    assert sell.filled_amount == 0
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert sell.filled_amount == 1000


@pytest.mark.parametrize("legacy", [False, True])
def test_bare_and_suffixed_apis_close_one_position(session, legacy):
    if legacy:
        position(session, key="601390", amount=100)
    else:
        obj = trade.order("601390", 100)
        engine._fill_pending_orders(session, DAY)
        assert obj.is_complete()
        engine._t1_unlock(session)
    obj = trade.order_pct(SEC, -1)
    assert obj is not None
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert obj.is_complete()
    assert not session._context.portfolio.positions


@pytest.mark.parametrize("blocked_by", ["volume", "t1"])
def test_zero_fill_remains_pending_then_recovers(session, monkeypatch, blocked_by):
    if blocked_by == "volume":
        monkeypatch.setattr(engine, "_get_volume_fast", lambda *a: 500)
        obj = trade.order(SEC, 1000)
    else:
        p = position(session, amount=1000)
        p.closeable_amount = 0
        obj = trade.order(SEC, -1000)
    engine._fill_pending_orders(session, DAY)
    assert obj.status == "pending"
    assert len(session._pending_orders) == 1
    monkeypatch.setattr(engine, "_get_volume_fast", lambda *a: 10_000)
    engine._t1_unlock(session)
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert obj.is_complete()


def test_cancel_partial_preserves_fills_cleans_queue_and_timestamp(session):
    obj = trade.order(SEC, 2000)
    engine._fill_pending_orders(session, DAY)
    assert obj.status == "partial_fill" and obj.filled_amount == 1000
    trade.cancel_order(obj)
    assert obj.status == "cancelled" and obj.filled_amount == 1000
    assert not obj.is_complete()
    assert not session._pending_orders
    assert obj.order_id not in session._order_timestamps


@pytest.mark.parametrize("method,value", [("order_value", 20000), ("order_target_value", 20000), ("order_target", 2000)])
def test_dynamic_order_quantity_and_completion(session, method, value):
    obj = getattr(trade, method)(SEC, value)
    assert not obj.is_complete()
    assert obj.remaining_amount() is None
    engine._fill_pending_orders(session, DAY)
    assert obj.status == "partial_fill"
    assert obj.filled_amount == 1000 and obj.remaining_amount() == 1000
    assert not obj.is_complete() and len(session._pending_orders) == 1
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert obj.is_complete() and obj.remaining_amount() == 0
    assert obj.filled_amount == 2000 and not session._pending_orders


def test_cash_partial_keeps_limit_style_and_daily_volume(session):
    session._context.portfolio.available_cash = 1010
    obj = trade.order(SEC, 2000, style=LimitOrder(10.1))
    session._slippage_model = FixedSlippage(0.001)
    engine._fill_pending_orders(session, DAY)
    assert obj.filled_amount == 100 and not obj.is_complete()
    assert obj.remaining_amount() == 1900
    assert session._context.portfolio.available_cash >= 0
    session._context.portfolio.available_cash = 100000
    session._slippage_model = FixedSlippage(0.02)
    engine._fill_pending_orders(session, DAY)
    assert obj.filled_amount == 100 and len(session._pending_orders) == 1
    session._slippage_model = None
    engine._fill_pending_orders(session, DAY)
    assert obj.filled_amount == 1000
    assert all(fill[1] <= 10.1 for fill in obj.partial_fills)
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert obj.is_complete() and obj.filled_amount == 2000


def test_missing_bar_core_loop_preserves_equity(monkeypatch):
    import pandas as pd
    from eqlib.objects import GlobalObject
    import eqlib
    days = [DAY + dt.timedelta(days=i) for i in range(3)]
    sess = st.BacktestSession()
    monkeypatch.setattr(st, "get_session", lambda: sess)
    class Feed:
        panel = None
        _dates = []
        load_stats = {}
        def load(self, *args, **kwargs):
            pass
        def get_bar(self, day, sec):
            if day == days[2]:
                return None
            px = 10 if day == days[0] else 20
            return dict(open=px, close=px, high=px, low=px, volume=10000)
        def get_close(self, day, sec):
            bar = self.get_bar(day, sec)
            return None if bar is None else bar["close"]
    monkeypatch.setattr(engine, "PreloadedData", Feed)
    monkeypatch.setattr(engine, "_get_trading_days", lambda *a: days)
    monkeypatch.setattr("eqlib.data.fetch_stock_data", lambda *a, **kw: pd.DataFrame())
    monkeypatch.setattr("eqlib.report.attach_chart_dual_indices", lambda *a, **kw: None)
    monkeypatch.setattr(eqlib, "g", GlobalObject())
    def initialize(ctx):
        ctx.universe = [SEC]
        trade.order(SEC, 100)
    result = engine._run_backtest_core(sess, initialize, days[0], days[-1],
            "daily", 1000000, "000300.XSHG", [SEC], None, None, "monthly:1", True, 512)
    values = [row["total_value"] for row in result["recorded_values"]]
    assert values[1] - values[0] == 1000
    assert values[2] == values[1]
    assert sess._context.portfolio.positions[SEC].current_price == 20
    assert sess._context.portfolio.positions[SEC].price_stale


def test_first_bare_position_keeps_dictionary_access_and_alias_orders(session):
    first = trade.order("601390", 100)
    second = trade.order(SEC, 100)
    engine._fill_pending_orders(session, DAY)
    assert first.is_complete() and second.is_complete()
    assert list(session._context.portfolio.positions) == ["601390"]
    assert session._context.portfolio.positions.get("601390").amount == 200
