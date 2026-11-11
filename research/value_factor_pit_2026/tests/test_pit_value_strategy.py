"""Unit tests for the point-in-time value strategy."""

from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "value_factor_2026"))

from pit_value_strategy import (  # noqa: E402
    PITValueConfig,
    eligible_state,
    make_pit_value_strategy,
    select_cheap_names,
)


def _frame(dates, pe=10.0, pb=1.0, tradestatus=1, is_st=0, close=10.0,
           volume=2e7):
    return pd.DataFrame(
        {
            "open": close, "high": close, "low": close, "close": close,
            "volume": volume, "pe_ttm": pe, "pb_mrq": pb,
            "tradestatus": tradestatus, "is_st": is_st,
        },
        index=pd.to_datetime(dates),
    )


DATES = pd.date_range("2013-01-01", periods=25, freq="B")
AS_OF = DATES[-1]
CONFIG = PITValueConfig()


def test_eligible_state_accepts_profitable_liquid_normal_name():
    assert eligible_state(_frame(DATES), AS_OF, CONFIG) == (10.0, 1.0)


def test_eligible_state_rejects_st_suspended_and_unprofitable():
    assert eligible_state(_frame(DATES, is_st=1), AS_OF, CONFIG) is None
    assert eligible_state(_frame(DATES, tradestatus=0), AS_OF, CONFIG) is None
    assert eligible_state(_frame(DATES, pe=0.0), AS_OF, CONFIG) is None
    assert eligible_state(_frame(DATES, pb=-1.0), AS_OF, CONFIG) is None


def test_eligible_state_rejects_stale_or_short_history():
    assert eligible_state(_frame(DATES[:-1]), AS_OF, CONFIG) is None
    assert eligible_state(_frame(DATES[-10:]), AS_OF, CONFIG) is None
    illiquid = _frame(DATES, volume=1e4)
    assert eligible_state(illiquid, AS_OF, CONFIG) is None


def test_eligible_state_never_reads_future_rows():
    frame = _frame(DATES)
    future = _frame([DATES[-1] + pd.Timedelta(days=1)], pe=1.0, pb=0.1)
    combined = pd.concat([frame.iloc[:-1], _frame([DATES[-1]], pe=50, pb=5),
                          future])
    assert eligible_state(combined, AS_OF, CONFIG) == (50.0, 5.0)


def test_select_cheap_names_deterministic_top_n():
    states = {f"6000{i:02d}": (100 - i, 10 - i * 0.1) for i in range(12)}
    picks = select_cheap_names(states, CONFIG)
    assert picks == [f"6000{i:02d}" for i in (11, 10, 9, 8, 7, 6, 5, 4)]
    assert picks == select_cheap_names(states, CONFIG)


# ── state-machine tests with a stubbed eqlib api ─────────────────────────


class _FakeOrder:
    def __init__(self, status):
        self.status = status


class _FakeAPI:
    def __init__(self, order_status="cancelled"):
        self.after = None
        self.order_status = order_status
        self.order_target_calls = []
        self.order_value_calls = []
        self.order_target_value_calls = []
        self.recorded = []
        self.OrderCost = lambda **kw: kw
        self.FixedSlippage = lambda **kw: kw

    def after_trading_end(self, fn):
        self.after = fn

    def set_benchmark(self, *_):
        pass

    def set_order_cost(self, *_):
        pass

    def set_slippage(self, *_):
        pass

    def set_option(self, *_):
        pass

    def record(self, **kw):
        self.recorded.append(kw)

    def order_target(self, code, amount):
        self.order_target_calls.append((code, amount))
        return _FakeOrder(self.order_status)

    def order_value(self, code, value):
        self.order_value_calls.append((code, value))
        return _FakeOrder(self.order_status)

    def order_target_value(self, code, value):
        self.order_target_value_calls.append((code, value))
        return _FakeOrder(self.order_status)


class _FakePos:
    amount = 1000
    value = 100_000.0
    price = 10.0


def _ctx(cash=1_000_000.0, positions=()):
    portfolio = types.SimpleNamespace(
        total_value=cash, available_cash=cash,
        positions={code: _FakePos() for code in positions},
    )
    return types.SimpleNamespace(
        current_dt=datetime(2013, 1, 4, 15, 0), frequency="daily",
        portfolio=portfolio,
    )


def _boot(api, membership=None, histories=None):
    if membership is None:
        membership = {"2013-01-04": set()}
    factory = make_pit_value_strategy(
        membership, histories or {}, CONFIG, order_cost=None
    )
    ctx = _ctx()
    factory(ctx)
    assert api.after is not None
    return ctx


def test_halt_exit_resubmitted_after_cancel(monkeypatch):
    api = _FakeAPI(order_status="cancelled")
    monkeypatch.setitem(sys.modules, "eqlib", api)
    ctx = _boot(api)
    ctx.portfolio.positions = {"600005.XSHG": _FakePos()}
    state = ctx.pit_value
    state.halt_until = state.day + 20

    api.after(ctx, None)
    assert api.order_target_calls == [("600005.XSHG", 0)]
    api.after(ctx, None)  # cancelled order must be re-submitted
    assert api.order_target_calls == [("600005.XSHG", 0)] * 2


def test_entry_retry_exactly_once(monkeypatch):
    api = _FakeAPI(order_status="cancelled")
    monkeypatch.setitem(sys.modules, "eqlib", api)
    ctx = _boot(api)
    state = ctx.pit_value
    state.pending_entries["600005"] = {
        "order": _FakeOrder("cancelled"), "retries": 0,
        "target_value": 100_000.0,
    }

    api.after(ctx, None)
    assert len(api.order_value_calls) == 1  # the single retry
    assert state.pending_entries["600005"]["retries"] == 1

    state.pending_entries["600005"]["order"].status = "cancelled"
    api.after(ctx, None)
    assert len(api.order_value_calls) == 1  # no second retry
    assert "600005" not in state.pending_entries
    assert any(e["action"] == "entry_abandoned" for e in state.events)


def test_index_removed_member_gets_exit_order(monkeypatch):
    api = _FakeAPI(order_status="submitted")
    monkeypatch.setitem(sys.modules, "eqlib", api)
    date = "2013-01-04"
    membership = {date: {"600005"}}
    histories = {"600005": _frame(DATES)}
    ctx = _boot(api, membership, histories)
    ctx.portfolio.positions = {"600004.XSHG": _FakePos()}  # not a member
    state = ctx.pit_value

    api.after(ctx, None)

    assert ("600004.XSHG", 0) in api.order_target_calls
    reasons = [e.get("reason") for e in state.events if e["action"] == "exit_order"]
    assert "index_removal" in reasons
