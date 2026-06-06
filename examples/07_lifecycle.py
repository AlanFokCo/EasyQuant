"""
07 - Strategy Lifecycle Callbacks
==================================

Demonstrates the full strategy lifecycle:
- before_trading_start: pre-market preparation (ST check, news)
- after_trading_end: post-market analysis (portfolio summary)
- set_universe / get_universe: dynamic stock pool management
- run_monthly: monthly rebalance scheduling
- get_extras("is_st"): ST stock detection
- get_trade_days: trading calendar inspection

Teaching Objectives:
    - Lifecycle hooks for pre/post market operations
    - Dynamic universe management (add/remove stocks)
    - ST stock filtering (A-share specific risk)
    - Monthly rebalance scheduling
    - Trading calendar awareness

Expected Output:
    - Pre-market ST stock warnings
    - Post-market portfolio summaries
    - Monthly rebalance trades
    - Trading calendar sample

Run:
    python examples/07_lifecycle.py
"""

import os
from datetime import datetime, timedelta

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_daily, run_monthly,
    before_trading_start, after_trading_end,
    set_universe, get_universe,
    get_extras, get_trade_days,
    attribute_history, order_value, order_target,
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

# Universe: 5 diversified stocks across sectors
UNIVERSE_CODES = [STOCKS["bank"], STOCKS["liquor"], STOCKS["ev"],
                  STOCKS["pharma"], STOCKS["cement"]]
UNIVERSE_TRADE = [STOCKS_TRADE["bank"], STOCKS_TRADE["liquor"],
                  STOCKS_TRADE["ev"], STOCKS_TRADE["pharma"],
                  STOCKS_TRADE["cement"]]


# ============================================================
# Lifecycle callbacks
# ============================================================

def pre_market_check(context, data=None):
    """Pre-market preparation — called before each trading day.

    Checks for ST stocks in the universe and removes them.
    ST (Special Treatment) stocks have abnormal financial
    conditions and carry higher risk of delisting.
    """
    universe = get_universe()

    # Check ST status for all stocks in universe
    try:
        st_info = get_extras("is_st", security_list=universe)
        if st_info:
            for code, is_st in st_info.items():
                if is_st:
                    log.warning("ST stock detected: %s — removing from universe",
                                code)
                    # Remove ST stock from universe
                    new_universe = [s for s in universe if s != code]
                    set_universe(new_universe)
    except Exception as e:
        log.debug("ST check skipped: %s", e)


def post_market_summary(context, data=None):
    """Post-market analysis — called after each trading day.

    Logs portfolio summary for monitoring.
    """
    portfolio = context.portfolio
    positions = portfolio.positions

    if positions:
        pos_summary = []
        for sec, pos in positions.items():
            if pos.amount > 0:
                pos_summary.append(f"{sec}:{pos.amount}")
        if pos_summary:
            log.info("EOD positions: %s | cash: %.0f | total: %.0f",
                     ", ".join(pos_summary),
                     portfolio.available_cash,
                     portfolio.total_value)


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Strategy initialization with lifecycle hooks."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    # Set initial universe
    set_universe(UNIVERSE_CODES)
    g.universe_trade = dict(zip(UNIVERSE_CODES, UNIVERSE_TRADE))

    # Register lifecycle callbacks
    before_trading_start(pre_market_check)
    after_trading_end(post_market_summary)

    # Schedule daily trading logic
    run_daily(daily_trade, time="every_bar")

    # Schedule monthly rebalance on the 1st of each month
    run_monthly(monthly_rebalance, day_of_month=1, time="09:30")

    log.info("Lifecycle strategy initialized: %d stocks, monthly rebalance",
             len(UNIVERSE_CODES))


def daily_trade(context):
    """Daily trading logic: simple momentum filter.

    Only trades if the stock's 5-day return is positive.
    Actual position sizing is handled by monthly_rebalance.
    """
    universe = get_universe()

    for security in universe:
        security_trade = g.universe_trade.get(security)
        if not security_trade:
            continue

        hist = attribute_history(security, 10, "1d", ["close"])
        if hist is None or hist.empty or len(hist) < 5:
            continue

        close = hist["close"]
        ret_5d = (close.iloc[-1] / close.iloc[-5]) - 1

        has_position = (security_trade in context.portfolio.positions
                        and context.portfolio.positions[security_trade].amount > 0)

        # Sell if 5-day momentum turns negative
        if ret_5d < -0.05 and has_position:
            order_target(security_trade, 0)
            log.info("Momentum SELL: %s, 5d return=%.1f%%",
                     security, ret_5d * 100)

    record(total_value=context.portfolio.total_value)


def monthly_rebalance(context):
    """Monthly rebalance: equal-weight allocation across universe.

    Called on the 1st of each month. Rebalances all positions
    to equal weight, adding new positions and trimming overweight.
    """
    universe = get_universe()
    if not universe:
        return

    # Calculate target allocation per stock
    total_value = context.portfolio.total_value
    target_per_stock = total_value * 0.90 / len(universe)  # 90% invested

    for security in universe:
        security_trade = g.universe_trade.get(security)
        if not security_trade:
            continue

        hist = attribute_history(security, 5, "1d", ["close"])
        if hist is None or hist.empty:
            continue

        current_price = hist["close"].iloc[-1]
        if current_price <= 0:
            continue

        # Calculate target shares
        target_shares = int(target_per_stock / current_price / 100) * 100
        if target_shares >= 100:
            order_target(security_trade, target_shares)

    log.info("Monthly rebalance: %d stocks, target %.0f each",
             len(universe), target_per_stock)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("07 - Strategy Lifecycle Callbacks")
    print("=" * 55)

    # Demo: inspect trading calendar
    print("\n--- Trading Calendar (get_trade_days) ---")
    today = datetime.now().date()
    month_ago = today - timedelta(days=30)
    trade_days = get_trade_days(start_date=month_ago, end_date=today)
    print(f"  Trading days in last 30 days: {len(trade_days)}")
    if trade_days:
        print(f"  First: {trade_days[0]}, Last: {trade_days[-1]}")
    print()

    # Demo: universe management
    print("--- Universe Management ---")
    print(f"  Initial universe: {UNIVERSE_CODES}")
    print(f"  Trade codes: {UNIVERSE_TRADE}")
    print()

    # Run backtest
    actual_start, actual_end = verify_data_available(
        UNIVERSE_CODES[0], START_DATE, END_DATE)

    os.makedirs("reports", exist_ok=True)

    result = run_backtest(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH * 2,  # 200K for 5-stock portfolio
        benchmark=INDEX_HS300,
        securities=UNIVERSE_CODES,
        use_local=True,
    )

    if result:
        print_evaluation(result, "Lifecycle Strategy (5 stocks, monthly rebalance)")
    else:
        print("Backtest failed")
