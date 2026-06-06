"""ML-specific validation utilities.

Extends the scientific validation layer with checks specific to
machine-learning strategies.
"""

import logging

import numpy as np
import pandas as pd

from .models import BaseMLModel

log = logging.getLogger(__name__)


def validate_ml_strategy(
    backtest_result: dict,
    model: BaseMLModel,
    feature_importance_threshold: float = 0.01,
) -> dict:
    """Run ML-specific validation checks on a backtest result.

    Parameters
    ----------
    backtest_result : dict
        Result dict from ``run_backtest()``.
    model : BaseMLModel
        The trained ML model used in the strategy.
    feature_importance_threshold : float
        Minimum importance for a feature to be considered significant.

    Returns
    -------
    dict
        Validation results including:
        - ``feature_importance``: per-feature importance
        - ``concentration_risk``: whether importance is too concentrated
        - ``model_stability``: variance of predictions (if available)
    """
    report = {
        "feature_importance": {},
        "concentration_risk": False,
        "model_stability": None,
    }

    # Feature importance check
    try:
        importances = model.feature_importances()
        if not importances.empty:
            report["feature_importance"] = importances.to_dict()
            total_top = importances.head(3).sum()
            if total_top > 0.8:
                report["concentration_risk"] = True
                log.warning(
                    "Top 3 features account for %.1f%% of importance — "
                    "consider whether this is robust.",
                    total_top * 100,
                )
    except Exception as exc:
        log.debug("Could not compute feature importance: %s", exc)

    return report


def check_feature_drift(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    threshold: float = 0.1,
) -> dict:
    """Check if the feature distribution has drifted between train and test.

    Uses the Kolmogorov-Smirnov statistic for each feature.

    Parameters
    ----------
    X_train : pd.DataFrame
        Training features.
    X_test : pd.DataFrame
        Test / out-of-sample features.
    threshold : float
        KS statistic threshold above which drift is flagged.

    Returns
    -------
    dict
        Per-feature drift scores and an overall ``drift_detected`` flag.
    """
    from scipy.stats import ks_2samp

    drift_scores = {}
    drifted_features = []

    for col in X_train.columns:
        train_vals = X_train[col].dropna()
        test_vals = X_test[col].dropna()
        if len(train_vals) < 10 or len(test_vals) < 10:
            continue
        try:
            stat, pvalue = ks_2samp(train_vals, test_vals)
            drift_scores[col] = {"ks_stat": float(stat), "p_value": float(pvalue)}
            if stat > threshold:
                drifted_features.append(col)
        except Exception:
            continue

    return {
        "drift_scores": drift_scores,
        "drifted_features": drifted_features,
        "drift_detected": len(drifted_features) > 0,
    }
