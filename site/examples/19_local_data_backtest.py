"""Example 19: Local Data Mode — download once, backtest offline.

Demonstrates the use_local parameter for local data management:
- First run: downloads data from network, saves to local CSV
- Subsequent runs: loads from local CSV, no network needed
- Manual data management: list, download, and remove local data

This is useful when:
- You want to backtest without internet connection
- You want to save time by reusing downloaded data
- You want to manage your own historical data files
- You want to backtest with specific data versions

Usage:
    # First run — downloads data and backtests
    python examples/19_local_data_backtest.py

    # Second run — uses local data only (no network)
    python examples/19_local_data_backtest.py

    # List your local data files
    python examples/19_local_data_backtest.py --list

    # Pre-download data for many stocks
    python examples/19_local_data_backtest.py --download-all
"""

import os
import sys
from eqlib import *


# ============================================================
# Strategy parameters
# ============================================================

SECURITY = "000768"
FAST_PERIOD = 5
SLOW_PERIOD = 20


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    g.security = SECURITY
    g.fast_period = FAST_PERIOD
    g.slow_period = SLOW_PERIOD
    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))
    context.universe = [g.security]
    run_daily(market_open, time="every_bar")


def market_open(context):
    hist = attribute_history(g.security, g.slow_period + 10, "1d", ["close"])
    if hist.empty or len(hist) < g.slow_period:
        return

    price = hist["close"].iloc[-1]
    ma_fast = hist["close"].tail(g.fast_period).mean()
    ma_slow = hist["close"].tail(g.slow_period).mean()

    if price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
            log.info("BUY %s @ %.3f" % (g.security, price))
    elif price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
            log.info("SELL %s @ %.3f" % (g.security, price))

    record(price=price, ma_fast=ma_fast, ma_slow=ma_slow)


# ============================================================
# Demo helpers
# ============================================================

def demo_local_data_info():
    """Show local data management utilities."""
    print("\n--- Local Data Management Demo ---\n")

    # Check if we have local data
    has_data = has_local_data(SECURITY)
    print("Has local data for %s: %s" % (SECURITY, has_data))

    # List all local stocks
    local_stocks = list_local_stocks()
    if local_stocks:
        print("Local stocks available: %s" % local_stocks)
    else:
        print("No local data found yet.")

    # Show where data is stored
    from eqlib.data_cache import _get_local_data_dir
    data_dir = _get_local_data_dir()
    print("Local data directory: %s" % data_dir)
    print()


def demo_download_all():
    """Pre-download data for a batch of stocks."""
    stocks = [SECURITY, "600519", "000858", "600036", "000001"]
    print("\nDownloading data for %d stocks..." % len(stocks))

    for sec in stocks:
        path = save_stock_local(sec)
        if path:
            print("  Downloaded %s -> %s" % (sec, path))
        else:
            print("  Failed to download %s" % sec)

    print("\nAll local stocks: %s" % list_local_stocks())
    print()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    if "--list" in sys.argv:
        demo_local_data_info()
        sys.exit(0)

    if "--download-all" in sys.argv:
        demo_download_all()
        sys.exit(0)

    # Show local data status before backtest
    demo_local_data_info()

    print("=" * 60)
    print("Local Data Backtest")
    print("=" * 60)
    print("use_local=True: will load from local CSV if available,")
    print("                download and save if not.")
    print()

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize,
        start_date="2024-01-01",
        end_date="2024-12-31",
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=[SECURITY],
        report_dir="reports",
        use_local=True,  # <-- Enable local data mode
    )

    # Show local data status after backtest
    print()
    print("--- After Backtest ---")
    print("Local stocks now: %s" % list_local_stocks())
