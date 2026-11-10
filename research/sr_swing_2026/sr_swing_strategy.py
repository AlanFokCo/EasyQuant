"""Support-pullback swing strategy for A-share daily research (sr_swing).

Buys established uptrends at clustered swing-support levels when the tape
shows rejection, sizes positions by risk to the stop below the level, and
exits at the next resistance, on a trailing ATR stop, or on trend break.
Signals are formed in ``after_trading_end`` from *completed* daily bars only;
orders fill at a later open through eqlib, so no decision uses the price it
trades at.

This is a research hypothesis, not evidence of profitability. See DESIGN.md
for the frozen choices and gate; the outcome lives in README.md.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from eqlib.strategies.ashare_sr_leader import compute_atr
from eqlib.strategies.sr_risk_budget import FIELDS, valid_bars
from eqlib.utils.levels import support_resistance_levels

OPEN_STATUSES = {"pending", "submitted", "partial_fill"}
TRADING_DAYS_PER_YEAR = 244


@dataclass(frozen=True)
class SRSwingConfig:
    """Frozen in DESIGN.md before the evaluation run. Weights vs equity."""

    # levels
    level_lookback: int = 120
    level_tolerance: float = 0.02
    # trend
    ma_fast: int = 20
    ma_slow: int = 60
    # entry
    atr_period: int = 20
    support_tolerance_atr: float = 1.0
    range_close_min: float = 0.6      # close in upper (1 - x)..1 of day's range
    min_price: float = 3.0
    turnover_window: int = 20
    min_avg_turnover: float = 100_000_000.0
    # stop / target
    stop_buffer_atr: float = 0.5
    min_stop_pct: float = 0.015
    max_stop_pct: float = 0.08
    min_reward_risk: float = 1.8
    no_resistance_target_r: float = 3.0
    trailing_atr: float = 3.0
    # exits
    max_holding_days: int = 60
    cooldown_days: int = 5
    # sizing
    risk_per_trade: float = 0.0075
    max_stock_weight: float = 0.15
    max_positions: int = 6
    max_exposure: float = 0.90
    min_order_value: float = 20_000.0
    # market overlay (halve risk under the index MA, never kill)
    market_ma: int = 200
    weak_market_risk_mul: float = 0.5
    # portfolio risk
    halt_drawdown: float = 0.10
    halt_days: int = 20
    slippage: float = 0.001

    def __post_init__(self):
        booleans: tuple = ()
        integers = (
            "level_lookback",
            "ma_fast",
            "ma_slow",
            "atr_period",
            "turnover_window",
            "max_positions",
            "max_holding_days",
            "cooldown_days",
            "market_ma",
            "halt_days",
        )
        for name, value in vars(self).items():
            if name in booleans:
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in integers:
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{name} must be a positive integer")
            elif isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.ma_fast >= self.ma_slow:
            raise ValueError("ma_fast must be below ma_slow")
        if self.level_lookback < 40:
            raise ValueError("level_lookback must span at least 40 bars")
        for name in (
            "level_tolerance",
            "min_stop_pct",
            "max_stop_pct",
            "risk_per_trade",
            "max_stock_weight",
            "max_exposure",
            "halt_drawdown",
            "slippage",
        ):
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be less than one")
        if not self.min_stop_pct < self.max_stop_pct:
            raise ValueError("min_stop_pct must be below max_stop_pct")
        if self.max_stock_weight * self.max_positions < self.max_exposure - 1e-9:
            raise ValueError("position caps cannot deploy the exposure budget")
        if not 0 < self.range_close_min < 1:
            raise ValueError("range_close_min must be in (0, 1)")
        if not 1 < self.min_reward_risk <= self.no_resistance_target_r:
            raise ValueError("reward/risk must exceed one and fit fallback target")

    @property
    def history_bars(self) -> int:
        return max(
            self.level_lookback + 8,
            self.ma_slow + 2,
            self.atr_period + 2,
            self.turnover_window + 2,
            # the market overlay reads market_ma bars of the same tailed frame;
            # omitting it silently disabled the overlay (adversarial review M1)
            self.market_ma + 2,
        )


@dataclass(frozen=True)
class PullbackPlan:
    code: str
    entry: float
    support: float
    stop: float
    target: float
    atr: float

    @property
    def reward_risk(self) -> float:
        return (self.target - self.entry) / (self.entry - self.stop)


# ── pure signal functions (unit-testable, no engine state) ────────────────


def trend_ok(frame: pd.DataFrame, config: SRSwingConfig) -> bool:
    """Established uptrend: close above the slow MA, fast above slow."""
    if not valid_bars(frame, config.ma_slow + 1):
        return False
    closes = frame["close"].astype(float)
    slow = float(closes.rolling(config.ma_slow).mean().iloc[-1])
    fast = float(closes.rolling(config.ma_fast).mean().iloc[-1])
    close = float(closes.iloc[-1])
    if not all(math.isfinite(v) for v in (slow, fast, close)):
        return False
    return close > slow and fast > slow


def nearest_levels(frame: pd.DataFrame, config: SRSwingConfig):
    """Clustered swing levels relative to the latest completed close."""
    if not valid_bars(frame, config.level_lookback):
        return None
    out = support_resistance_levels(
        frame["high"].astype(float),
        frame["low"].astype(float),
        frame["close"].astype(float),
        lookback=config.level_lookback,
        tolerance=config.level_tolerance,
    )
    return out


def pullback_plan(code: str, frame: pd.DataFrame, config: SRSwingConfig):
    """Build an entry plan when today's bar rejects a swing-support touch.

    Entry assumptions use today's completed close; the engine fills at a
    later open, and the reward/risk screen is evaluated at that signal price.
    """
    if not valid_bars(frame, config.atr_period + 2):
        return None
    bar = frame.iloc[-1]
    prev_close = float(frame["close"].iloc[-2])
    open_, high = float(bar["open"]), float(bar["high"])
    low, close = float(bar["low"]), float(bar["close"])
    if min(open_, high, low, close, prev_close) <= 0:
        return None
    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
    if not math.isfinite(atr) or atr <= 0:
        return None
    levels = nearest_levels(frame, config)
    if levels is None:
        return None
    support = levels["nearest_support"]
    if support is None or support >= close:
        return None
    # the tape must have come down to the level today ...
    if low > support + config.support_tolerance_atr * atr:
        return None
    # ... and rejected it: close back above the level, above yesterday's
    # close, and in the upper part of today's range
    if close <= support or close <= prev_close:
        return None
    if high > low and (close - low) / (high - low) < config.range_close_min:
        return None
    if close < config.min_price:
        return None
    stop = support - config.stop_buffer_atr * atr
    stop = min(stop, close * (1 - config.min_stop_pct))
    if stop < close * (1 - config.max_stop_pct):
        return None  # the level is too far away for a sane stop
    target = levels["nearest_resistance"]
    if target is None or target <= close:
        target = close + config.no_resistance_target_r * (close - stop)
    plan = PullbackPlan(code=code, entry=close, support=float(support),
                        stop=float(stop), target=float(target), atr=atr)
    if plan.reward_risk < config.min_reward_risk:
        return None
    return plan


def average_turnover(frame: pd.DataFrame, config: SRSwingConfig):
    """Mean close*volume over the turnover window, or None."""
    if not valid_bars(frame, config.turnover_window):
        return None
    recent = frame.iloc[-config.turnover_window:]
    value = float((recent["close"] * recent["volume"]).mean())
    return value if math.isfinite(value) and value > 0 else None


def market_risk_multiplier(frame: pd.DataFrame, config: SRSwingConfig) -> float:
    """Halve risk below the index's long MA; never kill entries outright.

    Fails loud on short history: a silent fallback to full risk once made
    this overlay dead code for an entire evaluation (review finding M1).
    """
    if not valid_bars(frame, config.market_ma):
        raise ValueError(
            f"market overlay needs {config.market_ma} bars; "
            "check history_bars and warm-up coverage"
        )
    closes = frame["close"].astype(float)
    ma = float(closes.rolling(config.market_ma).mean().iloc[-1])
    close = float(closes.iloc[-1])
    if not math.isfinite(ma) or not math.isfinite(close):
        return 1.0
    return 1.0 if close >= ma else config.weak_market_risk_mul


def position_value(plan: PullbackPlan, equity: float, cash: float,
                   gross: float, risk_mul: float,
                   config: SRSwingConfig) -> float:
    """Risk-budgeted order value, capped by name weight and exposure room."""
    risk_amount = equity * config.risk_per_trade * risk_mul
    per_share_risk = plan.entry - plan.stop
    if per_share_risk <= 0:
        return 0.0
    value = risk_amount * plan.entry / per_share_risk
    room = max(0.0, config.max_exposure * equity - gross)
    value = min(value, config.max_stock_weight * equity, room, cash * 0.99)
    return value if value >= config.min_order_value else 0.0


# ── engine-facing state ───────────────────────────────────────────────────


@dataclass
class _Holding:
    stop: float
    target: float
    peak_close: float
    entry_day: int


@dataclass
class _State:
    day: int = 0
    high_water: float = 0.0
    halt_until: int | None = None
    holdings: dict = field(default_factory=dict)
    pending_plans: dict = field(default_factory=dict)
    exit_reasons: dict = field(default_factory=dict)
    cooldown: dict = field(default_factory=dict)
    exits: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    entries: list = field(default_factory=list)
    flat_days: int = 0
    risk_mul: float = 1.0


def make_sr_swing_strategy(
    universe: list[str],
    config: SRSwingConfig | None = None,
    benchmark: str = "000300.XSHG",
    order_cost=None,
    eligible: Callable[[str, object], bool] | None = None,
):
    """Return an ``initialize`` callback for daily A-share research runs.

    ``eligible(code, date)`` can supply a point-in-time membership/ST filter.
    Without it the universe is explicitly a static, user-selected watchlist.
    All mutable state lives on the context, so runs stay independent.
    """
    import eqlib as api

    config = config or SRSwingConfig()
    codes = tuple(dict.fromkeys(code.split(".")[0] for code in universe))
    if not codes:
        raise ValueError("universe must not be empty")
    if any(len(code) != 6 or not code.isdigit() for code in codes):
        raise ValueError("universe must contain six-digit A-share codes")
    cost = order_cost or api.OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        min_commission=5,
    )

    def event(ctx, action, code="", **details):
        ctx.sr_swing.events.append(
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
            raise RuntimeError("sr_swing decisions require completed bars")
        state = ctx.sr_swing
        state.day += 1
        positions = {
            code.split(".")[0]: pos
            for code, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        }
        position_keys = {code.split(".")[0]: code for code in ctx.portfolio.positions}
        equity = float(ctx.portfolio.total_value)

        frames = {code: completed_frame(ctx, data, code) for code in codes}
        market = completed_frame(ctx, data, benchmark)
        state.risk_mul = market_risk_multiplier(market, config)

        # ── observe fills: new positions adopt their plan, departures cool down
        for code, pos in positions.items():
            if code not in state.holdings:
                plan = state.pending_plans.pop(code, None)
                close = float(pos.price)
                if plan is not None:
                    stop, target = plan.stop, plan.target
                else:
                    frame = frames.get(code, pd.DataFrame())
                    atr = (
                        float(compute_atr(frame, config.atr_period).iloc[-1])
                        if valid_bars(frame, config.atr_period + 1)
                        else float("nan")
                    )
                    stop = (
                        close - config.trailing_atr * atr
                        if math.isfinite(atr) and atr > 0
                        else close * (1 - config.trailing_atr * 0.02)
                    )
                    target = float("inf")
                state.holdings[code] = _Holding(
                    stop=stop, target=target,
                    peak_close=close, entry_day=state.day,
                )
                event(ctx, "entry_filled", code, shares=int(pos.amount),
                      stop=round(stop, 4),
                      target=None if math.isinf(target) else round(target, 4))
        for code in list(state.holdings):
            if code not in positions:
                state.holdings.pop(code)
                # only stop-outs cool the name down; target/trend exits may re-enter
                if state.exit_reasons.pop(code, "") == "trailing_stop":
                    state.cooldown[code] = state.day + config.cooldown_days
                event(ctx, "exit_filled", code)
        # pending_plans are overwritten by every fresh entry order and consumed
        # on fill, so a plan from an unfilled order can never bind to a later
        # position without a fresh signal.
        for code, order in list(state.exits.items()):
            if order is None or order.status not in OPEN_STATUSES:
                del state.exits[code]

        # ── portfolio kill switch ─────────────────────────────────────────
        state.high_water = max(state.high_water, equity)
        drawdown = 1 - equity / state.high_water if state.high_water > 0 else 0.0
        if state.halt_until is None and drawdown >= config.halt_drawdown:
            state.halt_until = state.day + config.halt_days
            event(ctx, "portfolio_halt", drawdown=round(drawdown, 4))
        if (
            state.halt_until is not None
            and state.day >= state.halt_until
            and not positions
        ):
            state.halt_until = None
            state.high_water = equity
            event(ctx, "portfolio_resume")
        halted = state.halt_until is not None

        # ── daily per-position risk exits ─────────────────────────────────
        for code, pos in positions.items():
            holding = state.holdings.get(code)
            reason = ""
            if holding is None:
                reason = "unmanaged_position"
            else:
                frame = frames.get(code)
                if valid_bars(frame, max(config.atr_period, config.ma_slow) + 1):
                    close = float(frame["close"].iloc[-1])
                    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
                    holding.peak_close = max(holding.peak_close, close)
                    if math.isfinite(atr) and atr > 0:
                        # stops only ever tighten; no intraday fill is assumed
                        holding.stop = max(
                            holding.stop,
                            holding.peak_close - config.trailing_atr * atr,
                        )
                    ma_slow = float(
                        frame["close"].rolling(config.ma_slow).mean().iloc[-1]
                    )
                    if close <= holding.stop:
                        reason = "trailing_stop"
                    elif close >= holding.target:
                        reason = "resistance_target"
                    elif math.isfinite(ma_slow) and close < ma_slow:
                        reason = "trend_break"
                if state.day - holding.entry_day >= config.max_holding_days:
                    reason = reason or "time_exit"
            if halted:
                reason = "portfolio_halt"
            elif eligible is not None and not eligible(code, ctx.current_dt.date()):
                reason = reason or "universe_exit"
            if reason:
                if code not in state.exits:
                    order = api.order_target(position_keys[code], 0)
                    if order is not None:
                        state.exits[code] = order
                        state.exit_reasons[code] = reason
                        event(ctx, "exit_order", code, reason=reason)

        gross = sum(float(pos.value) for pos in positions.values())
        exposure = gross / equity if equity > 0 else 0.0
        if not positions and not state.exits:
            state.flat_days += 1
        api.record(
            total_value=equity,
            cash=float(ctx.portfolio.available_cash),
            ss_exposure=exposure,
            ss_positions=len(positions),
            ss_halted=int(halted),
            ss_risk_mul=state.risk_mul,
        )

        # ── entries: event-driven, any day a pullback setup completes ─────
        if halted or state.exits or equity <= 0:
            return
        slots = config.max_positions - len(positions)
        if slots <= 0:
            return
        cash = float(ctx.portfolio.available_cash)
        plans = []
        for code in codes:
            if code in positions or state.cooldown.get(code, 0) > state.day:
                continue
            if eligible is not None and not eligible(code, ctx.current_dt.date()):
                continue
            frame = frames.get(code)
            # suspended names hand back a stale frame; never signal on it
            if frame is None or len(frame) == 0 or (
                frame.index[-1].date() != ctx.current_dt.date()
            ):
                continue
            if not trend_ok(frame, config):
                continue
            turnover = average_turnover(frame, config)
            if turnover is None or turnover < config.min_avg_turnover:
                continue
            plan = pullback_plan(code, frame, config)
            if plan is None:
                continue
            plans.append(plan)
        # closest close-above-support first when slots are scarce
        plans.sort(key=lambda p: (p.entry - p.support) / max(p.atr, 1e-9))
        for plan in plans[:slots]:
            value = position_value(plan, equity, cash, gross,
                                   state.risk_mul, config)
            if value <= 0:
                continue
            order = api.order_value(plan.code, value)
            if order is None:
                continue
            state.pending_plans[plan.code] = plan
            cash -= value
            gross += value
            state.entries.append(
                dict(date=ctx.current_dt.date().isoformat(),
                     code=plan.code, entry=round(plan.entry, 4),
                     support=round(plan.support, 4), stop=round(plan.stop, 4),
                     target=round(plan.target, 4),
                     reward_risk=round(plan.reward_risk, 3),
                     value=round(value, 2))
            )
            event(ctx, "entry_order", plan.code,
                  support=round(plan.support, 4), stop=round(plan.stop, 4),
                  target=round(plan.target, 4),
                  reward_risk=round(plan.reward_risk, 3),
                  target_value=round(value, 2))

    def initialize(ctx):
        if ctx.frequency != "daily":
            raise ValueError("sr_swing supports daily backtests only")
        api.set_benchmark(benchmark)
        api.set_order_cost(cost)
        api.set_slippage(api.FixedSlippage(pct=config.slippage))
        api.set_option("check_price_limit", True)
        api.set_option("treat_missing_bar_as_suspended", True)
        ctx.universe = list(codes) + [benchmark]
        ctx.sr_swing = _State(high_water=float(ctx.portfolio.total_value))
        api.after_trading_end(on_close)

    return initialize
