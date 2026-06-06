"""Moving Average Crossover Strategy.

Classic dual-MA strategy: buy on golden cross (fast MA crosses above slow MA),
sell on death cross (fast MA crosses below slow MA).

Ideal for: beginners learning trend-following and order execution.
"""
from eqlib import *


def initialize(context):
    """Initialize MA crossover strategy."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")
    log.info("MA Crossover initialized | security=%s | fast=%d | slow=%d"
             % (g.security, g.fast_period, g.slow_period))


def market_open(context):
    """Daily trading logic: golden cross buy, death cross sell."""
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


# Convenience: expose as a callable strategy object
ma_crossover_strategy = {
    "name": "Moving Average Crossover",
    "initialize": initialize,
    "market_open": market_open,
}
