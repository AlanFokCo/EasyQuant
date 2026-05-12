"""Example 4: Real-time stock screening.

Demonstrates how to scan the A-share market, filter potential buy candidates,
and confirm with technical indicators (golden cross).

Usage:
    python examples/04_stock_screener.py

    Custom parameters:
    python examples/04_stock_screener.py --min-price 15 --min-pct 2 --max-pct 6 --max-pe 40
"""

import argparse
from eqlib import scan_market, check_golden_cross, log


def screen_and_check(min_price=10, min_pct=3, max_pct=5, max_pe=50):
    """Scan the market and check for golden cross signals."""

    # Step 1: fundamental + volume/price filtering
    log.info("Scanning the full market...")
    candidates = scan_market(
        min_price=min_price,
        min_pct_change=min_pct,
        max_pct_change=max_pct,
        max_pe=max_pe,
    )

    if candidates.empty:
        log.info("No stocks match the initial screening criteria")
        return

    log.info(f"Passed initial screening: {len(candidates)} stocks")
    for _, row in candidates.iterrows():
        log.info(f"  {row['name']}({row['code']}) price={row['price']:.2f} "
                 f"change={row['pct_change']:.2f}% PE={row['pe']:.1f}")

    # Step 2: technical confirmation (golden cross)
    log.info(f"\nChecking technical indicators for {len(candidates)} stocks...")
    buy_signals = []

    for _, row in candidates.iterrows():
        code = row["code"]
        name = row["name"]
        price = row["price"]

        if check_golden_cross(code):
            buy_signals.append((code, name, price))
            log.info(f"  ** Golden cross: {name}({code}) @ {price:.2f}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Screening Results")
    print(f"{'=' * 60}")

    if buy_signals:
        print(f"Found {len(buy_signals)} golden cross signals:")
        for code, name, price in buy_signals:
            print(f"  {name}({code})  price={price:.2f}")
    else:
        print("No golden cross signals detected")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-time stock screener")
    parser.add_argument("--min-price", type=float, default=10,
                        help="Minimum stock price (default 10)")
    parser.add_argument("--min-pct", type=float, default=3,
                        help="Minimum daily change % (default 3)")
    parser.add_argument("--max-pct", type=float, default=5,
                        help="Maximum daily change % (default 5)")
    parser.add_argument("--max-pe", type=float, default=50,
                        help="Maximum dynamic P/E ratio (default 50)")
    args = parser.parse_args()

    screen_and_check(
        min_price=args.min_price,
        min_pct=args.min_pct,
        max_pct=args.max_pct,
        max_pe=args.max_pe,
    )
