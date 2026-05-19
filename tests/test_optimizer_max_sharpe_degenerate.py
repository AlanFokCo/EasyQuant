"""PR-4: MaxSharpe degenerate test.

Verifies that when one asset has zero variance (constant price),
MaxSharpe optimization does NOT allocate all weight to that asset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_prices(n_days: int = 60) -> pd.DataFrame:
    """Build price DataFrame: asset A has zero variance, asset B has normal vol."""
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    constant = np.ones(n_days) * 10.0          # zero variance
    trending = 10.0 + np.arange(n_days) * 0.05 + np.random.default_rng(42).normal(0, 0.3, n_days)
    return pd.DataFrame({"A": constant, "B": trending}, index=dates)


class TestMaxSharpeDegenerate:
    def test_weight_not_all_on_zero_variance_asset(self):
        """Zero-variance asset must not capture all weight under MaxSharpe."""
        from eqlib.optimizer import MaxSharpe, portfolio_optimizer

        prices = _make_prices()
        weights = portfolio_optimizer(["A", "B"], prices, target=MaxSharpe())
        assert weights is not None, "portfolio_optimizer returned None"
        w_a = float(weights["A"])
        w_b = float(weights["B"])
        # Weights must sum to 1
        assert abs(w_a + w_b - 1.0) < 1e-6
        # Zero-variance asset should NOT dominate
        assert w_a < 0.99, (
            f"Zero-variance asset A got weight {w_a:.4f}; optimizer was not pushed away"
        )

    def test_total_weights_sum_to_one(self):
        """Weights always sum to 1 even with degenerate asset."""
        from eqlib.optimizer import MaxSharpe, portfolio_optimizer

        prices = _make_prices()
        weights = portfolio_optimizer(["A", "B"], prices, target=MaxSharpe())
        assert weights is not None
        assert abs(weights.sum() - 1.0) < 1e-6
