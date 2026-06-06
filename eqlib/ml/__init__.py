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

__all__ = [
    "FeaturePipeline",
    "BaseMLModel",
    "MLSelector",
]
