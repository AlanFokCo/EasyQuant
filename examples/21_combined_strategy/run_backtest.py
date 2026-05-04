"""Example 21: All-Weather Alpha Strategy — Backtest Runner.

Runs a 3-year backtest (2022-01-01 to 2024-12-31) on the combined strategy
using 12 diversified A-share stocks.

The combined strategy integrates:
  - Multi-factor stock selection (momentum + volume + reversal + volatility)
  - Z-Score factor normalisation
  - Sector-rotation scoring
  - RSI + Bollinger Band mean-reversion entry/exit
  - MACD trend confirmation
  - ATR trailing stop
  - Donchian Channel breakout exit
  - Support/Resistance confirmation
  - Lifecycle callbacks (before_trading_start / after_trading_end)

See combined_strategy.py for full strategy documentation.
See tutorials/09_combined_strategy.md for the step-by-step tutorial.

Usage:
    python examples/21_combined_strategy/run_backtest.py

Output:
    reports/backtest_<timestamp>.png   — portfolio value chart
    reports/backtest_<timestamp>.html  — interactive HTML report
    reports/backtest_<timestamp>.md    — Markdown summary
    reports/backtest_<timestamp>.json  — full backtest data
"""

import os
import sys

# Add project root to path so eqlib and combined_strategy can be found
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from combined_strategy import initialize, STOCK_POOL
from eqlib import run_strategy, analyze_returns

# ============================================================
# Backtest configuration
# ============================================================

START_DATE    = "2022-01-01"
END_DATE      = "2024-12-31"
STARTING_CASH = 500_000      # ¥500,000 initial capital
BENCHMARK     = "000300.XSHG"
REPORT_DIR    = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../../reports"
)


if __name__ == "__main__":
    print("=" * 65)
    print("All-Weather Alpha — Combined Strategy Backtest")
    print("=" * 65)
    print("Period      : %s  →  %s" % (START_DATE, END_DATE))
    print("Capital     : ¥%s" % format(STARTING_CASH, ",.0f"))
    print("Benchmark   : CSI 300 (%s)" % BENCHMARK)
    print("Stock pool  : %d stocks" % len(STOCK_POOL))
    for code in STOCK_POOL:
        print("              %s" % code)
    print()

    result = run_strategy(
        initialize_func=initialize,
        start_date=START_DATE,
        end_date=END_DATE,
        starting_cash=STARTING_CASH,
        benchmark=BENCHMARK,
        securities=STOCK_POOL,
        report_dir=REPORT_DIR,
    )

    if result is None:
        print("Backtest failed: no result returned.")
        sys.exit(1)

    # --------------------------------------------------------
    # Summary output
    # --------------------------------------------------------
    context    = result["context"]
    final_val  = context.portfolio.total_value
    pnl        = final_val - STARTING_CASH
    pnl_pct    = pnl / STARTING_CASH * 100
    trade_count = len(result["trade_log"])

    print()
    print("=" * 65)
    print("Backtest Results")
    print("=" * 65)
    print("Starting cash : ¥%s" % format(STARTING_CASH, ",.2f"))
    print("Final value   : ¥%s" % format(final_val, ",.2f"))
    print("Total P&L     : ¥%s  (%+.2f%%)" % (format(pnl, "+,.2f"), pnl_pct))
    print("Total trades  : %d" % trade_count)

    # Risk metrics
    try:
        metrics = analyze_returns(result, risk_free_rate=0.03)
        print()
        print("Risk Metrics")
        print("-" * 40)
        print("Sharpe ratio  : %.4f" % metrics.get("sharpe_ratio", float("nan")))
        print("Sortino ratio : %.4f" % metrics.get("sortino_ratio", float("nan")))
        print("Max drawdown  : %.2f%%" % (metrics.get("max_drawdown", 0) * 100))
        print("Calmar ratio  : %.4f" % metrics.get("calmar_ratio", float("nan")))
        print("Alpha         : %.4f" % metrics.get("alpha", float("nan")))
        print("Beta          : %.4f" % metrics.get("beta", float("nan")))
        print("Win rate      : %.2f%%" % (metrics.get("win_rate", 0) * 100))
    except Exception as exc:
        print("(Could not compute risk metrics: %s)" % exc)

    print()
    print("Reports saved to: %s" % os.path.abspath(REPORT_DIR))
