"""Technical indicators for quantitative analysis.

Provides:
- Moving averages: MA, EMA, SMA, SMMA (Smoothed MA), WMA
- Trend: MACD, DMI/ADX
- Momentum: RSI, KDJ, CCI, ROC, WR (Williams %R), STOCH
- Volatility: Bollinger Bands, ATR, STD
- Volume: OBV, VWAP
- Pattern: golden_cross, death_cross
"""

import numpy as np
import pandas as pd


# ============================================================
# Moving Averages
# ============================================================

def ma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (identical to ``ma``; alias kept for compatibility).

    Returns a plain rolling mean — *not* the Wilder/smoothed variant.
    For the Smoothed Moving Average (SMMA/RMA/Wilder MA), use :func:`smma`.
    """
    return series.rolling(period).mean()


def smma(series: pd.Series, period: int, weight: float = 1.0) -> pd.Series:
    """Smoothed Moving Average (SMMA / RMA / Wilder MA).

    This is the custom smoothed average previously named ``sma`` in earlier
    versions of the library.  It uses an EMA-style recursive formula::

        SMMA[i] = (SMMA[i-1] * (period - weight) + series[i] * weight) / period

    Commonly used inside ADX, RSI, and similar Wilder-style indicators.

    Parameters:
        series: input price series
        period: smoothing period
        weight: weighting factor (default 1.0)
    """
    result = series.rolling(period).mean()
    if len(series) <= period:
        return result

    alpha = weight / period
    seeded = pd.concat([result.iloc[[period - 1]], series.iloc[period:]])
    result.iloc[period - 1:] = seeded.ewm(alpha=alpha, adjust=False).mean().values
    return result


def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average (linear weights)."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def vwap(high, low, close, volume, window: int = None) -> pd.Series:
    """Volume Weighted Average Price.

    Parameters:
        high, low, close, volume: OHLCV series
        window: rolling window size in bars.  When ``None`` (default) the VWAP
            is cumulative from the start of the series — suitable for intraday
            data where the series represents a single session.  For *daily*
            data, pass an explicit ``window`` (e.g., ``window=20``) to compute
            a rolling VWAP over the last *window* bars instead.

    Note:
        Cumulative VWAP (``window=None``) is only meaningful on intraday data
        whose index resets at each session open.  On daily OHLCV, use a
        rolling window to avoid a steadily drifting average.
    """
    typical = (high + low + close) / 3
    if window is None:
        # Cumulative VWAP — correct for intraday (single-session) series
        cum_vp = (typical * volume).cumsum()
        cum_vol = volume.cumsum()
        return cum_vp / cum_vol
    # Rolling VWAP — correct for multi-session (daily) usage
    cum_vp = (typical * volume).rolling(window).sum()
    cum_vol = volume.rolling(window).sum()
    return cum_vp / cum_vol.replace(0, np.nan)


# ============================================================
# MACD
# ============================================================

def compute_all_indicators(close: pd.Series, high: pd.Series, low: pd.Series,
                           volume: pd.Series,
                           rsi_period=14, boll_period=20, boll_std=2.0,
                           macd_fast=12, macd_slow=26, macd_signal=9,
                           atr_period=14, donchian_period=20):
    """Compute all standard indicators at once on a full price series.

    Returns a DataFrame with one column per indicator value (all aligned to
    the same index as the input series).  This is much faster than calling
    each indicator function separately because pandas can reuse intermediate
    rolling/ewm windows internally.

    Columns: rsi, bb_upper, bb_mid, bb_lower, macd_dif, macd_dea, macd_hist,
             atr, dc_upper, dc_mid, dc_lower
    """
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_vals = 100 - (100 / (1 + rs))

    # Bollinger Bands
    bb_mid = close.rolling(boll_period).mean()
    bb_std = close.rolling(boll_period).std()
    bb_upper = bb_mid + boll_std * bb_std
    bb_lower = bb_mid - boll_std * bb_std

    # MACD
    fast_ema = close.ewm(span=macd_fast, adjust=False).mean()
    slow_ema = close.ewm(span=macd_slow, adjust=False).mean()
    macd_dif = fast_ema - slow_ema
    macd_dea = macd_dif.ewm(span=macd_signal, adjust=False).mean()
    macd_hist = 2 * (macd_dif - macd_dea)

    # ATR
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_vals = tr.ewm(alpha=1 / atr_period, min_periods=atr_period, adjust=False).mean()

    # Donchian Channel
    dc_upper = high.rolling(donchian_period).max()
    dc_lower = low.rolling(donchian_period).min()
    dc_mid = (dc_upper + dc_lower) / 2

    return pd.DataFrame({
        "rsi": rsi_vals,
        "bb_upper": bb_upper,
        "bb_mid": bb_mid,
        "bb_lower": bb_lower,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "macd_hist": macd_hist,
        "atr": atr_vals,
        "dc_upper": dc_upper,
        "dc_mid": dc_mid,
        "dc_lower": dc_lower,
    })


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Moving Average Convergence Divergence.

    Returns:
        tuple: (dif, dea, macd_hist)
            dif = EMA(fast) - EMA(slow)
            dea = EMA(dif, signal)
            macd_hist = 2 * (dif - dea)
    """
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    dif = fast_ema - slow_ema
    dea = ema(dif, signal)
    hist = 2 * (dif - dea)
    return dif, dea, hist


# ============================================================
# RSI
# ============================================================

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ============================================================
# KDJ
# ============================================================

def kdj(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 9, smooth: int = 3):
    """Stochastic Oscillator (KDJ).

    Returns:
        tuple: (k, d, j)
    """
    lowest = low.rolling(period).min()
    highest = high.rolling(period).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, np.nan) * 100

    k = rsv.ewm(alpha=1 / smooth, adjust=False).mean()
    d = k.ewm(alpha=1 / smooth, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


# ============================================================
# Bollinger Bands
# ============================================================

def boll(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """Bollinger Bands.

    Returns:
        tuple: (upper, mid, lower)
    """
    mid = ma(close, period)
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


# ============================================================
# ATR
# ============================================================

def atr(high: pd.Series, low: pd.Series, close: pd.Series,
         period: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ============================================================
# CCI
# ============================================================

def cci(high: pd.Series, low: pd.Series, close: pd.Series,
      period: int = 14) -> pd.Series:
    """Commodity Channel Index."""
    tp = (high + low + close) / 3
    ma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=False)
    return (tp - ma_tp) / (0.015 * mad)


# ============================================================
# Williams %R
# ============================================================

def wr(high: pd.Series, low: pd.Series, close: pd.Series,
       period: int = 14) -> pd.Series:
    """Williams Percent Range."""
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    return (highest - close) / (highest - lowest).replace(0, np.nan) * -100


# ============================================================
# ROC
# ============================================================

def roc(close: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change."""
    return (close - close.shift(period)) / close.shift(period) * 100


# ============================================================
# OBV
# ============================================================

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume."""
    delta = close.diff()
    direction = np.sign(delta)
    return (volume * direction).cumsum()


# ============================================================
# DMI / ADX
# ============================================================

def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14):
    """Average Directional Index (standard Wilder smoothing).

    Uses a single Wilder EWM smoothing (``alpha=1/period``) for both the
    directional movement components and the DX smoothing, matching the
    standard definition used by most trading platforms.

    Returns:
        tuple: (pdi, mdi, adx, adxr)
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # Overlap: when both DM+ and DM- move, keep only the larger one
    mask = plus_dm > minus_dm
    plus_dm = plus_dm.where(mask, 0)
    minus_dm = minus_dm.where(~mask, 0)

    # Wilder smoothing for True Range and directional movements
    wilder = dict(alpha=1 / period, min_periods=period, adjust=False)
    true_range = atr(high, low, close, period)
    smooth_plus = plus_dm.ewm(**wilder).mean()
    smooth_minus = minus_dm.ewm(**wilder).mean()

    plus_di = 100 * smooth_plus / true_range.replace(0, np.nan)
    minus_di = 100 * smooth_minus / true_range.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(**wilder).mean()
    adxr = (adx_val + adx_val.shift(period)) / 2

    return plus_di, minus_di, adx_val, adxr


# ============================================================
# Pattern Detection
# ============================================================

def golden_cross(fast_ma: pd.Series, slow_ma: pd.Series) -> pd.Series:
    """Detect golden cross: fast MA crosses above slow MA.

    Returns:
        Boolean Series: True where cross occurs.
    """
    return (fast_ma.shift(1) <= slow_ma.shift(1)) & (fast_ma > slow_ma)


def death_cross(fast_ma: pd.Series, slow_ma: pd.Series) -> pd.Series:
    """Detect death cross: fast MA crosses below slow MA.

    Returns:
        Boolean Series: True where cross occurs.
    """
    return (fast_ma.shift(1) >= slow_ma.shift(1)) & (fast_ma < slow_ma)
