"""
17 - Multi-Factor Stock Selection
==================================

Multi-factor stock selection combining momentum, volume, and
price filters with north-capital sentiment gating. Weekly
rebalancing picks the top-3 stocks from a diversified pool.

Strategy Design Rationale:
    - Why multi-factor: Single-factor strategies (pure momentum
      or pure value) suffer from regime-dependent drawdowns.
      Combining factors reduces single-factor risk.
    - Factor weights: 60% momentum + 40% volume — momentum is the
      stronger factor in A-shares, volume adds confirmation.
    - North-capital gate: Foreign capital flow is a strong sentiment
      indicator in A-shares. Reducing position when 3-day net outflow
      > 10 billion CNY protects against systemic sell-offs.
    - Stock pool: 7 diversified stocks across sectors (bank, liquor,
      EV, pharma, cement, tech, insurance).

Teaching Objectives:
    - Z-score normalization for multi-factor scoring
    - Weekly rebalancing with run_weekly
    - North-capital sentiment as a gating signal
    - Multi-stock portfolio management

Expected Output:
    - Backtest with evaluation panel
    - Weekly rebalance trades logged
    - North-capital sentiment gate activation (if triggered)

Run:
    python examples/17_multi_factor.py
"""

import os

import numpy as np

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_weekly, attribute_history, order_value, order_target,
    record, log, g,
    get_north_money_flow, analyze_returns,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available, print_evaluation,
)


# ============================================================
# Strategy parameters
# ============================================================

# Diversified stock pool across 7 sectors
STOCK_POOL = [STOCKS["bank"], STOCKS["liquor"], STOCKS["ev"],
              STOCKS["pharma"], STOCKS["cement"], STOCKS["tech"],
              STOCKS["insurance"]]
STOCK_POOL_TRADE = [STOCKS_TRADE["bank"], STOCKS_TRADE["liquor"],
                    STOCKS_TRADE["ev"], STOCKS_TRADE["pharma"],
                    STOCKS_TRADE["cement"], STOCKS_TRADE["tech"],
                    STOCKS_TRADE["insurance"]]
STOCK_TO_TRADE = dict(zip(STOCK_POOL, STOCK_POOL_TRADE))

TOP_N = 3              # Buy top-3 stocks each week
LOOKBACK = 20          # Momentum lookback period (trading days)
MOMENTUM_WEIGHT = 0.6  # Factor weight for momentum
VOLUME_WEIGHT = 0.4    # Factor weight for volume

# North-capital sentiment gate
NORTH_OUTFLOW_THRESHOLD = 10  # Reduce position if 3-day net outflow > 10B CNY
POSITION_REDUCE_RATIO = 0.5   # Reduce to 50% position when gate is active


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Multi-factor selection with north-capital sentiment gate."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.stock_pool = STOCK_POOL
    g.stock_to_trade = STOCK_TO_TRADE
    g.top_n = TOP_N
    g.lookback = LOOKBACK
    g.momentum_weight = MOMENTUM_WEIGHT
    g.volume_weight = VOLUME_WEIGHT
    g.sentiment_gate_active = False

    context.universe = STOCK_POOL

    # Weekly rebalance: Monday at market open
    run_weekly(weekly_rebalance, day_of_week=0, time="09:30")

    log.info("Multi-factor strategy: %d stocks, top-%d, weekly rebalance",
             len(STOCK_POOL), TOP_N)


def check_north_sentiment():
    """Check north-capital sentiment gate.

    Returns True if sentiment is bearish (3-day net outflow > threshold).
    When gate is active, positions are reduced.
    """
    try:
        north_df = get_north_money_flow()
        if north_df is not None and not north_df.empty:
            if "net_buy" in north_df.columns:
                net_3d = north_df["net_buy"].tail(3).sum()
                if net_3d < -NORTH_OUTFLOW_THRESHOLD:
                    log.info("NORTH GATE ACTIVE: 3-day outflow %.1fB < -%dB",
                             net_3d, NORTH_OUTFLOW_THRESHOLD)
                    return True
    except Exception as e:
        log.debug("North sentiment check failed: %s", e)
    return False


def score_stocks(context):
    """Score all stocks using Z-score normalized multi-factor.

    Returns list of (code, score) tuples sorted by score descending.
    """
    scores = {}

    for security in g.stock_pool:
        hist = attribute_history(security, g.lookback + 5, "1d",
                             ["close", "volume"])
        if hist is None or hist.empty or len(hist) < g.lookback:
            continue

        close = hist["close"]
        volume = hist["volume"]

        # Factor 1: Momentum (20-day return)
        momentum = (close.iloc[-1] / close.iloc[-g.lookback]) - 1

        # Factor 2: Volume trend (5-day avg / 20-day avg)
        vol_5d = volume.tail(5).mean()
        vol_20d = volume.tail(g.lookback).mean()
        volume_trend = (vol_5d / vol_20d - 1) if vol_20d > 0 else 0

        # Price filter: exclude stocks > 200 or < 3 CNY
        price = close.iloc[-1]
        if price > 200 or price < 3:
            continue

        scores[security] = {
            "momentum": momentum,
            "volume_trend": volume_trend,
            "price": price,
        }

    if not scores:
        return []

    # Z-score normalization across all stocks
    momentums = [s["momentum"] for s in scores.values()]
    vol_trends = [s["volume_trend"] for s in scores.values()]

    mom_mean, mom_std = np.mean(momentums), np.std(momentums)
    vol_mean, vol_std = np.mean(vol_trends), np.std(vol_trends)

    ranked = []
    for code, factors in scores.items():
        mom_z = ((factors["momentum"] - mom_mean) / mom_std
                 if mom_std > 0 else 0)
        vol_z = ((factors["volume_trend"] - vol_mean) / vol_std
                 if vol_std > 0 else 0)

        composite = (g.momentum_weight * mom_z
                     + g.volume_weight * vol_z)
        ranked.append((code, composite))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def weekly_rebalance(context):
    """Weekly rebalance: pick top-N by composite score."""
    # Check sentiment gate
    g.sentiment_gate_active = check_north_sentiment()

    # Score and rank stocks
    ranked = score_stocks(context)
    if not ranked:
        return

    top_picks = [code for code, score in ranked[:g.top_n]]

    log.info("Top picks: %s", [(c, f"{s:.2f}") for c, s in ranked[:g.top_n]])

    # Determine position size (reduced if sentiment gate active)
    total_value = context.portfolio.total_value
    invest_pct = 0.90  # 90% invested normally
    if g.sentiment_gate_active:
        invest_pct *= POSITION_REDUCE_RATIO
        log.info("Sentiment gate: reducing position to %.0f%%",
                 invest_pct * 100)

    target_per_stock = total_value * invest_pct / len(top_picks)

    # Sell stocks not in top picks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in [g.stock_to_trade.get(s) for s in top_picks]:
            order_target(sec, 0)

    # Buy top picks
    for security in top_picks:
        security_trade = g.stock_to_trade.get(security)
        if not security_trade:
            continue

        hist = attribute_history(security, 3, "1d", ["close"])
        if hist is None or hist.empty:
            continue

        current_price = hist["close"].iloc[-1]
        target_shares = int(target_per_stock / current_price / 100) * 100

        if target_shares >= 100:
            order_target(security_trade, target_shares)

    record(total_value=context.portfolio.total_value)


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("17 - Multi-Factor Stock Selection")
    print("=" * 55)

    actual_start, actual_end = verify_data_available(
        STOCK_POOL[0], START_DATE, END_DATE)

    os.makedirs("reports", exist_ok=True)

    result = run_backtest(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH * 2,  # 200K for 7-stock pool
        benchmark=INDEX_HS300,
        securities=STOCK_POOL,
        use_local=True,
    )

    if result:
        print_evaluation(result, "Multi-Factor (momentum+volume, top-3)")
    else:
        print("Backtest failed")
