"""Integration test: full scientific validation pipeline end-to-end."""

import datetime
import numpy as np
import pandas as pd
import pytest

from eqlib.validation_config import ValidationConfig
from eqlib.scientific import (
    validate_backtest,
    ValidationResult,
    TrustRating,
    generate_validation_report,
    ReportConfig,
    ValidationReport,
    # Verify all public symbols import
    OverfittingWarning, OverfittingReport,
    ConfidenceLevel, ConfidenceReport,
    BiasSeverity, BiasReport,
    RiskRating, RiskReport,
    ComparisonJudgment, ComparisonReport,
)


def _make_full_backtest_result(n_days=504, seed=42):
    """Synthetic backtest result with all fields populated."""
    rng = np.random.RandomState(seed)
    daily_ret = rng.normal(0.0004, 0.012, n_days)
    dates = pd.bdate_range("2022-01-01", periods=n_days)
    starting_cash = 100_000.0
    values = [starting_cash]
    for r in daily_ret:
        values.append(values[-1] * (1 + r))

    recorded_values = [
        {"date": d.date(), "total_value": v, "cash": v * 0.05}
        for d, v in zip(dates, values[:-1])
    ]
    trade_log = [
        {"date": dates[i].date(), "type": "BUY" if i % 2 == 0 else "SELL",
         "security": "600000.XSHG", "price": 8.0 + rng.uniform(-0.5, 0.5),
         "amount": 100, "commission": 5.0}
        for i in range(0, n_days, 10)
    ]

    return {
        "recorded_values": recorded_values,
        "trade_log": trade_log,
        "context": type("Ctx", (), {
            "portfolio": type("P", (), {"starting_cash": starting_cash})(),
            "start_date": dates[0].date(),
            "end_date": dates[-1].date(),
        })(),
        "benchmark": "000300.XSHG",
    }


class TestFullValidationPipeline:
    """End-to-end integration tests."""

    def test_full_pipeline(self):
        """Run full validation pipeline with all modules enabled."""
        result = _make_full_backtest_result()
        config = ValidationConfig(
            overfitting=True,
            statistics=True,
            bias_check=True,
            risk_metrics="extended",
            comparison=False,
            n_bootstrap=50,   # small for speed
            n_monte_carlo=50,
        )
        vr = validate_backtest(result, config=config)

        assert isinstance(vr, ValidationResult)
        assert vr.trust_rating in (
            TrustRating.HIGH_TRUST,
            TrustRating.MEDIUM_TRUST,
            TrustRating.LOW_TRUST,
            TrustRating.INSUFFICIENT_DATA,
        )
        # All reports should be populated
        assert vr.bias_report is not None
        assert vr.risk_report is not None
        assert vr.confidence_report is not None
        assert vr.overfitting_report is not None
        # Comparison not enabled
        assert vr.comparison_report is None

        # Summary should be non-empty
        summary = vr.summary()
        assert isinstance(summary, str)
        assert len(summary) > 10

    def test_full_report_generation(self, tmp_path):
        """Generate markdown + json + html reports."""
        result = _make_full_backtest_result()
        config = ValidationConfig(
            overfitting=True,
            statistics=True,
            bias_check=True,
            risk_metrics="extended",
            comparison=False,
            n_bootstrap=30,
            n_monte_carlo=30,
        )
        vr = validate_backtest(result, config=config)

        report_config = ReportConfig(
            format=["markdown", "json", "html"],
            output_dir=str(tmp_path),
        )
        report = generate_validation_report(vr, config=report_config)
        assert isinstance(report, ValidationReport)

        # Check markdown
        assert report.markdown is not None
        assert len(report.markdown) > 100

        # Check JSON
        assert report.json_data is not None
        assert isinstance(report.json_data, dict)
        assert "execution_summary" in report.json_data
        assert "trust_rating" in report.json_data["execution_summary"]

        # Check HTML
        assert report.html is not None
        assert len(report.html) > 100

        # Save and verify files
        report.save(str(tmp_path))
        files = list(tmp_path.iterdir())
        assert len(files) >= 1

    def test_pipeline_with_comparison(self):
        """Test pipeline with platform comparison enabled."""
        result = _make_full_backtest_result()
        platform_result = {
            "total_return": 0.08,
            "sharpe_ratio": 0.9,
            "max_drawdown": -0.12,
            "annual_return": 0.06,
        }
        config = ValidationConfig(
            overfitting=False,
            statistics=False,
            bias_check=False,
            risk_metrics="basic",
            comparison=True,
        )
        vr = validate_backtest(result, config=config, platform_result=platform_result)
        assert isinstance(vr, ValidationResult)

    def test_resilience_to_bad_data(self):
        """Pipeline should not crash on degenerate input."""
        for bad_result in [
            {"recorded_values": [], "trade_log": []},
            {"recorded_values": [{"date": datetime.date(2023, 1, 1),
                                  "total_value": 100000, "cash": 100000}],
             "trade_log": []},
        ]:
            vr = validate_backtest(bad_result)
            assert isinstance(vr, ValidationResult)


class TestPublicAPICompleteness:
    """Verify all public symbols from the design doc are importable."""

    def test_overfitting_symbols(self):
        from eqlib.scientific.overfitting import (
            walk_forward_analysis,
            parameter_sensitivity,
            out_of_sample_test,
            OverfittingReport,
            OverfittingWarning,
        )

    def test_statistics_symbols(self):
        from eqlib.scientific.statistics import (
            bootstrap_metrics,
            monte_carlo_simulation,
            significance_test,
            sample_size_assessment,
            ConfidenceReport,
            ConfidenceLevel,
        )

    def test_bias_symbols(self):
        from eqlib.scientific.bias import (
            check_survivorship_bias,
            check_lookahead_bias,
            check_selection_bias,
            check_data_bias,
            BiasReport,
            BiasSeverity,
            SurvivorshipCorrectedData,
        )

    def test_risk_symbols(self):
        from eqlib.scientific.risk import (
            extended_risk_metrics,
            value_at_risk,
            conditional_var,
            stress_test,
            tail_risk_analysis,
            RiskReport,
            RiskRating,
        )

    def test_comparison_symbols(self):
        from eqlib.scientific.comparison import (
            align_benchmark,
            compare_with_platform,
            compare_metrics,
            verify_trades,
            ComparisonReport,
            ComparisonJudgment,
        )

    def test_runner_symbols(self):
        from eqlib.scientific.validation_runner import (
            validate_backtest,
            ValidationResult,
            TrustRating,
        )

    def test_report_symbols(self):
        from eqlib.scientific.report import (
            generate_validation_report,
            ValidationReport,
            ReportConfig,
        )

    def test_top_level_import(self):
        from eqlib.scientific import validate_backtest, ValidationConfig
        from eqlib import ValidationConfig as VC2
        assert VC2 is ValidationConfig
