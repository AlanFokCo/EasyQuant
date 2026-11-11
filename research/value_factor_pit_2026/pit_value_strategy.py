"""Point-in-time low-valuation factor strategy (value_factor_pit).

Same factor economics as research/value_factor_2026, but the universe is the
CSI 300 membership effective on each decision date and the daily frames carry
point-in-time PE(TTM)/PB(MRQ), trading status and ST flags. Completed bars
only; orders fill at a later open. See DESIGN.md for the frozen choices and
the 2013-2015 gate; the outcome lives in README.md.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from value_strategy import composite_scores  # reused unchanged, by design

OPEN_STATUSES = {"pending", "submitted", "partial_fill"}


@dataclass(frozen=True)
class PITValueConfig:
    """Frozen in DESIGN.md before the validation run. Weights vs equity."""

    rebalance_days: int = 20
    top_n: int = 8
    entry_retry_max: int = 1
    min_price: float = 3.0
    turnover_window: int = 20
    min_avg_turnover: float = 100_000_000.0
    max_stock_weight: float = 0.15
    max_exposure: float = 0.95
    min_order_value: float = 20_000.0
    sell_proceeds_buffer: float = 0.98
    use_kill_switch: bool = True      # identical to value_factor_2026
    halt_drawdown: float = 0.10
    halt_days: int = 20
    slippage: float = 0.001

    def __post_init__(self):
        booleans = ("use_kill_switch",)
        integers = ("rebalance_days", "top_n", "entry_retry_max",
                    "turnover_window", "halt_days")
        for name, value in vars(self).items():
            if name in booleans:
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in integers:
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{name} must be a positive integer")
            elif isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("max_stock_weight", "max_exposure", "halt_drawdown",
                     "slippage", "sell_proceeds_buffer"):
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be less than one")
        if self.max_stock_weight * self.top_n < self.max_exposure - 1e-9:
            raise ValueError("top_n cannot deploy the exposure budget")


def eligible_state(frame: pd.DataFrame, as_of, config: PITValueConfig):
    """(pe_ttm, pb_mrq) when the name is tradeable and measurable today.

    Every check reads only rows on or before ``as_of``; a missing today's row
    (suspension) or a non-normal status excludes the name.
    """
    if frame is None or frame.empty:
        return None
    past = frame.loc[frame.index <= pd.Timestamp(as_of)]
    if len(past) < config.turnover_window:
        return None
    last = past.iloc[-1]
    if past.index[-1].date() != pd.Timestamp(as_of).date():
        return None  # no bar today: suspended or not yet listed
    try:
        pe = float(last["pe_ttm"])
        pb = float(last["pb_mrq"])
        close = float(last["close"])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (pe, pb, close)):
        return None
    if pe <= 0 or pb <= 0:
        return None
    if int(last["tradestatus"]) != 1 or int(last["is_st"]) != 0:
        return None
    if close < config.min_price:
        return None
    recent = past.iloc[-config.turnover_window:]
    turnover = float((recent["close"] * recent["volume"]).mean())
    if not math.isfinite(turnover) or turnover < config.min_avg_turnover:
        return None
    return pe, pb


def select_cheap_names(states: dict, config: PITValueConfig) -> list[str]:
    """Cheapest-first top_n with a deterministic code tie-break."""
    scores = composite_scores(states)
    return sorted(scores, key=lambda c: (scores[c], c))[: config.top_n]


@dataclass
class _State:
    day: int = 0
    high_water: float = 0.0
    halt_until: int | None = None
    exits: dict = field(default_factory=dict)
    pending_entries: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    selections: list = field(default_factory=list)
    rebalances: int = 0
    flat_days: int = 0


def make_pit_value_strategy(
    membership: dict[str, set[str]],
    histories: dict[str, pd.DataFrame],
    config: PITValueConfig | None = None,
    benchmark: str = "000300.XSHG",
    order_cost=None,
    eligible: Callable[[str, object], bool] | None = None,
):
    """Return an ``initialize`` callback for daily A-share research runs.

    ``membership`` maps an ISO date to the CSI300 member set effective that
    day; the latest sampled date on or before a rebalance applies.
    ``histories`` maps bare codes to frozen daily frames with point-in-time
    valuation/status columns. State lives on the context.
    """
    import eqlib as api

    config = config or PITValueConfig()
    member_dates = sorted(
        (pd.Timestamp(d), set(codes)) for d, codes in membership.items()
    )
    if not member_dates:
        raise ValueError("membership must not be empty")
    cost = order_cost or api.OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025, min_commission=5,
    )

    def event(ctx, action, code="", **details):
        ctx.pit_value.events.append(
            dict(date=ctx.current_dt.date().isoformat(), action=action,
                 code=code, **details)
        )

    def members_on(today) -> set[str]:
        chosen = None
        for date, codes in member_dates:
            if date.date() <= today:
                chosen = codes
            else:
                break
        return chosen or set()

    def on_close(ctx, data):
        if ctx.current_dt.time() < time(15, 0):
            raise RuntimeError("pit_value decisions require completed bars")
        state = ctx.pit_value
        state.day += 1
        positions = {
            code.split(".")[0]: pos
            for code, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        }
        position_keys = {code.split(".")[0]: code
                         for code in ctx.portfolio.positions}
        equity = float(ctx.portfolio.total_value)
        today = ctx.current_dt.date()

        for code, order in list(state.exits.items()):
            if order is None or order.status not in OPEN_STATUSES:
                del state.exits[code]

        # ── entry retry: a cancelled unfilled entry gets exactly one retry ──
        for code, entry in list(state.pending_entries.items()):
            order = entry["order"]
            if order is not None and order.status in OPEN_STATUSES:
                continue
            if code in positions:
                del state.pending_entries[code]
                continue
            if entry["retries"] >= config.entry_retry_max:
                event(ctx, "entry_abandoned", code)
                del state.pending_entries[code]
                continue
            spend = min(entry["target_value"],
                        float(ctx.portfolio.available_cash) * 0.99)
            if spend < config.min_order_value:
                event(ctx, "entry_abandoned", code, reason="cash")
                del state.pending_entries[code]
                continue
            retry = api.order_value(code, spend)
            if retry is None:
                event(ctx, "entry_abandoned", code, reason="order_rejected")
                del state.pending_entries[code]
                continue
            entry["order"] = retry
            entry["retries"] += 1
            event(ctx, "entry_retry", code, value=round(spend, 2))

        # ── portfolio kill switch (exit resubmission while halted) ─────────
        state.high_water = max(state.high_water, equity)
        drawdown = 1 - equity / state.high_water if state.high_water > 0 else 0.0
        if (
            config.use_kill_switch
            and state.halt_until is None
            and drawdown >= config.halt_drawdown
        ):
            state.halt_until = state.day + config.halt_days
            event(ctx, "portfolio_halt", drawdown=round(drawdown, 4))
        if state.halt_until is not None:
            for code in positions:
                if code not in state.exits:
                    order = api.order_target(position_keys[code], 0)
                    if order is not None:
                        state.exits[code] = order
                        event(ctx, "exit_order", code, reason="portfolio_halt")
        if (
            state.halt_until is not None
            and state.day >= state.halt_until
            and not positions
        ):
            state.halt_until = None
            state.high_water = equity
            event(ctx, "portfolio_resume")
        halted = state.halt_until is not None

        gross = sum(float(pos.value) for pos in positions.values())
        exposure = gross / equity if equity > 0 else 0.0
        if not positions and not state.exits:
            state.flat_days += 1
        api.record(
            total_value=equity,
            cash=float(ctx.portfolio.available_cash),
            pv_exposure=exposure,
            pv_positions=len(positions),
            pv_halted=int(halted),
        )

        # ── monthly rebalance only ────────────────────────────────────────
        if halted or state.exits or equity <= 0:
            return
        is_rebalance = (
            state.rebalances == 0
            or (state.day - 1) % config.rebalance_days == 0
        )
        if not is_rebalance:
            return

        members = members_on(today)
        pe_pb = {}
        for code in sorted(members):
            if eligible is not None and not eligible(code, today):
                continue
            state_row = eligible_state(histories.get(code), today, config)
            if state_row is not None:
                pe_pb[code] = state_row

        picked = select_cheap_names(pe_pb, config)
        weight = min(config.max_stock_weight,
                     config.max_exposure / max(len(picked), 1))
        state.rebalances += 1
        state.selections.append(
            dict(date=today.isoformat(), day=state.day,
                 members=len(members), eligible=len(pe_pb),
                 picks=[{"code": c, "score": round(composite_scores(pe_pb)[c], 6),
                         "pe_ttm": round(pe_pb[c][0], 3),
                         "pb": round(pe_pb[c][1], 3),
                         "weight": round(weight, 6)} for c in picked])
        )
        event(ctx, "rebalance", picks=",".join(picked) or "-",
              members=len(members), eligible=len(pe_pb))

        # sells first: rank-outs and index removals
        proceeds = 0.0
        for code, pos in positions.items():
            if code in picked:
                continue
            reason = "rank_out" if code in members else "index_removal"
            order = api.order_target(position_keys[code], 0)
            if order is not None:
                state.exits[code] = order
                proceeds += float(pos.value)
                event(ctx, "exit_order", code, reason=reason)

        # buys/adjustments toward equal target weights
        cash = float(ctx.portfolio.available_cash)
        budget = cash + proceeds * config.sell_proceeds_buffer
        room = max(0.0, config.max_exposure * equity - gross + proceeds)
        for code in picked:
            target_value = min(weight * equity,
                               config.max_stock_weight * equity)
            current = float(positions[code].value) if code in positions else 0.0
            delta = target_value - current
            if delta < config.min_order_value:
                continue
            spend = min(delta, budget, room)
            if spend < config.min_order_value:
                continue
            order = api.order_target_value(code, target_value) \
                if spend >= delta else api.order_value(code, spend)
            if order is None:
                continue
            budget -= spend
            room -= spend
            state.pending_entries[code] = {
                "order": order, "retries": 0,
                "target_value": round(target_value, 2),
            }
            event(ctx, "entry_order", code, target_value=round(target_value, 2),
                  score=round(composite_scores(pe_pb)[code], 6))

    def initialize(ctx):
        if ctx.frequency != "daily":
            raise ValueError("pit_value supports daily backtests only")
        api.set_benchmark(benchmark)
        api.set_order_cost(cost)
        api.set_slippage(api.FixedSlippage(pct=config.slippage))
        api.set_option("check_price_limit", True)
        api.set_option("treat_missing_bar_as_suspended", True)
        ctx.universe = sorted(histories) + [benchmark]
        ctx.pit_value = _State(high_water=float(ctx.portfolio.total_value))
        api.after_trading_end(on_close)

    return initialize
