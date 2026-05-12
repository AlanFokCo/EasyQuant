"""Example 1: Fetching stock data.

Demonstrates eqlib data APIs:
- Fetch single stock OHLCV history
- Get full market stock list
- Download data and save to CSV
- Load data from local CSV
- Use get_price / history / attribute_history
- Scan market and check technical signals
"""

from eqlib import (
    get_price,
    get_all_securities,
    fetch_stock_data,
    download_stock_data,
    load_csv,
    history,
    attribute_history,
    scan_market,
    log,
)
import datetime


def demo_get_price():
    """Fetch historical price data for a single stock."""
    log.info("=== Historical Prices (get_price) ===")

    df = get_price("601390", start_date="2024-01-01", end_date="2024-03-01")
    if not df.empty:
        log.info(f"ICBC Jan-Feb 2024: {len(df)} bars")
        log.info(f"Latest close: {df['close'].iloc[-1]:.3f}")
        log.info(f"Columns: {df.columns.tolist()}")


def demo_fetch_stock_data():
    """Direct access to the underlying data interface."""
    log.info("=== Raw Data Interface (fetch_stock_data) ===")

    df = fetch_stock_data("000001", "2024-06-01", "2024-07-01")
    if not df.empty:
        log.info(f"Ping An Bank: {len(df)} bars")
        log.info(df.tail(3))


def demo_get_all_securities():
    """Fetch the full A-share stock list."""
    log.info("=== Full Market Stock List (get_all_securities) ===")

    df = get_all_securities()
    if not df.empty:
        log.info(f"Total A-shares: {len(df)}")
        log.info(df.head(5))


def demo_download_and_load():
    """Download data to CSV and reload it."""
    log.info("=== Download and Load CSV ===")

    path = download_stock_data(
        "600519", "2024-01-01", "2024-06-30",
        output_dir="data",
    )
    if path:
        log.info(f"Saved to: {path}")

        df = load_csv(path)
        if not df.empty:
            log.info(f"Loaded {len(df)} bars from CSV")
            log.info(df.head(3))


def demo_scan_market():
    """Scan the market for stocks matching criteria."""
    log.info("=== Market Scan (scan_market) ===")

    candidates = scan_market(
        min_price=20,
        min_pct_change=2,
        max_pct_change=5,
        max_pe=30,
    )
    if not candidates.empty:
        log.info(f"Found {len(candidates)} stocks")
        log.info(candidates.head(10))
    else:
        log.info("No stocks match the criteria today")


if __name__ == "__main__":
    demo_get_price()
    print()

    demo_fetch_stock_data()
    print()

    demo_get_all_securities()
    print()

    demo_download_and_load()
    print()

    demo_scan_market()
