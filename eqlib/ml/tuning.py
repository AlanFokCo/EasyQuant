"""Hyperparameter optimization for ML models.

Provides time-series-aware cross-validation for tuning model parameters.
"""

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

from .features import FeaturePipeline
from .models import BaseMLModel

log = logging.getLogger(__name__)


def optimize_hyperparams(
    pipeline: FeaturePipeline,
    model_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    param_grid: Optional[dict] = None,
    cv_method: str = "time_series_split",
    n_splits: int = 5,
    scoring: str = "roc_auc",
    **model_kwargs,
) -> dict:
    """Optimize model hyperparameters using time-series-aware CV.

    Parameters
    ----------
    pipeline : FeaturePipeline
        Feature pipeline instance (unused directly but kept for API consistency).
    model_type : str
        Type of model to optimize (e.g. ``'random_forest'``).
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target variable.
    param_grid : dict or None
        Parameter grid to search. If None, uses a sensible default.
    cv_method : str
        ``'time_series_split'`` or ``'walk_forward'``.
    n_splits : int
        Number of CV splits.
    scoring : str
        Scoring metric for GridSearchCV (e.g. ``'roc_auc'``, ``'accuracy'``,
        ``'neg_log_loss'``).
    **model_kwargs
        Base model kwargs.

    Returns
    -------
    dict
        Best parameters found.
    """
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

    if param_grid is None:
        param_grid = _default_param_grid(model_type)

    # Choose CV splitter
    if cv_method == "time_series_split":
        cv = TimeSeriesSplit(n_splits=n_splits)
    elif cv_method == "walk_forward":
        cv = TimeSeriesSplit(n_splits=n_splits)
    else:
        raise ValueError(f"Unknown cv_method: {cv_method}")

    # Build a temporary model for GridSearchCV
    tmp_model = BaseMLModel(model_type, **model_kwargs)

    # Clean data
    X_clean = X.copy().fillna(X.median())
    y_clean = y.copy()
    valid = y_clean.notna()
    X_clean = X_clean[valid]
    y_clean = y_clean[valid]

    if len(X_clean) < n_splits * 2:
        log.warning(
            "Not enough data for %d-fold CV (got %d). Using default params.",
            n_splits,
            len(X_clean),
        )
        return {}

    try:
        grid = GridSearchCV(
            tmp_model._model,
            param_grid,
            cv=cv,
            scoring=scoring,
            n_jobs=-1,
        )
        grid.fit(X_clean, y_clean)
        log.debug("Best params: %s, Best score: %.4f", grid.best_params_, grid.best_score_)
        return grid.best_params_
    except Exception as exc:
        log.error("Hyperparameter optimization failed: %s", exc)
        return {}


def _default_param_grid(model_type: str) -> dict:
    """Return a sensible default parameter grid for a given model type."""
    if model_type == "random_forest":
        return {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 5, 7, None],
            "min_samples_leaf": [1, 5, 10],
        }
    elif model_type == "logistic_regression":
        return {
            "C": [0.01, 0.1, 1.0, 10.0],
            "penalty": ["l1", "l2"],
        }
    elif model_type == "gradient_boosting":
        return {
            "n_estimators": [50, 100, 200],
            "max_depth": [2, 3, 5],
            "learning_rate": [0.01, 0.1, 0.2],
        }
    elif model_type == "xgboost":
        return {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.1, 0.2],
        }
    else:
        return {}
