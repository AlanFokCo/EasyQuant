"""Experimental daily A-share support/resistance strategy with risk sizing.

Signals are formed in ``after_trading_end`` from completed daily bars. Orders
execute at a later open through eqlib, never at the signal's closing price.
The parameters are research hypotheses, not evidence of profitability.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

import numpy as np
import pandas as pd

from eqlib.objects import LimitOrder
from eqlib.strategies.ashare_sr_leader import compute_atr, rolling_levels

FIELDS = ("open", "high", "low", "close", "volume")
OPEN_STATUSES = {"pending", "submitted", "partial_fill"}


@dataclass(frozen=True)
class SRRiskConfig:
    """Fixed, unoptimized defaults. All weights refer to current equity."""

    level_window: int = 60
    trend_window: int = 60
    market_window: int = 120
    atr_period: int = 20
    retest_bars: int = 5
    support_tolerance_atr: float = 0.75
    stop_buffer_atr: float = 0.5
    stop_atr: float = 1.5
    trailing_atr: float = 3.0
    min_reward_risk: float = 1.8
    breakout_target_r: float = 3.0
    entry_gap: float = 0.005
    min_stop_pct: float = 0.015
    max_stop_pct: float = 0.08
    min_price: float = 3.0
    min_avg_turnover: float = 50_000_000.0
    max_atr_pct: float = 0.06
    risk_per_trade: float = 0.005
    max_open_risk: float = 0.02
    max_stock_weight: float = 0.15
    max_exposure: float = 0.60
    max_positions: int = 5
    volume_participation: float = 0.005
    max_holding_days: int = 40
    cooldown_days: int = 5
    halt_drawdown: float = 0.10
    halt_days: int = 20
    slippage: float = 0.001
    allow_breakout: bool = False
    require_market_slope: bool = True
    exit_on_market_filter: bool = True

    def __post_init__(self):
        integer_fields = (
            "level_window",
            "trend_window",
            "market_window",
            "atr_period",
            "retest_bars",
            "max_positions",
            "max_holding_days",
            "cooldown_days",
            "halt_days",
        )
        for name, value in vars(self).items():
            if name in {
                "allow_breakout",
                "require_market_slope",
                "exit_on_market_filter",
            }:
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in integer_fields:
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{name} must be a positive integer")
            elif isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if min(self.level_window, self.trend_window, self.market_window) < 20:
            raise ValueError("level/trend/market windows must be at least 20")
        for name in (
            "entry_gap",
            "max_atr_pct",
            "min_stop_pct",
            "max_stop_pct",
            "risk_per_trade",
            "max_open_risk",
            "max_stock_weight",
            "max_exposure",
            "volume_participation",
            "halt_drawdown",
            "slippage",
        ):
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be less than one")
        if not self.min_stop_pct < self.max_stop_pct:
            raise ValueError("min_stop_pct must be below max_stop_pct")
        if not self.risk_per_trade <= self.max_open_risk < self.max_exposure:
            raise ValueError("risk budgets must fit within exposure")
        if self.max_stock_weight > self.max_exposure:
            raise ValueError("single-stock weight must not exceed exposure")
        if not 1 < self.min_reward_risk <= self.breakout_target_r:
            raise ValueError("reward/risk must exceed one and fit breakout target")

    @property
    def history_bars(self) -> int:
        return max(
            self.level_window + self.retest_bars + 2,
            self.trend_window + 20,
            self.market_window + 20,
            self.atr_period + 2,
        )


@dataclass(frozen=True)
class EntryPlan:
    kind: str
    support: float
    limit: float
    stop: float
    target: float
    atr: float
    avg_volume: float

    @property
    def reward_risk(self) -> float:
        return (self.target - self.limit) / (self.limit - self.stop)


def valid_bars(frame: pd.DataFrame, count: int) -> bool:
    """Reject malformed, nonfinite, duplicate and unordered observations."""
    if frame is None or len(frame) < count or not set(FIELDS) <= set(frame.columns):
        return False
    if not isinstance(frame.index, pd.DatetimeIndex):
        return False
    if (
        frame.index.hasnans
        or not frame.index.is_unique
        or not frame.index.is_monotonic_increasing
    ):
        return False
    try:
        x = frame.loc[:, FIELDS].to_numpy(dtype=float)
    except (TypeError, ValueError):
        return False
    if not np.isfinite(x).all() or (x[:, :4] <= 0).any() or (x[:, 4] < 0).any():
        return False
    return bool(
        (x[:, 1] >= x[:, :4].max(axis=1)).all()
        and (x[:, 2] <= x[:, :4].min(axis=1)).all()
    )


def market_allows_entry(frame: pd.DataFrame, config: SRRiskConfig) -> bool:
    """Require price above its average, optionally confirming a rising average."""
    if not valid_bars(frame, config.market_window + 20):
        return False
    ma = frame.close.rolling(config.market_window).mean()
    return bool(
        frame.close.iloc[-1] > ma.iloc[-1]
        and (not config.require_market_slope or ma.iloc[-1] > ma.iloc[-21])
    )


def plan_entry(frame: pd.DataFrame, config: SRRiskConfig) -> EntryPlan | None:
    """Find support bounces, breakout retests or optional direct breakouts.

    Levels exclude the signal bar. Retest resistance is frozen before the
    entire breakout window; no centered/future pivot confirmation is used.
    """
    required = max(
        config.level_window + config.retest_bars + 2,
        config.trend_window + 5,
        config.atr_period + 2,
    )
    if not valid_bars(frame, required):
        return None
    row, previous = frame.iloc[-1], frame.iloc[-2]
    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
    avg_volume = float(frame.volume.iloc[-21:-1].mean())
    turnover = float((frame.close * frame.volume).iloc[-21:-1].mean())
    ma = frame.close.rolling(config.trend_window).mean()
    if (
        row.close < config.min_price
        or row.volume <= 0
        or avg_volume <= 0
        or turnover < config.min_avg_turnover
        or atr <= 0
        or atr / row.close > config.max_atr_pct
        or row.close <= ma.iloc[-1]
        or ma.iloc[-1] < ma.iloc[-6]
        or row.close <= row.open
        or row.close <= previous.close
    ):
        return None

    resistance, support = rolling_levels(frame, config.level_window)
    kind = "support_bounce"
    near = (
        support - config.stop_buffer_atr * atr
        <= row.low
        <= support + config.support_tolerance_atr * atr
        and support < row.close <= support + 2 * config.support_tolerance_atr * atr
    )
    if not near:
        # The previous N bars may establish a breakout; today's bar retests it.
        anchor = frame.iloc[: -(config.retest_bars + 1)].tail(config.level_window)
        support = float(anchor.high.max())
        recent = frame.iloc[-(config.retest_bars + 1) : -1]
        confirmed = (
            (recent.close > support + 0.3 * atr) & (recent.volume > avg_volume * 1.2)
        ).any()
        near = (
            confirmed
            and support - config.stop_buffer_atr * atr
            <= row.low
            <= support + config.support_tolerance_atr * atr
            and support < row.close <= support + 2 * config.support_tolerance_atr * atr
        )
        if near:
            kind = "breakout_retest"
        elif (
            config.allow_breakout
            and resistance + 0.1 * atr < row.close <= resistance + 1.5 * atr
            and row.volume >= avg_volume
        ):
            # A completed close can confirm a breakout without a later retest.
            # The prior channel excludes today; reject extended moves instead
            # of lifting the buy limit to chase them at the next open.
            kind = "resistance_breakout"
            support = resistance
        else:
            return None

    # A buy limit prevents chasing gaps up. Gap-down/T+1 losses remain possible.
    limit = math.floor(float(row.close) * (1 + config.entry_gap) * 100) / 100
    stop = min(support - config.stop_buffer_atr * atr, limit - config.stop_atr * atr)
    distance = limit - stop
    if stop <= 0 or not config.min_stop_pct <= distance / limit <= config.max_stop_pct:
        return None
    target = resistance - 0.3 * atr
    if kind != "support_bounce":
        # At new highs there is no observed overhead resistance: use an explicitly
        # projected R-multiple target, not a fabricated historical price level.
        target = limit + config.breakout_target_r * distance
        overhead = (
            frame.high.iloc[: -(config.retest_bars + 1)]
            if kind == "breakout_retest"
            else frame.high.iloc[:-1]
        )
        overhead = overhead[overhead > limit]
        if not overhead.empty:
            target = min(target, float(overhead.max()) - 0.3 * atr)
    plan = EntryPlan(kind, support, limit, stop, target, atr, avg_volume)
    return plan if plan.reward_risk >= config.min_reward_risk else None


def size_entry(
    plan: EntryPlan,
    equity: float,
    cash: float,
    gross: float,
    open_risk: float,
    config: SRRiskConfig,
    cost,
) -> int:
    """Round down to 100 shares, reserving cash and round-trip friction.

    Risk is a planning estimate, not a maximum possible loss. The sell-tax
    allowance uses the higher historical 0.1% rate conservatively.
    """
    if not all(math.isfinite(x) and x >= 0 for x in (equity, cash, gross, open_risk)):
        return 0
    risk_budget = min(
        equity * config.risk_per_trade, equity * config.max_open_risk - open_risk
    )
    value_budget = min(
        cash, equity * config.max_stock_weight, equity * config.max_exposure - gross
    )
    unit_risk = (
        plan.limit
        - plan.stop
        + plan.limit
        * (cost.open_commission + cost.close_commission + 0.001 + 2 * config.slippage)
    )
    amount = (
        int(
            max(
                0,
                min(
                    (risk_budget - 2 * cost.min_commission) / unit_risk,
                    (value_budget - cost.min_commission)
                    / (plan.limit * (1 + cost.open_commission)),
                    plan.avg_volume * config.volume_participation,
                ),
            )
            // 100
        )
        * 100
    )
    while (
        amount
        and amount * plan.limit + cost.calc_open_cost(plan.limit, amount) > value_budget
    ):
        amount -= 100
    return amount


@dataclass
class _Holding:
    plan: EntryPlan
    stop: float
    peak_close: float
    entry_day: int
    exit_reason: str = ""


@dataclass
class _State:
    day: int = 0
    high_water: float = 0.0
    halt_until: int | None = None
    entries: dict = field(default_factory=dict)
    exits: dict = field(default_factory=dict)
    holdings: dict = field(default_factory=dict)
    cooldown: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


def make_sr_risk_budget_strategy(
    universe: list[str],
    config: SRRiskConfig | None = None,
    benchmark: str = "000300.XSHG",
    order_cost=None,
    eligible: Callable[[str, object], bool] | None = None,
):
    """Return an initialize callback for main-board A-share daily research.

    ``eligible(code, date)`` can supply a point-in-time membership/ST filter.
    Without it the universe is explicitly a static, user-selected watchlist.
    No current-name/ST endpoint is used to pretend to know historical status.
    State and order handles belong to each context, so runs are independent.
    """
    import eqlib as api

    config = config or SRRiskConfig()
    codes = tuple(dict.fromkeys(code.split(".")[0] for code in universe))
    if not codes or any(
        len(code) != 6
        or not code.isdigit()
        or not code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
        for code in codes
    ):
        raise ValueError(
            "universe must contain Shanghai/Shenzhen main-board A-share codes"
        )
    # Same defaults as examples/_defaults.py; caller can supply broker costs.
    cost = order_cost or api.OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        min_commission=5,
    )

    def event(ctx, action, code="", **details):
        ctx.sr_risk_budget.events.append(
            dict(
                date=ctx.current_dt.date().isoformat(),
                action=action,
                code=code,
                **details,
            )
        )

    def completed_frame(ctx, data, code):
        history = api.attribute_history(code, config.history_bars, "1d", FIELDS)
        bar = data[code]
        if bar is None:
            return pd.DataFrame(columns=FIELDS)
        today = pd.DataFrame(
            [{name: getattr(bar, name) for name in FIELDS}],
            index=pd.DatetimeIndex([ctx.current_dt.date()]),
        )
        # attribute_history intentionally excludes today, including after close.
        return pd.concat([history, today]).tail(config.history_bars)

    def on_close(ctx, data):
        if ctx.current_dt.time() < time(15, 0):
            raise RuntimeError(
                "support/resistance decisions require completed daily bars"
            )
        state = ctx.sr_risk_budget
        state.day += 1
        positions = {
            code.split(".")[0]: pos
            for code, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        }
        position_keys = {code.split(".")[0]: code for code in ctx.portfolio.positions}
        equity = float(ctx.portfolio.total_value)
        # Observe fills before removing one-session entry remainders. A partial
        # fill creates a holding; an unfilled order never creates a phantom one.
        for code, (order, plan) in list(state.entries.items()):
            if code in positions:
                state.holdings[code] = _Holding(
                    plan, plan.stop, positions[code].price, state.day
                )
                event(ctx, "entry_filled", code, shares=int(positions[code].amount))
            if order.status in OPEN_STATUSES:
                api.cancel_order(order)
            del state.entries[code]
        for code in list(state.holdings):
            if code not in positions:
                state.holdings.pop(code)
                state.cooldown[code] = state.day + config.cooldown_days
                event(ctx, "exit_filled", code)
        for code, order in list(state.exits.items()):
            if order.status not in OPEN_STATUSES:
                del state.exits[code]

        market = completed_frame(ctx, data, benchmark)
        market_ok = market_allows_entry(market, config)
        state.high_water = max(state.high_water, equity)
        drawdown = 1 - equity / state.high_water if state.high_water > 0 else 0.0
        if state.halt_until is None and drawdown >= config.halt_drawdown:
            state.halt_until = state.day + config.halt_days
            event(ctx, "portfolio_halt", drawdown=drawdown)
        if (
            state.halt_until is not None
            and state.day >= state.halt_until
            and not positions
            and market_ok
        ):
            state.halt_until = None
            state.high_water = equity
            event(ctx, "portfolio_resume")

        frames = {code: completed_frame(ctx, data, code) for code in codes}
        gross = sum(float(pos.value) for pos in positions.values())
        open_risk = 0.0
        for code, pos in positions.items():
            holding = state.holdings.get(code)
            reason = ""
            if holding is None:
                reason = "unmanaged_position"
            else:
                frame = frames.get(code)
                if valid_bars(frame, config.atr_period + 1):
                    close = float(frame.close.iloc[-1])
                    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
                    holding.peak_close = max(holding.peak_close, close)
                    # Stops can tighten, never widen. No assumed intraday fill.
                    holding.stop = max(
                        holding.stop, holding.peak_close - config.trailing_atr * atr
                    )
                    if close <= holding.stop:
                        reason = "support_or_trailing_stop"
                    elif close >= holding.plan.target:
                        reason = "resistance_or_r_target"
                if state.day - holding.entry_day >= config.max_holding_days:
                    reason = reason or "time_exit"
                open_risk += max(0.0, float(pos.price) - holding.stop) * pos.amount
                open_risk += float(pos.value) * (
                    cost.close_commission + 0.001 + config.slippage
                )
                open_risk += cost.min_commission
                reason = holding.exit_reason or reason
            if state.halt_until is not None:
                reason = "portfolio_halt"
            elif eligible is not None and not eligible(code, ctx.current_dt.date()):
                reason = reason or "universe_exit"
            elif config.exit_on_market_filter and not market_ok:
                reason = reason or "market_filter"
            if reason:
                if holding:
                    holding.exit_reason = reason
                if code not in state.exits:
                    order = api.order_target(position_keys[code], 0)
                    if order is not None:
                        state.exits[code] = order
                        event(ctx, "exit_order", code, reason=reason)

        # record() replaces this day's entry; retain the engine's equity/cash
        # marks when adding diagnostics from an after-close callback.
        api.record(
            total_value=equity,
            cash=float(ctx.portfolio.available_cash),
            sr_drawdown=drawdown,
            sr_exposure=gross / equity if equity > 0 else 0,
            sr_halted=int(state.halt_until is not None),
        )
        # Pending liquidations continue to consume gross exposure and risk.
        if not market_ok or state.halt_until is not None or state.exits or equity <= 0:
            return
        candidates = []
        for code in codes:
            if code in positions or state.cooldown.get(code, 0) > state.day:
                continue
            if eligible is not None and not eligible(code, ctx.current_dt.date()):
                continue
            plan = plan_entry(frames[code], config)
            if plan is not None:
                candidates.append((code, plan))
        # Stable ordering makes runs reproducible without optimizing to returns.
        candidates.sort(key=lambda item: (-item[1].reward_risk, item[0]))
        cash = float(ctx.portfolio.available_cash)
        slots = config.max_positions - len(positions)
        for code, plan in candidates[: max(0, slots)]:
            amount = size_entry(plan, equity, cash, gross, open_risk, config, cost)
            if not amount:
                continue
            order = api.order(code, amount, style=LimitOrder(plan.limit))
            if order is None:
                continue
            state.entries[code] = (order, plan)
            value = amount * plan.limit
            fees = cost.calc_open_cost(plan.limit, amount)
            cash -= value + fees
            gross += value
            open_risk += amount * (plan.limit - plan.stop) + fees
            open_risk += max(value * cost.close_commission, cost.min_commission)
            open_risk += value * (0.001 + 2 * config.slippage)
            event(
                ctx,
                "entry_order",
                code,
                kind=plan.kind,
                shares=amount,
                limit=plan.limit,
                support=plan.support,
                stop=plan.stop,
                target=plan.target,
                reward_risk=plan.reward_risk,
            )

    def initialize(ctx):
        if ctx.frequency != "daily":
            raise ValueError("sr_risk_budget supports daily backtests only")
        api.set_benchmark(benchmark)
        api.set_order_cost(cost)
        api.set_slippage(api.FixedSlippage(pct=config.slippage))
        api.set_option("check_price_limit", True)
        api.set_option("treat_missing_bar_as_suspended", True)
        ctx.universe = list(codes) + [benchmark]
        ctx.sr_risk_budget = _State(high_water=float(ctx.portfolio.total_value))
        api.after_trading_end(on_close)

    return initialize
