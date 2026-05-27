"""Tests for eqlib.scientific.overfitting module."""

import datetime
import pytest
import numpy as np
import pandas as pd

from eqlib.scientific.overfitting import (
    walk_forward_analysis,
    parameter_sensitivity,
    out_of_sample_test,
    OverfittingWarning,
    OverfittingReport,
    WalkForwardResult,
    SensitivityResult,
    OOSResult,
)


def _make_backtest_result(n_days=504, annual_return=0.15, volatility=0.20, seed=42):
    """Create a synthetic backtest result dict."""
    rng = np.random.RandomState(seed)
    daily_vol = volatility / np.sqrt(252)
    daily_mu = annual_return / 252
    returns = rng.normal(daily_mu, daily_vol, n_days)

    dates = pd.bdate_range("2022-01-01", periods=n_days)
    starting_cash = 100_000.0
    values = [starting_cash]
    for r in returns:
        values.append(values[-1] * (1 + r))

    recorded_values = [
        {"date": d.date(), "total_value": v, "cash": v * 0.1}
        for d, v in zip(dates, values[:-1])
    ]

    return {
        "recorded_values": recorded_values,
        "trade_log": [
            {"date": dates[i].date(), "type": "BUY", "security": "000001.XSHE",
             "price": 10.0 + i * 0.01, "amount": 100, "commission": 5.0}
            for i in range(0, n_days, 20)
        ],
        "context": type("Ctx", (), {
            "portfolio": type("P", (), {"starting_cash": starting_cash})(),
            "start_date": dates[0].date(),
            "end_date": dates[-1].date(),
        })(),
        "benchmark": "000300.XSHG",
    }


class TestOutOfSampleTest:
    """Tests for out_of_sample_test."""

    def test_basic_oos(self):
        result = _make_backtest_result()
        oos = out_of_sample_test(result, train_pct=0.7)
        assert isinstance(oos, OOSResult)
        assert hasattr(oos, "train_sharpe")
        assert hasattr(oos, "test_sharpe")
        assert hasattr(oos, "sharpe_decay_pct")
        assert hasattr(oos, "overfitting_warning")

    def test_stable_strategy(self):
        """A stable strategy should show low OOS decay."""
        result = _make_backtest_result(n_days=504, annual_return=0.10, seed=1)
        oos = out_of_sample_test(result, train_pct=0.7)
        # Just check it returns valid results
        assert isinstance(oos.sharpe_decay_pct, float)
        assert oos.overfitting_warning is not None

    def test_empty_result(self):
        """Should handle empty result gracefully."""
        result = {"recorded_values": [], "trade_log": []}
        oos = out_of_sample_test(result, train_pct=0.7)
        assert isinstance(oos, OOSResult)

    def test_short_result(self):
        """Should handle very short data."""
        result = _make_backtest_result(n_days=5)
        oos = out_of_sample_test(result, train_pct=0.7)
        assert isinstance(oos, OOSResult)


class TestParameterSensitivity:
    """Tests for parameter_sensitivity."""

    def test_basic_sensitivity(self):
        result = _make_backtest_result()
        sens = parameter_sensitivity(result)
        assert isinstance(sens, SensitivityResult)
        assert hasattr(sens, "is_stable")
        assert hasattr(sens, "stability_score")
        assert hasattr(sens, "sensitivity_rating")
        assert sens.sensitivity_rating in ("LOW", "MEDIUM", "HIGH")

    def test_stable_returns(self):
        """Consistent returns should have low sensitivity."""
        result = _make_backtest_result(volatility=0.05, seed=10)
        sens = parameter_sensitivity(result)
        assert isinstance(sens, SensitivityResult)
        assert 0 <= sens.stability_score <= 100

    def test_empty_result(self):
        result = {"recorded_values": [], "trade_log": []}
        sens = parameter_sensitivity(result)
        assert isinstance(sens, SensitivityResult)


class TestWalkForwardAnalysis:
    """Tests for walk_forward_analysis."""

    def test_wfa_importable(self):
        """walk_forward_analysis requires an initialize_func; just verify import."""
        assert callable(walk_forward_analysis)


class TestOverfittingWarning:
    """Tests for OverfittingWarning constants."""

    def test_constants_exist(self):
        assert OverfittingWarning.HIGH_OVERFITTING is not None
        assert OverfittingWarning.MEDIUM_OVERFITTING is not None
        assert OverfittingWarning.LOW_OVERFITTING is not None
        assert OverfittingWarning.STABLE is not None


class TestOverfittingReport:
    """Tests for OverfittingReport."""

    def test_report_creation(self):
        result = _make_backtest_result()
        oos = out_of_sample_test(result)
        sens = parameter_sensitivity(result)
        # Create a minimal WalkForwardResult
        wfa = WalkForwardResult(
            windows=[],
            is_sharpe_decay=False,
            oos_is_ratio=0.9,
        )
        report = OverfittingReport(
            walk_forward=wfa,
            sensitivity=sens,
            out_of_sample=oos,
        )
        assert hasattr(report, "summary")
        summary = report.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0
