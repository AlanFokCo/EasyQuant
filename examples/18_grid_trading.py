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
    - Grid construction: Uses recent 30-day high/low to define the
      range, divided into 8 equal intervals (9 levels).
    - Trigger logic: Track the grid level the price was in last bar.
      When price crosses DOWN to a lower level, buy (dip-buying at
      grid support). When price crosses UP to a higher level, sell
      (profit-taking at grid resistance). This is the canonical
      grid-trading pattern — every crossing generates a trade.
    - Grid stability: Range is rebuilt only when 30-day high/low
      shifts by more than 5%, so grid_filled state is not wiped
      out by daily noise.
    - Position sizing: Each grid trade uses 1/N of total capital,
      preventing over-concentration at any single level.
    - Applicable: Range-bound, high-liquidity stocks.
    - Not applicable: Strong trending markets (grid runs out of
      capital in downtrends or misses upside in uptrends).

Teaching Objectives:
    - Grid level construction from price range
    - Level-crossing detection (last_level vs current_level)
    - Stable grid rebuild (only on significant range shift)
    - Proportional position sizing per grid trade

Expected Output:
    - Backtest with evaluation panel
    - Grid trade log showing level-crossing buy/sell
    - Multiple small-profit round-trip trades

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

# Grid: 8 intervals (9 levels) across the recent 30-day price range
GRID_LEVELS = 8
RANGE_LOOKBACK = 30  # Use 30-day high/low to define range
RANGE_BUFFER = 0.02  # 2% buffer above high / below low
REBUILD_THRESHOLD = 0.05  # Rebuild grid only if range shifts >5%

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
    g.rebuild_threshold = REBUILD_THRESHOLD
    g.capital_per_grid = CAPITAL_PER_GRID

    # Grid state
    g.grid_prices = None     # List of grid level prices
    g.range_high = None
    g.range_low = None
    g.last_level = None      # Last bar's grid level (for crossing detection)

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Grid strategy: %d levels, %d-day range",
             GRID_LEVELS, RANGE_LOOKBACK)


def build_grid(high, low):
    """Build grid levels between high and low with buffer."""
    buffered_high = high * (1 + g.range_buffer)
    buffered_low = low * (1 - g.range_buffer)

    if buffered_low <= 0:
        return None, None

    step = (buffered_high - buffered_low) / g.grid_levels
    grid_prices = [buffered_low + i * step for i in range(g.grid_levels + 1)]

    return grid_prices, (buffered_high, buffered_low)


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
    """Grid trading logic: buy on downward crossings, sell on upward crossings."""
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

    # Build grid on first run, or rebuild only if range has shifted significantly
    need_rebuild = (
        g.grid_prices is None
        or g.range_high is None
        or abs(range_high - g.range_high) / g.range_high > g.rebuild_threshold
        or abs(range_low - g.range_low) / (g.range_low or range_low) > g.rebuild_threshold
    )
    if need_rebuild:
        g.grid_prices, (g.range_high, g.range_low) = build_grid(range_high, range_low)
        g.last_level = None  # Reset crossing tracker after rebuild
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

    # First bar after rebuild: just record level, no trade
    if g.last_level is None:
        g.last_level = level
    else:
        # Price crossed DOWN to a lower level → BUY (dip at grid support)
        if level < g.last_level:
            cash = context.portfolio.available_cash
            if cash > trade_value * 0.5:
                buy_value = min(trade_value, cash * 0.9)
                order_value(security_trade, buy_value)
                log.info("GRID BUY: level %d→%d @ %.2f (grid=%.2f)",
                         g.last_level, level, current_price, g.grid_prices[level])

        # Price crossed UP to a higher level → SELL (profit at grid resistance)
        elif level > g.last_level and has_position:
            position = context.portfolio.positions[security_trade]
            sell_value = min(trade_value, position.value * 0.5)
            if sell_value > 0:
                order_value(security_trade, -sell_value)
                log.info("GRID SELL: level %d→%d @ %.2f (grid=%.2f)",
                         g.last_level, level, current_price, g.grid_prices[level])

        g.last_level = level

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
        print_evaluation(result, "Grid Trading (8 levels)")
