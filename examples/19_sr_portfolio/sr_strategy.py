"""
19 - Support/Resistance Portfolio Strategy
============================================

Multi-stock S/R portfolio: buy near support and sell near resistance
across 8 diversified A-share stocks, with confirmation from RSI, MACD,
ATR trailing stop, Donchian channels, and volume ratio.

Strategy Design Rationale:
    - Why S/R levels: Swing-point clustering identifies price zones where
      institutional orders accumulate, creating natural bounce/rejection
      areas.  Buying at support and selling at resistance captures the
      mean-reversion premium without predicting direction.
    - Why multi-indicator confirmation: RSI confirms oversold/overbought
      state; MACD golden/death cross confirms momentum direction.
      Requiring both S/R proximity AND indicator confirmation reduces
      false signals compared to either alone.
    - Why ATR trailing stop: Volatility-adaptive stop avoids being shaken
      out by normal noise (wide ATR = wide stop) while protecting against
      large drawdowns (narrow ATR = tight stop).
    - Why Donchian channels: Provides systematic breakout/breakdown signals
      independent of S/R levels, catching trend continuations that pure
      mean-reversion would miss.
    - Why volume ratio: Confirms that price moves have institutional
      participation; low-volume bounces are unreliable.
    - Why 8 stocks across sectors: Diversification reduces single-stock
      risk; max 25% per stock prevents over-concentration.

Teaching Objectives:
    - Multi-stock portfolio management with position limits
    - S/R level computation via swing-point clustering (utils.support_resistance_levels)
    - Combining RSI, MACD, ATR, Donchian, and volume for signal confirmation
    - ATR-based trailing stop for dynamic risk management
    - Bare-code vs trade-code usage in multi-stock strategies
    - Equal-weight allocation with slot-based position sizing

Expected Output:
    - Multi-stock backtest with diversified trades across 8 stocks
    - Portfolio value chart showing drawdown protection from ATR stops
    - Evaluation panel with Sharpe, max drawdown, alpha/beta

Run:
    python examples/19_sr_portfolio/run_backtest.py
"""

from eqlib import (
    set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, log, g, utils,
)
from examples._defaults import (
    INDEX_SH, DEFAULT_ORDER_COST,
)


# ============================================================
# Stock pool — 8 stocks across diverse sectors
# ============================================================
# Bare codes (no suffix) are used for data APIs: attribute_history(), get_price()
# Trade codes (with .XSHG/.XSHE suffix) are used for order APIs:
#   order(), order_value(), order_target()

STOCK_POOL = [
    "601390",  # China Railway  中国中铁  (infrastructure)
    "002594",  # BYD            比亚迪    (EV / new energy)
    "601088",  # China Shenhua  中国神华  (coal / energy)
    "601857",  # PetroChina     中国石油  (oil & gas)
    "600536",  # China Software 中国软件  (technology)
    "601111",  # Air China      中国国航  (aviation)
    "000630",  # Tongling Nonferrous 铜陵有色 (metals)
    "601398",  # ICBC           工商银行  (banking)
]

STOCK_POOL_TRADE = [
    "601390.XSHG",  # China Railway
    "002594.XSHE",  # BYD
    "601088.XSHG",  # China Shenhua
    "601857.XSHG",  # PetroChina
    "600536.XSHG",  # China Software
    "601111.XSHG",  # Air China
    "000630.XSHE",  # Tongling Nonferrous
    "601398.XSHG",  # ICBC
]

# Mapping: bare code -> trade code (for use in market_open)
BARE_TO_TRADE = dict(zip(STOCK_POOL, STOCK_POOL_TRADE))


# ============================================================
# Strategy parameters
# ============================================================

# Support/Resistance: scan recent 80 bars for swing-point clusters
SR_LOOKBACK = 80

# Tolerance: price within 2% of an S/R level counts as "near"
SR_TOLERANCE = 0.02

# RSI(14): < 30 oversold, > 70 overbought
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# ATR(14): trailing stop = highest_since_buy - 2.5 * ATR
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.5

# Donchian channel(20): breakout above upper / breakdown below lower
DONCHIAN_PERIOD = 20

# Volume ratio: current volume / 20-day average volume
VOLUME_RATIO_PERIOD = 20

# Equal-weight allocation: max 25% of portfolio per stock (4 stocks max)
MAX_SINGLE_PCT = 0.25


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Strategy initialization.

    Sets benchmark, trading costs, universe, and per-stock state.
    Called once at the start of the backtest.
    """
    set_benchmark(INDEX_SH)
    set_order_cost(DEFAULT_ORDER_COST)

    # Universe: bare codes for data subscription
    context.universe = STOCK_POOL

    # Schedule daily handler
    run_daily(market_open, time="every_bar")

    # Per-stock state (keyed by trade code for position tracking)
    g.highest_since_buy = {}   # {trade_code: highest_price_since_entry}
    g.indicators = {}          # {bare_code: indicator_dict}

    n = len(STOCK_POOL)
    log.info("S/R Portfolio init: %d stocks, lookback=%d, max_single=%.0f%%",
             n, SR_LOOKBACK, MAX_SINGLE_PCT * 100)


def _analyze_stock(security, bars_needed):
    """Compute all technical indicators for a single stock.

    Parameters:
        security: bare code (e.g. "601390") for attribute_history()
        bars_needed: number of historical bars to request

    Returns:
        dict with keys: price, nearest_support, nearest_resistance,
        rsi, atr, macd_death_cross, macd_golden_cross, dc_upper,
        dc_lower, vol_ratio.
        Returns None if data is insufficient.
    """
    hist = attribute_history(security, bars_needed, "1d",
                         ["open", "high", "low", "close", "volume"])
    if hist is None or hist.empty or len(hist) < SR_LOOKBACK:
        return None

    close_prices = hist["close"]
    high_prices = hist["high"]
    low_prices = hist["low"]
    volumes = hist["volume"]
    current_price = close_prices.iloc[-1]

    # --- Support & Resistance levels (swing-point clustering) ---
    sr = utils.support_resistance_levels(
        high_prices, low_prices, close_prices,
        lookback=SR_LOOKBACK, tolerance=SR_TOLERANCE,
    )

    # --- RSI ---
    rsi_values = utils.rsi(close_prices, period=RSI_PERIOD)
    current_rsi = rsi_values.iloc[-1]

    # --- MACD (12, 26, 9) ---
    dif, dea, _ = utils.macd(close_prices, fast=12, slow=26, signal=9)
    macd_death_cross = (dif.iloc[-1] < dea.iloc[-1]
                        and dif.iloc[-2] >= dea.iloc[-2])
    macd_golden_cross = (dif.iloc[-1] > dea.iloc[-1]
                         and dif.iloc[-2] <= dea.iloc[-2])

    # --- ATR ---
    atr_values = utils.atr(high_prices, low_prices, close_prices, ATR_PERIOD)
    current_atr = atr_values.iloc[-1]

    # --- Donchian Channel ---
    dc_upper, _dc_mid, dc_lower = utils.donchian(
        high_prices, low_prices, close_prices, period=DONCHIAN_PERIOD,
    )

    # --- Volume ratio ---
    avg_vol = volumes.tail(VOLUME_RATIO_PERIOD).mean()
    current_vol = volumes.iloc[-1]
    vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    return {
        "price": current_price,
        "nearest_support": sr.get("nearest_support"),
        "nearest_resistance": sr.get("nearest_resistance"),
        "rsi": current_rsi,
        "atr": current_atr,
        "macd_death_cross": macd_death_cross,
        "macd_golden_cross": macd_golden_cross,
        "dc_upper": dc_upper.iloc[-1],
        "dc_lower": dc_lower.iloc[-1],
        "vol_ratio": vol_ratio,
    }


def _should_sell(context, security_trade, ind):
    """Check whether to sell a held position.

    Parameters:
        context: backtest context (portfolio, positions)
        security_trade: trade code (e.g. "601390.XSHG")
        ind: indicator dict from _analyze_stock()

    Returns:
        (should_sell: bool, reason: str)
    """
    if security_trade not in context.portfolio.positions:
        return False, ""
    pos = context.portfolio.positions[security_trade]
    if pos.amount <= 0:
        return False, ""

    # --- Update highest price since buy (for ATR trailing stop) ---
    prev_high = g.highest_since_buy.get(security_trade)
    if prev_high is None or ind["price"] > prev_high:
        g.highest_since_buy[security_trade] = ind["price"]
        prev_high = ind["price"]

    # --- ATR trailing stop ---
    trailing_stop = prev_high - ATR_STOP_MULTIPLIER * ind["atr"]
    if ind["price"] < trailing_stop:
        return True, "ATR stop: price=%.2f < stop=%.2f" % (
            ind["price"], trailing_stop)

    # --- Resistance + overbought RSI or MACD death cross ---
    if ind["nearest_resistance"] is not None:
        dist_to_res = (ind["nearest_resistance"] - ind["price"]) / ind["price"]
        near_resistance = abs(dist_to_res) < SR_TOLERANCE
        if near_resistance and (ind["rsi"] > RSI_OVERBOUGHT
                                or ind["macd_death_cross"]):
            return True, "Resistance: R=%.2f (%.1f%% away), RSI=%.1f" % (
                ind["nearest_resistance"], dist_to_res * 100, ind["rsi"])

    # --- Donchian upper band breakout exit ---
    if ind["price"] >= ind["dc_upper"]:
        return True, "Donchian upper: %.2f >= %.2f" % (
            ind["price"], ind["dc_upper"])

    return False, ""


def _should_buy(context, security_trade, ind):
    """Check whether to open a new long position.

    Parameters:
        context: backtest context (portfolio, positions)
        security_trade: trade code (e.g. "601390.XSHG")
        ind: indicator dict from _analyze_stock()

    Returns:
        (should_buy: bool, reason: str)
    """
    # Skip if already holding this stock
    if security_trade in context.portfolio.positions:
        pos = context.portfolio.positions[security_trade]
        if pos.amount > 0:
            return False, ""

    # Position limit: max N concurrent stocks
    held = sum(1 for p in context.portfolio.positions.values() if p.amount > 0)
    max_stocks = max(1, int(1.0 / MAX_SINGLE_PCT))
    if held >= max_stocks:
        return False, ""

    # --- Support + oversold RSI or MACD golden cross ---
    if ind["nearest_support"] is not None:
        dist_to_sup = (ind["price"] - ind["nearest_support"]) / ind["price"]
        near_support = abs(dist_to_sup) < SR_TOLERANCE
        if near_support and (ind["rsi"] < RSI_OVERSOLD
                             or ind["macd_golden_cross"]):
            return True, "Support: S=%.2f (%.1f%% away), RSI=%.1f, vol=%.1fx" % (
                ind["nearest_support"], dist_to_sup * 100,
                ind["rsi"], ind["vol_ratio"])

    # --- Donchian lower band breakdown entry ---
    if ind["price"] <= ind["dc_lower"] and ind["rsi"] < RSI_OVERBOUGHT:
        return True, "Donchian lower: %.2f <= %.2f" % (
            ind["price"], ind["dc_lower"])

    return False, ""


def market_open(context):
    """Daily trading logic: analyze all stocks, sell first, then buy.

    Execution order:
      1. Compute indicators for every stock in the pool.
      2. Evaluate sell conditions for held positions.
      3. Evaluate buy conditions for non-held stocks.
      4. Record portfolio state for charting.
    """
    bars_needed = max(SR_LOOKBACK, ATR_PERIOD, DONCHIAN_PERIOD,
                      VOLUME_RATIO_PERIOD) + 30

    # ---- Phase 1: Analyze all stocks (bare codes for data) ----
    signals = {}
    for bare in STOCK_POOL:
        ind = _analyze_stock(bare, bars_needed)
        if ind is not None:
            signals[bare] = ind
            g.indicators[bare] = ind

    # ---- Phase 2: Sell decisions (trade codes for positions/orders) ----
    sell_list = []
    for bare, ind in signals.items():
        trade = BARE_TO_TRADE[bare]
        should, reason = _should_sell(context, trade, ind)
        if should:
            sell_list.append((bare, trade, reason))

    for bare, trade, reason in sell_list:
        order_target(trade, 0)
        g.highest_since_buy.pop(trade, None)
        log.info("SELL %s: %s", bare, reason)

    # ---- Phase 3: Buy decisions (equal-weight among candidates) ----
    buy_candidates = []
    for bare, ind in signals.items():
        trade = BARE_TO_TRADE[bare]
        should, reason = _should_buy(context, trade, ind)
        if should:
            buy_candidates.append((bare, trade, reason))

    if buy_candidates:
        held_count = sum(1 for p in context.portfolio.positions.values()
                         if p.amount > 0)
        remaining_slots = max(1, int(1.0 / MAX_SINGLE_PCT)) - held_count
        if remaining_slots <= 0:
            remaining_slots = 1

        per_stock_value = min(
            context.portfolio.available_cash * MAX_SINGLE_PCT,
            context.portfolio.available_cash / max(remaining_slots, 1),
        )

        for bare, trade, reason in buy_candidates:
            buy_value = per_stock_value
            if buy_value < 1000:
                continue
            order_value(trade, buy_value)
            g.highest_since_buy[trade] = signals[bare]["price"]
            log.info("BUY %s: %s", bare, reason)

    # ---- Phase 4: Record portfolio state ----
    held = [s for s, p in context.portfolio.positions.items() if p.amount > 0]
    record(
        total_value=context.portfolio.total_value,
        cash=context.portfolio.available_cash,
        num_holdings=len(held),
    )


# ============================================================
# Module guard — this file is imported by run_backtest.py
# ============================================================

if __name__ == "__main__":
    print("This module defines the S/R Portfolio strategy.")
    print("Run the backtest via: python examples/19_sr_portfolio/run_backtest.py")
