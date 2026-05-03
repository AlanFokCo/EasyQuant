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

from eqlib import *


# ============================================================
# Strategy parameters
# ============================================================

g.stock_pool = [
    # A diversified set of A-share stocks for testing
    "601390",  # ICBC (banking)
    "600519",  # Kweichow Moutai (liquor)
    "000858",  # Wuliangye (liquor)
    "600036",  # China Merchants Bank (banking)
    "000001",  # Ping An Bank (banking)
    "601318",  # Ping An Insurance (insurance)
    "600276",  # Hengrui Pharma (pharma)
    "000333",  # Midea Group (appliances)
    "600887",  # Yili Industrial (dairy)
    "000651",  # Gree Electric (appliances)
]
g.top_n = 3                     # Pick top 3 stocks each week
g.lookback = 20                 # Momentum lookback period (days)
g.min_price = 3.0               # Minimum stock price (avoid penny stocks)
g.max_price = 200.0             # Maximum stock price


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

    context.universe = g.stock_pool
    # Rebalance every Monday
    run_weekly(rebalance, day_of_week=0, time="every_bar")

    log.info("Multi-factor init: pool=%d stocks, pick top %d" % (
        len(g.stock_pool), g.top_n))


def score_stocks(context):
    """Score all stocks in the pool using multiple factors.

    Returns a list of (security, score) sorted by score descending.
    """
    scores = {}

    for sec in g.stock_pool:
        hist = attribute_history(sec, g.lookback + 10, "1d",
                                 ["close", "volume"])
        if hist.empty or len(hist) < g.lookback:
            continue

        close_prices = hist["close"]
        volumes = hist["volume"]
        current_price = close_prices.iloc[-1]

        # --- Price filter ---
        if current_price < g.min_price or current_price > g.max_price:
            continue

        # --- Momentum factor (20-day return) ---
        past_price = close_prices.iloc[-g.lookback]
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

    top_stocks = [sec for sec, score in ranked[:g.top_n]]

    log.info("Weekly rebalance: top %d = %s" % (g.top_n, top_stocks))

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
    print("Stock pool: %d stocks" % len(g.stock_pool))
    print("Top picks per week: %d" % g.top_n)
    print("Momentum lookback: %d days" % g.lookback)
    print()

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2025-01-01",
        starting_cash=200000,
        benchmark="000300.XSHG",
        securities=g.stock_pool,
        report_dir="reports",
    )
