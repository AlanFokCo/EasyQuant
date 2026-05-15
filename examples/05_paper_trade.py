"""Example 5: Paper trading (live simulation).

Demonstrates how to run paper trading with eqlib.
The paper trader:
1. Connects to real-time market data
2. Automatically executes buy/sell on strategy signals
3. Tracks positions and P&L
4. Does NOT send real trades

Usage:
    # Use built-in strategy
    python examples/05_paper_trade.py

    # Specify a strategy file
    python examples/05_paper_trade.py --strategy examples/02_write_strategy

    # Custom parameters
    python examples/05_paper_trade.py --cash 200000 --interval 120

Note: The paper trader runs indefinitely until stopped with Ctrl+C.
"""

import argparse
import importlib.util
import os
import sys
from eqlib import *


def load_strategy(path):
    """Load a strategy module from a file."""
    if not path.endswith(".py"):
        path += ".py"
    if not os.path.exists(path):
        print(f"Strategy file not found: {path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("strategy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(strategy_path=None, cash=100000, interval=60):
    """Start paper trading."""

    if strategy_path:
        mod = load_strategy(strategy_path)
        if not hasattr(mod, "initialize"):
            print("Strategy file is missing initialize(context) function")
            sys.exit(1)
        init_func = mod.initialize
    else:
        init_func = ma_initialize

    log.info("=" * 60)
    log.info("Paper Trading Started")
    log.info(f"Initial capital: {cash:,.0f}")
    log.info(f"Polling interval: {interval}s")
    log.info("Press Ctrl+C to stop")
    log.info("=" * 60)

    run_paper_trade(
        initialize_func=init_func,
        starting_cash=cash,
        interval=interval,
    )


# ============================================================
# Built-in strategy: Moving Average Crossover
# ============================================================

def ma_initialize(context):
    """MA crossover strategy initialization."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(ma_on_bar, time="every_bar")

    log.info("Paper trading strategy: MA crossover %s MA%d/MA%d" % (
        g.security, g.fast_period, g.slow_period))


def ma_on_bar(context):
    """MA crossover strategy - execute every bar."""
    security = g.security
    close_data = attribute_history(security, 25, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = close_data["close"].tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close_data["close"].tail(g.slow_period + 1).head(g.slow_period).mean()

    # Golden cross: buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("Paper BUY: %s @ %.3f" % (security, current_price))

    # Death cross: sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Paper SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma,
           total_value=context.portfolio.total_value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper trading")
    parser.add_argument("--strategy", default=None,
                        help="Strategy file path (without .py)")
    parser.add_argument("--cash", type=float, default=100000,
                        help="Initial capital (default 100000)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Quote polling interval in seconds (default 60)")
    args = parser.parse_args()

    run(
        strategy_path=args.strategy,
        cash=args.cash,
        interval=args.interval,
    )
