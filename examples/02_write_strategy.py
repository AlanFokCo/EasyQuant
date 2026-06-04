"""
02 - Writing Your First Strategy
===============================

Demonstrates the core pattern for writing an EasyQuant strategy:
- initialize(context): one-time setup (benchmark, costs, scheduling)
- market_open(context): daily trading logic (data -> signal -> order)
- g object: global state shared across callbacks
- run_daily(): schedule functions to run each trading day

This example implements a dual Moving Average crossover strategy
on a single stock, which is the "Hello World" of quantitative trading.

Teaching Objectives:
    - Strategy lifecycle: initialize -> daily callback
    - The g object for global strategy state
    - attribute_history() for fetching historical data
    - order_value() and order_target() for placing trades
    - record() for charting custom metrics

Expected Output:
    - Strategy initialization messages
    - Buy/sell signals logged during backtest
    - Evaluation panel with Sharpe ratio, max drawdown, etc.

Run:
    python examples/02_write_strategy.py
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

# Why these periods? 5-day and 20-day are standard practitioner
# defaults for short-term and medium-term trends respectively.
# The 5/20 combination captures momentum reversals on a ~2-week lag.
SECURITY = STOCKS["bank"]              # 601398 ICBC
SECURITY_TRADE = STOCKS_TRADE["bank"]  # 601398.XSHG for trading
FAST_PERIOD = 5                        # Short-term moving average
SLOW_PERIOD = 20                       # Long-term moving average


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """One-time strategy setup.

    Called once at the start of the backtest. Use this to:
    - Set the benchmark for performance comparison
    - Configure trading costs
    - Store strategy parameters on the g (global) object
    - Schedule trading functions via run_daily/run_weekly/run_monthly
    """
    # Performance benchmark: CSI 300 index
    set_benchmark(INDEX_HS300)

    # Trading costs — use shared defaults for consistency
    set_order_cost(DEFAULT_ORDER_COST)

    # Store parameters on g (global state object)
    # g persists across all callbacks throughout the backtest
    g.security = SECURITY
    g.security_trade = SECURITY_TRADE
    g.fast_period = FAST_PERIOD
    g.slow_period = SLOW_PERIOD

    # Define the universe (stocks this strategy trades)
    context.universe = [g.security]

    # Schedule the trading function to run every trading day
    run_daily(market_open, time="every_bar")

    log.info("Strategy initialized: MA %d/%d on %s",
             g.fast_period, g.slow_period, g.security)


def market_open(context):
    """Daily trading logic: dual MA crossover.

    Called once per trading day. The workflow is:
    1. Fetch historical data via attribute_history()
    2. Calculate signals (MA crossover)
    3. Execute trades via order_value() or order_target()
    4. Record metrics for charting

    Signal logic:
    - BUY  when fast MA crosses above slow MA (golden cross)
    - SELL when fast MA crosses below slow MA (death cross)
    """
    security = g.security
    security_trade = g.security_trade

    # Step 1: Fetch enough history for the slow MA calculation
    bars_needed = g.slow_period + 5
    hist = attribute_history(security, bars_needed, "1d", ["close"])
    if hist is None or hist.empty or len(hist) < g.slow_period:
        return

    close = hist["close"]
    current_price = close.iloc[-1]

    # Step 2: Calculate moving averages
    fast_ma = close.rolling(g.fast_period).mean()
    slow_ma = close.rolling(g.slow_period).mean()

    if len(fast_ma.dropna()) < 2 or len(slow_ma.dropna()) < 2:
        return

    # Detect crossover: compare today vs yesterday
    prev_fast, curr_fast = fast_ma.iloc[-2], fast_ma.iloc[-1]
    prev_slow, curr_slow = slow_ma.iloc[-2], slow_ma.iloc[-1]

    golden_cross = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    death_cross = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

    # Step 3: Execute trades
    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if golden_cross and not has_position:
        # Buy: invest 95% of available cash (leave buffer for fees)
        cash = context.portfolio.available_cash
        if cash > current_price * 100:
            order_value(security_trade, cash * 0.95)
            log.info("BUY (golden cross): %s @ %.2f, fast=%.2f > slow=%.2f",
                     security, current_price, curr_fast, curr_slow)

    elif death_cross and has_position:
        # Sell: close entire position
        order_target(security_trade, 0)
        log.info("SELL (death cross): %s @ %.2f, fast=%.2f < slow=%.2f",
                 security, current_price, curr_fast, curr_slow)

    # Step 4: Record metrics for charting
    record(
        price=current_price,
        fast_ma=curr_fast,
        slow_ma=curr_slow,
        total_value=context.portfolio.total_value,
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("02 - Writing Your First Strategy (MA Crossover)")
    print("=" * 55)

    # Verify data is available before running
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
        print_evaluation(result, "MA Crossover (5/20)")
