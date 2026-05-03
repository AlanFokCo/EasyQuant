"""Test money management utility functions."""

import numpy as np
import pandas as pd
from eqlib.utils.money import (
    kelly_criterion, half_kelly, kelly_from_returns,
    fixed_fraction_size, fixed_ratio_size, percent_of_equity,
    volatility_target_size, atr_position_size,
    martingale_size, anti_martingale_size,
    equal_weight, risk_parity_weights, volatility_normalize,
)


class TestKelly:
    def test_kelly_criterion(self):
        # 60% win rate, avg_win=2, avg_loss=1
        result = kelly_criterion(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        expected = (2.0 * 0.6 - 0.4) / 2.0  # 0.4
        assert abs(result - expected) < 1e-10

    def test_kelly_criterion_unfavorable(self):
        # 30% win rate, avg_win=1, avg_loss=1 — should be 0
        result = kelly_criterion(win_rate=0.3, avg_win=1.0, avg_loss=1.0)
        assert result == 0.0  # Kelly is floored at 0

    def test_half_kelly(self):
        result = half_kelly(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        full = kelly_criterion(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        assert abs(result - full * 0.5) < 1e-10

    def test_kelly_from_returns(self):
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        result = kelly_from_returns(returns)
        assert isinstance(result, float)
        assert result >= 0


class TestPositionSizing:
    def test_fixed_fraction_size(self):
        # Risk 2% of 100k = 2000, stop distance = 50-48 = 2
        size = fixed_fraction_size(capital=100000, risk_pct=0.02, entry_price=50.0, stop_price=48.0)
        assert size == 100000 * 0.02 / 2 // 100 * 100  # 1000 // 100 * 100 = 1000

    def test_fixed_fraction_zero_on_tight_stop(self):
        # If stop == entry, no position
        size = fixed_fraction_size(capital=100000, risk_pct=0.02, entry_price=50.0, stop_price=50.0)
        assert size == 0

    def test_fixed_ratio_size(self):
        size = fixed_ratio_size(capital=100000, equity_ratio=0.1, entry_price=50.0)
        expected = int(100000 * 0.1 / 50 // 100) * 100  # 200 // 100 * 100 = 200
        assert size == expected

    def test_percent_of_equity(self):
        amount = percent_of_equity(capital=100000, pct=0.1)
        assert amount == 10000.0

    def test_volatility_target_size(self):
        size = volatility_target_size(
            capital=100000, target_vol=0.15, price=100.0, vol_per_share=20.0
        )
        assert isinstance(size, int)

    def test_atr_position_size(self):
        size = atr_position_size(capital=100000, risk_pct=0.01, atr=2.0, n_atr=2.0)
        # risk = 1000, stop = 2*2 = 4, shares = 1000/4 = 250 // 100 * 100 = 200
        assert size == 200


class TestMartingale:
    def test_martingale_size(self):
        size = martingale_size(base_amount=100, loss_streak=3)
        assert size == 800  # 100 * 2^3

    def test_anti_martingale_size(self):
        size = anti_martingale_size(base_amount=100, win_streak=2, multiplier=2.0)
        assert size == 400  # 100 * 2^2


class TestPortfolioWeights:
    def test_equal_weight(self):
        weights = equal_weight(n=3)
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 1e-10
        assert all(abs(w - 1/3) < 1e-10 for w in weights)

    def test_risk_parity_weights(self):
        vols = [0.1, 0.2, 0.15]
        weights = risk_parity_weights(vols)
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 1e-6
        # Lower vol asset should get higher weight
        assert weights[0] > weights[1]

    def test_volatility_normalize(self):
        np.random.seed(42)
        returns = pd.Series(np.random.randn(200) * 0.02)
        normalized = volatility_normalize(returns)
        assert len(normalized) == 200
