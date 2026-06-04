"""
19 - Support/Resistance Portfolio Strategy — Backtest Runner
==============================================================

Runs a 3-year backtest on the multi-stock S/R portfolio strategy
across 8 diversified A-share stocks.

The strategy buys near support levels (with RSI/MACD confirmation) and
sells near resistance levels, protected by ATR trailing stops and
Donchian channel breakout exits.  Equal-weight allocation limits each
position to 25% of the portfolio.

See sr_strategy.py for full strategy logic and parameter documentation.

Usage:
    # Default: 200,000 CNY starting capital
    python examples/19_sr_portfolio/run_backtest.py

    # Custom starting capital
    python examples/19_sr_portfolio/run_backtest.py --cash 500000

Output:
    reports/backtest_<timestamp>.png   — portfolio value chart
    reports/backtest_<timestamp>.html  — interactive HTML report
    reports/backtest_<timestamp>.md    — Markdown summary
    reports/backtest_<timestamp>.json  — full backtest data
"""

import argparse
import os
import sys

# Ensure the project root is on sys.path so that:
#   1. sr_strategy.py can do "from examples._defaults import ..."
#   2. We can import from sr_strategy in the same directory
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_here))
for _p in (_project_root, _here):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sr_strategy import initialize, STOCK_POOL, BARE_TO_TRADE

from eqlib import run_strategy
from examples._defaults import (
    INDEX_SH, START_DATE, END_DATE,
    verify_data_available, print_evaluation,
)


# ============================================================
# CLI
# ============================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the S/R Portfolio backtest on 8 A-share stocks.",
    )
    parser.add_argument(
        "--cash",
        type=int,
        default=200_000,
        help="Starting capital in CNY (default: 200000)",
    )
    return parser.parse_args()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    args = parse_args()
    starting_cash = args.cash

    print("=" * 60)
    print("19 - S/R Portfolio Strategy Backtest")
    print("=" * 60)
    print("Period       : %s  to  %s" % (START_DATE, END_DATE))
    print("Capital      : %s CNY" % format(starting_cash, ","))
    print("Benchmark    : Shanghai Composite (%s)" % INDEX_SH)
    print("Stock pool   : %d stocks" % len(STOCK_POOL))
    for bare, trade in BARE_TO_TRADE.items():
        print("               %s  (%s)" % (bare, trade))
    print()

    # Verify data is available for the first stock (representative check)
    representative = STOCK_POOL[0]
    print("Verifying data for %s ..." % representative)
    actual_start, actual_end = verify_data_available(
        representative, START_DATE, END_DATE,
    )
    print("  Data range: %s  to  %s" % (actual_start, actual_end))
    print()

    # Prepare report directory
    _root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    report_dir = os.path.join(_root, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # Run backtest
    result = run_strategy(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=starting_cash,
        benchmark=INDEX_SH,
        securities=STOCK_POOL,
        report_dir=report_dir,
    )

    if result is None:
        print("Backtest failed: no result returned.")
        sys.exit(1)

    # Summary output
    context = result["context"]
    final_value = context.portfolio.total_value
    pnl = final_value - starting_cash
    pnl_pct = pnl / starting_cash * 100
    trade_count = len(result.get("trade_log", []))

    print()
    print("=" * 60)
    print("Backtest Summary")
    print("=" * 60)
    print("Starting cash : %s CNY" % format(starting_cash, ",.2f"))
    print("Final value   : %s CNY" % format(final_value, ",.2f"))
    print("Total P&L     : %s (%+.2f%%)" % (format(pnl, "+,.2f"), pnl_pct))
    print("Total trades  : %d" % trade_count)

    # Standardized evaluation panel
    print_evaluation(result, "S/R Portfolio (8 stocks)")

    print()
    print("Reports saved to: %s" % os.path.abspath(report_dir))
