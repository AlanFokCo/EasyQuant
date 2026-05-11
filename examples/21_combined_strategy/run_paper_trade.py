"""Example 21: All-Weather Alpha Strategy — Paper Trading Runner.

Runs the combined strategy in paper-trading (live simulation) mode.
Real-time market data is fetched; orders are simulated but never sent
to a real broker.  Run during market hours for live quotes; outside
hours the prices will be the last available close.

Usage:
    # Default settings (capital ¥500,000, refresh every 60 s)
    python examples/21_combined_strategy/run_paper_trade.py

    # Custom capital and refresh interval
    python examples/21_combined_strategy/run_paper_trade.py --cash 200000 --interval 120

Press Ctrl+C to stop.
"""

import argparse
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import initialize
from eqlib import run_paper_trade, log


def main():
    parser = argparse.ArgumentParser(
        description="Paper-trade the All-Weather Alpha combined strategy"
    )
    parser.add_argument(
        "--cash", type=float, default=500_000,
        help="Starting capital in CNY (default: 500000)"
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Quote refresh interval in seconds (default: 60)"
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("All-Weather Alpha — Paper Trading")
    log.info("Starting capital : ¥%s" % format(args.cash, ",.0f"))
    log.info("Refresh interval : %ds" % args.interval)
    log.info("Press Ctrl+C to stop")
    log.info("=" * 60)

    run_paper_trade(
        initialize_func=initialize,
        starting_cash=args.cash,
        interval=args.interval,
    )


if __name__ == "__main__":
    main()
