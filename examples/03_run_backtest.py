"""
03 - Running a Backtest
=======================

Demonstrates the lower-level run_backtest() API and manual result
inspection. Unlike run_strategy() (which auto-generates all reports),
run_backtest() gives you full control over what to do with results.

Teaching Objectives:
    - run_backtest(): lower-level backtest runner (no auto-reports)
    - Inspecting trade_log: each trade's date, type, amount, price
    - Accessing portfolio state via result["context"].portfolio
    - analyze_returns(): compute risk/return metrics manually
    - Difference between run_strategy (high-level) and run_backtest

Expected Output:
    - Trade log printed (each buy/sell with date and price)
    - Final portfolio value and P&L
    - Risk/return metrics from analyze_returns

Run:
    python examples/03_run_backtest.py
"""

import os

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, log, g, analyze_returns,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available,
)


# ============================================================
# Strategy: same MA crossover as example 02
# ============================================================

SECURITY = STOCKS["insurance"]              # 601318 Ping An
SECURITY_TRADE = STOCKS_TRADE["insurance"]  # 601318.XSHG
FAST_PERIOD = 10   # Slightly longer fast period than example 02
SLOW_PERIOD = 30   # To demonstrate a different parameter choice


def initialize(context):
    """Strategy initialization."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = SECURITY
    g.security_trade = SECURITY_TRADE
    g.fast_period = FAST_PERIOD
    g.slow_period = SLOW_PERIOD

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")


def market_open(context):
    """MA crossover trading logic."""
    security = g.security
    security_trade = g.security_trade

    hist = attribute_history(security, g.slow_period + 5, "1d", ["close"])
    if hist is None or hist.empty or len(hist) < g.slow_period:
        return

    close = hist["close"]
    current_price = close.iloc[-1]

    fast_ma = close.rolling(g.fast_period).mean()
    slow_ma = close.rolling(g.slow_period).mean()

    if len(fast_ma.dropna()) < 2 or len(slow_ma.dropna()) < 2:
        return

    prev_fast, curr_fast = fast_ma.iloc[-2], fast_ma.iloc[-1]
    prev_slow, curr_slow = slow_ma.iloc[-2], slow_ma.iloc[-1]

    golden_cross = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    death_cross = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if golden_cross and not has_position:
        cash = context.portfolio.available_cash
        if cash > current_price * 100:
            order_value(security_trade, cash * 0.95)

    elif death_cross and has_position:
        order_target(security_trade, 0)

    record(total_value=context.portfolio.total_value)


# ============================================================
# Run backtest and inspect results
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("03 - Running a Backtest (Manual Inspection)")
    print("=" * 55)

    actual_start, actual_end = verify_data_available(
        SECURITY, START_DATE, END_DATE)

    # --- run_backtest vs run_strategy ---
    # run_backtest: returns result dict, NO auto-generated reports
    # run_strategy: runs backtest + generates PNG/HTML/MD/JSON reports
    # Use run_backtest when you want full control over output.
    result = run_backtest(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[SECURITY],
        use_local=True,
    )

    if result is None:
        print("Backtest failed — no results.")
        raise SystemExit(1)

    # --- Inspect the trade log ---
    print(f"\n{'='*55}")
    print("Trade Log")
    print(f"{'='*55}")

    trade_log = result["trade_log"]
    print(f"  Total trades: {len(trade_log)}")

    if trade_log:
        print(f"\n  {'Date':<12} {'Type':<6} {'Security':<14} "
              f"{'Amount':>8} {'Price':>10}")
        print(f"  {'-'*12} {'-'*6} {'-'*14} {'-'*8} {'-'*10}")
        for trade in trade_log[:20]:  # Show first 20 trades
            date = trade.get("date", "")
            ttype = trade.get("type", "")
            sec = trade.get("security", "")
            amount = trade.get("amount", 0)
            price = trade.get("price", 0)
            print(f"  {str(date):<12} {ttype:<6} {sec:<14} "
                  f"{amount:>8} {price:>10.2f}")
        if len(trade_log) > 20:
            print(f"  ... and {len(trade_log) - 20} more trades")

    # --- Inspect final portfolio state ---
    ctx = result["context"]
    portfolio = ctx.portfolio

    print(f"\n{'='*55}")
    print("Portfolio Summary")
    print(f"{'='*55}")
    print(f"  Starting cash:    {portfolio.starting_cash:>12,.2f}")
    print(f"  Final value:      {portfolio.total_value:>12,.2f}")
    print(f"  Available cash:   {portfolio.available_cash:>12,.2f}")
    print(f"  P&L:              {portfolio.total_value - portfolio.starting_cash:>+12,.2f}")
    print(f"  Return:           {(portfolio.total_value / portfolio.starting_cash - 1):>+12.2%}")

    # Show open positions
    if portfolio.positions:
        print(f"\n  Open positions:")
        for sec, pos in portfolio.positions.items():
            print(f"    {sec}: {pos.amount} shares @ avg {pos.avg_cost:.2f}")

    # --- Compute metrics with analyze_returns ---
    print(f"\n{'='*55}")
    print("Risk/Return Metrics (analyze_returns)")
    print(f"{'='*55}")

    metrics = analyze_returns(result, risk_free_rate=0.03)
    if metrics:
        print(f"  Total return:      {metrics['total_return']:>10.2%}")
        print(f"  Annual return:     {metrics['annual_return']:>10.2%}")
        print(f"  Annual volatility: {metrics['annual_volatility']:>10.2%}")
        print(f"  Sharpe ratio:      {metrics['sharpe_ratio']:>10.2f}")
        print(f"  Sortino ratio:     {metrics.get('sortino_ratio', 0):>10.2f}")
        print(f"  Max drawdown:      {metrics['max_drawdown']:>10.2%}")
        print(f"  Calmar ratio:      {metrics.get('calmar_ratio', 0):>10.2f}")
        print(f"  Win rate:          {metrics.get('win_rate_trade', 0):>10.1%}")
        print(f"  Trade count:       {metrics.get('trade_count', 0):>10.0f}")
        print(f"  Alpha:             {metrics.get('alpha', 0):>+10.2%}")
        print(f"  Beta:              {metrics.get('beta', 0):>10.2f}")
    else:
        print("  Could not compute metrics (insufficient recorded data)")
