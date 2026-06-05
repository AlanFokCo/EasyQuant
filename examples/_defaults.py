"""
Shared defaults for all examples.
=================================
Centralizes trading costs, stock selections, and backtest parameters
to ensure consistency across all examples.

This module is imported by every example file to avoid duplicating
configuration and to guarantee uniform trading cost assumptions.
"""

import sys
from datetime import datetime, timedelta

from eqlib import OrderCost, get_price, log


# ============================================================
# A-share trading costs (2024 current standards)
# ============================================================
# Note: OrderCost.calc_close_cost() applies date-aware stamp duty
# internally (0.05% after 2023-08-28, 0.1% before). We set
# close_tax=0.0005 explicitly for clarity in educational code.
DEFAULT_ORDER_COST = OrderCost(
    open_tax=0,
    close_tax=0.0005,        # Stamp duty 0.05% (halved since Aug 2023)
    open_commission=0.00025,  # Commission 0.025% (incl. regulatory fees)
    close_commission=0.00025,
    close_today_commission=0, # T+1 settlement, no intraday commission
    min_commission=5,         # Minimum 5 CNY per trade
)


# ============================================================
# Common backtest targets
# ============================================================
# Selection criteria: high liquidity, representative sectors, complete history.
# Bare codes for data APIs: get_price(), attribute_history(), etc.
STOCKS = {
    "bank":      "601398",   # ICBC — large-cap blue chip, low volatility
    "insurance": "601318",   # Ping An — financial conglomerate
    "liquor":    "600519",   # Kweichow Moutai — consumer leader
    "ev":        "002594",   # BYD — new energy, high volatility
    "tech":      "000725",   # BOE Technology — cyclical stock
    "pharma":    "600276",   # Hengrui Medicine — healthcare leader
    "cement":    "600585",   # Conch Cement — infrastructure proxy
    "shenhua":   "601088",   # China Shenhua — energy / dividend
}

# Suffixed codes for trading APIs: order(), order_target(), order_value()
STOCKS_TRADE = {
    "bank":      "601398.XSHG",
    "insurance": "601318.XSHG",
    "liquor":    "600519.XSHG",
    "ev":        "002594.XSHE",
    "tech":      "000725.XSHE",
    "pharma":    "600276.XSHG",
    "cement":    "600585.XSHG",
    "shenhua":   "601088.XSHG",
}

# Index codes
INDEX_HS300 = "000300.XSHG"   # CSI 300 — primary benchmark
INDEX_SH = "000001.XSHG"      # Shanghai Composite — reference


# ============================================================
# Backtest period
# ============================================================
BACKTEST_YEARS = 3
INITIAL_CASH = 100_000

# Relative dates: end = 30 days ago (buffer for data freshness)
#                  start = BACKTEST_YEARS years + 30 days before end
END_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=365 * BACKTEST_YEARS + 30)).strftime("%Y-%m-%d")


# ============================================================
# Utilities shared across examples
# ============================================================

def verify_data_available(security, start_date, end_date, max_extensions=2):
    """Verify data is obtainable with automatic lookback extension.

    Returns (actual_start, actual_end) on success.
    Exits with clear error message on failure.
    """
    current_start = datetime.strptime(start_date, "%Y-%m-%d")

    for attempt in range(max_extensions + 1):
        try:
            df = get_price(security,
                           current_start.strftime("%Y-%m-%d"),
                           end_date)
            if df is not None and not df.empty:
                return current_start.strftime("%Y-%m-%d"), end_date
        except Exception:
            pass

        if attempt < max_extensions:
            # Extend lookback by 6 months
            month = current_start.month - 6
            year = current_start.year
            if month <= 0:
                month += 12
                year -= 1
            current_start = current_start.replace(year=year, month=month)
            print(f"  No data found, extending lookback to "
                  f"{current_start.strftime('%Y-%m-%d')}...")

    print(f"Error: {security} has no data after extending to "
          f"{current_start.strftime('%Y-%m-%d')}")
    print("  Please check network connection and akshare version.")
    sys.exit(1)


def print_evaluation(result, strategy_name="Strategy"):
    """Standardized evaluation panel for all practical examples.

    Prints risk/return metrics and scientific rigor warnings.
    """
    from eqlib import analyze_returns

    metrics = analyze_returns(result, risk_free_rate=0.03)
    if metrics is None:
        print(f"\n  Warning: Could not compute metrics for {strategy_name}")
        return

    print(f"\n{'='*55}")
    print(f"  {strategy_name} — Evaluation Report")
    print(f"{'='*55}")
    print(f"  Total Return:    {metrics['total_return']:>10.2%}")
    print(f"  Annual Return:   {metrics['annual_return']:>10.2%}")
    print(f"  Annual Vol:      {metrics['annual_volatility']:>10.2%}")
    print(f"  Sharpe Ratio:    {metrics['sharpe_ratio']:>10.2f}")
    print(f"  Sortino Ratio:   {metrics.get('sortino_ratio', 0):>10.2f}")
    print(f"  Max Drawdown:    {metrics['max_drawdown']:>10.2%}")
    print(f"  Calmar Ratio:    {metrics.get('calmar_ratio', 0):>10.2f}")
    print(f"  Win Rate:        {metrics.get('win_rate_trade', 0):>10.1%}")
    print(f"  Profit/Loss:     {metrics.get('profit_loss_ratio', 0):>10.2f}")
    print(f"  Trade Count:     {metrics.get('trade_count', 0):>10.0f}")
    print(f"  Alpha:           {metrics.get('alpha', 0):>+10.2%}")
    print(f"  Beta:            {metrics.get('beta', 0):>10.2f}")
    print(f"{'='*55}")

    # Scientific rigor warnings
    trade_count = metrics.get('trade_count', 0)
    max_dd = abs(metrics.get('max_drawdown', 0))
    if trade_count < 10:
        print(f"  Warning: Trade count ({trade_count}) < 10 — "
              f"statistical significance insufficient")
    if max_dd > 0.30:
        print(f"  Warning: Max drawdown ({max_dd:.1%}) > 30% — "
              f"psychological pressure may be excessive")
