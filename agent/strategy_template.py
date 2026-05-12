"""Parameterized strategy template (EasyQuant).

Default example strategy for parameter search demos. It implements a dual-MA
crossover with:

  - Volume confirmation
  - ATR-based or fixed stop-loss
  - RSI filter (optional)
  - Market (index) filter (optional)

All tunable knobs live in ``PARAMS`` with bounds in ``PARAM_RANGES`` so scripts such
as ``agent/optimizer.py`` (or your own driver) can vary them across iterations.

To use this as a starting point:

  1. Copy this file.
  2. Adjust ``SECURITIES`` and ``PARAMS`` to match your target.
  3. Implement your logic in ``market_open()``.
  4. Point ``optimizer.py`` or your custom loop at the file and iterate.

Requirement:
  - Keep ``PARAMS`` and ``PARAM_RANGES`` at module level.
  - Read all tunable values from ``PARAMS`` inside ``initialize()`` / ``market_open()``.
"""

from eqlib import *
from eqlib import utils

# ============================================================
# Stock pool — change this to the securities you want to trade
# ============================================================

SECURITIES = ["601390"]   # China Railway (default single-stock template)

# ============================================================
# PARAMS — all tunable strategy parameters
# ============================================================

PARAMS: dict = {
    "fast_period":       5,     # fast MA lookback (days)
    "slow_period":       20,    # slow MA lookback (days)
    "stop_loss_pct":     0.08,  # hard stop-loss fraction (e.g. 0.08 = −8%)
    "position_pct":      1.0,   # fraction of available cash to deploy per buy signal
    "vol_confirm_mul":   1.5,   # volume confirmation multiplier (current vol > N × avg)
    "use_vol_filter":    1,     # 1 = require volume confirmation, 0 = skip
    "use_mkt_filter":    0,     # 1 = require index above its own MA, 0 = skip
}

# ============================================================
# PARAM_RANGES — (min, max, step) for each tunable parameter
# ============================================================

PARAM_RANGES: dict = {
    "fast_period":       (2,   15,   1),
    "slow_period":       (10,  60,   5),
    "stop_loss_pct":     (0.03, 0.15, 0.01),
    "position_pct":      (0.3,  1.0,  0.1),
    "vol_confirm_mul":   (1.0,  3.0,  0.25),
    "use_vol_filter":    (0,    1,    1),
    "use_mkt_filter":    (0,    1,    1),
}

# ============================================================
# Strategy implementation
# ============================================================

BENCHMARK = "000300.XSHG"
MARKET_INDEX = "000300.XSHG"   # used by the market filter


def initialize(context):
    """Strategy initialization.  Reads all parameters from PARAMS."""
    g.security        = SECURITIES[0]
    g.fast_period     = PARAMS["fast_period"]
    g.slow_period     = PARAMS["slow_period"]
    g.stop_loss_pct   = PARAMS["stop_loss_pct"]
    g.position_pct    = PARAMS["position_pct"]
    g.vol_confirm_mul = PARAMS["vol_confirm_mul"]
    g.use_vol_filter  = bool(PARAMS["use_vol_filter"])
    g.use_mkt_filter  = bool(PARAMS["use_mkt_filter"])

    set_benchmark(BENCHMARK)
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = list(SECURITIES)
    run_daily(market_open, time="every_bar")

    log.info(
        "Template strategy init: security=%s fast=%d slow=%d stop=%.2f%% "
        "pos=%.0f%% vol_mul=%.2f vol_filter=%s mkt_filter=%s",
        g.security, g.fast_period, g.slow_period,
        g.stop_loss_pct * 100, g.position_pct * 100,
        g.vol_confirm_mul, g.use_vol_filter, g.use_mkt_filter,
    )


def market_open(context):
    """Daily trading logic — dual-MA crossover with optional filters."""
    security = g.security
    lookback = max(g.slow_period + 5, 30)
    hist = attribute_history(security, lookback, "1d", ["close", "volume"])
    if hist is None or hist.empty or len(hist) < g.slow_period:
        return

    close  = hist["close"]
    volume = hist["volume"]

    price       = close.iloc[-1]
    fast_ma     = close.tail(g.fast_period).mean()
    slow_ma     = close.tail(g.slow_period).mean()
    prev_fast   = close.tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow   = close.tail(g.slow_period + 1).head(g.slow_period).mean()

    # ── Stop-loss check (highest priority) ──────────────────────────────────
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            loss_pct = (price - pos.avg_cost) / pos.avg_cost
            if loss_pct <= -g.stop_loss_pct:
                order_target(security, 0)
                log.info("STOP-LOSS %s @ %.3f  loss=%.1f%%", security, price, loss_pct * 100)
                return

    # ── Market (index) filter ────────────────────────────────────────────────
    if g.use_mkt_filter:
        idx_hist = attribute_history(MARKET_INDEX, g.slow_period + 5, "1d", ["close"])
        if idx_hist is not None and not idx_hist.empty and len(idx_hist) >= g.slow_period:
            idx_ma = idx_hist["close"].tail(g.slow_period).mean()
            idx_price = idx_hist["close"].iloc[-1]
            if idx_price < idx_ma:
                # Market below its own slow MA → avoid new longs
                if security in context.portfolio.positions:
                    order_target(security, 0)
                    log.info("MKT FILTER: index below MA, cleared %s", security)
                return

    # ── Volume confirmation ──────────────────────────────────────────────────
    avg_vol      = volume.tail(20).mean()
    current_vol  = volume.iloc[-1]
    vol_confirmed = (not g.use_vol_filter) or (current_vol >= avg_vol * g.vol_confirm_mul)

    # ── Crossover signals ────────────────────────────────────────────────────
    golden_cross = (prev_fast <= prev_slow) and (fast_ma > slow_ma)
    death_cross  = (prev_fast >= prev_slow) and (fast_ma < slow_ma)

    in_position = (
        security in context.portfolio.positions
        and context.portfolio.positions[security].amount > 0
    )

    if golden_cross and not in_position and vol_confirmed:
        cash = context.portfolio.available_cash
        order_value(security, cash * g.position_pct)
        log.info(
            "GOLDEN CROSS BUY %s @ %.3f  fast=%.3f slow=%.3f vol_ok=%s",
            security, price, fast_ma, slow_ma, vol_confirmed,
        )
    elif death_cross and in_position:
        order_target(security, 0)
        log.info(
            "DEATH CROSS SELL %s @ %.3f  fast=%.3f slow=%.3f",
            security, price, fast_ma, slow_ma,
        )

    record(price=price, fast_ma=fast_ma, slow_ma=slow_ma)
