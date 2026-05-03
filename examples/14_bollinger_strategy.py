"""Example 14: Bollinger Band Mean Reversion Strategy.

Demonstrates a classic mean reversion strategy using Bollinger Bands:
- Buy when price touches the lower band (oversold)
- Sell when price touches the upper band (overbought)
- Include stop-loss for risk management

Usage:
    python examples/14_bollinger_strategy.py
"""

from eqlib import *
from eqlib import utils


# ============================================================
# Strategy parameters
# ============================================================

g.security = "601390"       # ICBC
g.period = 20               # Bollinger Band period
g.std_dev = 2.0             # Standard deviation multiplier
g.stop_loss_pct = 0.08      # Stop loss at 8% below entry


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Strategy initialization."""
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

    log.info("Bollinger Band init: %s, period=%d, std=%.1f" % (
        g.security, g.period, g.std_dev))


def market_open(context):
    """Daily trading logic: mean reversion on Bollinger Bands."""
    security = g.security

    # Fetch price history (need enough bars for Bollinger calculation)
    bars_needed = g.period + 10
    close_data = attribute_history(security, bars_needed, "1d", ["close"])
    if close_data.empty or len(close_data) < g.period:
        return

    close_prices = close_data["close"]
    current_price = close_prices.iloc[-1]

    # Calculate Bollinger Bands
    upper, mid, lower = utils.boll(close_prices, period=g.period, num_std=g.std_dev)

    # === Stop-loss check ===
    if security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        loss_pct = (current_price - position.avg_cost) / position.avg_cost
        if loss_pct < -g.stop_loss_pct:
            order_target(security, 0)
            log.info("Stop-loss SELL: %s @ %.3f, loss=%.1f%%" % (
                security, current_price, loss_pct * 100))
            return

        # === Take-profit: price reaches upper band ===
        if current_price > upper.iloc[-1] and position.amount > 0:
            order_target(security, 0)
            log.info("Upper band SELL: %s @ %.3f, upper=%.3f" % (
                security, current_price, upper.iloc[-1]))
            return

    # === Buy signal: price drops below lower band (oversold) ===
    if current_price < lower.iloc[-1]:
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("Lower band BUY: %s @ %.3f, lower=%.3f" % (
                security, current_price, lower.iloc[-1]))

    # Record for analysis
    record(
        price=current_price,
        upper=upper.iloc[-1],
        mid=mid.iloc[-1],
        lower=lower.iloc[-1],
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Bollinger Band Mean Reversion Strategy")
    print("=" * 60)

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2025-01-01",
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=["601390"],
        report_dir="reports",
    )
