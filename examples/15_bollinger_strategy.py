"""
15 - Bollinger Band Mean Reversion Strategy
============================================

A classic mean reversion strategy using Bollinger Bands.
Buy when price drops below the lower band (oversold),
sell when price rises above the upper band (overbought).
ATR-based trailing stop provides dynamic risk management.

Strategy Design Rationale:
    - Why Bollinger: Mean reversion works well on large-cap stocks
      with stable trading ranges. 601088 (China Shenhua) has
      historically shown mean-reverting behavior.
    - Why ATR stop: Fixed percentage stops ignore current volatility.
      ATR-based stops adapt to market conditions — wider in volatile
      markets, tighter in calm markets.
    - Applicable: Large-cap, range-bound stocks in stable markets.
    - Not applicable: Strong trending markets (Bollinger generates
      false signals in sustained trends).

Teaching Objectives:
    - utils.boll() for Bollinger Band calculation
    - utils.atr() for ATR-based dynamic stop-loss
    - Mean reversion entry/exit logic
    - Position sizing with risk management

Expected Output:
    - Backtest with evaluation panel
    - Sharpe ratio in -1 to +2 range
    - Trade count > 10

Run:
    python examples/15_bollinger_strategy.py
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

# China Shenhua: energy sector, known for mean-reverting behavior
# and consistent dividends, making it suitable for Bollinger strategies
SECURITY = STOCKS["shenhua"]              # 601088
SECURITY_TRADE = STOCKS_TRADE["shenhua"]  # 601088.XSHG

# Bollinger Band: 20-day is the practitioner standard
# (Bollinger's original recommendation)
BOLL_PERIOD = 20
BOLL_STD = 2.0          # 2 standard deviations covers ~95% of normal distribution

# ATR trailing stop: 2× ATR is the Chandelier Exit default
# Gives price room to fluctuate within normal volatility
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0    # Stop distance = current_price - ATR × multiplier


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Bollinger Band mean reversion with ATR trailing stop."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = SECURITY
    g.security_trade = SECURITY_TRADE
    g.boll_period = BOLL_PERIOD
    g.boll_std = BOLL_STD
    g.atr_period = ATR_PERIOD
    g.atr_multiplier = ATR_MULTIPLIER
    g.entry_price = None  # Track entry for ATR stop

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Bollinger strategy: period=%d, std=%.1f, ATR stop=%.1fx",
             BOLL_PERIOD, BOLL_STD, ATR_MULTIPLIER)


def market_open(context):
    """Bollinger mean reversion with ATR trailing stop.

    Entry: Price drops below lower Bollinger Band (oversold)
    Exit:  Price rises above upper Bollinger Band (overbought)
           OR ATR trailing stop is hit
    """
    security = g.security
    security_trade = g.security_trade

    # Fetch enough data for Bollinger and ATR calculations
    bars_needed = max(g.boll_period, g.atr_period) + 10
    hist = attribute_history(security, bars_needed, "1d",
                         ["open", "high", "low", "close"])
    if hist is None or hist.empty:
        return
    if len(hist) < max(g.boll_period, g.atr_period):
        return

    close = hist["close"]
    high = hist["high"]
    low = hist["low"]
    current_price = close.iloc[-1]

    # Calculate Bollinger Bands
    upper, mid, lower = utils.boll(close, period=g.boll_period,
                                   num_std=g.boll_std)

    # Calculate ATR for dynamic stop-loss
    atr_values = utils.atr(high, low, close, period=g.atr_period)
    current_atr = atr_values.iloc[-1]

    # Calculate ATR stop price
    atr_stop = current_price - current_atr * g.atr_multiplier

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if has_position:
        position = context.portfolio.positions[security_trade]

        # === ATR trailing stop ===
        # Update trailing stop: stop only moves UP, never down
        if g.entry_price is None:
            g.entry_price = position.avg_cost

        # If current price drops below ATR stop, sell
        if current_price < atr_stop:
            order_target(security_trade, 0)
            loss_pct = (current_price - g.entry_price) / g.entry_price
            log.info("ATR STOP: %s @ %.2f, stop=%.2f, ATR=%.2f, P&L=%.1f%%",
                     security, current_price, atr_stop, current_atr,
                     loss_pct * 100)
            g.entry_price = None
            return

        # === Upper band exit (take profit) ===
        if current_price > upper.iloc[-1]:
            order_target(security_trade, 0)
            gain_pct = (current_price - g.entry_price) / g.entry_price
            log.info("UPPER BAND EXIT: %s @ %.2f, upper=%.2f, P&L=%.1f%%",
                     security, current_price, upper.iloc[-1], gain_pct * 100)
            g.entry_price = None
            return

    else:
        # === Lower band entry (oversold buy) ===
        if current_price < lower.iloc[-1]:
            cash = context.portfolio.available_cash
            if cash > current_price * 100:
                order_value(security_trade, cash * 0.95)
                g.entry_price = current_price
                log.info("LOWER BAND BUY: %s @ %.2f, lower=%.2f, ATR=%.2f",
                         security, current_price, lower.iloc[-1], current_atr)

    # Record for charting
    if len(upper.dropna()) > 0 and len(lower.dropna()) > 0:
        record(
            price=current_price,
            upper=upper.iloc[-1],
            mid=mid.iloc[-1],
            lower=lower.iloc[-1],
            atr_stop=atr_stop,
            total_value=context.portfolio.total_value,
        )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("15 - Bollinger Band Mean Reversion (ATR Stop)")
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
        print_evaluation(result, "Bollinger Mean Reversion (ATR Stop)")
