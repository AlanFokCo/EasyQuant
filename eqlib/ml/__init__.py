"""Machine Learning module for eqlib.

Provides ML-based stock selection, feature engineering, and model training
integrated with the existing backtest framework.

Usage:
    from eqlib.ml import MLSelector, FeaturePipeline

    selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum'],
        target='forward_return_5d',
        top_n=5
    )
    selected = selector.rank(context.universe, context)
"""

from eqlib.ml.features import FeaturePipeline
from eqlib.ml.models import BaseMLModel
from eqlib.ml.selection import MLSelector
from eqlib.ml.tuning import optimize_hyperparams, auto_tune_selector
from eqlib.ml.validation import validate_ml_strategy, check_feature_drift

__all__ = [
    "FeaturePipeline",
    "BaseMLModel",
    "MLSelector",
    "optimize_hyperparams",
    "auto_tune_selector",
    "validate_ml_strategy",
    "check_feature_drift",
]
