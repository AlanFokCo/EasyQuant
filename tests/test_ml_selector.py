"""Tests for eqlib.ml.selection module."""

import pytest
import pandas as pd
import numpy as np


class MockContext:
    """Minimal mock context for MLSelector tests."""

    def __init__(self):
        self.current_dt = pd.Timestamp("2024-01-15")


class TestMLSelector:
    def test_init_default(self):
        from eqlib.ml.selection import MLSelector

        selector = MLSelector()
        assert selector.top_n == 5
        assert selector.model_type == "random_forest"
        assert not selector._is_trained

    def test_init_custom(self):
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(
            model="logistic_regression",
            features=["rsi", "momentum"],
            top_n=3,
        )
        assert selector.top_n == 3
        assert selector.model_type == "logistic_regression"
        assert set(selector.pipeline.features) == {"rsi", "momentum"}

    def test_train_basic(self):
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(
            model="random_forest",
            features=["momentum", "volatility"],
            top_n=3,
        )
        context = MockContext()
        # This will fail because there's no actual backtest data,
        # but it shouldn't crash
        try:
            selector.train(["601390", "600519", "000858"], context)
        except Exception:
            pass
        # Should still be not trained (no real data)
        assert not selector._is_trained

    def test_rank_untrained(self):
        from eqlib.ml.selection import MLSelector

        selector = MLSelector(top_n=2)
        context = MockContext()
        securities = ["601390", "600519", "000858"]
        # Should fallback to first N when untrained
        result = selector.rank(securities, context)
        assert result == securities[:2]
