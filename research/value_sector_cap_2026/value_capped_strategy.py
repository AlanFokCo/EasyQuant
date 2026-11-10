"""Sector-capped low-valuation factor strategy (value_sector_cap).

Identical to research/value_factor_2026 except for three frozen changes
(DESIGN.md): a sector cap of 2 names per rebalance, one retry of
limit-cancelled entries, and halt-exit resubmission while halted. Signals in
``after_trading_end`` from completed bars and point-in-time frozen valuation
samples (carried forward ≤ 21 calendar days); fills at a later open.

This is a research hypothesis, not evidence of profitability. See DESIGN.md
for the frozen choices, windows, and gate; the outcome lives in README.md.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from eqlib.strategies.sr_risk_budget import FIELDS, valid_bars

OPEN_STATUSES = {"pending", "submitted", "partial_fill"}


@dataclass(frozen=True)
class CappedValueConfig:
    """Frozen in DESIGN.md before the validation run. Weights vs equity."""

    rebalance_days: int = 20
    top_n: int = 8
    sector_max: int = 2               # CHANGE 1: max names per sector
    entry_retry_max: int = 1          # CHANGE 2: retry limit-cancelled entries once
    staleness_days: int = 21
    min_price: float = 3.0
    turnover_window: int = 20
    min_avg_turnover: float = 100_000_000.0
    max_stock_weight: float = 0.15
    max_exposure: float = 0.95
    min_order_value: float = 20_000.0
    sell_proceeds_buffer: float = 0.98
    use_kill_switch: bool = False     # DESIGN.md v2: removed on dev evidence
    halt_drawdown: float = 0.10
    halt_days: int = 20
    slippage: float = 0.001

    def __post_init__(self):
        booleans = ("use_kill_switch",)
        integers = ("rebalance_days", "top_n", "sector_max", "entry_retry_max",
                    "staleness_days", "turnover_window", "halt_days")
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

    @property
    def history_bars(self) -> int:
        return self.turnover_window + 2


def latest_valuation(frame: pd.DataFrame, as_of, staleness_days: int):
    """Most recent (pe_ttm, pb) sampled on or before ``as_of``, or None."""
    if frame is None or frame.empty:
        return None
    past = frame.loc[frame.index <= pd.Timestamp(as_of)]
    if past.empty:
        return None
    last = past.iloc[-1]
    age = (pd.Timestamp(as_of) - past.index[-1]).days
    if age > staleness_days:
        return None
    pe, pb = float(last["pe_ttm"]), float(last["pb"])
    if not (math.isfinite(pe) and math.isfinite(pb)):
        return None
    return pe, pb


def average_turnover(frame: pd.DataFrame, window: int):
    """Mean close*volume over the window, or None."""
    if not valid_bars(frame, window):
        return None
    recent = frame.iloc[-window:]
    value = float((recent["close"] * recent["volume"]).mean())
    return value if math.isfinite(value) and value > 0 else None


def composite_scores(eligible_pe_pb: dict) -> dict:
    """0.5 × pct-rank(PE asc) + 0.5 × pct-rank(PB asc); lower is cheaper."""
    codes = list(eligible_pe_pb)
    if not codes:
        return {}
    pe = pd.Series({c: eligible_pe_pb[c][0] for c in codes})
    pb = pd.Series({c: eligible_pe_pb[c][1] for c in codes})
    score = 0.5 * pe.rank(pct=True) + 0.5 * pb.rank(pct=True)
    return score.to_dict()


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


def make_value_capped_strategy(
    universe: list[str],
    valuations: dict[str, pd.DataFrame],
    sectors: dict[str, str],
    config: CappedValueConfig | None = None,
    benchmark: str = "000300.XSHG",
    order_cost=None,
    eligible: Callable[[str, object], bool] | None = None,
):
    """Return an ``initialize`` callback for daily A-share research runs.

    ``valuations`` maps bare codes to frozen DataFrames (columns ``pe_ttm``,
    ``pb``) indexed by sample date; only samples ≤ the decision date are read.
    ``sectors`` maps bare codes to sector labels. ``eligible(code, date)`` can
    add a point-in-time membership/ST filter. State lives on the context.
    """
    import eqlib as api

    config = config or CappedValueConfig()
    codes = tuple(dict.fromkeys(code.split(".")[0] for code in universe))
    if not codes:
        raise ValueError("universe must not be empty")
    if any(len(code) != 6 or not code.isdigit() for code in codes):
        raise ValueError("universe must contain six-digit A-share codes")
    missing_val = [c for c in codes if c not in valuations]
    if missing_val:
        raise ValueError(f"valuations missing for: {missing_val}")
    missing_sector = [c for c in codes if c not in sectors]
    if missing_sector:
        raise ValueError(f"sectors missing for: {missing_sector}")
    cost = order_cost or api.OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        min_commission=5,
    )

    def event(ctx, action, code="", **details):
        ctx.value_capped.events.append(
            dict(date=ctx.current_dt.date().isoformat(), action=action,
                 code=code, **details)
        )

    def completed_frame(ctx, data, code):
        """History plus today's completed bar; attribute_history excludes today."""
        history = api.attribute_history(code, config.history_bars, "1d", FIELDS)
        bar = data[code] if data is not None else None
        if bar is None:
            return history if history is not None else pd.DataFrame(columns=FIELDS)
        today = pd.DataFrame(
            [{name: getattr(bar, name) for name in FIELDS}],
            index=pd.DatetimeIndex([ctx.current_dt.date()]),
        )
        return pd.concat([history, today]).tail(config.history_bars)

    def on_close(ctx, data):
        if ctx.current_dt.time() < time(15, 0):
            raise RuntimeError("value_capped decisions require completed bars")
        state = ctx.value_capped
        state.day += 1
        positions = {
            code.split(".")[0]: pos
            for code, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        }
        position_keys = {code.split(".")[0]: code for code in ctx.portfolio.positions}
        equity = float(ctx.portfolio.total_value)
        today = ctx.current_dt.date()

        for code, order in list(state.exits.items()):
            if order is None or order.status not in OPEN_STATUSES:
                del state.exits[code]

        # ── entry retry: a limit-cancelled entry gets exactly one retry ────
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

        # ── portfolio kill switch (with exit resubmission, review F3) ─────
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
            vc_exposure=exposure,
            vc_positions=len(positions),
            vc_halted=int(halted),
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

        frames = {code: completed_frame(ctx, data, code) for code in codes}
        pe_pb = {}
        for code in codes:
            if eligible is not None and not eligible(code, today):
                continue
            v = latest_valuation(valuations.get(code), today,
                                 config.staleness_days)
            if v is None:
                continue
            pe, pb = v
            if pe <= 0 or pb <= 0:
                continue
            frame = frames.get(code)
            # suspended names hand back a stale frame; never trade on it
            if frame is None or len(frame) == 0 or (
                frame.index[-1].date() != today
            ):
                continue
            close = float(frame["close"].iloc[-1])
            if close < config.min_price:
                continue
            turnover = average_turnover(frame, config.turnover_window)
            if turnover is None or turnover < config.min_avg_turnover:
                continue
            pe_pb[code] = (pe, pb)

        scores = composite_scores(pe_pb)
        ranked = sorted(scores, key=lambda c: (scores[c], c))
        # CHANGE 1: sector cap — cheap-first, skip names whose sector is full
        sector_counts: dict[str, int] = {}
        picked = []
        for code in ranked:
            if len(picked) >= config.top_n:
                break
            sector = sectors[code]
            if sector_counts.get(sector, 0) >= config.sector_max:
                continue
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            picked.append(code)
        weight = min(config.max_stock_weight, config.max_exposure / max(len(picked), 1))
        state.rebalances += 1
        state.selections.append(
            dict(date=today.isoformat(), day=state.day,
                 picks=[{"code": c, "sector": sectors[c],
                         "score": round(scores[c], 6),
                         "pe_ttm": round(pe_pb[c][0], 3),
                         "pb": round(pe_pb[c][1], 3),
                         "weight": round(weight, 6)} for c in picked])
        )
        event(ctx, "rebalance", picks=",".join(picked) or "-",
              eligible=len(pe_pb))

        # sells first: drop names that fell out of the top set
        proceeds = 0.0
        for code, pos in positions.items():
            if code in picked:
                continue
            order = api.order_target(position_keys[code], 0)
            if order is not None:
                state.exits[code] = order
                proceeds += float(pos.value)
                event(ctx, "exit_order", code, reason="rank_out")

        # buys/adjustments toward equal target weights
        cash = float(ctx.portfolio.available_cash)
        budget = cash + proceeds * config.sell_proceeds_buffer
        room = max(0.0, config.max_exposure * equity - gross + proceeds)
        for code in picked:
            target_value = min(weight * equity, config.max_stock_weight * equity)
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
                  score=round(scores[code], 6))

    def initialize(ctx):
        if ctx.frequency != "daily":
            raise ValueError("value_capped supports daily backtests only")
        api.set_benchmark(benchmark)
        api.set_order_cost(cost)
        api.set_slippage(api.FixedSlippage(pct=config.slippage))
        api.set_option("check_price_limit", True)
        api.set_option("treat_missing_bar_as_suspended", True)
        ctx.universe = list(codes) + [benchmark]
        ctx.value_capped = _State(high_water=float(ctx.portfolio.total_value))
        api.after_trading_end(on_close)

    return initialize
