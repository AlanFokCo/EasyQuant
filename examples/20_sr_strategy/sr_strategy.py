"""Portfolio Support & Resistance Strategy.

Buys near support levels and sells near resistance levels across
a pool of stocks, with confirmation from RSI, MACD, ATR, and volume.

Strategy logic:
  BUY  when price is near support AND RSI is oversold AND volume confirms
  SELL when price is near resistance AND RSI is overbought OR MACD death cross
  STOP LOSS via ATR trailing stop
  Equal-weight allocation: max 1/N of portfolio per stock

Stock pool:
    601390  China Railway 中国中铁 (infrastructure)
    518880  Gold ETF 黄金ETF
    002594  BYD 比亚迪 (EV/new energy)
    601088  China Shenhua 中国神华 (coal)
    601857  PetroChina 中国石油 (oil)
    600536  China Soft 中国软件 (technology)
    601111  Air China 中国国航 (aviation)
    000630  Tongling Nonferrous 铜陵有色 (metals)

Usage:
    from sr_strategy import initialize
    from eqlib import run_strategy

    run_strategy(
        initialize,
        start_date="2020-01-01",
        end_date="2026-03-30",
        starting_cash=1000000,
        benchmark="000001.XSHG",
        securities=["601390", "600916", "002594", "601088",
                    "601857", "600536", "601398", "518880"],
        use_local=True,
    )
"""

from eqlib import *
from eqlib import utils


# ============================================================
# Strategy parameters
# ============================================================

STOCK_POOL = [
    "601390",  # China Railway 中国中铁
    "518880",  # Gold ETF 黄金ETF
    "002594",  # BYD 比亚迪
    "601088",  # China Shenhua 中国神华
    "601857",  # PetroChina 中国石油
    "600536",  # China Soft 中国软件
    "601111",  # Air China 中国国航
    "000630",  # Tongling Nonferrous 铜陵有色
]
SR_LOOKBACK = 80                   # Support/resistance lookback (days)
SR_TOLERANCE = 0.02                # Tolerance near S/R level (2%)
RSI_PERIOD = 14                    # RSI period
RSI_OVERSOLD = 30                  # RSI oversold threshold
RSI_OVERBOUGHT = 70                # RSI overbought threshold
ATR_PERIOD = 14                    # ATR period
ATR_STOP_MULTIPLIER = 2.5          # Trailing stop: highest - N * ATR
DONCHIAN_PERIOD = 20               # Donchian channel period
VOLUME_RATIO_PERIOD = 20           # Volume confirmation period
MAX_SINGLE_PCT = 0.25              # Max position per stock (% of total)


# ============================================================
# Strategy code
# ============================================================

def initialize(context):
    """Strategy initialization."""
    set_benchmark("000001.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = STOCK_POOL
    run_daily(market_open, time="every_bar")

    # Per-stock state
    g.highest_since_buy = {}           # {security: highest_price}
    g.indicators = {}                  # {security: {rsi, atr, ...}}

    n = len(STOCK_POOL)
    log.info("S/R Portfolio init: %d stocks, lookback=%d, max_single=%.0f%%" % (
        n, SR_LOOKBACK, MAX_SINGLE_PCT * 100))


def _analyze_stock(security, bars_needed):
    """Calculate all indicators for a single stock.

    Returns a dict with price, support, resistance, rsi, atr,
    macd_death_cross, macd_golden_cross, vol_ratio,
    dc_upper, dc_lower, or None if data insufficient.
    """
    hist = attribute_history(security, bars_needed, "1d",
                             ["open", "high", "low", "close", "volume"])
    if hist.empty or len(hist) < SR_LOOKBACK:
        return None

    close_prices = hist["close"]
    high_prices = hist["high"]
    low_prices = hist["low"]
    volumes = hist["volume"]
    current_price = close_prices.iloc[-1]

    # Support & Resistance
    sr = utils.support_resistance_levels(
        high_prices, low_prices, close_prices,
        lookback=SR_LOOKBACK, tolerance=SR_TOLERANCE,
    )

    # RSI
    rsi_values = utils.rsi(close_prices, period=RSI_PERIOD)
    current_rsi = rsi_values.iloc[-1]

    # MACD
    dif, dea, _ = utils.macd(close_prices, fast=12, slow=26, signal=9)
    macd_death_cross = (dif.iloc[-1] < dea.iloc[-1] and
                        dif.iloc[-2] >= dea.iloc[-2])
    macd_golden_cross = (dif.iloc[-1] > dea.iloc[-1] and
                         dif.iloc[-2] <= dea.iloc[-2])

    # ATR
    atr_values = utils.atr(high_prices, low_prices, close_prices, ATR_PERIOD)
    current_atr = atr_values.iloc[-1]

    # Donchian Channel
    dc_upper, dc_mid, dc_lower = utils.donchian(
        high_prices, low_prices, close_prices, period=DONCHIAN_PERIOD)

    # Volume ratio
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


def _should_sell(context, security, ind):
    """Check if we should sell a held stock. Returns (should_sell, reason)."""
    if security not in context.portfolio.positions:
        return False, ""
    pos = context.portfolio.positions[security]
    if pos.amount <= 0:
        return False, ""

    # Update highest price since buy
    prev_high = g.highest_since_buy.get(security)
    if prev_high is None or ind["price"] > prev_high:
        g.highest_since_buy[security] = ind["price"]
        prev_high = ind["price"]

    # ATR trailing stop
    trailing_stop = prev_high - ATR_STOP_MULTIPLIER * ind["atr"]
    if ind["price"] < trailing_stop:
        return True, "ATR trailing stop: %.4f < %.4f" % (ind["price"], trailing_stop)

    # Resistance + overbought / MACD death cross
    if ind["nearest_resistance"] is not None:
        dist_to_res = (ind["nearest_resistance"] - ind["price"]) / ind["price"]
        near_resistance = dist_to_res < SR_TOLERANCE
        if near_resistance and (ind["rsi"] > RSI_OVERBOUGHT or ind["macd_death_cross"]):
            return True, "Resistance: R=%.4f (%.1f%% away), RSI=%.1f" % (
                ind["nearest_resistance"], dist_to_res * 100, ind["rsi"])

    # Donchian upper band
    if ind["price"] >= ind["dc_upper"]:
        return True, "Donchian upper: %.4f >= %.4f" % (ind["price"], ind["dc_upper"])

    return False, ""


def _should_buy(context, security, ind):
    """Check if we should buy a stock. Returns (should_buy, reason)."""
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            return False, ""

    # Position limit: max N stocks
    held = sum(1 for _, p in context.portfolio.positions.items() if p.amount > 0)
    max_stocks = max(1, int(1.0 / MAX_SINGLE_PCT))
    if held >= max_stocks:
        return False, ""

    # Support + oversold / MACD golden cross
    if ind["nearest_support"] is not None:
        dist_to_sup = (ind["price"] - ind["nearest_support"]) / ind["price"]
        near_support = dist_to_sup < SR_TOLERANCE
        if near_support and (ind["rsi"] < RSI_OVERSOLD or ind["macd_golden_cross"]):
            return True, "Support: S=%.4f (%.1f%% away), RSI=%.1f, vol=%.1f" % (
                ind["nearest_support"], dist_to_sup * 100, ind["rsi"], ind["vol_ratio"])

    # Donchian lower band
    if ind["price"] <= ind["dc_lower"] and ind["rsi"] < RSI_OVERBOUGHT:
        return True, "Donchian lower: %.4f <= %.4f" % (ind["price"], ind["dc_lower"])

    return False, ""


def market_open(context):
    """Daily trading logic: process all stocks in the pool."""
    bars_needed = max(SR_LOOKBACK, ATR_PERIOD, DONCHIAN_PERIOD,
                      VOLUME_RATIO_PERIOD) + 30

    # --- Phase 1: Analyze all stocks ---
    signals = {}
    for sec in STOCK_POOL:
        ind = _analyze_stock(sec, bars_needed)
        if ind is not None:
            signals[sec] = ind
            g.indicators[sec] = ind

    # --- Phase 2: Sell decisions ---
    sell_list = []
    for sec, ind in signals.items():
        should, reason = _should_sell(context, sec, ind)
        if should:
            sell_list.append((sec, reason))

    for sec, reason in sell_list:
        order_target(sec, 0)
        g.highest_since_buy[sec] = None
        log.info("SELL %s: %s" % (sec, reason))

    # --- Phase 3: Buy decisions (equal-weight among candidates) ---
    buy_candidates = []
    for sec, ind in signals.items():
        should, reason = _should_buy(context, sec, ind)
        if should:
            buy_candidates.append((sec, reason))

    if buy_candidates:
        held_count = sum(1 for s, p in context.portfolio.positions.items() if p.amount > 0)
        remaining_slots = max(1, int(1.0 / MAX_SINGLE_PCT)) - held_count
        if remaining_slots <= 0:
            remaining_slots = 1

        per_stock_value = min(
            context.portfolio.available_cash * MAX_SINGLE_PCT,
            context.portfolio.available_cash / remaining_slots,
        )

        for sec, reason in buy_candidates:
            buy_value = per_stock_value
            if buy_value < 1000:
                continue
            order_value(sec, buy_value)
            g.highest_since_buy[sec] = signals[sec]["price"]
            log.info("BUY %s: %s" % (sec, reason))

    # --- Phase 4: Record portfolio state ---
    held = [s for s, p in context.portfolio.positions.items() if p.amount > 0]
    record(
        total_value=context.portfolio.total_value,
        cash=context.portfolio.available_cash,
        num_holdings=len(held),
    )
