"""Example 21: All-Weather Alpha — Comprehensive Combined Strategy.

A production-ready, multi-layer quantitative strategy that integrates all major
techniques covered in the EasyQuant tutorials and examples:

  Layer 1 — Multi-factor weekly stock selection (Tutorial 08, Example 16)
      Momentum factor  : 20-day price return           (weight 35 %)
      Volume factor    : 5-day / 20-day average volume (weight 30 %)
      Reversal factor  : negative 5-day return          (weight 15 %)
      Volatility factor: negative 20-day return std-dev (weight 20 %)
      Each factor is Z-Score normalised across the whole pool before weighting.

  Layer 2 — Industry-rotation scoring (Tutorial 07)
      Each candidate stock is tagged with its sector (8 sectors).
      A sector momentum bonus/malus adjusts the composite score so that
      stocks from currently strong sectors rank higher.

  Layer 3 — Technical entry & exit signals (Tutorials 06/04, Examples 14/15/20)
      Entry  : RSI < oversold  OR  price below Bollinger lower band
               AND (MACD golden cross  OR  near support level)
               AND volume confirms (current vol > 1.2 × 20-day avg)
      Exit   : ATR trailing stop
               OR  (RSI > overbought  AND  (Bollinger upper band / near resistance))
               OR  MACD death cross
               OR  Donchian upper-band breakout exit

  Layer 4 — Risk management & position sizing (Example 11)
      Equal-weight among top-N selected stocks.
      Hard position cap: max 20 % of total portfolio per stock (5 stocks max).
      Stop-loss floor  : –8 % from average cost (absolute hard stop).

  Lifecycle integration (Example 08)
      before_trading_start — ST-flag check, log pre-market state
      after_trading_end    — log post-close portfolio snapshot

Stock pool (12 stocks, 8 sectors):
    Banking      601398  ICBC 工商银行
    Liquor       600519  Kweichow Moutai 贵州茅台
    New Energy   002594  BYD 比亚迪
    Oil & Gas    601857  PetroChina 中国石油
    Coal         601088  China Shenhua 中国神华
    Infra        601390  China Railway 中国中铁
    Healthcare   600276  Hengrui Pharma 恒瑞医药
    Appliances   000333  Midea 美的集团
    Gold         600916  China Gold 中国黄金
    Liquor2      000858  Wuliangye 五粮液
    Insurance    601318  Ping An 中国平安
    Consumer     600887  Yili 伊利股份

Usage (backtest):
    python examples/21_combined_strategy/run_backtest.py

Usage (paper trade):
    python examples/21_combined_strategy/run_paper_trade.py

Usage (import as module):
    from combined_strategy import initialize
    from eqlib import run_strategy
    result = run_strategy(initialize, start_date="2022-01-01",
                          end_date="2024-12-31", starting_cash=500000,
                          securities=STOCK_POOL)
"""

import statistics

from eqlib import *
from eqlib import utils
from eqlib import get_north_money_flow


# ============================================================
# 1. Stock pool and sector mapping
# ============================================================

STOCK_POOL = [
    "601390",  # China Railway 中国中铁
    "600036",  # China Merchants Bank 招商银行
    "159819",  # ETF fund
    "518880",  # Gold ETF 黄金ETF
    "601088",  # China Shenhua 中国神华
    "601857",  # PetroChina 中国石油
    "002594",  # BYD 比亚迪
    "000768",  # AVIC Jonhon 中航光电
    "600536",  # China National Software 中国软件
    "601111",  # Air China 中国国航
    "601179",  # China XD Electric 中国西电
    "516090",  # ETF fund
]

# Map each stock to its sector (for sector-rotation bonus)
SECTOR_MAP = {
    "601390": "Infrastructure",
    "600036": "Banking",
    "159819": "ETF",
    "518880": "Gold",
    "601088": "Coal",
    "601857": "OilGas",
    "002594": "NewEnergy",
    "000768": "Technology",
    "600536": "Technology",
    "601111": "Infrastructure",
    "601179": "Energy",
    "516090": "ETF",
}

# For sector-rotation scoring we use the most liquid / representative
# stock from each sector to gauge sector momentum.
SECTOR_REPRESENTATIVES = {
    "Infrastructure":"601390",
    "Banking":       "600036",
    "Gold":          "518880",
    "Coal":          "601088",
    "OilGas":        "601857",
    "NewEnergy":     "002594",
    "Technology":    "600536",
    "Energy":        "601179",
    "ETF":           "516090",
}


# ============================================================
# 2. Strategy parameters (tunable)
# ============================================================

# --- Stock selection (weekly rebalance) ---
TOP_N                   = 5      # Hold top-N stocks at any time
MOMENTUM_PERIOD         = 20     # Momentum lookback (trading days)
REVERSAL_PERIOD         = 5      # Short-term reversal lookback
VOL_SHORT               = 5      # Volume ratio: short window
VOL_LONG                = 20     # Volume ratio: long window
SECTOR_LOOKBACK         = 10     # Sector momentum lookback (days)

# Factor weights (must sum to 1.0)
W_MOMENTUM  = 0.35
W_VOLUME    = 0.30
W_REVERSAL  = 0.15
W_VOLATILITY = 0.20

# --- Technical indicators ---
RSI_PERIOD     = 14
RSI_OVERSOLD   = 35    # More selective than the default 30
RSI_OVERBOUGHT = 65    # More selective than the default 70
BOLL_PERIOD    = 20    # Bollinger Band period
BOLL_STD       = 2.0   # Bollinger Band standard-deviation multiplier
MACD_FAST      = 12
MACD_SLOW      = 26
MACD_SIGNAL    = 9
ATR_PERIOD     = 14
ATR_MULTIPLIER = 2.5   # ATR trailing-stop multiplier
DONCHIAN_PERIOD = 20   # Donchian Channel period
SR_LOOKBACK    = 60    # Support/resistance lookback (days)
SR_TOLERANCE   = 0.025 # ±2.5 % tolerance to "near" a S/R level

# --- Risk / position ---
MAX_SINGLE_PCT    = 0.20   # Max 20 % of total value per stock
HARD_STOP_PCT     = 0.08   # Hard stop: sell if loss > 8 % of avg cost
VOL_CONFIRM_RATIO = 1.2    # Volume must be ≥ 1.2× 20-day avg to confirm buy

# --- Derived state (populated at runtime) ---
# g.selected_stocks     : list[str]  — top-N from weekly scoring
# g.highest_since_buy   : dict       — trailing-stop state
# g.sector_scores       : dict       — latest sector momentum scores


# ============================================================
# 3. Helper: Z-Score normalisation across a dict of values
# ============================================================

def _zscore_normalize(values_dict):
    """Return Z-Score–normalised copy of {code: raw_value}.

    Formula:
        z = (x - μ) / σ

    where μ = mean(values) and σ = std(values, ddof=1).
    Codes with None values are skipped; they receive z=0.
    """
    valid = {k: v for k, v in values_dict.items() if v is not None}
    if len(valid) < 2:
        return {k: 0.0 for k in values_dict}

    vals = list(valid.values())
    mu  = statistics.mean(vals)
    sig = statistics.stdev(vals) or 1e-9

    result = {k: 0.0 for k in values_dict}
    for code, val in valid.items():
        result[code] = (val - mu) / sig
    return result


# ============================================================
# 4. Multi-factor stock scoring (weekly)
# ============================================================

def _compute_factors(code):
    """Compute raw factor values for a single stock.

    Returns (momentum, volume_ratio, reversal, neg_volatility)
    or None if data are insufficient.

    Factor definitions
    ------------------
    Momentum   : ret_20 = (P_t / P_{t-20}) − 1
                 High momentum → price has been rising → buy signal.

    Volume     : vol_ratio = mean(vol[-5:]) / mean(vol[-20:])
                 Ratio > 1 means recent interest is above the norm →
                 confirms price moves with capital inflows.

    Reversal   : rev_5 = −((P_t / P_{t-5}) − 1)
                 Short-term reversal correction: a large 5-day gain
                 raises the reversal factor's *raw* value to be negative,
                 penalising recent over-runners and avoiding chasing tops.

    Volatility : neg_vol = −std(daily_returns[-20:])
                 Low-volatility stocks are preferred (lower drawdown risk).
                 We negate so that lower volatility → higher factor value.
    """
    bars_needed = MOMENTUM_PERIOD + 10
    hist = attribute_history(code, bars_needed, "1d", ["close", "volume"])
    if hist is None or hist.empty or len(hist) < MOMENTUM_PERIOD:
        return None

    close = hist["close"]
    vol   = hist["volume"]
    price = close.iloc[-1]

    # Price filter: skip penny stocks (< 3 ¥) and extreme-high stocks (> 600 ¥)
    if price < 3.0 or price > 600.0:
        return None

    # Factor 1 — Momentum (20-day)
    past_price = close.iloc[-MOMENTUM_PERIOD]
    if past_price <= 0:
        return None
    momentum = (price / past_price) - 1.0

    # Factor 2 — Volume ratio (5d / 20d)
    vol_short_avg = vol.tail(VOL_SHORT).mean()
    vol_long_avg  = vol.tail(VOL_LONG).mean()
    volume_ratio  = vol_short_avg / vol_long_avg if vol_long_avg > 0 else 1.0

    # Factor 3 — Short-term reversal correction (negative 5-day return)
    past5 = close.iloc[-REVERSAL_PERIOD] if len(close) >= REVERSAL_PERIOD else price
    reversal = -((price / past5) - 1.0) if past5 > 0 else 0.0

    # Factor 4 — Negative volatility (lower std → higher factor)
    daily_rets = close.pct_change().dropna().tail(MOMENTUM_PERIOD)
    neg_vol = -daily_rets.std() if len(daily_rets) >= 5 else 0.0

    return (momentum, volume_ratio, reversal, neg_vol)


def _score_sector_momentum():
    """Compute a sector momentum score for each sector.

    We use the 10-day return of each sector's representative stock as a
    proxy for sector strength.  The scores are then Z-Score–normalised.

    Returns dict {sector_name: z_score}.
    """
    raw = {}
    for sector, rep_code in SECTOR_REPRESENTATIVES.items():
        hist = attribute_history(rep_code, SECTOR_LOOKBACK + 5, "1d", ["close"])
        if hist is None or hist.empty or len(hist) < SECTOR_LOOKBACK:
            continue
        close = hist["close"]
        ret = (close.iloc[-1] / close.iloc[-SECTOR_LOOKBACK]) - 1.0
        raw[sector] = ret

    return _zscore_normalize(raw)


def rank_stocks_weekly(context):
    """Score and rank all stocks in the pool using the multi-factor model.

    Step 1 — Compute raw factor values for each stock.
    Step 2 — Z-Score–normalise each factor across the pool.
    Step 3 — Combine: score = Σ (w_i × z_i).
    Step 4 — Add sector-rotation bonus (0.1 × sector_z_score).
    Step 5 — Sort descending; return top-N list.

    Returns list[str]: codes of the selected top-N stocks.
    """
    # --- Step 1: Raw factors ---
    raw_data = {}
    for code in STOCK_POOL:
        f = _compute_factors(code)
        if f is not None:
            raw_data[code] = f

    if not raw_data:
        log.warning("No stocks passed factor computation; skipping rebalance.")
        return getattr(g, "selected_stocks", STOCK_POOL[:TOP_N])

    # --- Step 2: Normalise each factor ---
    z_mom  = _zscore_normalize({c: v[0] for c, v in raw_data.items()})
    z_vol  = _zscore_normalize({c: v[1] for c, v in raw_data.items()})
    z_rev  = _zscore_normalize({c: v[2] for c, v in raw_data.items()})
    z_nvol = _zscore_normalize({c: v[3] for c, v in raw_data.items()})

    # --- Step 3: Composite factor score ---
    scores = {}
    for code in raw_data:
        scores[code] = (
            W_MOMENTUM   * z_mom.get(code, 0.0) +
            W_VOLUME     * z_vol.get(code, 0.0) +
            W_REVERSAL   * z_rev.get(code, 0.0) +
            W_VOLATILITY * z_nvol.get(code, 0.0)
        )

    # --- Step 4: Sector-rotation bonus ---
    sector_z = _score_sector_momentum()
    for code in scores:
        sector = SECTOR_MAP.get(code, "")
        sz = sector_z.get(sector, 0.0)
        scores[code] += 0.10 * sz   # 10 % weight to sector momentum

    # --- Step 5: Rank and select top-N ---
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    log.info("=== Weekly factor scores ===")
    for i, (code, score) in enumerate(ranked):
        tag = " ← SELECTED" if i < TOP_N else ""
        log.info("  %2d. %s  score=%.4f%s" % (i + 1, code, score, tag))

    top_codes = [code for code, _ in ranked[:TOP_N]]
    return top_codes


# ============================================================
# 5. Per-stock technical indicator calculation (daily)
# ============================================================

def _compute_indicators(code):
    """Calculate all technical indicators needed for entry/exit decisions.

    Uses precomputed indicators from PreloadedData if available (fast path),
    otherwise falls back to on-the-fly computation.

    Indicators computed
    -------------------
    RSI-14      : Relative Strength Index — measures overbought/oversold.
                  RSI = 100 − 100 / (1 + AvgGain / AvgLoss)
    Bollinger   : Upper = MA(20) + 2σ,  Lower = MA(20) − 2σ
    MACD        : DIF = EMA(12) − EMA(26);  DEA = EMA(DIF, 9)
                  Signal: DIF crosses DEA.
    ATR-14      : Average True Range — dynamic volatility measure.
                  TR = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)
                  ATR = EMA(TR, 14)
    Donchian-20 : Upper = max(High, 20d);  Lower = min(Low, 20d)
    S/R levels  : Swing-high/low cluster analysis over 60 bars.
    Volume ratio: today's volume / 20-day average volume.

    Returns dict with all indicators, or None if data are insufficient.
    """
    from eqlib.engine import _get_preloaded

    preloaded = _get_preloaded()
    bars_needed = max(SR_LOOKBACK, MACD_SLOW + MACD_SIGNAL,
                      BOLL_PERIOD, ATR_PERIOD, DONCHIAN_PERIOD) + 30

    # Try fast path: precomputed indicators from PreloadedData
    if preloaded is not None and preloaded._indicators:
        ind_df = preloaded.get_indicators(code, bars_needed, _context_if_available())
        if ind_df is not None and not ind_df.empty and len(ind_df) >= SR_LOOKBACK:
            # Still need OHLCV for S/R levels and volume ratio
            hist = attribute_history(code, bars_needed, "1d",
                                     ["open", "high", "low", "close", "volume"])
            if hist is None or hist.empty or len(hist) < SR_LOOKBACK:
                return None

            close  = hist["close"]
            high   = hist["high"]
            low    = hist["low"]
            volume = hist["volume"]
            price  = close.iloc[-1]

            # --- Support / Resistance (not precomputed) ---
            sr = utils.support_resistance_levels(
                high, low, close,
                lookback=SR_LOOKBACK,
                tolerance=SR_TOLERANCE,
            )
            nearest_support    = sr.get("nearest_support")
            nearest_resistance = sr.get("nearest_resistance")

            # --- Volume ratio ---
            avg_vol_20  = volume.tail(VOL_LONG).mean()
            current_vol = volume.iloc[-1]
            vol_ratio   = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

            # Read precomputed indicator values
            last = ind_df.iloc[-1]
            dif_val = last["macd_dif"]
            dea_val = last["macd_dea"]
            if len(ind_df) >= 2:
                prev = ind_df.iloc[-2]
                macd_golden = (dif_val > dea_val and prev["macd_dif"] <= prev["macd_dea"])
                macd_death  = (dif_val < dea_val and prev["macd_dif"] >= prev["macd_dea"])
            else:
                macd_golden = False
                macd_death = False

            return {
                "price":             price,
                "rsi":               last["rsi"],
                "bb_upper":          last["bb_upper"],
                "bb_mid":            last["bb_mid"],
                "bb_lower":          last["bb_lower"],
                "macd_golden":       macd_golden,
                "macd_death":        macd_death,
                "dif":               dif_val,
                "dea":               dea_val,
                "atr":               last["atr"],
                "dc_upper":          last["dc_upper"],
                "dc_lower":          last["dc_lower"],
                "nearest_support":   nearest_support,
                "nearest_resistance":nearest_resistance,
                "vol_ratio":         vol_ratio,
            }

    # Fallback: full on-the-fly computation
    hist = attribute_history(code, bars_needed, "1d",
                             ["open", "high", "low", "close", "volume"])
    if hist is None or hist.empty or len(hist) < SR_LOOKBACK:
        return None

    close  = hist["close"]
    high   = hist["high"]
    low    = hist["low"]
    volume = hist["volume"]
    price  = close.iloc[-1]

    # --- RSI ---
    rsi_series = utils.rsi(close, period=RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]

    # --- Bollinger Bands ---
    bb_upper, bb_mid, bb_lower = utils.boll(close,
                                             period=BOLL_PERIOD,
                                             num_std=BOLL_STD)

    # --- MACD ---
    dif, dea, _ = utils.macd(close,
                              fast=MACD_FAST,
                              slow=MACD_SLOW,
                              signal=MACD_SIGNAL)
    macd_golden = (dif.iloc[-1] > dea.iloc[-1] and
                   dif.iloc[-2] <= dea.iloc[-2])
    macd_death  = (dif.iloc[-1] < dea.iloc[-1] and
                   dif.iloc[-2] >= dea.iloc[-2])

    # --- ATR ---
    atr_series   = utils.atr(high, low, close, ATR_PERIOD)
    current_atr  = atr_series.iloc[-1]

    # --- Donchian Channel ---
    dc_upper, _dc_mid, dc_lower = utils.donchian(high, low, close,
                                                  period=DONCHIAN_PERIOD)

    # --- Support / Resistance ---
    sr = utils.support_resistance_levels(
        high, low, close,
        lookback=SR_LOOKBACK,
        tolerance=SR_TOLERANCE,
    )
    nearest_support    = sr.get("nearest_support")
    nearest_resistance = sr.get("nearest_resistance")

    # --- Volume ratio ---
    avg_vol_20  = volume.tail(VOL_LONG).mean()
    current_vol = volume.iloc[-1]
    vol_ratio   = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

    return {
        "price":             price,
        "rsi":               current_rsi,
        "bb_upper":          bb_upper.iloc[-1],
        "bb_mid":            bb_mid.iloc[-1],
        "bb_lower":          bb_lower.iloc[-1],
        "macd_golden":       macd_golden,
        "macd_death":        macd_death,
        "dif":               dif.iloc[-1],
        "dea":               dea.iloc[-1],
        "atr":               current_atr,
        "dc_upper":          dc_upper.iloc[-1],
        "dc_lower":          dc_lower.iloc[-1],
        "nearest_support":   nearest_support,
        "nearest_resistance":nearest_resistance,
        "vol_ratio":         vol_ratio,
    }


def _context_if_available():
    """Return current_dt from context or None if not available."""
    try:
        from eqlib._state import _context
        if _context is not None:
            return _context.current_dt
    except Exception:
        pass
    return None


# ============================================================
# 6. Sell logic
# ============================================================

def _check_sell(context, code, ind):
    """Determine whether to sell a held position.

    Exit conditions (first match wins):
    1. Hard stop-loss  : current price ≤ avg_cost × (1 − 8 %)
       Justification: absolute floor that overrides all other signals.
    2. ATR trailing stop : price < highest_since_buy − ATR_mult × ATR
       Justification: dynamic stop that locks in profits as price rises.
    3. Bollinger upper + RSI overbought:
       price ≥ bb_upper  AND  rsi ≥ rsi_overbought
       Justification: price has stretched above the 2σ band while momentum
       is exhausted → mean-reversion exit.
    4. MACD death cross: DIF crosses below DEA
       Justification: trend reversal signal from Example 15.
    5. Donchian upper-band exit: price ≥ dc_upper
       Justification: price has reached the 20-day high → trailing exit
       used in Example 20.
    6. Near resistance + RSI overbought:
       price within sr_tolerance of nearest_resistance  AND  rsi overbought
       Justification: price at a proven supply zone while overbought.

    Returns (should_sell: bool, reason: str).
    """
    pos = context.portfolio.positions.get(code)
    if pos is None or pos.amount <= 0:
        return False, ""

    price    = ind["price"]
    avg_cost = pos.avg_cost

    # 1. Hard stop-loss
    if avg_cost > 0:
        loss_pct = (price - avg_cost) / avg_cost
        if loss_pct < -HARD_STOP_PCT:
            return True, "Hard stop-loss: loss=%.1f%% (> %.0f%%)" % (
                loss_pct * 100, HARD_STOP_PCT * 100)

    # 2. ATR trailing stop
    prev_high = g.highest_since_buy.get(code)
    if prev_high is None or price > prev_high:
        g.highest_since_buy[code] = price
        prev_high = price

    trailing_stop = prev_high - ATR_MULTIPLIER * ind["atr"]
    if price < trailing_stop:
        return True, "ATR trailing stop: price=%.4f < stop=%.4f" % (
            price, trailing_stop)

    # 3. Bollinger upper + overbought
    if (price >= ind["bb_upper"] and ind["rsi"] >= RSI_OVERBOUGHT):
        return True, "Bollinger upper+overbought: price=%.4f, RSI=%.1f" % (
            price, ind["rsi"])

    # 4. MACD death cross
    if ind["macd_death"]:
        return True, "MACD death cross: DIF=%.4f crossed below DEA=%.4f" % (
            ind["dif"], ind["dea"])

    # 5. Donchian upper breakout exit
    if price >= ind["dc_upper"]:
        return True, "Donchian upper exit: price=%.4f >= dc_upper=%.4f" % (
            price, ind["dc_upper"])

    # 6. Near resistance + overbought
    if ind["nearest_resistance"] is not None:
        dist = (ind["nearest_resistance"] - price) / price
        if 0 <= dist < SR_TOLERANCE and ind["rsi"] >= RSI_OVERBOUGHT:
            return True, (
                "Near resistance+overbought: R=%.4f (%.1f%% away), RSI=%.1f"
                % (ind["nearest_resistance"], dist * 100, ind["rsi"])
            )

    return False, ""


# ============================================================
# 7. Buy logic
# ============================================================

def _check_buy(context, code, ind):
    """Determine whether to open a new position.

    Entry conditions:
    A. The stock must be in this week's selected_stocks list.
       Justification: we only buy what the multi-factor model endorses.

    B. Position limit: cannot exceed max_single_pct of total portfolio,
       and total held positions must leave room for this stock.

    C. At least ONE oversold / reversal signal:
       - RSI ≤ rsi_oversold        (oversold — Tutorial 06)
       - price ≤ Bollinger lower   (below 2σ band — Example 14)
       - Donchian lower touch      (at 20-day low — Example 20)

    D. At least ONE trend / confirmation signal:
       - MACD golden cross          (trend turning up — Example 15)
       - Near support level         (supply zone — Example 20)

    E. Volume confirmation:
       current_vol ≥ vol_confirm_ratio × avg_vol_20
       Justification: price moves backed by volume are more reliable.
       (Example 15 uses the same 1.5× threshold; we use 1.2× to be
       slightly more inclusive.)

    Returns (should_buy: bool, reason: str).
    """
    # A. Must be in selected list
    if code not in g.selected_stocks:
        return False, ""

    # Already holding
    pos = context.portfolio.positions.get(code)
    if pos is not None and pos.amount > 0:
        return False, ""

    # B. Position-count limit
    held = sum(1 for p in context.portfolio.positions.values() if p.amount > 0)
    max_positions = max(1, int(1.0 / MAX_SINGLE_PCT))
    if held >= max_positions:
        return False, ""

    # C. Oversold / reversal signal
    oversold_signal = (
        ind["rsi"] <= RSI_OVERSOLD
        or ind["price"] <= ind["bb_lower"]
        or ind["price"] <= ind["dc_lower"]
    )
    if not oversold_signal:
        return False, ""

    # D. Confirmation signal
    near_support = False
    if ind["nearest_support"] is not None:
        dist = (ind["price"] - ind["nearest_support"]) / ind["price"]
        near_support = 0 <= dist < SR_TOLERANCE

    confirmation = ind["macd_golden"] or near_support
    if not confirmation:
        return False, ""

    # E. Volume confirmation
    if ind["vol_ratio"] < VOL_CONFIRM_RATIO:
        return False, ""

    reason = (
        "RSI=%.1f, boll_lower=%.4f, price=%.4f, MACD_golden=%s, "
        "support=%s, vol_ratio=%.2f"
        % (
            ind["rsi"], ind["bb_lower"], ind["price"],
            ind["macd_golden"],
            str(ind["nearest_support"]),
            ind["vol_ratio"],
        )
    )
    return True, reason


# ============================================================
# 8. Lifecycle callbacks
# ============================================================

def _before_market_open(context, data=None):
    """Pre-market preparation (registered via before_trading_start).

    Logs current portfolio state and warns about any ST stocks that
    may have been flagged overnight (see Example 08).
    """
    portfolio = context.portfolio
    held = [c for c, p in portfolio.positions.items() if p.amount > 0]
    log.info("PRE-MARKET | total=%.2f | cash=%.2f | positions=%d: %s" % (
        portfolio.total_value,
        portfolio.available_cash,
        len(held), str(held),
    ))

    # ST-flag check (if API is available; silently skip if not)
    try:
        universe = get_universe()
        if universe:
            st_map    = get_extras("is_st", security_list=universe)
            st_stocks = [c for c, flag in st_map.items() if flag]
            if st_stocks:
                log.warning("ST stocks in universe: %s" % str(st_stocks))
    except Exception:
        pass

    # North-capital regime signal (A-share specific)
    # 5-day rolling net buy → bull / bear / neutral
    try:
        north_df = get_north_money_flow()
        if not north_df.empty and "net_buy" in north_df.columns:
            recent_5d = north_df.tail(5)
            net_5d = recent_5d["net_buy"].sum()
            if net_5d > 50:
                g.regime = "bull"
                log.info("NORTH-CAPITAL REGIME: bull (5d net buy %.1f亿 > 50亿)" % net_5d)
            elif net_5d < -50:
                g.regime = "bear"
                log.info("NORTH-CAPITAL REGIME: bear (5d net buy %.1f亿 < -50亿)" % net_5d)
            else:
                g.regime = "neutral"
                log.info("NORTH-CAPITAL REGIME: neutral (5d net buy %.1f亿)" % net_5d)
        else:
            g.regime = "neutral"
    except Exception as exc:
        g.regime = "neutral"
        log.warning("North-capital data unavailable, regime=neutral (%s)" % exc)


def _after_market_close(context, data=None):
    """Post-close portfolio snapshot (registered via after_trading_end)."""
    portfolio = context.portfolio
    pnl     = portfolio.total_value - portfolio.starting_cash
    pnl_pct = pnl / portfolio.starting_cash * 100
    held    = sum(1 for p in portfolio.positions.values() if p.amount > 0)
    record(
        total_value=portfolio.total_value,
        cash=portfolio.available_cash,
        num_holdings=held,
        pnl_pct=pnl_pct,
    )
    log.info("POST-MARKET | total=%.2f | P&L %.2f (%.2f%%) | holdings=%d" % (
        portfolio.total_value, pnl, pnl_pct, held,
    ))


# ============================================================
# 9. Weekly rebalance callback
# ============================================================

def weekly_rebalance(context):
    """Monday rebalance: re-score stocks and adjust the target universe.

    1. Re-run the multi-factor model to get new top-N selection.
    2. Sell any position that is no longer in the top-N (and not stopped
       out by the daily logic — caught here as a catch-up).
    3. Update g.selected_stocks for the daily buy logic.
    """
    new_selected = rank_stocks_weekly(context)
    g.selected_stocks = new_selected

    log.info("Weekly selection: %s" % str(g.selected_stocks))

    # Proactively close positions ranked out of the top-N
    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[code]
        if pos.amount > 0 and code not in g.selected_stocks:
            order_target(code, 0)
            g.highest_since_buy[code] = None
            log.info("SELL (ranked out) %s" % code)


# ============================================================
# 10. Daily trading logic
# ============================================================

def daily_trading(context):
    """Daily bar: compute indicators, execute sell/buy decisions.

    Phase 1 — Compute indicators for all stocks.
    Phase 2 — Sell phase: process held positions first to free cash.
    Phase 3 — Buy phase: consider buy candidates from selected stocks.
    """
    # Phase 1 — Indicators
    indicators = {}
    for code in STOCK_POOL:
        ind = _compute_indicators(code)
        if ind is not None:
            indicators[code] = ind

    # Phase 2 — Sell decisions
    for code, ind in indicators.items():
        should_sell, reason = _check_sell(context, code, ind)
        if should_sell:
            order_target(code, 0)
            g.highest_since_buy[code] = None
            log.info("SELL %s | %s" % (code, reason))

    # Phase 3 — Buy decisions
    # Equal-weight allocation: invest max_single_pct × total_value per stock.
    buy_candidates = []
    for code in g.selected_stocks:
        ind = indicators.get(code)
        if ind is None:
            continue
        should_buy, reason = _check_buy(context, code, ind)
        if should_buy:
            buy_candidates.append((code, reason))

    if buy_candidates:
        total_value = context.portfolio.total_value
        # Regime-based position scaling: reduce size in bear, hold in neutral
        regime_scale = {"bull": 1.0, "neutral": 0.75, "bear": 0.5}.get(g.regime, 1.0)
        effective_max_pct = MAX_SINGLE_PCT * regime_scale
        per_stock_value = min(
            total_value * effective_max_pct,
            context.portfolio.available_cash / len(buy_candidates),
        )
        for code, reason in buy_candidates:
            if per_stock_value < 1000:
                log.info("  SKIP BUY %s: insufficient cash (%.0f)" % (
                    code, per_stock_value))
                continue
            order_value(code, per_stock_value)
            g.highest_since_buy[code] = indicators[code]["price"]
            log.info("BUY %s | value=%.0f | %s" % (code, per_stock_value, reason))


# ============================================================
# 11. Strategy initialisation
# ============================================================

def initialize(context):
    """Initialise the All-Weather Alpha combined strategy.

    Registers all callbacks:
    - before_trading_start  → pre-market log + ST check
    - after_trading_end     → post-close snapshot
    - run_weekly (Monday)   → multi-factor rebalance
    - run_daily  (every bar)→ indicator-based entry / exit
    """
    # Benchmark and cost model
    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,          # 0.1 % stamp duty on sells
        open_commission=0.0003,   # 0.03 % brokerage on buys
        close_commission=0.0003,  # 0.03 % brokerage on sells
        close_today_commission=0,
        min_commission=5,         # ¥5 minimum per order
    ))

    # Stock universe
    context.universe = STOCK_POOL

    # Runtime state
    g.selected_stocks   = STOCK_POOL[:TOP_N]  # bootstrap with first N
    g.highest_since_buy = {}                      # {code: float|None}
    g.regime            = "neutral"               # north-capital regime: bull/bear/neutral

    # Register lifecycle callbacks (Example 08 pattern)
    before_trading_start(_before_market_open)
    after_trading_end(_after_market_close)

    # Weekly rebalance every Monday (Tutorial 07 / 08 pattern)
    run_weekly(weekly_rebalance, day_of_week=0, time="every_bar")

    # Daily technical signals (Example 15 / 20 pattern)
    run_daily(daily_trading, time="every_bar")

    n = len(STOCK_POOL)
    log.info("=" * 60)
    log.info("All-Weather Alpha Combined Strategy — Initialized")
    log.info("  Stock pool  : %d stocks across 8 sectors" % n)
    log.info("  Top-N       : %d positions max" % TOP_N)
    log.info("  Max per pos : %.0f%%" % (MAX_SINGLE_PCT * 100))
    log.info("  Hard stop   : -%.0f%%" % (HARD_STOP_PCT * 100))
    log.info("  ATR mult    : %.1f×" % ATR_MULTIPLIER)
    log.info("=" * 60)
