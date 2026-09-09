"""Numerical reference cases for review findings F07, F08 and F09."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from eqlib.report import _build_drawdown_from_cumulative_pct, _compute_chart_data
from eqlib.scientific.overfitting import _compute_max_drawdown
from eqlib.scientific.risk import _max_drawdown, conditional_var as scientific_cvar
from eqlib.scientific.statistics import _metric_max_drawdown, bootstrap_metrics
from eqlib.utils.stats import conditional_var, drawdown


@pytest.mark.parametrize(
    "returns, expected",
    [
        ([-0.5], -0.5),
        ([-0.5, 0.0, 0.0], -0.5),
        ([-0.2, -0.25, 1.0], -0.4),
        ([1.0, -0.25], -0.25),
        ([-1.0, 0.0], -1.0),
        ([0.0, 0.0], 0.0),
        ([0.1, 0.2], 0.0),
    ],
)
def test_scientific_drawdown_matches_equity_reference(returns, expected):
    # The reference explicitly contains the capital before the first return.
    equity = pd.Series(np.r_[1.0, np.cumprod(1.0 + np.array(returns))])
    reference = drawdown(equity).min()
    assert reference == pytest.approx(expected)
    series = pd.Series(returns, index=pd.bdate_range("2024-01-01", periods=len(returns)))
    assert _max_drawdown(series) == pytest.approx(reference)
    assert _compute_max_drawdown(series) == pytest.approx(reference)
    # Bootstrap metrics intentionally report drawdown as a positive magnitude.
    assert _metric_max_drawdown(series) == pytest.approx(abs(reference))


def test_bootstrap_point_estimate_includes_first_observed_loss():
    result = {
        "recorded_values": [
            {"date": date, "total_value": value}
            for date, value in zip(pd.bdate_range("2024-01-01", periods=4), [100, 50, 50, 50])
        ]
    }
    metric = bootstrap_metrics(result, n_bootstrap=20, metrics=["max_drawdown"]).metrics["max_drawdown"]
    assert metric.point_estimate == pytest.approx(0.5)


@pytest.mark.parametrize(
    "cumulative_pct, expected",
    [
        ([0.0, 100.0, 50.0], [0.0, 0.0, -25.0]),
        ([-50.0, -50.0], [-50.0, -50.0]),
        ([0.0, -100.0, -100.0], [0.0, -100.0, -100.0]),
        ([0.0, 10.0, 20.0], [0.0, 0.0, 0.0]),
        ([], []),
    ],
)
def test_chart_drawdown_uses_peak_wealth(cumulative_pct, expected):
    points = [{"time": str(i), "value": value} for i, value in enumerate(cumulative_pct)]
    result = _build_drawdown_from_cumulative_pct(points)
    assert [point["time"] for point in result] == [point["time"] for point in points]
    assert [point["value"] for point in result] == pytest.approx(expected)


def test_strategy_and_benchmark_chart_drawdown_agree():
    values = [100.0, 200.0, 150.0]
    dates = pd.bdate_range("2024-01-01", periods=3)
    benchmark = [
        {"time": date.strftime("%Y-%m-%d"), "value": (value / 100.0 - 1.0) * 100.0}
        for date, value in zip(dates, values)
    ]
    result = {
        "context": SimpleNamespace(
            portfolio=SimpleNamespace(starting_cash=100.0),
            start_date=dates[0], end_date=dates[-1], universe=["A"],
        ),
        "trade_log": [],
        "recorded_values": [
            {"date": date, "total_value": value} for date, value in zip(dates, values)
        ],
        "ohlcv_data": {
            "A": pd.DataFrame(
                {"open": values, "high": values, "low": values, "close": values, "volume": [100] * 3},
                index=dates,
            )
        },
        "chart_index_hs300": benchmark,
        "chart_index_sse": benchmark,
    }
    actual = _compute_chart_data(result)["drawdown_data"]
    assert actual == _build_drawdown_from_cumulative_pct(benchmark)
    assert actual[-1]["value"] == pytest.approx(-25.0)


@pytest.mark.parametrize(
    "returns, tail_probability, expected",
    [
        ([-0.1] + [i / 100 for i in range(1, 40)], 0.05, 0.045),
        ([-0.1, 0.0, 0.1], 0.5, 0.05),
        ([-0.1, -0.1, 0.2], 0.05, 0.1),
        ([0.1, 0.2, 0.3], 0.05, 0.0),
        ([-0.1], 0.05, 0.1),
        ([0.0, 0.0], 0.05, 0.0),
    ],
)
def test_cvar_averages_tail_even_when_quantile_is_nonnegative(returns, tail_probability, expected):
    series = pd.Series(returns)
    actual = conditional_var(series, confidence=tail_probability)
    assert actual == pytest.approx(expected)
    assert scientific_cvar(series, confidence_level=1.0 - tail_probability)["cvar"] == pytest.approx(actual)
