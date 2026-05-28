"""Tests for eqlib.scientific.validation_runner and report modules."""

import datetime
import pytest
import numpy as np
import pandas as pd

from eqlib.validation_config import ValidationConfig
from eqlib.scientific.validation_runner import (
    validate_backtest,
    ValidationResult,
    TrustRating,
)
from eqlib.scientific.report import (
    generate_validation_report,
    ReportConfig,
    ValidationReport,
)


def _make_backtest_result(n_days=252, annual_return=0.12, volatility=0.18, seed=42):
    """Create a synthetic backtest result dict."""
    rng = np.random.RandomState(seed)
    daily_vol = volatility / np.sqrt(252)
    daily_mu = annual_return / 252
    returns = rng.normal(daily_mu, daily_vol, n_days)

    dates = pd.bdate_range("2023-01-01", periods=n_days)
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
            for i in range(0, n_days, 15)
        ],
        "context": type("Ctx", (), {
            "portfolio": type("P", (), {"starting_cash": starting_cash})(),
            "start_date": dates[0].date(),
            "end_date": dates[-1].date(),
        })(),
        "benchmark": "000300.XSHG",
    }


class TestValidateBacktest:
    """Tests for the unified validate_backtest function."""

    def test_default_config(self):
        """validate_backtest with default config should return a ValidationResult."""
        result = _make_backtest_result()
        vr = validate_backtest(result)
        assert isinstance(vr, ValidationResult)
        assert vr.trust_rating is not None
        assert isinstance(vr.trust_rating, str)

    def test_all_disabled(self):
        """All modules disabled should return a nearly empty result."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=False,
            bias_check=False,
            risk_metrics="basic",
            comparison=False,
        )
        vr = validate_backtest(result, config=config)
        assert isinstance(vr, ValidationResult)

    def test_only_risk(self):
        """Enable only risk metrics."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=False,
            bias_check=False,
            risk_metrics="extended",
            comparison=False,
        )
        vr = validate_backtest(result, config=config)
        assert vr.risk_report is not None

    def test_only_statistics(self):
        """Enable only statistics."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=True,
            bias_check=False,
            risk_metrics="basic",
            comparison=False,
            n_bootstrap=50,
        )
        vr = validate_backtest(result, config=config)
        assert vr.confidence_report is not None

    def test_only_bias(self):
        """Enable only bias check."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=False,
            bias_check=True,
            risk_metrics="basic",
            comparison=False,
        )
        vr = validate_backtest(result, config=config)
        assert vr.bias_report is not None

    def test_only_overfitting(self):
        """Enable only overfitting detection."""
        result = _make_backtest_result(n_days=504)
        config = ValidationConfig(
            overfitting=True,
            statistics=False,
            bias_check=False,
            risk_metrics="basic",
            comparison=False,
        )
        vr = validate_backtest(result, config=config)
        assert vr.overfitting_report is not None

    def test_summary(self):
        """summary() should return a non-empty string."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=True,
            bias_check=True,
            risk_metrics="extended",
            comparison=False,
            n_bootstrap=50,
        )
        vr = validate_backtest(result, config=config)
        summary = vr.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_empty_result(self):
        """Should handle empty backtest result gracefully."""
        result = {"recorded_values": [], "trade_log": []}
        vr = validate_backtest(result)
        assert isinstance(vr, ValidationResult)


class TestTrustRating:
    """Tests for TrustRating constants."""

    def test_constants(self):
        assert TrustRating.HIGH_TRUST is not None
        assert TrustRating.MEDIUM_TRUST is not None
        assert TrustRating.LOW_TRUST is not None
        assert TrustRating.INSUFFICIENT_DATA is not None


class TestValidationConfig:
    """Tests for ValidationConfig."""

    def test_defaults(self):
        config = ValidationConfig()
        assert config.overfitting is True
        assert config.statistics is True
        assert config.bias_check is True
        assert config.risk_metrics == "extended"
        assert config.comparison is False
        assert config.n_bootstrap == 1000
        assert config.walk_forward_windows is not None

    def test_custom(self):
        config = ValidationConfig(
            overfitting=False,
            n_bootstrap=500,
            significance_level=0.01,
        )
        assert config.overfitting is False
        assert config.n_bootstrap == 500
        assert config.significance_level == 0.01


class TestReportGeneration:
    """Tests for report generation."""

    def test_markdown_report(self):
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False,
            statistics=True,
            bias_check=True,
            risk_metrics="extended",
            comparison=False,
            n_bootstrap=50,
        )
        vr = validate_backtest(result, config=config)
        report = generate_validation_report(vr)
        assert isinstance(report, ValidationReport)
        assert report.markdown is not None
        assert "验证" in report.markdown or "validation" in report.markdown.lower() or len(report.markdown) > 0

    def test_json_report(self):
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False, statistics=False, bias_check=True,
            risk_metrics="extended", comparison=False,
        )
        vr = validate_backtest(result, config=config)
        report_config = ReportConfig(format=["json"])
        report = generate_validation_report(vr, config=report_config)
        assert isinstance(report, ValidationReport)
        assert report.json_data is not None
        assert isinstance(report.json_data, dict)

    def test_html_report(self):
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False, statistics=False, bias_check=False,
            risk_metrics="extended", comparison=False,
        )
        vr = validate_backtest(result, config=config)
        report_config = ReportConfig(format=["html"])
        report = generate_validation_report(vr, config=report_config)
        assert isinstance(report, ValidationReport)
        assert report.html is not None
        assert "<html" in report.html.lower() or "<div" in report.html.lower() or len(report.html) > 0

    def test_save_report(self, tmp_path):
        """save() should write files without error."""
        result = _make_backtest_result()
        config = ValidationConfig(
            overfitting=False, statistics=False, bias_check=True,
            risk_metrics="basic", comparison=False,
        )
        vr = validate_backtest(result, config=config)
        report_config = ReportConfig(format=["markdown", "json"])
        report = generate_validation_report(vr, config=report_config)
        report.save(str(tmp_path))
        # Should have written at least one file
        files = list(tmp_path.iterdir())
        assert len(files) >= 1
