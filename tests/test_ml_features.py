"""Tests for eqlib.ml.features module."""

import pytest
import pandas as pd
import numpy as np


def test_feature_pipeline_default_features():
    from eqlib.ml.features import FeaturePipeline

    pipeline = FeaturePipeline()
    assert pipeline.features == FeaturePipeline.DEFAULT_FEATURES


def test_feature_pipeline_custom_features():
    from eqlib.ml.features import FeaturePipeline

    pipeline = FeaturePipeline(features=['rsi', 'macd_hist'])
    assert set(pipeline.features) == {'rsi', 'macd_hist'}


def test_feature_pipeline_unknown_feature_raises():
    from eqlib.ml.features import FeaturePipeline

    with pytest.raises(ValueError, match="Unknown features"):
        FeaturePipeline(features=['nonexistent_feature'])


def test_compute_rsi():
    from eqlib.ml.features import FeaturePipeline

    close = pd.Series(range(100, 150), dtype=float)

    pipeline = FeaturePipeline(features=['rsi'])
    result = FeaturePipeline._compute_rsi(close)
    assert 'rsi' in result
    assert isinstance(result['rsi'], float) or np.isnan(result['rsi'])


def test_compute_momentum():
    from eqlib.ml.features import FeaturePipeline

    close = pd.Series(range(100, 200), dtype=float)
    result = FeaturePipeline._compute_momentum(close)
    assert 'momentum' in result
    assert isinstance(result['momentum'], float)


def test_compute_volatility():
    from eqlib.ml.features import FeaturePipeline

    close = pd.Series(np.random.randn(100).cumsum() + 100, dtype=float)
    result = FeaturePipeline._compute_volatility(close)
    assert 'volatility' in result
    assert isinstance(result['volatility'], float)
    assert result['volatility'] >= 0


def test_compute_volume_ratio():
    from eqlib.ml.features import FeaturePipeline

    volume = pd.Series(range(1000, 2000), dtype=float)
    result = FeaturePipeline._compute_volume_ratio(volume)
    assert 'volume_ratio' in result
    assert isinstance(result['volume_ratio'], float)
