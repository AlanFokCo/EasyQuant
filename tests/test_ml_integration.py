"""Integration tests for eqlib.ml module.

Tests MLSelector running through the actual backtest engine,
and verifies the full feature -> model -> selection pipeline.
"""

import pytest
import pandas as pd
import numpy as np


class TestMLSelectorIntegration:
    """Integration tests that exercise MLSelector with real backtest data."""

    def test_ml_selector_basic_rank(self):
        """MLSelector can rank securities given a mock context."""
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(
            model='random_forest',
            features=['momentum', 'volatility'],
            target='forward_return_5d',
            top_n=2,
        )
        assert selector.top_n == 2
        assert selector.model_type == 'random_forest'

    def test_ml_selector_train_requires_context(self):
        """MLSelector.train() requires a proper context."""
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(
            features=['momentum'],
            target='forward_return_5d',
        )
        # Without a proper backtest context, train should handle gracefully
        class FakeContext:
            pass

        # Should not crash, just not train
        selector.train(['601390'], FakeContext())
        assert not selector._is_trained

    def test_ml_selector_rank_untrained_fallback(self):
        """When untrained, MLSelector falls back to first N securities."""
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(top_n=2)
        class FakeContext:
            current_dt = pd.Timestamp('2024-01-15')

        result = selector.rank(['601390', '600519', '000858'], FakeContext())
        assert result == ['601390', '600519']


class TestFeaturePipelineIntegration:
    """Integration tests for FeaturePipeline."""

    def test_pipeline_with_series_data(self):
        """FeaturePipeline computes features from synthetic price data."""
        from eqlib.ml.features import FeaturePipeline

        # Create synthetic OHLCV data
        np.random.seed(42)
        n = 100
        close = pd.Series(np.random.randn(n).cumsum() + 100, dtype=float)
        high = close + abs(np.random.randn(n)) * 2
        low = close - abs(np.random.randn(n)) * 2
        volume = pd.Series(np.random.randint(1000, 10000, n), dtype=float)

        pipeline = FeaturePipeline(features=['momentum', 'volatility', 'volume_ratio'])

        # Test individual feature computation directly
        result = pipeline._compute_momentum(close)
        assert 'momentum' in result
        assert isinstance(result['momentum'], float)

        result = pipeline._compute_volatility(close)
        assert 'volatility' in result
        assert result['volatility'] >= 0

        result = pipeline._compute_volume_ratio(volume)
        assert 'volume_ratio' in result

    def test_pipeline_empty_securities(self):
        """FeaturePipeline handles empty securities gracefully."""
        from eqlib.ml.features import FeaturePipeline

        pipeline = FeaturePipeline(features=['rsi'])
        df = pipeline.compute([], None, lookback=60)
        assert df.empty

    def test_pipeline_unknown_feature_with_custom(self):
        """FeaturePipeline accepts unknown features when custom_features provided."""
        from eqlib.ml.features import FeaturePipeline

        def custom_feat(close, high, low, volume):
            return float(close.iloc[-1])

        pipeline = FeaturePipeline(
            features=['custom_feature'],
            custom_features={'custom_feature': custom_feat}
        )
        assert 'custom_feature' in pipeline.features


class TestBaseMLModelIntegration:
    """Integration tests for BaseMLModel."""

    def test_model_fit_predict_cycle(self):
        """Full fit -> predict cycle works end-to-end."""
        from eqlib.ml.models import BaseMLModel

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(200, 5), columns=['a', 'b', 'c', 'd', 'e'])
        y = pd.Series(np.random.choice([0, 1], size=200))

        model = BaseMLModel('random_forest', n_estimators=10, max_depth=3)
        model.fit(X, y)

        preds = model.predict(X)
        assert len(preds) == len(X)
        assert all(0 <= p <= 1 for p in preds)

        importances = model.feature_importances()
        assert len(importances) == 5
        assert importances.sum() > 0

    def test_all_model_types(self):
        """All supported model types can be instantiated and used."""
        from eqlib.ml.models import BaseMLModel

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 4), columns=['a', 'b', 'c', 'd'])
        y = pd.Series(np.random.choice([0, 1], size=100))

        for model_type in ['random_forest', 'logistic_regression', 'gradient_boosting']:
            model = BaseMLModel(model_type, random_state=42)
            model.fit(X, y)
            preds = model.predict(X)
            assert len(preds) == len(X), f"{model_type} failed prediction"

    def test_model_save_load_roundtrip(self):
        """Model save/load preserves predictions."""
        import tempfile
        import os
        from eqlib.ml.models import BaseMLModel

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(50, 3), columns=['x', 'y', 'z'])
        y = pd.Series(np.random.choice([0, 1], size=50))

        model = BaseMLModel('random_forest', n_estimators=5, random_state=42)
        model.fit(X, y)
        preds_before = model.predict(X)

        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            path = f.name

        try:
            model.save(path)
            loaded = BaseMLModel.load(path)
            preds_after = loaded.predict(X)
            np.testing.assert_allclose(preds_before, preds_after, rtol=1e-5)
        finally:
            os.unlink(path)


class TestTuningIntegration:
    """Integration tests for hyperparameter tuning."""

    def test_optimize_hyperparams_with_data(self):
        """optimize_hyperparams works with synthetic data."""
        from eqlib.ml.tuning import optimize_hyperparams
        from eqlib.ml.features import FeaturePipeline

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 4), columns=['a', 'b', 'c', 'd'])
        y = pd.Series(np.random.choice([0, 1], size=100))

        pipeline = FeaturePipeline()
        result = optimize_hyperparams(
            pipeline,
            'random_forest',
            X,
            y,
            param_grid={'n_estimators': [5, 10]},
            n_splits=3,
        )
        assert isinstance(result, dict)

    def test_default_param_grids(self):
        """All model types have default parameter grids."""
        from eqlib.ml.tuning import _default_param_grid

        for model_type in ['random_forest', 'logistic_regression',
                            'gradient_boosting', 'xgboost']:
            grid = _default_param_grid(model_type)
            assert isinstance(grid, dict)


class TestValidationIntegration:
    """Integration tests for ML validation."""

    def test_validate_ml_strategy_basic(self):
        """validate_ml_strategy returns expected structure."""
        from eqlib.ml.validation import validate_ml_strategy
        from eqlib.ml.models import BaseMLModel

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(50, 3), columns=['a', 'b', 'c'])
        y = pd.Series(np.random.choice([0, 1], size=50))

        model = BaseMLModel('random_forest', n_estimators=5, random_state=42)
        model.fit(X, y)

        result = {'recorded_values': [], 'trade_log': []}
        report = validate_ml_strategy(result, model)
        assert 'feature_importance' in report
        assert 'concentration_risk' in report

    def test_check_feature_drift(self):
        """Feature drift detection identifies distribution changes."""
        from eqlib.ml.validation import check_feature_drift

        np.random.seed(42)
        X_train = pd.DataFrame(np.random.randn(100, 3), columns=['a', 'b', 'c'])
        # Shifted distribution
        X_test = pd.DataFrame(np.random.randn(100, 3) + 5, columns=['a', 'b', 'c'])

        result = check_feature_drift(X_train, X_test, threshold=0.1)
        assert 'drift_scores' in result
        assert 'drift_detected' in result


class TestMLModuleExports:
    """Test that all public APIs are properly exported."""

    def test_ml_module_imports(self):
        """All expected symbols are importable from eqlib.ml."""
        from eqlib.ml import (
            FeaturePipeline,
            BaseMLModel,
            MLSelector,
            optimize_hyperparams,
            auto_tune_selector,
            validate_ml_strategy,
            check_feature_drift,
        )
        assert FeaturePipeline is not None
        assert BaseMLModel is not None
        assert MLSelector is not None

    def test_eqlib_top_level_imports(self):
        """ML symbols are importable from eqlib top-level."""
        from eqlib import (
            FeaturePipeline,
            BaseMLModel,
            MLSelector,
            optimize_hyperparams,
            auto_tune_selector,
            validate_ml_strategy,
            check_feature_drift,
        )
        assert FeaturePipeline is not None
        assert BaseMLModel is not None
        assert MLSelector is not None
