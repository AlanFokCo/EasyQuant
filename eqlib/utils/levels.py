"""Support, resistance, and pivot point calculations.

Provides:
- Pivot Points: classic, Fibonacci, Woodie, Camarilla, DeMark
- Support / Resistance: swing-based (fractal), volume-profile,
  moving-average, round-number, Fibonacci retracement,
  Donchian channel, psychological levels
"""

import numpy as np
import pandas as pd


# ============================================================
# Pivot Points
# ============================================================

def pivot_classic(high: pd.Series, low: pd.Series, close: pd.Series):
    """Classic (Floor) Pivot Points.

    PP  = (H + L + C) / 3
    R1  = 2*PP - L
    S1  = 2*PP - H
    R2  = PP + (H - L)
    S2  = PP - (H - L)
    R3  = H + 2*(PP - L)
    S3  = L - 2*(H - PP)
    """
    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    return pp, r1, s1, r2, s2, r3, s3


def pivot_fibonacci(high: pd.Series, low: pd.Series, close: pd.Series):
    """Fibonacci Pivot Points.

    PP  = (H + L + C) / 3
    R1  = PP + 0.382 * (H - L)
    S1  = PP - 0.382 * (H - L)
    R2  = PP + 0.618 * (H - L)
    S2  = PP - 0.618 * (H - L)
    R3  = PP + 1.000 * (H - L)
    S3  = PP - 1.000 * (H - L)
    """
    pp = (high + low + close) / 3
    rng = high - low
    r1 = pp + 0.382 * rng
    s1 = pp - 0.382 * rng
    r2 = pp + 0.618 * rng
    s2 = pp - 0.618 * rng
    r3 = pp + 1.000 * rng
    s3 = pp - 1.000 * rng
    return pp, r1, s1, r2, s2, r3, s3


def pivot_woodie(high: pd.Series, low: pd.Series, close: pd.Series):
    """Woodie Pivot Points (gives more weight to close).

    PP  = (H + L + 2*C) / 4
    R1  = 2*PP - L
    S1  = 2*PP - H
    R2  = PP + (H - L)
    S2  = PP - (H - L)
    """
    pp = (high + low + 2 * close) / 4
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    return pp, r1, s1, r2, s2


def pivot_camarilla(high: pd.Series, low: pd.Series, close: pd.Series):
    """Camarilla Pivot Points (tighter levels for intraday).

    R4  = (H - L) * 1.1 / 2 + C    (strong resistance / breakout)
    R3  = (H - L) * 1.1 / 4 + C
    R2  = (H - L) * 1.1 / 6 + C
    R1  = (H - L) * 1.1 / 12 + C
    S1  = C - (H - L) * 1.1 / 12
    S2  = C - (H - L) * 1.1 / 6
    S3  = C - (H - L) * 1.1 / 4
    S4  = C - (H - L) * 1.1 / 2    (strong support / breakdown)
    """
    rng = high - low
    r4 = rng * 1.1 / 2 + close
    r3 = rng * 1.1 / 4 + close
    r2 = rng * 1.1 / 6 + close
    r1 = rng * 1.1 / 12 + close
    s1 = close - rng * 1.1 / 12
    s2 = close - rng * 1.1 / 6
    s3 = close - rng * 1.1 / 4
    s4 = close - rng * 1.1 / 2
    return r4, r3, r2, r1, s1, s2, s3, s4


def pivot_demark(high: pd.Series, low: pd.Series, close: pd.Series,
                 open_: pd.Series = None):
    """DeMark Pivot Points (uses open-close relationship).

    If C < O:   X = H + 2*L + C
    If C > O:   X = 2*H + L + C
    If C == O:  X = H + L + 2*C
    PP = X / 4
    R1 = X/2 - L
    S1 = X/2 - H
    """
    if open_ is None:
        open_ = close.shift(1).fillna(close)
    c = close.values
    o = open_.values
    x = np.where(c < o, high + 2 * low + close,
                 np.where(c > o, 2 * high + low + close,
                          high + low + 2 * close))
    x = pd.Series(x, index=close.index)
    pp = x / 4
    r1 = x / 2 - low
    s1 = x / 2 - high
    return pp, r1, s1


# ============================================================
# Support / Resistance via Swing Highs / Lows (Fractal)
# ============================================================

def swing_highs_lows(high: pd.Series, low: pd.Series,
                     left_bars: int = 5, right_bars: int = 5):
    """Identify swing highs and swing lows (fractal pivots).

    A swing high: a bar whose high is *strictly* greater than the
    `left_bars` bars immediately before it AND the `right_bars` bars
    immediately after it.

    A swing low: a bar whose low is *strictly* less than the
    `left_bars` bars before it AND the `right_bars` bars after it.

    The left and right windows are treated independently so that
    asymmetric values (e.g., left_bars=5, right_bars=3) are handled
    correctly.  Ties (two adjacent bars at the same price) are *not*
    flagged as swing points, preventing false signals on flat candles.

    Returns:
        tuple: (swing_high_levels, swing_low_levels) — Series with
               numeric values at swing positions and NaN elsewhere.
    """
    # Max of the left_bars bars strictly to the left of each position
    left_max_h = high.shift(1).rolling(left_bars, min_periods=left_bars).max()
    # Max of the right_bars bars strictly to the right — reverse-roll trick
    right_max_h = (
        high.shift(-1).iloc[::-1]
        .rolling(right_bars, min_periods=right_bars)
        .max()
        .iloc[::-1]
    )
    # Min of the left_bars bars strictly to the left
    left_min_l = low.shift(1).rolling(left_bars, min_periods=left_bars).min()
    # Min of the right_bars bars strictly to the right
    right_min_l = (
        low.shift(-1).iloc[::-1]
        .rolling(right_bars, min_periods=right_bars)
        .min()
        .iloc[::-1]
    )

    # Strict comparison: the pivot bar must be greater/less than all neighbors
    is_swing_high = (high > left_max_h) & (high > right_max_h)
    is_swing_low = (low < left_min_l) & (low < right_min_l)

    swing_high = pd.Series(np.nan, index=high.index)
    swing_low = pd.Series(np.nan, index=low.index)
    swing_high[is_swing_high] = high[is_swing_high]
    swing_low[is_swing_low] = low[is_swing_low]

    return swing_high, swing_low


def support_resistance_levels(high: pd.Series, low: pd.Series,
                              close: pd.Series = None,
                              lookback: int = 50,
                              tolerance: float = 0.02):
    """Calculate support and resistance levels from recent swing points.

    Clusters nearby swing highs/lows within `tolerance` fraction
    to form consolidated levels.

    Parameters:
        high: high price series
        low: low price series
        close: optional close for current price reference
        lookback: number of recent bars to scan for swings
        tolerance: price proximity threshold for clustering (fraction)

    Returns:
        dict: {
            'resistance': sorted list of resistance levels,
            'support':    sorted list of support levels,
            'nearest_support': float or None,
            'nearest_resistance': float or None,
        }
    """
    recent_high = high.tail(lookback)
    recent_low = low.tail(lookback)

    swing_h, swing_l = swing_highs_lows(recent_high, recent_low)

    # Collect non-NA swing prices
    highs = swing_h.dropna().values
    lows = swing_l.dropna().values

    def cluster(levels, tol):
        """Cluster nearby price levels into consolidated zones.

        Each cluster's representative is its true mean (not a pairwise
        running mean that double-weights the most recent value).  A new
        point is assigned to the last cluster when it lies within `tol`
        fraction of that cluster's current mean; otherwise it starts a
        new cluster.
        """
        if len(levels) == 0:
            return []
        levels = np.sort(levels)
        # Each element is a list of raw prices in that cluster
        clusters: list[list] = [[levels[0]]]
        for p in levels[1:]:
            rep = float(np.mean(clusters[-1]))
            if abs(p - rep) / max(rep, 1e-9) > tol:
                clusters.append([p])
            else:
                clusters[-1].append(p)
        return sorted(float(np.mean(c)) for c in clusters)

    resistances = cluster(highs, tolerance)
    supports = cluster(lows, tolerance)

    # Find nearest to current price
    current = close.iloc[-1] if close is not None else None
    nearest_s = None
    nearest_r = None
    if current is not None:
        below = [s for s in supports if s < current]
        above = [r for r in resistances if r > current]
        nearest_s = max(below) if below else None
        nearest_r = min(above) if above else None

    return {
        'resistance': resistances,
        'support': supports,
        'nearest_support': nearest_s,
        'nearest_resistance': nearest_r,
    }


# ============================================================
# Fibonacci Retracement
# ============================================================

def fibonacci_retracement(high: pd.Series, low: pd.Series,
                          close: pd.Series = None,
                          lookback: int = 100):
    """Fibonacci Retracement Levels from recent swing.

    Levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

    For an uptrend (from swing low to swing high):
        level = high_swing - ratio * (high_swing - low_swing)

    Parameters:
        high: high price series
        low: low price series
        close: current close (determines trend direction)
        lookback: bars to look back for swing range

    Returns:
        dict: {ratio: level, ...} plus 'uptrend' flag
    """
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

    recent_h = high.tail(lookback)
    recent_l = low.tail(lookback)
    swing_high_val = recent_h.max()
    swing_low_val = recent_l.min()
    diff = swing_high_val - swing_low_val

    if diff == 0:
        # Degenerate range: all levels collapse to the same price
        levels = {r: swing_high_val for r in ratios}
        levels['uptrend'] = True
        levels['swing_high'] = swing_high_val
        levels['swing_low'] = swing_low_val
        return levels

    if close is not None:
        uptrend = close.iloc[-1] > (swing_high_val + swing_low_val) / 2
    else:
        uptrend = True

    if uptrend:
        levels = {r: swing_high_val - r * diff for r in ratios}
    else:
        levels = {r: swing_low_val + r * diff for r in ratios}

    levels['uptrend'] = uptrend
    levels['swing_high'] = swing_high_val
    levels['swing_low'] = swing_low_val
    return levels


# ============================================================
# Donchian Channel
# ============================================================

def donchian(high: pd.Series, low: pd.Series, close: pd.Series = None,
             period: int = 20):
    """Donchian Channel (highest high and lowest low over N periods).

    Upper Band = max(high) over period
    Lower Band = min(low)  over period
    Mid Band   = (Upper + Lower) / 2

    Returns:
        tuple: (upper, mid, lower)
    """
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    mid = (upper + lower) / 2
    return upper, mid, lower


# ============================================================
# Round-number / Psychological Levels
# ============================================================

def psychological_levels(price: float, step: float = 1.0,
                         count: int = 10):
    """Generate round-number support/resistance levels around a price.

    E.g., price=5.23, step=1.0 -> [1.0, 2.0, 3.0, ..., 10.0] near price.

    Parameters:
        price: current price
        step: rounding step (1.0 = whole numbers, 0.1 = tenths)
        count: how many levels above/below

    Returns:
        list: sorted round-number levels
    """
    base = int(price / step)
    levels = []
    for i in range(-count, count + 1):
        levels.append(round((base + i) * step, 10))
    return sorted(levels)


# ============================================================
# Volume-weighted Support / Resistance
# ============================================================

def volume_profile_support_resistance(close: pd.Series, volume: pd.Series,
                                      n_bins: int = 50,
                                      lookback: int = 100):
    """Volume Profile: identify support/resistance by high-volume price nodes.

    Divides the price range into bins and sums volume in each bin.
    High-volume bins act as support/resistance.

    Returns:
        dict: {
            'poc': price of highest volume bin (Point of Control),
            'vah': value area high (70% volume above POC),
            'val': value area low (70% volume below POC),
            'levels': list of significant volume nodes,
        }
    """
    c = close.tail(lookback)
    v = volume.tail(lookback)

    price_min = c.min()
    price_max = c.max()
    bin_edges = np.linspace(price_min, price_max, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Use np.digitize for vectorized, accurate bin assignment.
    # np.digitize returns 1-based indices; subtract 1 and clip so that
    # prices exactly at price_max land in the last valid bin rather than
    # falling outside all bins.
    bin_indices = np.clip(
        np.digitize(c.values, bin_edges) - 1, 0, n_bins - 1
    )
    vol_profile = np.zeros(n_bins)
    for i in range(n_bins):
        vol_profile[i] = v.values[bin_indices == i].sum()

    poc_idx = np.argmax(vol_profile)
    poc = bin_centers[poc_idx]

    # Value Area (70% of total volume around POC)
    total_vol = vol_profile.sum()
    target = total_vol * 0.70

    va_high, va_low = poc, poc
    accumulated = vol_profile[poc_idx]
    left, right = poc_idx - 1, poc_idx + 1
    while accumulated < target and (left >= 0 or right < n_bins):
        left_vol = vol_profile[left] if left >= 0 else -1
        right_vol = vol_profile[right] if right < n_bins else -1
        if right_vol >= left_vol and right < n_bins:
            va_high = bin_centers[right]
            accumulated += right_vol
            right += 1
        elif left >= 0:
            va_low = bin_centers[left]
            accumulated += left_vol
            left -= 1
        else:
            break

    # Significant nodes: bins whose volume exceeds the mean of non-zero bins.
    # Using the median as threshold is unreliable when many bins are empty
    # (median = 0 → every non-empty bin is flagged as significant).
    nonzero_vols = vol_profile[vol_profile > 0]
    threshold = float(nonzero_vols.mean()) if len(nonzero_vols) > 0 else 0.0
    sig_nodes = [
        bin_centers[i]
        for i in range(n_bins)
        if vol_profile[i] > threshold
    ]

    return {
        'poc': poc,
        'vah': va_high,
        'val': va_low,
        'levels': sorted(sig_nodes),
    }


# ============================================================
# Moving Average as Dynamic S/R
# ============================================================

def ma_support_resistance(close: pd.Series,
                          periods: list[int] = None):
    """Moving averages as dynamic support/resistance.

    Common periods: 20 (short-term), 50 (medium), 200 (long-term).

    Returns:
        dict: {period: ma_series, ...}
    """
    if periods is None:
        periods = [20, 50, 200]

    from eqlib.utils.indicators import ma
    return {p: ma(close, p) for p in periods}


# ============================================================
# Previous Day/Week High-Low
# ============================================================

def prev_day_levels(high: pd.Series, low: pd.Series,
                    close: pd.Series,
                    date_index: pd.DatetimeIndex = None):
    """Previous day's high, low, and close as reference levels.

    Parameters:
        high: daily high series
        low: daily low series
        close: daily close series
        date_index: DatetimeIndex for grouping by day

    Returns:
        dict: {
            'prev_high': previous day's high,
            'prev_low': previous day's low,
            'prev_close': previous day's close,
        }
    """
    return {
        'prev_high': high.shift(1),
        'prev_low': low.shift(1),
        'prev_close': close.shift(1),
    }


# ============================================================
# ATR-based Trailing Stop
# ============================================================

def trailing_stop(close: pd.Series, atr: pd.Series = None,
                  high: pd.Series = None, low: pd.Series = None,
                  multiplier: float = 2.0, period: int = 14):
    """ATR-based trailing stop level.

    For long positions: stop = highest close since entry - multiplier * ATR.
    The stop only moves up, never down.

    Parameters:
        close: close price series
        atr: pre-computed ATR (computed internally if None)
        high: optional high series
        low: optional low series
        multiplier: ATR multiplier
        period: ATR period (used if atr is None)

    Returns:
        Series: trailing stop level for each bar.
    """
    if atr is None:
        if high is None or low is None:
            raise ValueError("atr or (high, low) must be provided")
        from eqlib.utils.indicators import atr as _atr
        atr = _atr(high, low, close, period)

    # Trailing stop = rolling max of (close - multiplier * ATR)
    stops = close - multiplier * atr
    return stops.cummax()


# ============================================================
# Gap Detection
# ============================================================

def gap_up_down(open_: pd.Series, high: pd.Series, low: pd.Series,
                close: pd.Series):
    """Detect price gaps (breakaway zones that act as S/R).

    A gap up: today's low > yesterday's high.
    A gap down: today's high < yesterday's low.

    Returns:
        tuple: (gap_up_levels, gap_down_levels) — Series with gap
               levels at gap bars, NaN elsewhere.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    gap_up = pd.Series(np.nan, index=close.index)
    gap_down = pd.Series(np.nan, index=close.index)

    mask_up = low > prev_high
    mask_down = high < prev_low

    gap_up[mask_up] = (prev_high[mask_up] + low[mask_up]) / 2
    gap_down[mask_down] = (prev_low[mask_down] + high[mask_down]) / 2

    return gap_up, gap_down
