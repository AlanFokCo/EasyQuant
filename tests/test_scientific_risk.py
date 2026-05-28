from types import SimpleNamespace

import pandas as pd

from eqlib.scientific.risk import (
    RiskRating,
    RiskReport,
    conditional_var,
    extended_risk_metrics,
    stress_test,
    tail_risk_analysis,
    value_at_risk,
)


def _sample_backtest_result():
    values = [100000, 101500, 100500, 102000, 99000, 99500, 100200, 98200, 99000, 101000]
    recorded_values = [
        {"date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i), "total_value": value, "cash": value * 0.1}
        for i, value in enumerate(values)
    ]
    portfolio = SimpleNamespace(starting_cash=100000.0, total_value=values[-1])
    context = SimpleNamespace(portfolio=portfolio)
    return {
        "recorded_values": recorded_values,
        "trade_log": [],
        "context": context,
        "benchmark_values": [],
    }


def test_extended_risk_metrics_returns_expected_keys():
    metrics = extended_risk_metrics(_sample_backtest_result())

    assert set(metrics) == {
        "sortino_ratio",
        "calmar_ratio",
        "var_95",
        "var_99",
        "cvar_95",
        "cvar_99",
        "downside_deviation",
        "skewness",
        "kurtosis",
        "max_consecutive_loss_days",
        "best_day",
        "worst_day",
        "risk_rating",
    }
    assert metrics["var_99"] >= metrics["var_95"]
    assert metrics["cvar_99"] >= metrics["var_99"]
    assert metrics["risk_rating"] in {
        RiskRating.LOW_RISK,
        RiskRating.MEDIUM_RISK,
        RiskRating.HIGH_RISK,
    }


def test_var_cvar_tail_and_stress_outputs_are_structured():
    returns = pd.Series([-0.03, -0.02, 0.01, 0.015, -0.01, 0.005, -0.025, 0.02])

    var_result = value_at_risk(returns, confidence_level=0.95, method="cornish_fisher")
    cvar_result = conditional_var(returns, confidence_level=0.95)
    tail_result = tail_risk_analysis(returns)
    stress_result = stress_test(_sample_backtest_result())

    assert var_result["method"] == "cornish_fisher"
    assert var_result["var"] >= 0.0
    assert cvar_result["cvar"] >= cvar_result["var"]
    assert tail_result["tail_risk_rating"] in {"LOW", "MEDIUM", "HIGH"}
    assert len(stress_result["scenarios"]) == 4
    assert {scenario["stress_rating"] for scenario in stress_result["scenarios"]} <= {
        RiskRating.RESILIENT,
        RiskRating.VULNERABLE,
        RiskRating.CRITICAL,
    }


def test_risk_report_summary_contains_core_sections():
    metrics = extended_risk_metrics(_sample_backtest_result())
    report = RiskReport(
        extended_metrics=metrics,
        var_95=value_at_risk(pd.Series([0.01, -0.02, 0.015, -0.01])),
        cvar_95=conditional_var(pd.Series([0.01, -0.02, 0.015, -0.01])),
        tail_risk=tail_risk_analysis(pd.Series([0.01, -0.02, 0.015, -0.01])),
        stress_test=stress_test(_sample_backtest_result()),
    )

    summary = report.summary()
    assert "Risk Report" in summary
    assert "VaR 95% / CVaR 95%" in summary
    assert "Worst stress" in summary
