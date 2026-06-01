from __future__ import annotations

"""Statistical confidence tools for evaluating backtest robustness.

This module quantifies how reliable a backtest appears under resampling,
Monte-Carlo permutation, hypothesis testing, and basic sample-size checks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS_PER_YEAR = 252
DEFAULT_BOOTSTRAP_METRICS = [
    "sharpe_ratio",
    "annual_return",
    "max_drawdown",
    "sortino_ratio",
]


@dataclass(frozen=True)
class MetricCI:
    """Confidence interval summary for a single metric."""

    point_estimate: float
    ci_lower: float
    ci_upper: float
    std_error: float
    ci_width_pct: float


@dataclass(frozen=True)
class BootstrapResult:
    """Bootstrap confidence intervals for backtest metrics."""

    metrics: Dict[str, MetricCI]
    n_bootstrap: int
    confidence_level: float


@dataclass(frozen=True)
class MonteCarloResult:
    """Distributional summary from Monte-Carlo return-path simulations."""

    sharpe_distribution: list[float]
    return_distribution: list[float]
    p_value_vs_random: float
    mean_sharpe: float
    std_sharpe: float
    median_sharpe: float
    percentile_5: float
    percentile_95: float


@dataclass(frozen=True)
class SignificanceResult:
    """Hypothesis-test output for strategy returns."""

    test_type: str
    statistic: float
    p_value: float
    is_significant: bool
    mean_return: float
    mean_benchmark: Optional[float]
    conclusion: str


@dataclass(frozen=True)
class SampleSizeResult:
    """Assessment of whether the backtest sample is large enough."""

    trade_count: Optional[int]
    time_span_years: Optional[float]
    daily_observations: int
    is_sufficient: bool
    warnings: list[str]
    recommended_min_trades: int
    recommended_min_years: float
    assessment: str


class ConfidenceLevel:
    """Canonical confidence level labels for validation reports."""

    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class ConfidenceReport:
    """Aggregate report spanning all statistical confidence checks."""

    bootstrap_result: Optional[BootstrapResult] = None
    monte_carlo_result: Optional[MonteCarloResult] = None
    significance_result: Optional[SignificanceResult] = None
    sample_size_result: Optional[SampleSizeResult] = None
    confidence_level: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def inferred_confidence_level(self) -> str:
        """Infer an overall confidence label from the available evidence."""
        if self.confidence_level:
            return self.confidence_level

        if self.sample_size_result and self.sample_size_result.assessment == "INSUFFICIENT":
            return ConfidenceLevel.INSUFFICIENT_DATA

        positive_signals = 0
        if self.significance_result and self.significance_result.is_significant:
            positive_signals += 1
        if self.monte_carlo_result and self.monte_carlo_result.p_value_vs_random <= 0.05:
            positive_signals += 1

        sharpe_ci = None
        if self.bootstrap_result is not None:
            sharpe_ci = self.bootstrap_result.metrics.get("sharpe_ratio")
        if sharpe_ci is not None and np.isfinite(sharpe_ci.ci_lower) and sharpe_ci.ci_lower > 0:
            positive_signals += 1

        if self.sample_size_result and self.sample_size_result.assessment == "SUFFICIENT":
            if positive_signals >= 3:
                return ConfidenceLevel.HIGH_CONFIDENCE
            if positive_signals >= 1:
                return ConfidenceLevel.MEDIUM_CONFIDENCE
            return ConfidenceLevel.LOW_CONFIDENCE

        if positive_signals >= 2:
            return ConfidenceLevel.MEDIUM_CONFIDENCE
        return ConfidenceLevel.LOW_CONFIDENCE

    def summary(self) -> str:
        """Return a human-readable summary sentence."""
        level = self.inferred_confidence_level()
        parts = [f"Overall confidence: {level}"]

        if self.sample_size_result is not None:
            parts.append(f"sample size assessment: {self.sample_size_result.assessment}")
        if self.significance_result is not None:
            parts.append(
                f"p-value={self.significance_result.p_value:.4f} ({'significant' if self.significance_result.is_significant else 'not significant'})"
            )
        if self.monte_carlo_result is not None:
            parts.append(f"Monte Carlo p-value={self.monte_carlo_result.p_value_vs_random:.4f}")

        sharpe_ci = None
        if self.bootstrap_result is not None:
            sharpe_ci = self.bootstrap_result.metrics.get("sharpe_ratio")
        if sharpe_ci is not None:
            parts.append(f"Sharpe CI=[{sharpe_ci.ci_lower:.3f}, {sharpe_ci.ci_upper:.3f}]")

        if self.notes:
            parts.append("notes=" + "; ".join(self.notes))
        return "; ".join(parts)


def _extract_daily_returns(backtest_result: Mapping[str, Any]) -> pd.Series:
    """Extract daily percentage returns from a run_backtest result."""
    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)
    values = pd.Series({r["date"]: r["total_value"] for r in recorded}).sort_index()
    returns = values.pct_change().dropna()
    return returns


def _as_returns_series(returns: Optional[Sequence[float] | pd.Series]) -> pd.Series:
    """Normalize array-like daily returns into a clean pandas Series."""
    if returns is None:
        return pd.Series(dtype=float)
    if isinstance(returns, pd.Series):
        series = returns.astype(float)
    else:
        series = pd.Series(list(returns), dtype=float)
    return series.replace([np.inf, -np.inf], np.nan).dropna()


def _metric_sharpe_ratio(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    std = float(returns.std(ddof=1))
    if not np.isfinite(std) or np.isclose(std, 0.0):
        return 0.0
    return float((returns.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _metric_annual_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    total_return = float((1.0 + returns).prod() - 1.0)
    growth = 1.0 + total_return
    if growth <= 0:
        return -1.0
    return float(growth ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0)


def _metric_max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    cumulative = (1.0 + returns).cumprod()
    drawdowns = cumulative / cumulative.cummax() - 1.0
    return float(abs(drawdowns.min()))


def _metric_sortino_ratio(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    downside = np.minimum(returns.to_numpy(dtype=float), 0.0)
    downside_std = float(np.sqrt(np.mean(np.square(downside))))
    if not np.isfinite(downside_std) or np.isclose(downside_std, 0.0):
        return 0.0
    return float((returns.mean() / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR))


_METRIC_FUNCTIONS = {
    "sharpe_ratio": _metric_sharpe_ratio,
    "annual_return": _metric_annual_return,
    "max_drawdown": _metric_max_drawdown,
    "sortino_ratio": _metric_sortino_ratio,
}


def _compute_metric(metric_name: str, returns: pd.Series) -> float:
    """Compute a supported metric from daily return observations."""
    if metric_name not in _METRIC_FUNCTIONS:
        raise ValueError(f"Unsupported metric: {metric_name}")
    return _METRIC_FUNCTIONS[metric_name](returns)


def _bootstrap_sample(returns: pd.Series, rng: np.random.Generator) -> pd.Series:
    values = returns.to_numpy(dtype=float)
    sample = rng.choice(values, size=len(values), replace=True)
    return pd.Series(sample, dtype=float)


def _distribution_summary(values: Iterable[float]) -> tuple[float, float, float, float, float]:
    data = np.asarray(list(values), dtype=float)
    if data.size == 0:
        nan = float("nan")
        return nan, nan, nan, nan, nan
    return (
        float(np.mean(data)),
        float(np.std(data, ddof=1)) if data.size > 1 else 0.0,
        float(np.median(data)),
        float(np.percentile(data, 5)),
        float(np.percentile(data, 95)),
    )


def bootstrap_metrics(
    backtest_result: Mapping[str, Any],
    n_bootstrap: int = 1000,
    metrics: Optional[Sequence[str]] = None,
    confidence_level: float = 0.95,
) -> BootstrapResult:
    """Estimate confidence intervals for core backtest metrics via bootstrap.

    Parameters
    ----------
    backtest_result:
        Result dictionary returned by :func:`run_backtest`.
    n_bootstrap:
        Number of bootstrap resamples.
    metrics:
        Metric names to evaluate. Defaults to Sharpe, annual return,
        max drawdown, and Sortino ratio.
    confidence_level:
        Central confidence level for percentile intervals.
    """
    returns = _extract_daily_returns(backtest_result)
    metric_names = list(metrics or DEFAULT_BOOTSTRAP_METRICS)
    alpha = (1.0 - confidence_level) / 2.0
    rng = np.random.default_rng()

    results: Dict[str, MetricCI] = {}
    for metric_name in metric_names:
        point_estimate = _compute_metric(metric_name, returns)
        samples: list[float] = []
        if not returns.empty:
            for _ in range(max(int(n_bootstrap), 0)):
                samples.append(_compute_metric(metric_name, _bootstrap_sample(returns, rng)))

        sample_array = np.asarray(samples, dtype=float)
        if sample_array.size == 0:
            ci_lower = ci_upper = std_error = ci_width_pct = float("nan")
        else:
            ci_lower = float(np.quantile(sample_array, alpha))
            ci_upper = float(np.quantile(sample_array, 1.0 - alpha))
            std_error = float(np.std(sample_array, ddof=1)) if sample_array.size > 1 else 0.0
            if np.isfinite(point_estimate) and not np.isclose(point_estimate, 0.0):
                ci_width_pct = float(abs(ci_upper - ci_lower) / abs(point_estimate) * 100.0)
            else:
                ci_width_pct = float("nan")

        results[metric_name] = MetricCI(
            point_estimate=float(point_estimate),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            std_error=std_error,
            ci_width_pct=ci_width_pct,
        )

    return BootstrapResult(
        metrics=results,
        n_bootstrap=int(n_bootstrap),
        confidence_level=float(confidence_level),
    )


def _apply_param_perturbation(
    returns: np.ndarray,
    rng: np.random.Generator,
    param_ranges: Optional[Mapping[str, Sequence[float]]],
) -> np.ndarray:
    """Lightly perturb mean/volatility when Monte-Carlo parameter randomization is requested."""
    if not param_ranges:
        return returns

    perturbed = returns.astype(float, copy=True)
    drift_low, drift_high = param_ranges.get("drift_multiplier", (1.0, 1.0))
    vol_low, vol_high = param_ranges.get("volatility_multiplier", (1.0, 1.0))

    drift_scale = float(rng.uniform(float(drift_low), float(drift_high)))
    vol_scale = float(rng.uniform(float(vol_low), float(vol_high)))

    mean = float(np.mean(perturbed))
    centered = perturbed - mean
    return mean * drift_scale + centered * vol_scale


def monte_carlo_simulation(
    backtest_result: Mapping[str, Any],
    n_simulations: int = 500,
    random_start_dates: bool = False,
    random_params: bool = False,
    param_ranges: Optional[Mapping[str, Sequence[float]]] = None,
) -> MonteCarloResult:
    """Generate synthetic return paths and compare observed Sharpe to random outcomes."""
    returns = _extract_daily_returns(backtest_result)
    observed_sharpe = _metric_sharpe_ratio(returns)
    rng = np.random.default_rng()

    sharpe_distribution: list[float] = []
    return_distribution: list[float] = []
    base = returns.to_numpy(dtype=float)

    for _ in range(max(int(n_simulations), 0)):
        if base.size == 0:
            simulated = np.asarray([], dtype=float)
        else:
            working = base.copy()
            if random_start_dates and working.size > 1:
                working = np.roll(working, int(rng.integers(0, working.size)))
            simulated = rng.choice(working, size=len(working), replace=True)
            if random_params:
                simulated = _apply_param_perturbation(simulated, rng, param_ranges)

        sim_returns = pd.Series(simulated, dtype=float)
        sharpe_distribution.append(_metric_sharpe_ratio(sim_returns))
        return_distribution.append(float((1.0 + sim_returns).prod() - 1.0) if not sim_returns.empty else float("nan"))

    mean_sharpe, std_sharpe, median_sharpe, percentile_5, percentile_95 = _distribution_summary(
        sharpe_distribution
    )

    sharpe_array = np.asarray(sharpe_distribution, dtype=float)
    valid = sharpe_array[np.isfinite(sharpe_array)]
    if valid.size == 0 or not np.isfinite(observed_sharpe):
        p_value_vs_random = float("nan")
    else:
        p_value_vs_random = float(np.mean(valid >= observed_sharpe))

    return MonteCarloResult(
        sharpe_distribution=sharpe_distribution,
        return_distribution=return_distribution,
        p_value_vs_random=p_value_vs_random,
        mean_sharpe=mean_sharpe,
        std_sharpe=std_sharpe,
        median_sharpe=median_sharpe,
        percentile_5=percentile_5,
        percentile_95=percentile_95,
    )


def significance_test(
    strategy_returns: Sequence[float] | pd.Series,
    benchmark_returns: Optional[Sequence[float] | pd.Series] = None,
    test_type: str = "t-test",
) -> SignificanceResult:
    """Test whether strategy returns or excess returns differ from zero."""
    strategy = _as_returns_series(strategy_returns)
    benchmark = _as_returns_series(benchmark_returns)

    if benchmark_returns is not None:
        aligned = pd.concat([strategy.rename("strategy"), benchmark.rename("benchmark")], axis=1).dropna()
        observed = aligned["strategy"] - aligned["benchmark"]
        mean_benchmark = float(aligned["benchmark"].mean()) if not aligned.empty else float("nan")
        subject = "Excess returns versus benchmark"
        mean_return = float(aligned["strategy"].mean()) if not aligned.empty else float("nan")
    else:
        observed = strategy
        mean_benchmark = None
        subject = "Strategy returns"
        mean_return = float(strategy.mean()) if not strategy.empty else float("nan")

    observed = observed.replace([np.inf, -np.inf], np.nan).dropna()
    if observed.empty:
        statistic = float("nan")
        p_value = float("nan")
    elif test_type == "t-test":
        statistic, p_value = stats.ttest_1samp(observed, popmean=0.0, nan_policy="omit")
        statistic = float(statistic)
        p_value = float(p_value)
    elif test_type == "wilcoxon":
        if np.allclose(observed.to_numpy(dtype=float), 0.0):
            statistic = 0.0
            p_value = 1.0
        else:
            statistic, p_value = stats.wilcoxon(observed)
            statistic = float(statistic)
            p_value = float(p_value)
    else:
        raise ValueError("test_type must be 't-test' or 'wilcoxon'")

    is_significant = bool(np.isfinite(p_value) and p_value < 0.05)
    if np.isfinite(p_value):
        significance_text = "statistically significant" if is_significant else "not statistically significant"
        conclusion = f"{subject} are {significance_text} under {test_type} (p={p_value:.4f})."
    else:
        conclusion = f"{subject} could not be evaluated under {test_type} because the sample is empty."

    return SignificanceResult(
        test_type=test_type,
        statistic=statistic,
        p_value=p_value,
        is_significant=is_significant,
        mean_return=mean_return,
        mean_benchmark=mean_benchmark,
        conclusion=conclusion,
    )


def _infer_trade_count(backtest_result: Mapping[str, Any]) -> Optional[int]:
    trade_log = backtest_result.get("trade_log")
    return len(trade_log) if isinstance(trade_log, list) else None


def _infer_time_span_years(backtest_result: Mapping[str, Any]) -> Optional[float]:
    recorded = backtest_result.get("recorded_values", [])
    if len(recorded) < 2:
        return None
    dates = pd.to_datetime([row.get("date") for row in recorded], errors="coerce")
    dates = dates[~pd.isna(dates)]
    if len(dates) < 2:
        return None
    span_days = (dates.max() - dates.min()).days
    return float(span_days / 365.25) if span_days >= 0 else None


def sample_size_assessment(
    trade_count: Optional[int] = None,
    time_span_years: Optional[float] = None,
    target_sharpe: float = 1.0,
    backtest_result: Optional[Mapping[str, Any]] = None,
) -> SampleSizeResult:
    """Assess whether a backtest has enough observations for robust conclusions."""
    returns = _extract_daily_returns(backtest_result or {}) if backtest_result is not None else pd.Series(dtype=float)
    daily_observations = int(len(returns))

    if backtest_result is not None:
        if trade_count is None:
            trade_count = _infer_trade_count(backtest_result)
        if time_span_years is None:
            time_span_years = _infer_time_span_years(backtest_result)
        if time_span_years is None and daily_observations > 0:
            time_span_years = float(daily_observations / TRADING_DAYS_PER_YEAR)

    warnings: list[str] = []
    recommended_min_trades = 30
    recommended_min_years = 2.0
    recommended_daily_observations = TRADING_DAYS_PER_YEAR * 2

    if trade_count is None:
        warnings.append("Trade count is unavailable; win-rate reliability cannot be assessed.")
    elif trade_count < recommended_min_trades:
        warnings.append(
            f"Only {trade_count} trades observed; at least {recommended_min_trades} trades are recommended for a meaningful win-rate estimate."
        )

    if time_span_years is None:
        warnings.append("Backtest time span is unavailable; Sharpe reliability cannot be assessed.")
    elif time_span_years < recommended_min_years:
        warnings.append(
            f"Time span is {time_span_years:.2f} years; at least {recommended_min_years:.1f} years are recommended for Sharpe reliability around a target Sharpe of {target_sharpe:.2f}."
        )

    if daily_observations < recommended_daily_observations:
        warnings.append(
            f"Only {daily_observations} daily observations available; at least {recommended_daily_observations} are recommended for annualized metrics."
        )

    if not warnings:
        assessment = "SUFFICIENT"
    elif len(warnings) == 1:
        assessment = "MARGINAL"
    else:
        assessment = "INSUFFICIENT"

    return SampleSizeResult(
        trade_count=trade_count,
        time_span_years=time_span_years,
        daily_observations=daily_observations,
        is_sufficient=assessment == "SUFFICIENT",
        warnings=warnings,
        recommended_min_trades=recommended_min_trades,
        recommended_min_years=recommended_min_years,
        assessment=assessment,
    )


__all__ = [
    "BootstrapResult",
    "ConfidenceLevel",
    "ConfidenceReport",
    "MetricCI",
    "MonteCarloResult",
    "SampleSizeResult",
    "SignificanceResult",
    "bootstrap_metrics",
    "monte_carlo_simulation",
    "sample_size_assessment",
    "significance_test",
    "_extract_daily_returns",
]
