"""Technical indicators for quantitative analysis.

Provides:
- Moving averages: MA, EMA, SMA, WMA
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


def sma(series: pd.Series, period: int, weight: float = 1.0) -> pd.Series:
    """Smoothed Moving Average (like TradingView sma)."""
    result = series.rolling(period).mean()
    for i in range(period, len(series)):
        result.iloc[i] = (result.iloc[i - 1] * (period - weight) + series.iloc[i] * weight) / period
    return result


def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average (linear weights)."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def vwap(high, low, close, volume) -> pd.Series:
    """Volume Weighted Average Price."""
    typical = (high + low + close) / 3
    cum_vp = (typical * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_vp / cum_vol


# ============================================================
# MACD
# ============================================================

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
    """Average Directional Index.

    Returns:
        tuple: (pdi, mdi, adx, adxr)
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # Overlap: when DM+ and DM- conflict
    mask = plus_dm > minus_dm
    plus_dm = plus_dm.where(mask, 0)
    minus_dm = minus_dm.where(~mask, 0)

    true_range = atr(high, low, close, period)
    # Smoothed DM
    plus_di = 100 * sma(plus_dm, period).ewm(
        alpha=1 / period, min_periods=period, adjust=False).mean() / true_range
    minus_di = 100 * sma(minus_dm, period).ewm(
        alpha=1 / period, min_periods=period, adjust=False).mean() / true_range

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()
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
