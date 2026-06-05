"""
06 - Local Data Management
==========================

Demonstrates downloading, caching, and using local stock data.
Local data avoids repeated network calls to akshare, making
repeated backtests much faster.

Teaching Objectives:
    - save_stock_local(): download and cache data as local CSV
    - has_local_data(): check if a stock has cached data
    - list_local_stocks(): list all cached stocks
    - use_local=True: run backtest using cached data
    - Batch download workflow for multiple stocks

Expected Output:
    - Local CSV files saved for demo stocks
    - Cache inventory listing
    - Backtest completes using local data (no network calls)

Run:
    python examples/06_local_data.py
    python examples/06_local_data.py --list          # list cached stocks
    python examples/06_local_data.py --download 601398  # download specific
"""

import argparse
import os
from datetime import datetime, timedelta

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, g,
    save_stock_local, has_local_data, list_local_stocks,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available, print_evaluation,
)


# ============================================================
# Local data management demos
# ============================================================

def demo_save_local():
    """Download stock data and save to local CSV cache.

    save_stock_local() fetches data from akshare and saves it
    as a local CSV file. Subsequent backtests with use_local=True
    will read from this cache instead of hitting the network.
    """
    print("--- Save Local Data ---")

    for name, code in [("ICBC", STOCKS["bank"]),
                       ("Moutai", STOCKS["liquor"]),
                       ("BYD", STOCKS["ev"])]:
        try:
            path = save_stock_local(code)
            if path:
                print(f"  {name} ({code}): saved to {path}")
            else:
                print(f"  {name} ({code}): save failed")
        except Exception as e:
            print(f"  {name} ({code}): error — {e}")
    print()


def demo_check_cache():
    """Inspect the local data cache.

    has_local_data(code): returns True if cached CSV exists
    list_local_stocks(): returns list of all cached stock codes
    """
    print("--- Cache Inspection ---")

    # Check individual stocks
    for name, code in [("ICBC", STOCKS["bank"]),
                       ("Moutai", STOCKS["liquor"]),
                       ("Unknown", "999999")]:
        cached = has_local_data(code)
        print(f"  {name} ({code}): {'cached' if cached else 'not cached'}")

    # List all cached stocks
    all_cached = list_local_stocks()
    print(f"\n  Total cached stocks: {len(all_cached)}")
    if all_cached:
        print(f"  First 10: {all_cached[:10]}")
    print()


def demo_local_backtest():
    """Run a backtest using local cached data.

    Setting use_local=True tells the backtest engine to read
    from local CSV files instead of fetching from akshare.
    This is significantly faster for repeated runs.
    """
    print("--- Local Data Backtest ---")

    security = STOCKS["bank"]
    security_trade = STOCKS_TRADE["bank"]

    # Ensure we have local data
    if not has_local_data(security):
        print(f"  Downloading {security} to local cache...")
        save_stock_local(security)

    def init(ctx):
        set_benchmark(INDEX_HS300)
        set_order_cost(DEFAULT_ORDER_COST)
        g.security = security
        g.security_trade = security_trade
        ctx.universe = [security]
        run_daily(trade, time="every_bar")

    def trade(ctx):
        hist = attribute_history(g.security, 25, "1d", ["close"])
        if hist is None or hist.empty or len(hist) < 20:
            return

        close = hist["close"]
        price = close.iloc[-1]
        fast = close.rolling(5).mean()
        slow = close.rolling(20).mean()

        if len(fast.dropna()) < 2 or len(slow.dropna()) < 2:
            return

        golden = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        death = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]

        has_pos = (g.security_trade in ctx.portfolio.positions
                   and ctx.portfolio.positions[g.security_trade].amount > 0)

        if golden and not has_pos:
            cash = ctx.portfolio.available_cash
            if cash > price * 100:
                order_value(g.security_trade, cash * 0.95)
        elif death and has_pos:
            order_target(g.security_trade, 0)

        record(total_value=ctx.portfolio.total_value)

    actual_start, actual_end = verify_data_available(
        security, START_DATE, END_DATE)

    result = run_backtest(
        initialize_func=init,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[security],
        use_local=True,  # KEY: use cached local data
    )

    if result:
        print_evaluation(result, "Local Data Backtest (MA 5/20)")
    else:
        print("  Backtest failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Data Management")
    parser.add_argument("--list", action="store_true",
                        help="List cached stocks and exit")
    parser.add_argument("--download", type=str, metavar="CODE",
                        help="Download specific stock to cache")
    args = parser.parse_args()

    print("=" * 55)
    print("06 - Local Data Management")
    print("=" * 55)
    print()

    if args.list:
        demo_check_cache()
    elif args.download:
        print(f"Downloading {args.download}...")
        path = save_stock_local(args.download)
        print(f"  Saved to: {path}" if path else "  Download failed")
    else:
        demo_save_local()
        demo_check_cache()
        demo_local_backtest()
