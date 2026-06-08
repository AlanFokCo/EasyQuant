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

# Map target names to whether they are classification or regression targets.
_CLASSIFICATION_TARGETS = {"will_rise_5d"}


def _is_classification_target(target: str) -> bool:
    return target in _CLASSIFICATION_TARGETS


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
        Target variable name.
        Currently supported: ``'past_return_5d'`` (default),
        ``'past_return_10d'``, ``'will_rise_5d'``.
        **Note:** ``past_return_*`` uses historical returns as labels,
        which is a simplification. For true forward-return prediction,
        provide ``label_data``.
    top_n : int
        Number of stocks to select.
    train_start : str or None
        Start date for training data (``'YYYY-MM-DD'``). If None, uses
        the beginning of available data.
    train_end : str or None
        End date for training data. If None, uses ``context.current_dt``.
    lookback : int
        Number of historical bars to fetch for computing features.
    label_data : pd.DataFrame or None
        Optional pre-computed labels. If provided, must be a DataFrame
        with columns ``['security', 'date', 'label']``.
        When ``None``, labels are computed from historical data using
        the selected ``target`` (past returns by default).
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
        target: str = "past_return_5d",
        top_n: int = 5,
        train_start: Optional[str] = None,
        train_end: Optional[str] = None,
        lookback: int = 60,
        label_data: Optional[pd.DataFrame] = None,
        **model_kwargs,
    ):
        self.model_type = model if isinstance(model, str) else model.model_type
        self.is_classifier = _is_classification_target(target)
        if isinstance(model, BaseMLModel):
            self._model = model
        else:
            self._model = BaseMLModel(model, is_classifier=self.is_classifier, **model_kwargs)

        self.pipeline = FeaturePipeline(features=features)
        self.target = target
        self.top_n = top_n
        self.train_start = train_start
        self.train_end = train_end
        self.lookback = lookback
        self.label_data = label_data
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

        current_dt = getattr(context, "current_dt", None)
        if current_dt is None:
            log.warning("context.current_dt is not available, cannot train model.")
            return

        log.debug("Training ML model on %d securities", len(securities))

        # Build training dataset
        # If label_data is provided, use it; otherwise compute from historical data
        if self.label_data is not None:
            X, y = self._build_training_set_from_labels(securities, context)
        else:
            X, y = self._build_training_set_simple(securities, context)

        if X is None or y is None or X.empty or y.empty:
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

    def _build_training_set_simple(
        self, securities: list[str], context
    ) -> tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """Build training set from a single cross-section (simplified).

        This is the default P0 implementation: uses one day's data only.
        For more robust training, use ``label_data`` to provide pre-computed
        panel data with historical features and labels.
        """
        X = self.pipeline.compute(securities, context, lookback=self.lookback)
        y = self._compute_target(securities, context, self.target)
        return X, y

    def _build_training_set_from_labels(
        self, securities: list[str], context
    ) -> tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """Build training set from pre-computed label_data.

        label_data must be a DataFrame with columns:
        ['security', 'date', 'label'].
        """
        if self.label_data is None:
            return None, None

        current_dt = getattr(context, "current_dt", None)
        if current_dt is None:
            return None, None

        # Filter labels for current date
        labels = self.label_data
        if "date" in labels.columns:
            labels = labels[labels["date"] == current_dt]

        # Compute features
        X = self.pipeline.compute(securities, context, lookback=self.lookback)

        # Build y from labels
        y = pd.Series(dtype=float)
        if "security" in labels.columns and "label" in labels.columns:
            y = labels.set_index("security")["label"]

        return X, y

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
            return securities[: self.top_n] if len(securities) > self.top_n else securities

        X = self.pipeline.compute(securities, context, lookback=self.lookback)
        if X.empty:
            return securities[: self.top_n] if len(securities) > self.top_n else securities

        try:
            predictions = self._model.predict(X)
            scores = pd.Series(predictions, index=X.index)
            scores = scores.sort_values(ascending=False)
            return scores.head(self.top_n).index.tolist()
        except Exception as exc:
            log.error("Failed to predict with ML model: %s", exc)
            return securities[: self.top_n] if len(securities) > self.top_n else securities

    def _compute_target(
        self,
        securities: list[str],
        context,
        target_name: str,
    ) -> pd.Series:
        """Compute the target variable (label) for training.

        Uses historical data only — no look-ahead bias.
        **Note:** These are *past* returns, not forward returns.
        """
        results = {}

        for sec in securities:
            try:
                if target_name in ("past_return_5d", "forward_return_5d"):
                    hist = attribute_history(
                        sec, self.lookback + 10, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 25:
                        continue

                    close = hist["close"]
                    ret_5d = (
                        close.iloc[-1] / close.iloc[-6] - 1.0
                        if len(close) >= 6
                        else np.nan
                    )
                    results[sec] = ret_5d

                elif target_name == "past_return_10d":
                    hist = attribute_history(
                        sec, self.lookback + 15, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 15:
                        continue
                    close = hist["close"]
                    ret_10d = (
                        close.iloc[-1] / close.iloc[-11] - 1.0
                        if len(close) >= 11
                        else np.nan
                    )
                    results[sec] = ret_10d

                elif target_name == "will_rise_5d":
                    hist = attribute_history(
                        sec, self.lookback + 10, "1d", fields=["close"]
                    )
                    if hist is None or hist.empty or len(hist) < 10:
                        continue
                    close = hist["close"]
                    ret_5d = (
                        close.iloc[-1] / close.iloc[-6] - 1.0
                        if len(close) >= 6
                        else np.nan
                    )
                    results[sec] = 1 if ret_5d > 0 else 0

                else:
                    log.warning("Unknown target: %s", target_name)
                    results[sec] = np.nan

            except Exception as exc:
                log.debug("Failed to compute target for %s: %s", sec, exc)
                results[sec] = np.nan

        return pd.Series(results)
