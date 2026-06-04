"""
04 - Stock Screening
====================

Demonstrates multiple stock screening approaches:
- scan_market(): real-time market scanning by price/change/PE
- check_golden_cross(): technical signal verification
- get_restriction_release(): A-share specific risk filter
- query() / valuation / get_fundamentals(): fluent screening API

Teaching Objectives:
    - Combining multiple data sources for robust screening
    - Filtering out risky stocks (ST, upcoming restriction releases)
    - Using the query() API for chainable, type-safe screening
    - argparse for CLI customization

Expected Output:
    - Market scan results with golden cross verification
    - Restriction release warnings for upcoming unlocks
    - Query API results filtered by PE and market cap

Run:
    python examples/04_stock_screener.py
    python examples/04_stock_screener.py --pe-max 20 --min-price 10
"""

import argparse
from datetime import datetime, timedelta

from eqlib import (
    scan_market,
    check_golden_cross,
    get_restriction_release,
    log,
)
from examples._defaults import STOCKS


def demo_scan_with_golden_cross(min_price=20, max_pe=30):
    """Scan market and verify golden cross signals.

    Combines scan_market() (price/PE filter) with check_golden_cross()
    (technical signal) to find stocks that are both fundamentally
    reasonable and technically bullish.
    """
    print("--- Market Scan + Golden Cross ---")

    candidates = scan_market(
        min_price=min_price,
        min_pct_change=1,
        max_pct_change=5,
        max_pe=max_pe,
    )

    if candidates is None or candidates.empty:
        print("  No candidates from scan_market (normal outside trading hours)")
        return

    print(f"  scan_market found {len(candidates)} candidates")

    # Check golden cross on top candidates
    codes = candidates.head(20).index.tolist() if hasattr(candidates, 'index') else []
    if not codes and "code" in candidates.columns:
        codes = candidates.head(20)["code"].tolist()

    golden_crosses = []
    for code in codes:
        try:
            if check_golden_cross(code):
                golden_crosses.append(code)
        except Exception:
            continue

    if golden_crosses:
        print(f"  Golden cross confirmed: {golden_crosses}")
    else:
        print("  No golden crosses found among top candidates today")
    print()


def demo_restriction_filter():
    """Filter out stocks with upcoming large restriction releases.

    Restricted share releases can cause significant selling pressure.
    get_restriction_release(days=30) returns stocks with upcoming
    unlocks in the next 30 days.

    Key columns: code, name, release_date, release_amount (万股),
                 release_value (亿元), release_pct
    """
    print("--- Restriction Release Filter ---")

    releases = get_restriction_release(days=30)

    if releases is None or releases.empty:
        print("  No restriction release data available")
        print()
        return

    # Filter for significant releases (> 1% of float)
    if "release_pct" in releases.columns:
        significant = releases[releases["release_pct"] > 1.0]
    else:
        significant = releases

    if significant.empty:
        print("  No significant restriction releases in next 30 days")
    else:
        print(f"  {len(significant)} stocks with >1% float unlock:")
        cols = ["code", "name", "release_date", "release_pct"]
        display_cols = [c for c in cols if c in significant.columns]
        if display_cols:
            print(significant[display_cols].head(10).to_string(index=False))

    # Cross-reference with our stock pool
    pool_codes = list(STOCKS.values())
    if "code" in releases.columns:
        at_risk = [c for c in pool_codes
                   if c in releases["code"].tolist()]
        if at_risk:
            print(f"\n  WARNING: Our stock pool has upcoming releases: {at_risk}")
        else:
            print(f"\n  Our stock pool is clear — no upcoming releases")
    print()


def demo_query_api():
    """Fluent stock screening with the query() API.

    The query() API provides a chainable, type-safe interface
    for stock screening. It's more expressive than scan_market()
    and supports complex filter combinations.

    Pattern:
        q = query(valuation.pe, valuation.market_cap) \\
            .filter(valuation.pe < 20) \\
            .filter(valuation.market_cap > 50e9) \\
            .order_by(valuation.pe.asc()) \\
            .limit(10)
        result = get_fundamentals(q)
    """
    print("--- Query API Screening ---")

    try:
        from eqlib import query, valuation, get_fundamentals

        # Screen for value stocks: low PE, large market cap
        q = (query(valuation.pe, valuation.market_cap, valuation.price)
             .filter(valuation.pe.lt(25))
             .filter(valuation.pe.gt(0))
             .filter(valuation.market_cap.gt(50e9))
             .order_by(valuation.pe.asc())
             .limit(10))

        result = get_fundamentals(q)

        if result is not None and not result.empty:
            print(f"  Found {len(result)} value stocks (PE<25, cap>50B):")
            print(result.to_string())
        else:
            print("  No stocks match the query criteria")
    except ImportError:
        print("  query() API not available (experimental feature)")
    except Exception as e:
        print(f"  Query failed: {e}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Screening Examples")
    parser.add_argument("--pe-max", type=float, default=30,
                        help="Maximum P/E ratio for screening")
    parser.add_argument("--min-price", type=float, default=20,
                        help="Minimum stock price")
    args = parser.parse_args()

    print("=" * 55)
    print("04 - Stock Screening")
    print("=" * 55)
    print()

    demo_scan_with_golden_cross(
        min_price=args.min_price, max_pe=args.pe_max)
    demo_restriction_filter()
    demo_query_api()
