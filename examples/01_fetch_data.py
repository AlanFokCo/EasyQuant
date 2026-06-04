"""
01 - Data Fetching
==================

Demonstrates the core data APIs for retrieving A-share market data.
This is typically the first step in any quantitative workflow:
get data -> explore -> analyze -> build strategy.

Teaching Objectives:
    - get_price(): historical OHLCV for a single stock
    - fetch_stock_data(): raw data interface with multi-source fallback
    - get_all_securities(): full A-share stock listing
    - download_stock_data() + load_csv(): local CSV workflow
    - scan_market(): real-time market screening

Expected Output:
    - Printed DataFrames showing stock data
    - CSV file saved to data/ directory
    - Market scan results (may be empty outside trading hours)

Run:
    python examples/01_fetch_data.py
"""

import os
from datetime import datetime, timedelta

from eqlib import (
    get_price,
    fetch_stock_data,
    get_all_securities,
    download_stock_data,
    load_csv,
    scan_market,
    log,
)
from examples._defaults import STOCKS


def demo_get_price():
    """Fetch historical OHLCV data for a single stock.

    get_price() is the most commonly used data API. It returns a
    pandas DataFrame with columns: open, high, low, close, volume.
    """
    security = STOCKS["liquor"]  # 600519 Kweichow Moutai
    end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    print("--- get_price ---")
    df = get_price(security, start_date=start, end_date=end)
    if df is not None and not df.empty:
        print(f"  {security}: {len(df)} bars from {start} to {end}")
        print(f"  Latest close: {df['close'].iloc[-1]:.2f}")
        print(f"  Columns: {df.columns.tolist()}")
        print(df.tail(3).to_string())
    else:
        print(f"  No data for {security}")
    print()


def demo_fetch_stock_data():
    """Direct data interface with multi-source fallback.

    fetch_stock_data() tries multiple data sources (EastMoney,
    Tencent, Sina, BaoStock) and returns the first successful result.
    Default adjustment is 'qfq' (forward-adjusted).
    """
    security = STOCKS["bank"]  # 601398 ICBC
    end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    print("--- fetch_stock_data ---")
    df = fetch_stock_data(security, start, end)
    if df is not None and not df.empty:
        print(f"  {security}: {len(df)} bars (qfq adjusted)")
        print(df.tail(3).to_string())
    else:
        print(f"  No data for {security}")
    print()


def demo_get_all_securities():
    """Get the full A-share stock listing.

    Returns a DataFrame with columns: code, name.
    Useful for iterating over the entire market.
    """
    print("--- get_all_securities ---")
    df = get_all_securities()
    if df is not None and not df.empty:
        print(f"  Total A-share stocks: {len(df)}")
        print(df.head(5).to_string())
    print()


def demo_download_and_load():
    """Download data to local CSV and reload it.

    This workflow is useful for offline analysis or when you need
    to repeatedly access the same data without hitting the network.
    """
    security = STOCKS["ev"]  # 002594 BYD
    end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    print("--- download_stock_data + load_csv ---")
    os.makedirs("data", exist_ok=True)
    path = download_stock_data(security, start, end, output_dir="data")
    if path:
        print(f"  Saved to: {path}")
        df = load_csv(path)
        if df is not None and not df.empty:
            print(f"  Loaded {len(df)} bars from CSV")
            print(df.head(3).to_string())
    else:
        print(f"  Download failed for {security}")
    print()


def demo_scan_market():
    """Real-time market screening with multiple filters.

    scan_market() scans all A-shares and filters by:
    - min_price / max_price
    - min_pct_change / max_pct_change (daily %)
    - max_pe (P/E ratio)

    Note: Results depend on current market conditions. Outside
    trading hours, the scan may return fewer results.
    """
    print("--- scan_market ---")
    candidates = scan_market(
        min_price=20,
        min_pct_change=2,
        max_pct_change=5,
        max_pe=30,
    )
    if candidates is not None and not candidates.empty:
        print(f"  Found {len(candidates)} matching stocks")
        print(candidates.head(10).to_string())
    else:
        print("  No stocks match the criteria (normal outside trading hours)")
    print()


if __name__ == "__main__":
    print("=" * 55)
    print("01 - Data Fetching APIs")
    print("=" * 55)
    print()

    demo_get_price()
    demo_fetch_stock_data()
    demo_get_all_securities()
    demo_download_and_load()
    demo_scan_market()
