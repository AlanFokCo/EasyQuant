"""Example 16: Multi-Factor Stock Selection Strategy.

Demonstrates a quantitative stock selection strategy that combines
multiple factors to pick stocks and rebalance weekly:
- Momentum factor: past 20-day return
- Volume factor: recent volume vs. average
- Price factor: stock price range filter (avoid penny stocks and very high-priced)

Each Monday, the strategy selects top-N stocks and equal-weights the portfolio.

Usage:
    python examples/16_multi_factor_strategy.py
"""

import os
from eqlib import *


# ============================================================
# Strategy parameters
# ============================================================

STOCK_POOL = [
    # A diversified set of A-share stocks for testing
    "601390",  # China Railway 中国中铁
    "600036",  # China Merchants Bank 招商银行
    "000630",  # Tongling Nonferrous 铜陵有色
    "518880",  # Gold ETF 黄金ETF
    "601088",  # China Shenhua 中国神华
    "601857",  # PetroChina 中国石油
    "002594",  # BYD 比亚迪
    "000768",  # AVIC Jonhon Optronic 中航光电
    "600536",  # China National Software 中国软件
    "601111",  # Air China 中国国航
]
TOP_N = 3                     # Pick top 3 stocks each week
LOOKBACK = 20                 # Momentum lookback period (days)
MIN_PRICE = 3.0               # Minimum stock price (avoid penny stocks)
MAX_PRICE = 200.0             # Maximum stock price


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Strategy initialization."""
    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = STOCK_POOL
    # Rebalance every Monday
    run_weekly(rebalance, day_of_week=0, time="every_bar")

    log.info("Multi-factor init: pool=%d stocks, pick top %d" % (
        len(STOCK_POOL), TOP_N))


def score_stocks(context):
    """Score all stocks in the pool using multiple factors.

    Returns a list of (security, score) sorted by score descending.
    """
    scores = {}

    for sec in STOCK_POOL:
        hist = attribute_history(sec, LOOKBACK + 10, "1d",
                                 ["close", "volume"])
        if hist.empty or len(hist) < LOOKBACK:
            continue

        close_prices = hist["close"]
        volumes = hist["volume"]
        current_price = close_prices.iloc[-1]

        # --- Price filter ---
        if current_price < MIN_PRICE or current_price > MAX_PRICE:
            continue

        # --- Momentum factor (20-day return) ---
        past_price = close_prices.iloc[-LOOKBACK]
        if past_price <= 0:
            continue
        momentum = (current_price - past_price) / past_price

        # --- Volume factor (recent volume vs. longer average) ---
        vol_5 = volumes.tail(5).mean()
        vol_20 = volumes.tail(20).mean()
        volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

        # --- Composite score ---
        # Weight: 70% momentum + 30% volume
        composite_score = momentum * 0.7 + (volume_ratio - 1.0) * 0.3

        scores[sec] = composite_score

    # Sort by score, highest first
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


def rebalance(context):
    """Weekly rebalance: sell bottom stocks, buy top stocks."""
    ranked = score_stocks(context)
    if not ranked:
        log.info("No stocks pass screening this week")
        return

    top_stocks = [sec for sec, score in ranked[:TOP_N]]

    log.info("Weekly rebalance: top %d = %s" % (TOP_N, top_stocks))

    # === Sell stocks not in top N ===
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            position = context.portfolio.positions[sec]
            if position.amount > 0:
                order_target(sec, 0)
                log.info("  SELL %s (ranked out)" % sec)

    # === Equal-weight buy top N stocks ===
    if not top_stocks:
        return

    per_stock_cash = context.portfolio.available_cash / len(top_stocks)
    for sec in top_stocks:
        if per_stock_cash < 1000:
            continue
        # If we already hold this stock, skip (it's already allocated)
        if sec in context.portfolio.positions and \
           context.portfolio.positions[sec].amount > 0:
            continue
        order_value(sec, per_stock_cash)
        log.info("  BUY %s, amount=%.0f" % (sec, per_stock_cash))

    # Record portfolio state
    record(
        total_value=context.portfolio.total_value,
        num_holdings=len([
            s for s, p in context.portfolio.positions.items()
            if p.amount > 0
        ]),
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Factor Stock Selection Strategy")
    print("=" * 60)
    print("Stock pool: %d stocks" % len(STOCK_POOL))
    print("Top picks per week: %d" % TOP_N)
    print("Momentum lookback: %d days" % LOOKBACK)
    print()

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2025-01-01",
        starting_cash=200000,
        benchmark="000300.XSHG",
        securities=STOCK_POOL,
        report_dir="reports",
        use_local=True,
    )
