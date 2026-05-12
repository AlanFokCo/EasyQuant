"""Example 2: Writing strategies.

Demonstrates how to write trading strategies using the eqlib API.
Strategy framework uses a standard event-driven model:
- initialize(context): strategy setup
- handle_data(context, data): executed every bar
- run_daily(func): scheduled daily execution
- run_weekly(func): scheduled weekly execution
- run_monthly(func): scheduled monthly execution
- g.*: global variables for strategy parameters
- context.portfolio: account state
"""

from eqlib import *


# ============================================================
# Strategy 1: Moving Average Crossover
# ============================================================

def ma_cross_initialize(context):
    """MA crossover strategy initialization."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(ma_cross_handle, time="every_bar")

    log.info("MA crossover init: %s, MA%d/MA%d" % (
        g.security, g.fast_period, g.slow_period))


def ma_cross_handle(context):
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

    # Golden cross: buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("Golden cross BUY: %s @ %.3f" % (security, current_price))

    # Death cross: sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Death cross SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma)


# ============================================================
# Strategy 2: RSI Overbought/Oversold
# ============================================================

def rsi_initialize(context):
    """RSI strategy initialization."""
    g.security = "000001"
    g.rsi_period = 14
    g.overbought = 70
    g.oversold = 30

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(rsi_handle, time="every_bar")

    log.info("RSI strategy init: %s, period=%d" % (g.security, g.rsi_period))


def rsi_handle(context):
    """RSI trading logic."""
    security = g.security
    close_data = attribute_history(security, 30, "1d", ["close"])

    if close_data.empty or len(close_data) < g.rsi_period + 1:
        return

    delta = close_data["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.tail(g.rsi_period).mean()
    avg_loss = loss.tail(g.rsi_period).mean()

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    current_price = close_data["close"].iloc[-1]
    log.info("RSI=%.1f, price=%.3f" % (rsi, current_price))

    # Oversold: buy
    if rsi < g.oversold:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash * 0.9)
            log.info("RSI oversold BUY: %s @ %.3f, RSI=%.1f" % (security, current_price, rsi))

    # Overbought: sell
    elif rsi > g.overbought:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("RSI overbought SELL: %s @ %.3f, RSI=%.1f" % (security, current_price, rsi))

    record(price=current_price, rsi=rsi)


# ============================================================
# Strategy 3: Multi-stock Rotation (equal weight)
# ============================================================

def multi_stock_initialize(context):
    """Multi-stock strategy initialization."""
    g.stocks = ["601390", "000001", "600036"]
    g.lookback = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = g.stocks
    run_weekly(multi_stock_handle, day_of_week=0, time="09:30")

    log.info("Multi-stock strategy init: %s (rebalance Monday)" % g.stocks)


def multi_stock_handle(context):
    """Equal-weight rotation logic."""
    prices = {}
    for sec in g.stocks:
        df = attribute_history(sec, g.lookback, "1d", ["close"])
        if not df.empty:
            prices[sec] = df["close"].iloc[-1]

    if len(prices) < len(g.stocks):
        return

    per_stock_cash = context.portfolio.available_cash / len(g.stocks)
    for sec in g.stocks:
        if sec not in context.portfolio.positions \
           or context.portfolio.positions[sec].amount == 0:
            if per_stock_cash > 1000:
                order_value(sec, per_stock_cash)

    record(total_value=context.portfolio.total_value)
