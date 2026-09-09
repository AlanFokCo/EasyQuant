"""ML-based stock selection.

Replaces hand-tuned factor weights with a learned model.
"""

import logging
from copy import copy
from typing import Optional

import numpy as np
import pandas as pd

from eqlib.data import attribute_history
from eqlib.selection import StockSelector

from .features import FeaturePipeline
from .models import BaseMLModel
from ._history import history_at, market_timestamp

log = logging.getLogger(__name__)

# Map target names to whether they are classification or regression targets.
_CLASSIFICATION_TARGETS = {"will_rise_5d"}


def _is_classification_target(target: str) -> bool:
    return target in _CLASSIFICATION_TARGETS


class MLSelector(StockSelector):
    """Machine-learning based stock selector.

    .. warning::

        The default training path uses a **single cross-section** (one day's
        data) to fit the model. With small universes (<50 stocks) this
        produces few samples and the model cannot learn meaningful patterns.
        For robust training, provide ``label_data`` as a panel DataFrame
        with historical features and labels across many dates.

    .. warning::

        ``target='past_return_5d'`` (the default) uses **past** returns as
        labels, not forward returns. This is a simplification for
        backward compatibility and does not produce a true forward-looking
        model. ``target='forward_return_5d'`` is intentionally not
        implemented — attempting to use it raises ``NotImplementedError``.
        For true forward-return prediction, provide ``label_data`` with
        pre-computed forward labels.

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
        with columns ``['security', 'date', 'label', 'available_at']``.
        ``date`` is the historical feature date; features use earlier daily
        bars. ``available_at`` is when the entire label actually became
        observable, including its forward horizon and publication delay.
        Date-only availability is conservatively usable from the next day.
        Only historical rows whose labels were available before the current
        decision are used, within ``train_start`` / ``train_end``.
        When ``None``, labels are computed from historical data using
        the selected ``target`` (past returns by default).
    custom_features : dict or None
        Optional mapping of ``{name: func(close, high, low, volume) -> float}``
        for custom feature functions. Names must also appear in ``features``.
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
        custom_features: Optional[dict] = None,
        **model_kwargs,
    ):
        self.model_type = model if isinstance(model, str) else model.model_type
        self.is_classifier = _is_classification_target(target)
        if isinstance(model, BaseMLModel):
            self._model = model
        else:
            self._model = BaseMLModel(model, is_classifier=self.is_classifier, **model_kwargs)

        self.pipeline = FeaturePipeline(features=features, custom_features=custom_features)
        self.target = target
        self.top_n = top_n
        self.train_start = train_start
        self.train_end = train_end
        if train_start is not None and train_end is not None:
            if market_timestamp(train_start).normalize() > market_timestamp(train_end).normalize():
                raise ValueError("train_start must not be after train_end")
        self.lookback = lookback
        self.label_data = label_data
        self._is_trained = False
        self._trained_at = None

    def train(self, securities: list[str], context) -> None:
        """Train the model on historical data.

        Parameters
        ----------
        securities : list[str]
            Universe of stocks to train on.
        context : Context
            The current backtest context.
        """
        current_dt = getattr(context, "current_dt", None)
        if current_dt is None:
            log.warning("context.current_dt is not available, cannot train model.")
            return

        self._is_trained = False

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
            self._trained_at = market_timestamp(current_dt)
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
        sample_context = copy(context)
        sample_day = market_timestamp(context.current_dt).normalize()
        if self.train_end is not None:
            sample_day = min(sample_day, market_timestamp(self.train_end).normalize())
        if self.train_start is not None and sample_day < market_timestamp(self.train_start).normalize():
            return None, None
        sample_context.current_dt = sample_day
        X = self.pipeline.compute(securities, sample_context, lookback=self.lookback)
        y = self._compute_target(securities, sample_context, self.target)
        return X, y

    def _build_training_set_from_labels(
        self, securities: list[str], context
    ) -> tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """Build training set from pre-computed label_data.

        Features and labels are joined by (sample date, security), never by
        security alone. Labels without availability metadata are rejected.
        """
        if self.label_data is None:
            return None, None

        current_dt = getattr(context, "current_dt", None)
        if current_dt is None:
            return None, None

        required = {"security", "date", "label", "available_at"}
        if not isinstance(self.label_data, pd.DataFrame) or not required.issubset(self.label_data.columns):
            raise ValueError("label_data requires security, date, label, available_at columns")
        labels = self.label_data.copy()
        labels["date"] = labels["date"].map(market_timestamp).dt.normalize()
        labels["available_at"] = labels["available_at"].map(market_timestamp)
        # Daily labels typically realize at the close, not midnight. A date
        # with no intraday timestamp is safe only from the following day.
        midnight = labels["available_at"] == labels["available_at"].dt.normalize()
        labels.loc[midnight, "available_at"] += pd.Timedelta(days=1)
        if (labels["available_at"] < labels["date"]).any():
            raise ValueError("label available_at cannot precede its feature date")
        now = market_timestamp(current_dt)
        eligible = labels["security"].isin(securities) & (labels["date"] < now.normalize()) & (labels["available_at"] < now)
        if self.train_start is not None:
            eligible &= labels["date"] >= market_timestamp(self.train_start).normalize()
        if self.train_end is not None:
            eligible &= labels["date"] <= market_timestamp(self.train_end).normalize()
        labels = labels.loc[eligible]
        if labels.duplicated(["date", "security"]).any():
            raise ValueError("label_data has duplicate date/security samples")
        features, targets = [], []
        for sample_day, sample in labels.groupby("date", sort=True):
            sample_context = copy(context)
            sample_context.current_dt = sample_day
            codes = sample["security"].tolist()
            X = self.pipeline.compute(codes, sample_context, lookback=self.lookback)
            if X.empty:
                continue
            y = sample.set_index("security")["label"].reindex(X.index)
            y = pd.to_numeric(y, errors="raise")
            valid = np.isfinite(y.to_numpy(dtype=float)) & ~X.isna().all(axis=1).to_numpy()
            X, y = X.loc[valid].copy(), y.loc[valid].copy()
            index = pd.MultiIndex.from_arrays([[sample_day] * len(X), X.index], names=["date", "security"])
            X.index = y.index = index
            features.append(X)
            targets.append(y)
        if not features:
            return None, None
        return pd.concat(features), pd.concat(targets)

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
        current_dt = getattr(context, "current_dt", None)
        if self._trained_at is not None and current_dt is not None:
            if market_timestamp(current_dt) < self._trained_at:
                # A selector reused in an earlier fold/run must not retain a
                # model trained with information from its future.
                self._is_trained = False
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
        if target_name == "forward_return_5d":
            raise NotImplementedError(
                "true forward-return prediction requires label_data panel; "
                "use past_return_5d for backward-compatible behavior or "
                "provide label_data"
            )

        results = {}

        for sec in securities:
            try:
                if target_name == "past_return_5d":
                    hist = history_at(
                        attribute_history, sec, self.lookback + 10, context, fields=["close"]
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
                    hist = history_at(
                        attribute_history, sec, self.lookback + 15, context, fields=["close"]
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
                    hist = history_at(
                        attribute_history, sec, self.lookback + 10, context, fields=["close"]
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
