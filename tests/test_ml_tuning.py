"""Tests for eqlib.ml.tuning module."""

import pytest
import pandas as pd
import numpy as np


class TestOptimizeHyperparams:
    def test_default_param_grid_random_forest(self):
        from eqlib.ml.tuning import _default_param_grid

        grid = _default_param_grid("random_forest")
        assert "n_estimators" in grid
        assert "max_depth" in grid
        assert "min_samples_leaf" in grid

    def test_default_param_grid_logistic_regression(self):
        from eqlib.ml.tuning import _default_param_grid

        grid = _default_param_grid("logistic_regression")
        assert "C" in grid
        assert "penalty" in grid

    def test_optimize_hyperparams_basic(self):
        from eqlib.ml.tuning import optimize_hyperparams
        from eqlib.ml.features import FeaturePipeline

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 4), columns=["a", "b", "c", "d"])
        y = pd.Series(np.random.choice([0, 1], size=100))

        pipeline = FeaturePipeline()
        # With very few samples, this will fall back to defaults
        result = optimize_hyperparams(
            pipeline,
            "random_forest",
            X,
            y,
            param_grid={"n_estimators": [10, 20]},
            n_splits=3,
        )
        assert isinstance(result, dict)
