"""Example 20: Support & Resistance Portfolio Strategy Backtest.

A real-world portfolio strategy that buys near support levels and sells
near resistance levels across 8 diversified A-share stocks.

Strategy:
  BUY  when price is near support AND RSI is oversold OR MACD golden cross
  SELL when price is near resistance AND RSI is overbought OR MACD death cross
  STOP LOSS via ATR trailing stop
  Equal-weight allocation: max 25% per stock

Stock pool (8 stocks across sectors):
    601390  China Railway 中国中铁 (infrastructure)
    600916  China Gold 中国黄金 (gold)
    002594  BYD 比亚迪 (EV/new energy)
    601088  China Shenhua 中国神华 (coal)
    601857  PetroChina 中国石油 (oil)
    600536  China Soft 中国软件 (technology)
    601398  ICBC 工商银行 (banking)
    518880  Gold ETF 黄金ETF

Backtest results (2020-01-01 to 2026-03-30):
    Starting cash:  1,000,000
    Final value:    2,371,889.70
    Total return:   +137.19%
    Total trades:   226

Reports in this directory:
    - backtest_*.html   Interactive HTML report with K-line charts
    - backtest_*.png    Static chart with portfolio value
    - backtest_*.md     Markdown summary report
    - backtest_*.json   Full backtest data

Usage:
    # Run the backtest (requires local data in data/ directory)
    python examples/20_sr_strategy/run_backtest.py

    # First time: download data, then run
    python examples/19_local_data_backtest.py --download-all
    python examples/20_sr_strategy/run_backtest.py
"""

import os
import sys

# Add project root and this directory to path so eqlib and sr_strategy can be found
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sr_strategy import initialize
from eqlib import *

STOCK_POOL = [
    "601390", "600916", "002594", "601088",
    "601857", "600536", "601398", "518880",
]

if __name__ == "__main__":
    import os
    import datetime

    print("=" * 60)
    print("Portfolio Support & Resistance Strategy Backtest")
    print("=" * 60)
    print("Stocks   : %d" % len(STOCK_POOL))
    for code in STOCK_POOL:
        print("           %s" % code)
    print("Period   : 2020-01-01 to 2026-03-30")
    print("Cash     : 1,000,000")
    print("Local data: Yes (load from CSV)")
    print()

    result = run_strategy(
        initialize_func=initialize,
        start_date="2020-01-01",
        end_date="2026-03-30",
        starting_cash=1000000,
        benchmark="000001.XSHG",
        securities=STOCK_POOL,
        use_local=True,
        report_dir=os.path.dirname(os.path.abspath(__file__)),
    )

    if result is None:
        print("Backtest failed: no result returned.")
    else:
        context = result["context"]
        final_value = context.portfolio.total_value
        pnl = final_value - 1000000
        pnl_pct = pnl / 1000000 * 100

        print()
        print("=" * 60)
        print("Results")
        print("=" * 60)
        print("Final value : %s" % format(final_value, ",.2f"))
        print("Total P&L   : %s (%.2f%%)" % (format(pnl, "+,.2f"), pnl_pct))
        print("Trades      : %d" % len(result["trade_log"]))
