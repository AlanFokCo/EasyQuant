import numpy as np
import pandas as pd

from eqlib.scientific.statistics import (
    BootstrapResult,
    ConfidenceLevel,
    ConfidenceReport,
    MonteCarloResult,
    _extract_daily_returns,
    bootstrap_metrics,
    monte_carlo_simulation,
    sample_size_assessment,
    significance_test,
)


def _make_backtest_result(days: int = 756) -> dict:
    rng = np.random.default_rng(123)
    dates = pd.bdate_range("2020-01-01", periods=days)
    daily_returns = rng.normal(0.001, 0.01, size=days)

    total_value = 100000.0
    recorded_values = []
    for date, daily_return in zip(dates, daily_returns):
        total_value *= 1.0 + daily_return
        recorded_values.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "total_value": total_value,
                "cash": total_value * 0.1,
            }
        )

    trade_log = [
        {
            "date": dates[i].strftime("%Y-%m-%d"),
            "type": "buy" if i % 2 == 0 else "sell",
            "security": "000001.XSHE",
            "price": 10.0 + i,
            "amount": 100,
            "commission": 5.0,
        }
        for i in range(40)
    ]
    return {"recorded_values": recorded_values, "trade_log": trade_log}


def test_extract_daily_returns_from_backtest_result():
    result = {
        "recorded_values": [
            {"date": "2024-01-02", "total_value": 100.0, "cash": 50.0},
            {"date": "2024-01-03", "total_value": 105.0, "cash": 50.0},
            {"date": "2024-01-04", "total_value": 103.95, "cash": 50.0},
        ]
    }

    returns = _extract_daily_returns(result)

    assert len(returns) == 2
    assert np.isclose(returns.iloc[0], 0.05)
    assert np.isclose(returns.iloc[1], -0.01)


def test_bootstrap_metrics_returns_confidence_intervals():
    result = _make_backtest_result()

    bootstrap = bootstrap_metrics(result, n_bootstrap=100, confidence_level=0.90)

    assert isinstance(bootstrap, BootstrapResult)
    assert bootstrap.n_bootstrap == 100
    assert bootstrap.confidence_level == 0.90
    assert set(bootstrap.metrics) == {
        "sharpe_ratio",
        "annual_return",
        "max_drawdown",
        "sortino_ratio",
    }
    assert (
        bootstrap.metrics["sharpe_ratio"].ci_upper
        >= bootstrap.metrics["sharpe_ratio"].ci_lower
    )


def test_monte_carlo_simulation_returns_distribution_summary():
    result = _make_backtest_result()

    simulation = monte_carlo_simulation(
        result,
        n_simulations=50,
        random_start_dates=True,
        random_params=True,
        param_ranges={
            "drift_multiplier": (0.9, 1.1),
            "volatility_multiplier": (0.9, 1.1),
        },
    )

    assert isinstance(simulation, MonteCarloResult)
    assert len(simulation.sharpe_distribution) == 50
    assert len(simulation.return_distribution) == 50
    assert 0.0 <= simulation.p_value_vs_random <= 1.0
    assert simulation.percentile_95 >= simulation.percentile_5


def test_bootstrap_metrics_is_reproducible_with_random_state():
    result = _make_backtest_result()

    first = bootstrap_metrics(result, n_bootstrap=50, random_state=7)
    second = bootstrap_metrics(result, n_bootstrap=50, random_state=7)

    assert first == second


def test_monte_carlo_simulation_is_reproducible_with_random_state():
    result = _make_backtest_result()

    first = monte_carlo_simulation(
        result, n_simulations=50, random_start_dates=True, random_state=7
    )
    second = monte_carlo_simulation(
        result, n_simulations=50, random_start_dates=True, random_state=7
    )

    assert first == second


def test_significance_test_supports_ttest_and_wilcoxon():
    rng = np.random.default_rng(42)
    strategy = pd.Series(rng.normal(0.002, 0.004, size=120))
    benchmark = pd.Series(rng.normal(0.0005, 0.004, size=120))

    t_test_result = significance_test(
        strategy, benchmark_returns=benchmark, test_type="t-test"
    )
    wilcoxon_result = significance_test(strategy, test_type="wilcoxon")

    assert t_test_result.test_type == "t-test"
    assert t_test_result.mean_benchmark is not None
    assert "benchmark" in t_test_result.conclusion.lower()
    assert wilcoxon_result.test_type == "wilcoxon"
    assert wilcoxon_result.p_value < 0.05
    assert wilcoxon_result.is_significant


def test_sample_size_assessment_infers_counts_and_span_from_backtest_result():
    result = _make_backtest_result()

    assessment = sample_size_assessment(backtest_result=result)

    assert assessment.trade_count == 40
    assert assessment.daily_observations >= 504
    assert assessment.time_span_years is not None and assessment.time_span_years >= 2.0
    assert assessment.assessment == "SUFFICIENT"
    assert assessment.is_sufficient


def test_confidence_report_summary_uses_inferred_level():
    result = _make_backtest_result()
    report = ConfidenceReport(
        bootstrap_result=bootstrap_metrics(result, n_bootstrap=50),
        monte_carlo_result=monte_carlo_simulation(result, n_simulations=30),
        significance_result=significance_test(
            _extract_daily_returns(result), test_type="t-test"
        ),
        sample_size_result=sample_size_assessment(backtest_result=result),
    )

    summary = report.summary()

    assert report.inferred_confidence_level() in {
        ConfidenceLevel.HIGH_CONFIDENCE,
        ConfidenceLevel.MEDIUM_CONFIDENCE,
        ConfidenceLevel.LOW_CONFIDENCE,
    }
    assert "Overall confidence:" in summary
    assert "Sharpe CI=" in summary
