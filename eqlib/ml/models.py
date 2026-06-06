"""ML model wrappers for eqlib.

Provides a unified interface over scikit-learn models with optional
XGBoost support. Handles model persistence (save/load) and exposes
feature importances.
"""

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class BaseMLModel:
    """Wrapper for sklearn (and optionally XGBoost) models.

    Parameters
    ----------
    model_type : str
        One of ``'random_forest'``, ``'logistic_regression'``,
        ``'gradient_boosting'``, ``'xgboost'``.
    **kwargs
        Additional keyword arguments passed to the underlying estimator.

    Examples
    --------
    >>> model = BaseMLModel('random_forest', n_estimators=100, max_depth=5)
    >>> model.fit(X_train, y_train)
    >>> predictions = model.predict(X_test)
    >>> importance = model.feature_importances()
    """

    _SUPPORTED_TYPES = {
        "random_forest",
        "logistic_regression",
        "gradient_boosting",
        "xgboost",
    }

    def __init__(self, model_type: str = "random_forest", **kwargs):
        if model_type not in self._SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported model_type '{model_type}'. "
                f"Choose from {self._SUPPORTED_TYPES}"
            )
        self.model_type = model_type
        self.kwargs = kwargs
        self._model = None
        self._feature_names: list[str] = []
        self._is_classifier: bool = False
        self._build_model()

    def _build_model(self):
        """Instantiate the underlying sklearn model."""
        mt = self.model_type
        kw = self.kwargs

        if mt == "random_forest":
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

            n_estimators = kw.get("n_estimators", 100)
            max_depth = kw.get("max_depth", 5)
            min_samples_leaf = kw.get("min_samples_leaf", 5)
            random_state = kw.get("random_state", 42)
            # Default to classifier for stock selection (rank by probability)
            self._model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                random_state=random_state,
                n_jobs=-1,
            )
            self._is_classifier = True

        elif mt == "logistic_regression":
            from sklearn.linear_model import LogisticRegression

            max_iter = kw.get("max_iter", 1000)
            C = kw.get("C", 1.0)
            self._model = LogisticRegression(
                max_iter=max_iter, C=C, random_state=kw.get("random_state", 42)
            )
            self._is_classifier = True

        elif mt == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier

            n_estimators = kw.get("n_estimators", 100)
            max_depth = kw.get("max_depth", 3)
            learning_rate = kw.get("learning_rate", 0.1)
            self._model = GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=kw.get("random_state", 42),
            )
            self._is_classifier = True

        elif mt == "xgboost":
            try:
                from xgboost import XGBClassifier
            except ImportError as exc:
                raise ImportError(
                    "xgboost is required for model_type='xgboost'. "
                    "Install with: pip install xgboost"
                ) from exc
            n_estimators = kw.get("n_estimators", 100)
            max_depth = kw.get("max_depth", 5)
            learning_rate = kw.get("learning_rate", 0.1)
            self._model = XGBClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=kw.get("random_state", 42),
                use_label_encoder=False,
                eval_metric="logloss",
            )
            self._is_classifier = True

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit the underlying model.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.
        y : pd.Series
            Target variable.
        """
        if self._model is None:
            raise RuntimeError("Model has not been initialized.")

        self._feature_names = list(X.columns)

        # Handle NaN values - simple forward fill + drop
        X_clean = X.copy()
        X_clean = X_clean.fillna(X_clean.median())

        # Drop rows where y is NaN
        valid_idx = y.notna()
        X_clean = X_clean[valid_idx]
        y_clean = y[valid_idx]

        if len(X_clean) < 2:
            raise ValueError("Insufficient data to train model (need >= 2 samples).")

        self._model.fit(X_clean, y_clean)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return model predictions (or probabilities for classifiers).

        For classifiers, returns the probability of the positive class
        (higher = more likely to have positive return).
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained.")

        # Align columns
        X_aligned = self._align_columns(X)
        X_aligned = X_aligned.fillna(X_aligned.median())

        if self._is_classifier and hasattr(self._model, "predict_proba"):
            # Return probability of positive class (class 1)
            proba = self._model.predict_proba(X_aligned)
            return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]
        else:
            return self._model.predict(X_aligned)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability predictions for all classes.

        Returns
        -------
        np.ndarray
            Array of shape (n_samples, n_classes).
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained.")
        if not hasattr(self._model, "predict_proba"):
            raise AttributeError(f"{self.model_type} does not support predict_proba.")

        X_aligned = self._align_columns(X)
        X_aligned = X_aligned.fillna(X_aligned.median())
        return self._model.predict_proba(X_aligned)

    def feature_importances(self) -> pd.Series:
        """Return feature importances as a pandas Series.

        Returns
        -------
        pd.Series
            Indexed by feature name. Empty if the model does not expose
            feature importances.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained.")

        importances = None
        if hasattr(self._model, "feature_importances_"):
            importances = self._model.feature_importances_
        elif hasattr(self._model, "coef_"):
            # Logistic regression: use absolute coefficient values
            importances = np.abs(self._model.coef_[0])

        if importances is not None and self._feature_names:
            return pd.Series(importances, index=self._feature_names).sort_values(
                ascending=False
            )
        return pd.Series(dtype=float)

    def save(self, path: str) -> None:
        """Serialize the model to disk using pickle.

        Parameters
        ----------
        path : str
            File path to save to.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained.")
        data = {
            "model_type": self.model_type,
            "kwargs": self.kwargs,
            "feature_names": self._feature_names,
            "is_classifier": self._is_classifier,
            "model": self._model,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "BaseMLModel":
        """Deserialize a model from disk.

        Parameters
        ----------
        path : str
            File path to load from.

        Returns
        -------
        BaseMLModel
            Restored model instance.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)

        instance = cls(data["model_type"], **data["kwargs"])
        instance._model = data["model"]
        instance._feature_names = data["feature_names"]
        instance._is_classifier = data["is_classifier"]
        return instance

    def _align_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align DataFrame columns to the training feature order."""
        if not self._feature_names:
            return X
        # Reindex columns, fill missing with NaN
        return X.reindex(columns=self._feature_names)
