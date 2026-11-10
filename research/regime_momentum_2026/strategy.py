"""Regime-filtered cross-sectional momentum for A-share daily research.

Signals are formed in ``after_trading_end`` from *completed* daily bars only;
orders are buffered and filled at a later open by the engine, so no decision
ever uses the price it trades at.

This is a research hypothesis, not evidence of profitability. See PLAN.md for
the pre-registered gate and research/regime_momentum_2026/README.md for the
outcome.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

import numpy as np
import pandas as pd

from eqlib.strategies.ashare_sr_leader import compute_atr
from eqlib.strategies.sr_risk_budget import FIELDS, valid_bars

OPEN_STATUSES = {"pending", "submitted", "partial_fill"}
TRADING_DAYS_PER_YEAR = 244


@dataclass(frozen=True)
class RegimeMomentumConfig:
    """Fixed, unoptimized defaults. Weights refer to current equity."""

    # market regime
    regime_ma: int = 200
    regime_slope_days: int = 20
    use_regime_filter: bool = True
    exit_on_regime_filter: bool = True
    breadth_min: float = 0.0        # 0.0 disables the breadth requirement
    stock_ma: int = 100
    # cross-sectional momentum
    momentum_window: int = 120
    momentum_skip: int = 20
    vol_window: int = 60
    risk_adjusted: bool = False
    require_positive_momentum: bool = True
    # portfolio construction
    top_n: int = 5
    rebalance_days: int = 5
    inverse_vol: bool = False
    max_stock_weight: float = 0.22
    max_exposure: float = 0.95
    # liquidity
    turnover_window: int = 20
    min_avg_turnover: float = 100_000_000.0
    # per-position risk
    atr_period: int = 20
    trailing_atr: float = 3.0
    max_holding_days: int = 120
    cooldown_days: int = 5
    # portfolio risk
    halt_drawdown: float = 0.10
    halt_days: int = 20
    slippage: float = 0.001

    def __post_init__(self):
        booleans = (
            "use_regime_filter",
            "exit_on_regime_filter",
            "risk_adjusted",
            "require_positive_momentum",
            "inverse_vol",
        )
        integers = (
            "regime_ma",
            "regime_slope_days",
            "stock_ma",
            "momentum_window",
            "momentum_skip",
            "vol_window",
            "top_n",
            "rebalance_days",
            "turnover_window",
            "atr_period",
            "max_holding_days",
            "cooldown_days",
            "halt_days",
        )
        for name, value in vars(self).items():
            if name in booleans:
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in integers:
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{name} must be a positive integer")
            elif isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.regime_ma < 20 or self.stock_ma < 20:
            raise ValueError("trend moving averages must span at least 20 bars")
        if self.momentum_window < 20:
            raise ValueError("momentum_window must span at least 20 bars")
        for name in (
            "breadth_min",
            "max_stock_weight",
            "max_exposure",
            "halt_drawdown",
            "slippage",
        ):
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be less than one")
        if self.max_stock_weight > self.max_exposure:
            raise ValueError("single-name weight must not exceed gross exposure")
        if self.max_stock_weight * self.top_n < self.max_exposure * 0.5:
            raise ValueError("top_n cannot deploy the exposure budget")
        if self.trailing_atr <= 0:
            raise ValueError("trailing_atr must be positive")

    @property
    def history_bars(self) -> int:
        """Bars of completed history every decision needs."""
        return max(
            self.regime_ma + self.regime_slope_days + 2,
            self.momentum_window + self.momentum_skip + 2,
            self.stock_ma + 2,
            self.vol_window + 2,
            self.turnover_window + 2,
            self.atr_period + 2,
        )


# ── pure signal functions (unit-testable, no engine state) ────────────────


def regime_state(frame: pd.DataFrame, config: RegimeMomentumConfig) -> dict:
    """Market regime from completed benchmark bars.

    Risk-on means the index closes above its long moving average *and* that
    average is not declining — the second condition keeps the filter from
    flipping on inside a bear-market rally of a falling trend.
    """
    need = config.regime_ma + config.regime_slope_days + 1
    payload = {"risk_on": False, "above_ma": False, "ma_rising": False,
               "ma": None, "close": None}
    if not config.use_regime_filter:
        payload["risk_on"] = True
        payload["above_ma"] = payload["ma_rising"] = True
        return payload
    if not valid_bars(frame, need):
        return payload
    closes = frame["close"].astype(float)
    ma = closes.rolling(config.regime_ma).mean()
    ma_now = float(ma.iloc[-1])
    ma_prev = float(ma.iloc[-1 - config.regime_slope_days])
    close = float(closes.iloc[-1])
    if not all(math.isfinite(v) for v in (ma_now, ma_prev, close)):
        return payload
    above = close > ma_now
    rising = ma_now >= ma_prev
    payload.update(
        risk_on=bool(above and rising),
        above_ma=above,
        ma_rising=rising,
        ma=ma_now,
        close=close,
    )
    return payload


def breadth_ratio(frames: dict, config: RegimeMomentumConfig) -> float:
    """Fraction of the pool closing above its own ``stock_ma``."""
    if config.breadth_min <= 0:
        return 1.0
    observed = 0
    above = 0
    for frame in frames.values():
        if not valid_bars(frame, config.stock_ma + 1):
            continue
        closes = frame["close"].astype(float)
        ma = float(closes.rolling(config.stock_ma).mean().iloc[-1])
        if not math.isfinite(ma):
            continue
        observed += 1
        above += int(float(closes.iloc[-1]) > ma)
    return above / observed if observed else 0.0


def momentum_score(frame: pd.DataFrame, config: RegimeMomentumConfig):
    """Trailing return over ``momentum_window`` ending ``momentum_skip`` bars ago.

    Skipping the most recent month is the standard short-term-reversal
    correction. Returns ``(score, raw_return, annualized_vol)`` or ``None``
    when history is insufficient or prices are non-positive.
    """
    need = config.momentum_window + config.momentum_skip + 1
    if not valid_bars(frame, need):
        return None
    closes = frame["close"].astype(float)
    end = float(closes.iloc[-1 - config.momentum_skip])
    start = float(closes.iloc[-1 - config.momentum_skip - config.momentum_window])
    if start <= 0 or end <= 0:
        return None
    raw = end / start - 1.0
    window = closes.iloc[-config.vol_window - 1:-config.momentum_skip]
    returns = window.pct_change().dropna()
    if len(returns) < 20:
        return None
    vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    if not math.isfinite(vol) or vol <= 0:
        return None
    score = raw / vol if config.risk_adjusted else raw
    if not math.isfinite(score):
        return None
    return score, raw, vol


def average_turnover(frame: pd.DataFrame, config: RegimeMomentumConfig):
    """Mean close*volume over the turnover window, or None."""
    if not valid_bars(frame, config.turnover_window):
        return None
    recent = frame.iloc[-config.turnover_window:]
    value = float((recent["close"] * recent["volume"]).mean())
    return value if math.isfinite(value) and value > 0 else None


def initial_stop(frame: pd.DataFrame, config: RegimeMomentumConfig):
    """ATR trailing stop seeded from the latest completed close."""
    if not valid_bars(frame, config.atr_period + 1):
        return None
    close = float(frame["close"].iloc[-1])
    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
    if not math.isfinite(atr) or atr <= 0:
        return None
    return close - config.trailing_atr * atr


def target_weights(scores: dict, vols: dict, config: RegimeMomentumConfig) -> dict:
    """Map selected names to equity weights, capped by name and in total."""
    if not scores:
        return {}
    if not config.inverse_vol:
        weight = min(config.max_stock_weight, config.max_exposure / len(scores))
        return {code: weight for code in scores}
    inv = {
        code: 1.0 / vols[code]
        for code in scores
        if vols.get(code) and math.isfinite(vols[code]) and vols[code] > 0
    }
    if not inv:
        weight = min(config.max_stock_weight, config.max_exposure / len(scores))
        return {code: weight for code in scores}
    total = sum(inv.values())
    budget = min(config.max_exposure, config.max_stock_weight * len(scores))
    return {code: budget * value / total for code, value in inv.items()}


# ── engine-facing state ───────────────────────────────────────────────────


@dataclass
class _Holding:
    stop: float
    peak_close: float
    entry_day: int
    exit_reason: str = ""


@dataclass
class _State:
    day: int = 0
    high_water: float = 0.0
    halt_until: int | None = None
    holdings: dict = field(default_factory=dict)
    cooldown: dict = field(default_factory=dict)
    exits: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    selections: list = field(default_factory=list)
    regime_on: bool = False
    breadth: float = 0.0
    rebalances: int = 0
    flat_days: int = 0


def make_regime_momentum_strategy(
    universe: list[str],
    config: RegimeMomentumConfig | None = None,
    benchmark: str = "000300.XSHG",
    order_cost=None,
    eligible: Callable[[str, object], bool] | None = None,
):
    """Return an ``initialize`` callback for daily A-share research runs.

    ``eligible(code, date)`` can supply a point-in-time membership/ST filter.
    Without it the universe is explicitly a static, user-selected watchlist;
    no current-name endpoint is used to pretend to know historical status.
    All mutable state lives on the context, so runs stay independent.
    """
    import eqlib as api

    config = config or RegimeMomentumConfig()
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
        ctx.regime_momentum.events.append(
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
            raise RuntimeError("regime-momentum decisions require completed bars")
        state = ctx.regime_momentum
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
        regime = regime_state(market, config)
        state.regime_on = bool(regime["risk_on"])
        state.breadth = breadth_ratio(frames, config)
        market_ok = state.regime_on and state.breadth >= config.breadth_min

        # ── observe fills: new positions get a holding, gone positions cool down
        for code, pos in positions.items():
            if code not in state.holdings:
                stop = initial_stop(frames.get(code, pd.DataFrame()), config)
                close = float(pos.price)
                if stop is None:
                    stop = close * (1 - config.trailing_atr * 0.02)
                state.holdings[code] = _Holding(
                    stop=min(stop, close), peak_close=close, entry_day=state.day
                )
                event(ctx, "entry_filled", code, shares=int(pos.amount),
                      stop=round(state.holdings[code].stop, 4))
        for code in list(state.holdings):
            if code not in positions:
                state.holdings.pop(code)
                state.cooldown[code] = state.day + config.cooldown_days
                event(ctx, "exit_filled", code)
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
            and market_ok
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
                if valid_bars(frame, config.atr_period + 1):
                    close = float(frame["close"].iloc[-1])
                    atr = float(compute_atr(frame, config.atr_period).iloc[-1])
                    holding.peak_close = max(holding.peak_close, close)
                    if math.isfinite(atr) and atr > 0:
                        # stops only ever tighten; no intraday fill is assumed
                        holding.stop = max(
                            holding.stop,
                            holding.peak_close - config.trailing_atr * atr,
                        )
                    if close <= holding.stop:
                        reason = "trailing_stop"
                if state.day - holding.entry_day >= config.max_holding_days:
                    reason = reason or "time_exit"
                reason = holding.exit_reason or reason
            if halted:
                reason = "portfolio_halt"
            elif eligible is not None and not eligible(code, ctx.current_dt.date()):
                reason = reason or "universe_exit"
            elif config.exit_on_regime_filter and not market_ok:
                reason = reason or "regime_filter"
            if reason:
                if holding is not None:
                    holding.exit_reason = reason
                if code not in state.exits:
                    order = api.order_target(position_keys[code], 0)
                    if order is not None:
                        state.exits[code] = order
                        event(ctx, "exit_order", code, reason=reason)

        gross = sum(float(pos.value) for pos in positions.values())
        exposure = gross / equity if equity > 0 else 0.0
        if not positions and not state.exits:
            state.flat_days += 1
        api.record(
            total_value=equity,
            cash=float(ctx.portfolio.available_cash),
            rm_exposure=exposure,
            rm_regime=int(state.regime_on),
            rm_breadth=round(state.breadth, 4),
            rm_drawdown=drawdown,
            rm_halted=int(halted),
            rm_positions=len(positions),
        )

        # ── entries only on rebalance days, and only in a healthy regime ──
        if halted or not market_ok or state.exits or equity <= 0:
            return
        is_rebalance = (
            state.rebalances == 0
            or (state.day - 1) % config.rebalance_days == 0
        )
        if not is_rebalance:
            return

        scored = []
        for code in codes:
            if code in positions or state.cooldown.get(code, 0) > state.day:
                continue
            if eligible is not None and not eligible(code, ctx.current_dt.date()):
                continue
            frame = frames.get(code)
            turnover = average_turnover(frame, config)
            if turnover is None or turnover < config.min_avg_turnover:
                continue
            signal = momentum_score(frame, config)
            if signal is None:
                continue
            score, raw, vol = signal
            if config.require_positive_momentum and raw <= 0:
                continue
            scored.append((code, score, raw, vol))
        # Stable ordering keeps runs reproducible without tuning to returns.
        scored.sort(key=lambda item: (-item[1], item[0]))
        picked = scored[: config.top_n]

        # keep survivors that still rank inside the target set
        ranked = {code for code, *_ in picked}
        for code, pos in positions.items():
            if code in state.exits or code in ranked:
                continue
            reason = "rank_out"
            holding = state.holdings.get(code)
            if holding is not None:
                holding.exit_reason = reason
            order = api.order_target(position_keys[code], 0)
            if order is not None:
                state.exits[code] = order
                event(ctx, "exit_order", code, reason=reason)

        weights = target_weights(
            {code: score for code, score, _, _ in picked},
            {code: vol for code, _, _, vol in picked},
            config,
        )
        state.rebalances += 1
        state.selections.append(
            dict(
                date=ctx.current_dt.date().isoformat(),
                day=state.day,
                breadth=round(state.breadth, 4),
                picks=[
                    {
                        "code": code,
                        "score": round(score, 6),
                        "momentum": round(raw, 6),
                        "vol": round(vol, 6),
                        "weight": round(weights.get(code, 0.0), 6),
                    }
                    for code, score, raw, vol in picked
                ],
            )
        )
        event(ctx, "rebalance", picks=",".join(code for code, *_ in picked) or "-",
              candidates=len(scored), breadth=round(state.breadth, 4))
        for rank, (code, score, raw, vol) in enumerate(picked, 1):
            weight = weights.get(code, 0.0)
            if weight <= 0:
                continue
            value = weight * equity
            order = api.order_target_value(code, value)
            if order is None:
                continue
            event(ctx, "entry_order", code, weight=round(weight, 4),
                  target_value=round(value, 2), score=round(score, 6),
                  momentum=round(raw, 6), rank=rank)

    def initialize(ctx):
        if ctx.frequency != "daily":
            raise ValueError("regime_momentum supports daily backtests only")
        api.set_benchmark(benchmark)
        api.set_order_cost(cost)
        api.set_slippage(api.FixedSlippage(pct=config.slippage))
        api.set_option("check_price_limit", True)
        api.set_option("treat_missing_bar_as_suspended", True)
        ctx.universe = list(codes) + [benchmark]
        ctx.regime_momentum = _State(high_water=float(ctx.portfolio.total_value))
        api.after_trading_end(on_close)

    return initialize
