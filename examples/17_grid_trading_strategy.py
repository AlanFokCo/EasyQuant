"""Example 17: Grid Trading Strategy.

Demonstrates a grid trading strategy for range-bound markets:
- Set a price range and divide it into N grid levels
- Buy one batch when price drops to a grid level
- Sell one batch when price rises to a grid level
- Profit from price oscillation within the range

Best for low-volatility stocks that trade in a range (e.g. bank stocks).

Usage:
    python examples/17_grid_trading_strategy.py

⚠️  RISK DISCLOSURE — TEACHING EXAMPLE ONLY
    This script is provided for educational purposes to demonstrate the
    EasyQuant backtesting framework.  Do NOT deploy this strategy to live
    trading without thorough out-of-sample validation.  Past backtest
    performance does NOT guarantee future results.  Grid strategies carry
    significant gap risk in trending or highly volatile markets.
"""

import os
from eqlib import *


# ============================================================
# Strategy parameters
# ============================================================

SECURITY = "601857"           # PetroChina 中国石油
GRID_LEVELS = 10              # Number of grid lines
GRID_RANGE_PCT = 0.15         # Grid range: +/- 15% from center price
TRADE_VALUE = 10000           # Each trade: 10,000 yuan


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

    context.universe = [SECURITY]
    run_daily(market_open, time="every_bar")

    # Grid state
    g.grid_initialized = False
    g.grid_prices = []
    g.grid_holding = {}          # {grid_index: bool} whether we hold at this level
    g.last_grid_idx = None       # Last grid level where we traded
    g.trade_count = 0

    log.info("Grid Trading init: %s, levels=%d, range=+/%.0f%%" % (
        SECURITY, GRID_LEVELS, GRID_RANGE_PCT * 100))


def build_grid(center_price):
    """Build grid price levels."""
    lower = center_price * (1 - GRID_RANGE_PCT)
    upper = center_price * (1 + GRID_RANGE_PCT)
    step = (upper - lower) / GRID_LEVELS

    g.grid_prices = [lower + step * i for i in range(GRID_LEVELS + 1)]

    # Pre-fill: assume we buy at the initial price level
    init_idx = _find_level(center_price)
    g.grid_holding = {i: False for i in range(len(g.grid_prices))}
    g.grid_holding[init_idx] = True
    g.last_grid_idx = init_idx

    log.info("Grid built: %.3f .. %.3f (step=%.3f), start level=%d" % (
        g.grid_prices[0], g.grid_prices[-1], step, init_idx))


def _find_level(price):
    """Find closest grid level index."""
    best = 0
    best_d = abs(price - g.grid_prices[0])
    for i, p in enumerate(g.grid_prices):
        d = abs(price - p)
        if d < best_d:
            best_d = d
            best = i
    return best


def market_open(context):
    """Daily trading logic."""
    security = SECURITY

    hist = attribute_history(security, 5, "1d", ["close"])
    if hist.empty:
        return

    price = hist["close"].iloc[-1]

    # Build grid on first bar
    if not g.grid_initialized:
        build_grid(price)
        # Initial position: buy at center price
        order_value(security, TRADE_VALUE * 5)
        g.grid_initialized = True
        log.info("Initial position: BUY %s @ %.3f" % (security, price))
        return

    grid_idx = _find_level(price)

    # Price dropped to a new lower grid level -> BUY one batch
    if grid_idx < g.last_grid_idx:
        order_value(security, TRADE_VALUE)
        g.grid_holding[grid_idx] = True
        g.trade_count += 1
        log.info("Grid BUY level %d: %s @ %.3f" % (grid_idx, security, price))
        g.last_grid_idx = grid_idx

    # Price rose to a new higher grid level -> SELL one batch
    elif grid_idx > g.last_grid_idx:
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount >= 100:
            order(security, -100)
            g.trade_count += 1
            log.info("Grid SELL level %d: %s @ %.3f" % (grid_idx, security, price))
            g.last_grid_idx = grid_idx

    record(price=price, grid_level=grid_idx,
           total_value=context.portfolio.total_value,
           trades=g.trade_count)


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Grid Trading Strategy")
    print("=" * 60)
    print("Stock: %s" % SECURITY)
    print("Grid levels: %d" % GRID_LEVELS)
    print("Range: +/-%.0f%%" % (GRID_RANGE_PCT * 100))
    print("Trade size: %.0f yuan/grid" % TRADE_VALUE)
    print()

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2025-01-01",
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=["601857"],
        report_dir="reports",
        use_local=True,
    )
