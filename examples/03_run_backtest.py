"""Example 3: Running a backtest.

Demonstrates how to run a backtest and generate charts and reports.

Usage:
    python examples/03_run_backtest.py
"""

from eqlib import *
import datetime


def initialize(context):
    """Strategy initialization."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Backtest strategy init: %s" % g.security)


def market_open(context):
    """Daily trading logic."""
    security = g.security
    close_data = attribute_history(security, 25, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = close_data["close"].tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close_data["close"].tail(g.slow_period + 1).head(g.slow_period).mean()

    cash = context.portfolio.available_cash

    # Golden cross: buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, cash)
            log.info("Golden cross BUY: %s @ %.3f" % (security, current_price))

    # Death cross: sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Death cross SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma)


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    import os

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2024-12-31",
        starting_cash=100000,
        benchmark="000300.XSHG",
        report_dir="reports",
        securities=["601390"],
        use_local=True,
    )

    if result is not None:
        ctx = result["context"]
        trades = result["trade_log"]

        print(f"\n{'=' * 60}")
        print("Trade detail:")
        print(f"{'=' * 60}")
        for i, t in enumerate(trades, 1):
            action = "BUY" if t["type"] == "BUY" else "SELL"
            print(f"  {i}. {t['date']} {action} {t['security']} "
                  f"amount={t['amount']} price={t['price']:.3f} "
                  f"commission={t['commission']:.2f}")
