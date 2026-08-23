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
    is_classifier : bool
        Whether the model should be a classifier (``True``) or regressor
        (``False``). Default is ``True`` for backward compatibility.
        Set to ``False`` when the target is continuous (e.g. returns).
    **kwargs
        Additional keyword arguments passed to the underlying estimator.

    Examples
    --------
    >>> # Classification (default)
    >>> model = BaseMLModel('random_forest')
    >>> # Regression (continuous target)
    >>> model = BaseMLModel('random_forest', is_classifier=False)
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

    def __init__(
        self, model_type: str = "random_forest", is_classifier: bool = True, **kwargs
    ):
        if model_type not in self._SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported model_type '{model_type}'. "
                f"Choose from {self._SUPPORTED_TYPES}"
            )
        self.model_type = model_type
        self.is_classifier = is_classifier
        self.kwargs = kwargs
        self._model = None
        self._feature_names: list[str] = []
        self._is_classifier: bool = is_classifier
        self._imputation_values: Optional[pd.Series] = None
        self._build_model()

    def _build_model(self):
        """Instantiate the underlying sklearn model."""
        mt = self.model_type
        kw = self.kwargs
        is_clf = self._is_classifier

        if mt == "random_forest":
            if is_clf:
                from sklearn.ensemble import RandomForestClassifier

                self._model = RandomForestClassifier(
                    n_estimators=kw.get("n_estimators", 100),
                    max_depth=kw.get("max_depth", 5),
                    min_samples_leaf=kw.get("min_samples_leaf", 5),
                    random_state=kw.get("random_state", 42),
                    n_jobs=-1,
                )
            else:
                from sklearn.ensemble import RandomForestRegressor

                self._model = RandomForestRegressor(
                    n_estimators=kw.get("n_estimators", 100),
                    max_depth=kw.get("max_depth", 5),
                    min_samples_leaf=kw.get("min_samples_leaf", 5),
                    random_state=kw.get("random_state", 42),
                    n_jobs=-1,
                )

        elif mt == "logistic_regression":
            if is_clf:
                from sklearn.linear_model import LogisticRegression

                self._model = LogisticRegression(
                    max_iter=kw.get("max_iter", 1000),
                    C=kw.get("C", 1.0),
                    random_state=kw.get("random_state", 42),
                )
            else:
                from sklearn.linear_model import LinearRegression

                self._model = LinearRegression()

        elif mt == "gradient_boosting":
            if is_clf:
                from sklearn.ensemble import GradientBoostingClassifier

                self._model = GradientBoostingClassifier(
                    n_estimators=kw.get("n_estimators", 100),
                    max_depth=kw.get("max_depth", 3),
                    learning_rate=kw.get("learning_rate", 0.1),
                    random_state=kw.get("random_state", 42),
                )
            else:
                from sklearn.ensemble import GradientBoostingRegressor

                self._model = GradientBoostingRegressor(
                    n_estimators=kw.get("n_estimators", 100),
                    max_depth=kw.get("max_depth", 3),
                    learning_rate=kw.get("learning_rate", 0.1),
                    random_state=kw.get("random_state", 42),
                )

        elif mt == "xgboost":
            try:
                if is_clf:
                    from xgboost import XGBClassifier

                    self._model = XGBClassifier(
                        n_estimators=kw.get("n_estimators", 100),
                        max_depth=kw.get("max_depth", 5),
                        learning_rate=kw.get("learning_rate", 0.1),
                        random_state=kw.get("random_state", 42),
                        use_label_encoder=False,
                        eval_metric="logloss",
                    )
                else:
                    from xgboost import XGBRegressor

                    self._model = XGBRegressor(
                        n_estimators=kw.get("n_estimators", 100),
                        max_depth=kw.get("max_depth", 5),
                        learning_rate=kw.get("learning_rate", 0.1),
                        random_state=kw.get("random_state", 42),
                    )
            except ImportError as exc:
                raise ImportError(
                    "xgboost is required for model_type='xgboost'. "
                    "Install with: pip install xgboost"
                ) from exc

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseMLModel":
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
        X_clean, y_clean = self._prepare_fit_data(X, y)
        self._model.fit(X_clean, y_clean)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return model predictions.

        For classifiers, returns the probability of the positive class
        (higher = more likely to have positive return).
        For regressors, returns the predicted value directly.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained.")

        # Align columns
        X_aligned = self._prepare_predict_data(X)

        if self._is_classifier and hasattr(self._model, "predict_proba"):
            # Return probability of positive class (class 1)
            proba = self._model.predict_proba(X_aligned)
            classes = np.asarray(self._model.classes_)
            positive_index = np.flatnonzero(classes == 1)
            return (
                proba[:, positive_index[0]]
                if len(positive_index)
                else np.zeros(len(X_aligned))
            )
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

        X_aligned = self._prepare_predict_data(X)
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
            # Logistic regression / Linear regression: use absolute coefficient values
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
            "is_classifier": self._is_classifier,
            "kwargs": self.kwargs,
            "feature_names": self._feature_names,
            "imputation_values": self._imputation_values,
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

        instance = cls(
            data["model_type"],
            is_classifier=data.get("is_classifier", True),
            **data["kwargs"],
        )
        instance._model = data["model"]
        instance._feature_names = data["feature_names"]
        instance._is_classifier = data.get("is_classifier", True)
        instance._imputation_values = data.get("imputation_values")
        if instance._imputation_values is None:
            raise ValueError(
                "Model imputation statistics are unavailable in this saved model."
            )
        return instance

    def _align_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align DataFrame columns to the training feature order."""
        if not self._feature_names:
            return X
        # Reindex columns, fill missing with NaN
        return X.reindex(columns=self._feature_names)

    def _prepare_fit_data(
        self, X: pd.DataFrame, y: pd.Series
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Align labels and derive imputation values exclusively from training data."""
        if not X.index.is_unique or not y.index.is_unique:
            raise ValueError("X and y indexes must be unique")
        y_aligned = y.reindex(X.index)
        valid = y_aligned.notna()
        X_clean = X.loc[valid].replace([np.inf, -np.inf], np.nan)
        y_clean = y_aligned.loc[valid]
        if len(X_clean) < 2:
            raise ValueError("Insufficient data to train model (need >= 2 samples).")
        imputation = X_clean.median(numeric_only=True).reindex(X_clean.columns)
        if imputation.isna().any():
            raise ValueError(
                "Each feature must have at least one finite training value"
            )
        self._imputation_values = imputation
        return X_clean.fillna(imputation), y_clean

    def _prepare_predict_data(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align and impute prediction features using persisted training medians."""
        if self._imputation_values is None:
            raise RuntimeError("Model imputation statistics are unavailable.")
        prepared = self._align_columns(X).replace([np.inf, -np.inf], np.nan)
        prepared = prepared.fillna(self._imputation_values)
        if not np.isfinite(prepared.to_numpy(dtype=float)).all():
            raise ValueError(
                "Prediction features must be finite after training-data imputation"
            )
        return prepared
