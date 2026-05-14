"""Example 15: MACD Trend Following with Volume Confirmation.

Demonstrates a trend-following strategy that combines:
- MACD golden/death cross for trend direction
- Volume surge for signal confirmation
- Trailing stop based on ATR (Average True Range)

Usage:
    python examples/15_macd_volume_strategy.py

⚠️  RISK DISCLOSURE — TEACHING EXAMPLE ONLY
    This script is provided for educational purposes to demonstrate the
    EasyQuant backtesting framework.  Do NOT deploy this strategy to live
    trading without thorough out-of-sample validation.  Past backtest
    performance does NOT guarantee future results.
"""

import os
from eqlib import *
from eqlib import utils


# ============================================================
# Strategy parameters
# ============================================================

SECURITY = "600536"           # China National Software 中国软件
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_RATIO = 1.0            # Volume must be 1.0x the 20-day average
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.5          # Trailing stop = highest - 2.5 * ATR


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

    context.universe = [SECURITY]
    run_daily(market_open, time="every_bar")

    log.info("MACD+Volume init: %s, MACD(%d,%d,%d)" % (
        SECURITY, MACD_FAST, MACD_SLOW, MACD_SIGNAL))


def market_open(context):
    """Daily trading logic: MACD + volume + ATR trailing stop."""
    security = SECURITY

    # Need enough history for MACD (slow period + signal period) + ATR + volume
    bars_needed = max(MACD_SLOW + MACD_SIGNAL, ATR_PERIOD) + 20
    hist = attribute_history(security, bars_needed, "1d",
                             ["open", "high", "low", "close", "volume"])
    if hist.empty or len(hist) < bars_needed - 10:
        return

    close_prices = hist["close"]
    high_prices = hist["high"]
    low_prices = hist["low"]
    volumes = hist["volume"]
    current_price = close_prices.iloc[-1]

    # === Calculate MACD ===
    dif, dea, macd_hist = utils.macd(
        close_prices, fast=MACD_FAST,
        slow=MACD_SLOW, signal=MACD_SIGNAL,
    )

    # MACD golden cross detection
    macd_cross_up = (dif.iloc[-1] > dea.iloc[-1] and
                     dif.iloc[-2] <= dea.iloc[-2])
    macd_cross_down = (dif.iloc[-1] < dea.iloc[-1] and
                       dif.iloc[-2] >= dea.iloc[-2])

    # === Volume confirmation ===
    avg_vol_20 = volumes.tail(20).mean()
    current_vol = volumes.iloc[-1]
    volume_confirmed = current_vol > avg_vol_20 * VOLUME_RATIO

    # === ATR trailing stop ===
    atr_values = utils.atr(high_prices, low_prices, close_prices, ATR_PERIOD)
    current_atr = atr_values.iloc[-1]

    if security in context.portfolio.positions:
        position = context.portfolio.positions[security]

        # Update trailing stop (highest price since entry minus ATR buffer)
        highest = high_prices.tail(20).max()
        trailing_stop = highest - ATR_MULTIPLIER * current_atr

        if current_price < trailing_stop:
            order_target(security, 0)
            log.info("ATR trailing stop SELL: %s @ %.3f, stop=%.3f, ATR=%.3f" % (
                security, current_price, trailing_stop, current_atr))
            return

        # MACD death cross: exit
        if macd_cross_down and position.amount > 0:
            order_target(security, 0)
            log.info("MACD death cross SELL: %s @ %.3f" % (
                security, current_price))
            return

    # === Buy signal: MACD golden cross + volume surge ===
    if macd_cross_up and volume_confirmed:
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("MACD golden cross + volume BUY: %s @ %.3f, vol_ratio=%.1f" % (
                security, current_price, current_vol / avg_vol_20))

    # Record for analysis
    record(
        price=current_price,
        dif=dif.iloc[-1],
        dea=dea.iloc[-1],
        volume_ratio=current_vol / avg_vol_20 if avg_vol_20 > 0 else 0,
        atr=current_atr,
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MACD Trend Following + Volume Confirmation Strategy")
    print("=" * 60)

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2025-01-01",
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=["600536"],
        report_dir="reports",
        use_local=True,
    )
