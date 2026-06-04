"""
16 - MACD Trend Following with Volume Confirmation
===================================================

MACD (Moving Average Convergence Divergence) trend following
strategy with volume confirmation and ATR trailing stop.
Only enters when MACD golden cross is accompanied by above-average
volume, reducing false signal entries.

Strategy Design Rationale:
    - Why MACD: Captures momentum shifts with built-in signal line.
      12/26/9 parameters are the industry standard (Appel, 1979).
    - Why volume confirmation: MACD alone generates many false signals
      in choppy markets. Requiring volume > 1.5× average filters out
      low-conviction crossovers.
    - Target: 002594 (BYD) — high liquidity, clear trending behavior
      in the EV sector.
    - Applicable: Trending stocks with clear momentum shifts.
    - Not applicable: Low-volume or range-bound stocks.

Teaching Objectives:
    - utils.macd() returning DIF, DEA, and histogram
    - Volume confirmation for signal quality
    - ATR trailing stop for dynamic risk management
    - Combining multiple indicators for robust signals

Expected Output:
    - Backtest with evaluation panel
    - Sharpe ratio in -1 to +3 range
    - Trade count > 5

Run:
    python examples/16_macd_volume.py
"""

import os

from eqlib import (
    run_strategy, set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, log, g, utils,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available, print_evaluation,
)


# ============================================================
# Strategy parameters
# ============================================================

# BYD: high liquidity, trending EV stock
SECURITY = STOCKS["ev"]
SECURITY_TRADE = STOCKS_TRADE["ev"]

# MACD: standard 12/26/9 (Appel's original parameters)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Volume confirmation: only trade when volume > 1.5× 20-day average
VOLUME_RATIO_THRESHOLD = 1.5
VOLUME_AVG_PERIOD = 20

# ATR trailing stop: 2.5× for trend-following (wider than mean-reversion)
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.5


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """MACD + volume confirmation + ATR trailing stop."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = SECURITY
    g.security_trade = SECURITY_TRADE
    g.entry_price = None

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("MACD strategy: %d/%d/%d, vol ratio>%.1f, ATR stop=%.1fx",
             MACD_FAST, MACD_SLOW, MACD_SIGNAL,
             VOLUME_RATIO_THRESHOLD, ATR_MULTIPLIER)


def market_open(context):
    """MACD trend following with volume confirmation."""
    security = g.security
    security_trade = g.security_trade

    # Fetch OHLCV data
    bars_needed = MACD_SLOW + MACD_SIGNAL + 10
    hist = attribute_history(security, bars_needed, "1d",
                         ["high", "low", "close", "volume"])
    if hist is None or hist.empty or len(hist) < MACD_SLOW + MACD_SIGNAL:
        return

    close = hist["close"]
    high = hist["high"]
    low = hist["low"]
    volume = hist["volume"]
    current_price = close.iloc[-1]

    # Calculate MACD
    dif, dea, macd_hist = utils.macd(close, fast=MACD_FAST,
                                      slow=MACD_SLOW, signal=MACD_SIGNAL)

    # Calculate average volume for confirmation
    avg_volume = volume.rolling(VOLUME_AVG_PERIOD).mean()
    current_volume = volume.iloc[-1]
    vol_ratio = current_volume / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 0

    # Calculate ATR for trailing stop
    atr_values = utils.atr(high, low, close, period=ATR_PERIOD)
    current_atr = atr_values.iloc[-1]
    atr_stop = current_price - current_atr * ATR_MULTIPLIER

    # Detect MACD crossover
    if len(dif.dropna()) < 2 or len(dea.dropna()) < 2:
        return

    macd_golden = (dif.iloc[-2] <= dea.iloc[-2]) and (dif.iloc[-1] > dea.iloc[-1])
    macd_death = (dif.iloc[-2] >= dea.iloc[-2]) and (dif.iloc[-1] < dea.iloc[-1])

    # Volume confirmation: only trade when volume is above average
    volume_confirmed = vol_ratio > VOLUME_RATIO_THRESHOLD

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if has_position:
        # === ATR trailing stop ===
        if g.entry_price is None:
            g.entry_price = context.portfolio.positions[security_trade].avg_cost

        if current_price < atr_stop:
            order_target(security_trade, 0)
            pnl = (current_price - g.entry_price) / g.entry_price
            log.info("ATR STOP: %s @ %.2f, stop=%.2f, P&L=%.1f%%",
                     security, current_price, atr_stop, pnl * 100)
            g.entry_price = None
            return

        # === MACD death cross exit ===
        if macd_death:
            order_target(security_trade, 0)
            pnl = (current_price - g.entry_price) / g.entry_price
            log.info("MACD DEATH EXIT: %s @ %.2f, P&L=%.1f%%",
                     security, current_price, pnl * 100)
            g.entry_price = None
            return

    else:
        # === MACD golden cross + volume confirmation ===
        if macd_golden and volume_confirmed:
            cash = context.portfolio.available_cash
            if cash > current_price * 100:
                order_value(security_trade, cash * 0.95)
                g.entry_price = current_price
                log.info("MACD BUY: %s @ %.2f, vol_ratio=%.1fx, DIF=%.4f",
                         security, current_price, vol_ratio, dif.iloc[-1])

    # Record for charting
    record(
        price=current_price,
        dif=dif.iloc[-1],
        dea=dea.iloc[-1],
        macd=macd_hist.iloc[-1],
        vol_ratio=vol_ratio,
        atr_stop=atr_stop,
        total_value=context.portfolio.total_value,
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("16 - MACD Trend Following + Volume Confirmation")
    print("=" * 55)

    actual_start, actual_end = verify_data_available(
        SECURITY, START_DATE, END_DATE)

    os.makedirs("reports", exist_ok=True)

    result = run_strategy(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[SECURITY],
        report_dir="reports",
        use_local=True,
    )

    if result:
        print_evaluation(result, "MACD + Volume (12/26/9)")
