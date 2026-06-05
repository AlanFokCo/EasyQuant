"""
18 - Grid Trading Strategy
===========================

Grid trading for range-bound markets: divide the price range
into equal intervals (grid levels), buy at each lower level
and sell at each upper level. Profits from oscillation without
predicting direction.

Strategy Design Rationale:
    - Why grid: Works well on stocks that oscillate within a range.
      601398 (ICBC) historically trades within tight ranges due to
      its large market cap and institutional ownership.
    - Grid construction: Uses recent 60-day high/low to define the
      range, divided into 10 equal intervals.
    - Position sizing: Each grid trade uses 1/N of total capital,
      preventing over-concentration at any single level.
    - Applicable: Range-bound, high-liquidity stocks.
    - Not applicable: Strong trending markets (grid runs out of
      capital in downtrends or misses upside in uptrends).

Teaching Objectives:
    - Grid level construction from price range
    - Grid state management (which levels are filled)
    - Proportional position sizing per grid level
    - Range-bound market detection

Expected Output:
    - Backtest with evaluation panel
    - Grid trade log showing level-based buy/sell
    - Multiple small-profit trades

Run:
    python examples/18_grid_trading.py
"""

import os

from eqlib import (
    run_strategy, set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, log, g,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available, print_evaluation,
)


# ============================================================
# Strategy parameters
# ============================================================

# ICBC: large-cap, range-bound, high liquidity
SECURITY = STOCKS["bank"]
SECURITY_TRADE = STOCKS_TRADE["bank"]

# Grid: 10 levels across the recent price range
GRID_LEVELS = 10
RANGE_LOOKBACK = 60  # Use 60-day high/low to define range
RANGE_BUFFER = 0.02  # 2% buffer above high / below low

# Each grid trade uses this fraction of capital
CAPITAL_PER_GRID = 1.0 / (GRID_LEVELS + 2)  # Leave buffer


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Grid trading with dynamic range detection."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = SECURITY
    g.security_trade = SECURITY_TRADE
    g.grid_levels = GRID_LEVELS
    g.range_lookback = RANGE_LOOKBACK
    g.range_buffer = RANGE_BUFFER
    g.capital_per_grid = CAPITAL_PER_GRID

    # Grid state
    g.grid_prices = None     # List of grid level prices
    g.grid_filled = None     # Boolean list: which levels have positions
    g.range_high = None
    g.range_low = None

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Grid strategy: %d levels, %d-day range",
             GRID_LEVELS, RANGE_LOOKBACK)


def build_grid(high, low):
    """Build grid levels between high and low with buffer."""
    buffered_high = high * (1 + g.range_buffer)
    buffered_low = low * (1 - g.range_buffer)

    if buffered_low <= 0:
        return None, None, None

    step = (buffered_high - buffered_low) / g.grid_levels
    grid_prices = [buffered_low + i * step for i in range(g.grid_levels + 1)]
    grid_filled = [False] * (g.grid_levels + 1)

    return grid_prices, grid_filled, (buffered_high, buffered_low)


def find_grid_level(price, grid_prices):
    """Find which grid level the current price is nearest to."""
    if not grid_prices:
        return -1
    min_dist = float("inf")
    nearest = -1
    for i, gp in enumerate(grid_prices):
        dist = abs(price - gp)
        if dist < min_dist:
            min_dist = dist
            nearest = i
    return nearest


def market_open(context):
    """Grid trading logic: buy at lower levels, sell at upper levels."""
    security = g.security
    security_trade = g.security_trade

    # Fetch price history for range calculation
    hist = attribute_history(security, g.range_lookback + 5, "1d",
                         ["high", "low", "close"])
    if hist is None or hist.empty or len(hist) < g.range_lookback:
        return

    current_price = hist["close"].iloc[-1]
    range_high = hist["high"].tail(g.range_lookback).max()
    range_low = hist["low"].tail(g.range_lookback).min()

    # Build or update grid
    if g.grid_prices is None or range_high != g.range_high or range_low != g.range_low:
        g.grid_prices, g.grid_filled, (g.range_high, g.range_low) = build_grid(
            range_high, range_low)
        if g.grid_prices is None:
            return

    # Find current grid level
    level = find_grid_level(current_price, g.grid_prices)
    if level < 0:
        return

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    # Calculate trade value per grid level
    total_value = context.portfolio.total_value
    trade_value = total_value * g.capital_per_grid

    # === Buy: price drops to a grid level that isn't filled ===
    if not g.grid_filled[level] and level < len(g.grid_prices) // 2:
        # Only buy at lower half of grid (below midpoint)
        cash = context.portfolio.available_cash
        if cash > trade_value * 0.5:
            order_value(security_trade, min(trade_value, cash * 0.95))
            g.grid_filled[level] = True
            log.info("GRID BUY: level %d @ %.2f (grid=%.2f)",
                     level, current_price, g.grid_prices[level])

    # === Sell: price rises to a filled grid level above current ===
    elif g.grid_filled[level] and level > len(g.grid_prices) // 2:
        # Only sell at upper half of grid (above midpoint)
        if has_position:
            position = context.portfolio.positions[security_trade]
            # Sell proportional to grid level
            sell_shares = max(100, (position.amount // g.grid_levels) * 100 // 100 * 100)
            if sell_shares > 0 and sell_shares <= position.amount:
                order_target(security_trade, position.amount - sell_shares)
                g.grid_filled[level] = False
                log.info("GRID SELL: level %d @ %.2f (grid=%.2f)",
                         level, current_price, g.grid_prices[level])

    # Record for charting
    mid_price = g.grid_prices[len(g.grid_prices) // 2] if g.grid_prices else 0
    record(
        price=current_price,
        range_high=g.range_high,
        range_low=g.range_low,
        grid_mid=mid_price,
        total_value=context.portfolio.total_value,
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("18 - Grid Trading Strategy")
    print("=" * 55)

    actual_start, actual_end = verify_data_available(
        SECURITY, START_DATE, END_DATE)

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[SECURITY],
        report_dir="reports",
        use_local=True,
    )

    if result:
        print_evaluation(result, "Grid Trading (10 levels)")
