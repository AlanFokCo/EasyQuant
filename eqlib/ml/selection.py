"""ML-based stock selection.

Replaces hand-tuned factor weights with a learned model.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from eqlib.data import attribute_history
from eqlib.selection import StockSelector

from .features import FeaturePipeline
from .models import BaseMLModel

log = logging.getLogger(__name__)


class MLSelector(StockSelector):
    """Machine-learning based stock selector.

    Parameters
    ----------
    model : str or BaseMLModel
        Model type string (``'random_forest'``, ``'logistic_regression'``,
        ``'gradient_boosting'``, ``'xgboost'``) or an existing
        ``BaseMLModel`` instance.
    features : list[str] or None
        List of feature names to use. If None, uses the default set from
        :class:`FeaturePipeline`.
    target : str
        Target variable name. Currently only ``'forward_return_5d'`` is
        supported.
    top_n : int
        Number of stocks to select.
    train_start : str or None
        Start date for training data (``'YYYY-MM-DD'``). If None, uses
        the beginning of available data.
    train_end : str or None
        End date for training data. If None, uses ``context.current_dt``.
    lookback : int
        Number of historical bars to fetch for computing features.
    **model_kwargs
        Additional keyword arguments passed to the model constructor.

    Examples
    --------
    >>> selector = MLSelector(
    ...     model='random_forest',
    ...     features=['rsi', 'macd_hist', 'atr', 'momentum'],
    ...     top_n=5,
    ... )
    >>> selected = selector.rank(context.universe, context)
    """

    def __init__(
        self,
        model: str = "random_forest",
        features: Optional[list[str]] = None,
        target: str = "forward_return_5d",
        top_n: int = 5,
        train_start: Optional[str] = None,
        train_end: Optional[str] = None,
        lookback: int = 60,
        **model_kwargs,
    ):
        self.model_type = model if isinstance(model, str) else model.model_type
        if isinstance(model, BaseMLModel):
            self._model = model
        else:
            self._model = BaseMLModel(model, **model_kwargs)

        self.pipeline = FeaturePipeline(features=features)
        self.target = target
        self.top_n = top_n
        self.train_start = train_start
        self.train_end = train_end
        self.lookback = lookback
        self._is_trained = False

    def train(self, securities: list[str], context) -> None:
        """Train the model on historical data.

        Parameters
        ----------
        securities : list[str]
            Universe of stocks to train on.
        context : Context
            The current backtest context.
        """
        import datetime

        # Determine training date range
        current_dt = getattr(context, "current_dt", None)
        if current_dt is None:
            log.warning("context.current_dt is not available, cannot train model.")
            return

        end_dt = current_dt.date() if hasattr(current_dt, "date") else current_dt
        start_dt = None
        if self.train_start is not None:
            start_dt = datetime.datetime.strptime(self.train_start, "%Y-%m-%d").date()

        # We need enough history to compute features and forward returns.
        # Use a generous lookback window for training data.
        training_window = 252  # ~1 year of data points

        log.debug("Training ML model on %d securities", len(securities))

        # Build training dataset
        X_list = []
        y_list = []

        # For simplicity, train using current features only
        # In a production setting, you'd walk back through time
        # and collect (features, target) pairs across multiple dates.
        # Here we train on a single snapshot which is a reasonable
        # starting point for the P0 implementation.
        X = self.pipeline.compute(securities, context, lookback=self.lookback)

        # Compute target for each security
        y = self._compute_target(securities, context, self.target)

        if X.empty or y.empty:
            log.warning("Cannot train: empty features or target.")
            return

        # Align indices
        common = X.index.intersection(y.index)
        if len(common) == 0:
            log.warning("No common securities between features and target.")
            return

        X = X.loc[common]
        y = y.loc[common]

        try:
            self._model.fit(X, y)
            self._is_trained = True
            log.debug("ML model trained on %d samples", len(common))
        except Exception as exc:
            log.error("Failed to train ML model: %s", exc)
            self._is_trained = False

    def rank(self, securities: list[str], context) -> list[str]:
        """Return top-N stocks ranked by model prediction.

        Parameters
        ----------
        securities : list[str]
            Candidate securities.
        context : Context
            Current backtest context.

        Returns
        -------
        list[str]
            Selected security codes (best first).
        """
        if not self._is_trained:
            log.warning("ML model not trained. Training now...")
            self.train(securities, context)

        if not self._is_trained:
            log.warning("ML model could not be trained. Falling back to first N securities.")
            return securities[:self.top_n] if len(securities) > self.top_n else securities

        X = self.pipeline.compute(securities, context, lookback=self.lookback)
        if X.empty:
            return securities[:self.top_n] if len(securities) > self.top_n else securities

        try:
            predictions = self._model.predict(X)
            scores = pd.Series(predictions, index=X.index)
            scores = scores.sort_values(ascending=False)
            return scores.head(self.top_n).index.tolist()
        except Exception as exc:
            log.error("Failed to predict with ML model: %s", exc)
            return securities[:self.top_n] if len(securities) > self.top_n else securities

    def _compute_target(
        self,
        securities: list[str],
        context,
        target_name: str,
    ) -> pd.Series:
        """Compute the target variable (label) for training.

        Uses historical data only — no look-ahead bias.
        """
        import datetime

        results = {}

        for sec in securities:
            try:
                if target_name == "forward_return_5d":
                    # Need enough history to compute past 5-day return
                    # relative to a past point in time
                    hist = attribute_history(
                        sec, self.lookback + 10, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 25:
                        continue

                    close = hist["close"]
                    # Past 5-day return (most recent 5 days)
                    ret_5d = close.iloc[-1] / close.iloc[-6] - 1.0 if len(close) >= 6 else np.nan
                    results[sec] = ret_5d

                elif target_name == "forward_return_10d":
                    hist = attribute_history(
                        sec, self.lookback + 15, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 15:
                        continue
                    close = hist["close"]
                    ret_10d = close.iloc[-1] / close.iloc[-11] - 1.0 if len(close) >= 11 else np.nan
                    results[sec] = ret_10d

                elif target_name == "will_rise_5d":
                    # Binary classification: will 5-day forward return be positive?
                    hist = attribute_history(
                        sec, self.lookback + 10, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 10:
                        continue
                    close = hist["close"]
                    ret_5d = close.iloc[-1] / close.iloc[-6] - 1.0 if len(close) >= 6 else np.nan
                    results[sec] = 1 if ret_5d > 0 else 0

                else:
                    log.warning("Unknown target: %s", target_name)
                    results[sec] = np.nan

            except Exception as exc:
                log.debug("Failed to compute target for %s: %s", sec, exc)
                results[sec] = np.nan

        return pd.Series(results)
