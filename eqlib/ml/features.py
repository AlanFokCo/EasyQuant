"""Feature pipeline for ML-based stock selection.

Computes technical indicator features from OHLCV data using
attribute_history, ensuring no look-ahead bias.
"""

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

from eqlib.data import attribute_history

log = logging.getLogger(__name__)


def _safe_scalar(val: pd.Series, default: float = np.nan) -> float:
    """Safely extract the last scalar value from a Series."""
    try:
        if val is not None and not val.empty and not pd.isna(val.iloc[-1]):
            return float(val.iloc[-1])
    except Exception:
        pass
    return default


def _compute_indicator_safe(name: str, compute_fn, *args, **kwargs) -> dict:
    """Wrapper that computes an indicator and handles exceptions gracefully.

    Returns a dict ``{name: value}`` with NaN on failure.
    """
    try:
        result = compute_fn(*args, **kwargs)
        # Support both single Series and tuple returns
        if isinstance(result, tuple):
            names = kwargs.pop("names", [])
            return {n: _safe_scalar(v) for n, v in zip(names, result)}
        return {name: _safe_scalar(result)}
    except Exception:
        return {name: np.nan}


class FeaturePipeline:
    """Builds ML-ready feature matrices from OHLCV data.

    All features are computed point-in-time using ``attribute_history``
    to guarantee no look-ahead bias.

    Parameters
    ----------
    features : list[str] or None
        List of built-in feature names to compute. If None, uses a default
        set of commonly useful features.
    custom_features : dict[str, Callable] or None
        Optional dict mapping feature name to a callable that accepts
        (close, high, low, volume) Series and returns a scalar feature value.

    Examples
    --------
    >>> pipeline = FeaturePipeline(features=['rsi', 'macd_hist', 'atr'])
    >>> df = pipeline.compute(['601390', '600519'], context, lookback=60)
    """

    # Supported built-in features
    BUILT_IN_FEATURES = {
        'rsi',
        'macd_dif',
        'macd_dea',
        'macd_hist',
        'atr',
        'boll_upper',
        'boll_mid',
        'boll_lower',
        'donchian_upper',
        'donchian_mid',
        'donchian_lower',
        'cci',
        'obv',
        'volume_ratio',
        'momentum',
        'volatility',
        'roc',
    }

    DEFAULT_FEATURES = [
        'rsi',
        'macd_hist',
        'atr',
        'boll_upper',
        'boll_lower',
        'volume_ratio',
        'momentum',
        'volatility',
    ]

    def __init__(
        self,
        features: Optional[list[str]] = None,
        custom_features: Optional[dict[str, Callable]] = None,
    ):
        if features is None:
            self.features = list(self.DEFAULT_FEATURES)
        else:
            unknown = set(features) - self.BUILT_IN_FEATURES
            if unknown and not custom_features:
                raise ValueError(f"Unknown features: {unknown}")
            self.features = list(features)

        self.custom_features = custom_features or {}
        self._feature_cache: dict = {}

    def compute(
        self,
        securities: list[str],
        context,
        lookback: int = 60,
    ) -> pd.DataFrame:
        """Compute features for the given securities at ``context.current_dt``.

        Parameters
        ----------
        securities : list[str]
            List of bare security codes (e.g. ``['601390', '600519']``).
        context : Context
            The current backtest context (provides ``current_dt``).
        lookback : int
            Number of historical bars to fetch for computing indicators.

        Returns
        -------
        pd.DataFrame
            DataFrame indexed by security code, columns = feature names.
            Missing values (e.g. insufficient history) are filled with NaN.
        """
        rows = []
        for sec in securities:
            try:
                row = self._compute_single(sec, context, lookback)
            except Exception as exc:
                log.debug("Feature compute failed for %s: %s", sec, exc)
                row = {}
            rows.append(row)

        df = pd.DataFrame(rows, index=securities)
        # Ensure all requested columns exist even if empty
        for feat in self.features:
            if feat not in df.columns:
                df[feat] = np.nan
        return df

    def _compute_single(self, sec: str, context, lookback: int) -> dict:
        """Compute features for a single security."""
        # Need extra bars for indicators that need history
        # RSI(14) needs 14 bars, MACD needs ~33, Bollinger needs 20
        # Add a safety buffer
        min_history = max(lookback, 60)

        hist = attribute_history(
            sec, min_history, "1d",
            fields=["close", "high", "low", "volume"],
        )
        if hist is None or hist.empty or len(hist) < 20:
            return {}

        close = hist["close"]
        high = hist["high"]
        low = hist["low"]
        volume = hist["volume"]

        result = {}

        # Only compute features that were requested
        if any(f in self.features for f in ('rsi',)):
            result.update(self._compute_rsi(close))

        if any(f in self.features for f in ('macd_dif', 'macd_dea', 'macd_hist')):
            result.update(self._compute_macd(close))

        if any(f in self.features for f in ('atr',)):
            result.update(self._compute_atr(high, low, close))

        if any(f in self.features for f in ('boll_upper', 'boll_mid', 'boll_lower')):
            result.update(self._compute_bollinger(close))

        if any(f in self.features for f in ('donchian_upper', 'donchian_mid', 'donchian_lower')):
            result.update(self._compute_donchian(high, low, close))

        if any(f in self.features for f in ('cci',)):
            result.update(self._compute_cci(high, low, close))

        if any(f in self.features for f in ('obv',)):
            result.update(self._compute_obv(close, volume))

        if any(f in self.features for f in ('volume_ratio',)):
            result.update(self._compute_volume_ratio(volume))

        if any(f in self.features for f in ('momentum',)):
            result.update(self._compute_momentum(close))

        if any(f in self.features for f in ('volatility',)):
            result.update(self._compute_volatility(close))

        if any(f in self.features for f in ('roc',)):
            result.update(self._compute_roc(close))

        # Custom features
        for name, func in self.custom_features.items():
            try:
                result[name] = func(close, high, low, volume)
            except Exception as exc:
                log.debug("Custom feature %s failed for %s: %s", name, sec, exc)
                result[name] = np.nan

        # Filter to only requested features
        result = {k: v for k, v in result.items() if k in self.features}
        return result

    # -- Built-in feature calculators ---------------------------------------

    @staticmethod
    def _compute_rsi(close: pd.Series) -> dict:
        from eqlib.utils.indicators import rsi
        return _compute_indicator_safe('rsi', rsi, close, 14)

    @staticmethod
    def _compute_macd(close: pd.Series) -> dict:
        from eqlib.utils.indicators import macd
        try:
            dif, dea, hist = macd(close, fast=12, slow=26, signal=9)
            return {
                'macd_dif': _safe_scalar(dif),
                'macd_dea': _safe_scalar(dea),
                'macd_hist': _safe_scalar(hist),
            }
        except Exception:
            return {
                'macd_dif': np.nan,
                'macd_dea': np.nan,
                'macd_hist': np.nan,
            }

    @staticmethod
    def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
        from eqlib.utils.indicators import atr
        return _compute_indicator_safe('atr', atr, high, low, close, 14)

    @staticmethod
    def _compute_bollinger(close: pd.Series) -> dict:
        from eqlib.utils.indicators import boll
        try:
            upper, mid, lower = boll(close, period=20, num_std=2.0)
            return {
                'boll_upper': _safe_scalar(upper),
                'boll_mid': _safe_scalar(mid),
                'boll_lower': _safe_scalar(lower),
            }
        except Exception:
            return {
                'boll_upper': np.nan,
                'boll_mid': np.nan,
                'boll_lower': np.nan,
            }

    @staticmethod
    def _compute_donchian(high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
        from eqlib.utils.indicators import donchian
        try:
            upper, mid, lower = donchian(high, low, close, period=20)
            return {
                'donchian_upper': _safe_scalar(upper),
                'donchian_mid': _safe_scalar(mid),
                'donchian_lower': _safe_scalar(lower),
            }
        except Exception:
            return {
                'donchian_upper': np.nan,
                'donchian_mid': np.nan,
                'donchian_lower': np.nan,
            }

    @staticmethod
    def _compute_cci(high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
        from eqlib.utils.indicators import cci
        return _compute_indicator_safe('cci', cci, high, low, close, 14)

    @staticmethod
    def _compute_obv(close: pd.Series, volume: pd.Series) -> dict:
        from eqlib.utils.indicators import obv
        return _compute_indicator_safe('obv', obv, close, volume)

    @staticmethod
    def _compute_volume_ratio(volume: pd.Series) -> dict:
        """5-day average volume / 20-day average volume."""
        if len(volume) < 20:
            return {'volume_ratio': np.nan}
        vol_5 = volume.iloc[-5:].mean()
        vol_20 = volume.iloc[-20:].mean()
        if vol_20 == 0:
            return {'volume_ratio': np.nan}
        return {'volume_ratio': float(vol_5 / vol_20)}

    @staticmethod
    def _compute_momentum(close: pd.Series) -> dict:
        """Price / price 20 days ago - 1."""
        if len(close) < 21:
            return {'momentum': np.nan}
        return {'momentum': float(close.iloc[-1] / close.iloc[-21] - 1.0)}

    @staticmethod
    def _compute_volatility(close: pd.Series) -> dict:
        """20-day standard deviation of daily returns."""
        if len(close) < 21:
            return {'volatility': np.nan}
        returns = close.pct_change().dropna()
        if len(returns) < 20:
            return {'volatility': np.nan}
        return {'volatility': float(returns.iloc[-20:].std())}

    @staticmethod
    def _compute_roc(close: pd.Series) -> dict:
        """Rate of change (12-period)."""
        from eqlib.utils.indicators import roc
        return _compute_indicator_safe('roc', roc, close, 12)
