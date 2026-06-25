"""Extended risk analytics for backtest results.

This module is intentionally self-contained so it can operate directly on the
result dictionary returned by :func:`run_backtest` without importing the rest of
``eqlib``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd
from scipy.stats import jarque_bera, kurtosis as scipy_kurtosis, norm, skew as scipy_skew

from eqlib.constants import TRADING_DAYS_PER_YEAR
ReturnInput = Optional[Union[Sequence[float], pd.Series, np.ndarray]]


class RiskRating:
    """Risk classification labels used across the module."""

    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"

    RESILIENT = "RESILIENT"
    VULNERABLE = "VULNERABLE"
    CRITICAL = "CRITICAL"


@dataclass
class RiskReport:
    """Container for aggregated extended risk analytics."""

    extended_metrics: dict[str, Any] = field(default_factory=dict)
    var_95: dict[str, Any] = field(default_factory=dict)
    var_99: dict[str, Any] = field(default_factory=dict)
    cvar_95: dict[str, Any] = field(default_factory=dict)
    cvar_99: dict[str, Any] = field(default_factory=dict)
    tail_risk: dict[str, Any] = field(default_factory=dict)
    stress_test: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Return a compact human-readable summary."""
        metrics = self.extended_metrics
        stress_results = self.stress_test.get("scenarios", [])
        worst_stress = max(stress_results, key=lambda item: item.get("estimated_loss_pct", 0.0), default={})
        return "\n".join(
            [
                "Risk Report",
                f"Risk rating: {metrics.get('risk_rating', RiskRating.MEDIUM_RISK)}",
                f"Sortino/Calmar: {metrics.get('sortino_ratio', 0.0):.2f} / {metrics.get('calmar_ratio', 0.0):.2f}",
                f"VaR 95% / CVaR 95%: {self.var_95.get('var', 0.0):.2%} / {self.cvar_95.get('cvar', 0.0):.2%}",
                f"Worst day / Best day: {metrics.get('worst_day', 0.0):.2%} / {metrics.get('best_day', 0.0):.2%}",
                f"Tail risk: {self.tail_risk.get('tail_risk_rating', 'MEDIUM')} (JB p={self.tail_risk.get('jarque_bera_pvalue', 1.0):.4f})",
                (
                    "Worst stress: "
                    f"{worst_stress.get('name', 'N/A')} {worst_stress.get('estimated_loss_pct', 0.0):.2%} "
                    f"[{worst_stress.get('stress_rating', RiskRating.VULNERABLE)}]"
                ),
            ]
        )


def _extract_daily_returns(backtest_result: Mapping[str, Any]) -> pd.Series:
    """Extract daily return series from backtest result dict."""
    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)
    values = pd.Series(
        {pd.Timestamp(r["date"]): float(r["total_value"]) for r in recorded}
    ).sort_index()
    returns = values.pct_change().dropna()
    return returns.astype(float)


def _clean_returns(returns: ReturnInput) -> pd.Series:
    """Normalize returns input to a clean pandas Series."""
    if returns is None:
        return pd.Series(dtype=float)
    if isinstance(returns, pd.Series):
        series = returns.astype(float)
    else:
        series = pd.Series(list(returns), dtype=float)
    return series.replace([np.inf, -np.inf], np.nan).dropna()


def _annualized_return(returns: pd.Series, trading_days: int = TRADING_DAYS_PER_YEAR) -> float:
    if returns.empty:
        return 0.0
    cumulative = float((1.0 + returns).prod())
    if cumulative <= 0:
        return -1.0
    return cumulative ** (trading_days / len(returns)) - 1.0


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    wealth = (1.0 + returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def _downside_deviation(returns: pd.Series, target_return: float = 0.0, trading_days: int = TRADING_DAYS_PER_YEAR) -> float:
    if returns.empty:
        return 0.0
    downside = np.minimum(returns - target_return, 0.0)
    return float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(trading_days))


def _longest_losing_streak(returns: pd.Series) -> int:
    streak = longest = 0
    for ret in returns:
        if ret < 0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    return int(longest)


def _safe_skewness(returns: pd.Series) -> float:
    if len(returns) < 3:
        return 0.0
    value = float(scipy_skew(returns, bias=False))
    return value if np.isfinite(value) else 0.0


def _safe_kurtosis(returns: pd.Series, *, fisher: bool) -> float:
    if len(returns) < 4:
        return 0.0
    value = float(scipy_kurtosis(returns, fisher=fisher, bias=False))
    return value if np.isfinite(value) else 0.0


def _risk_rating(max_drawdown: float, downside_deviation: float, cvar_95: float) -> str:
    if abs(max_drawdown) >= 0.25 or downside_deviation >= 0.25 or cvar_95 >= 0.04:
        return RiskRating.HIGH_RISK
    if abs(max_drawdown) >= 0.12 or downside_deviation >= 0.15 or cvar_95 >= 0.02:
        return RiskRating.MEDIUM_RISK
    return RiskRating.LOW_RISK


def _stress_rating(loss_pct: float) -> str:
    if loss_pct >= 0.25:
        return RiskRating.CRITICAL
    if loss_pct >= 0.10:
        return RiskRating.VULNERABLE
    return RiskRating.RESILIENT


def _worst_window_returns(returns: pd.Series, window: int) -> np.ndarray:
    if returns.empty:
        return np.zeros(window, dtype=float)
    array = returns.to_numpy(dtype=float)
    window = max(1, int(window))
    if len(array) <= window:
        if len(array) < window:
            array = np.pad(array, (0, window - len(array)), constant_values=0.0)
        return array

    worst_return = np.inf
    worst_slice = array[:window]
    for start in range(len(array) - window + 1):
        sample = array[start:start + window]
        cumulative = float(np.prod(1.0 + sample) - 1.0)
        if cumulative < worst_return:
            worst_return = cumulative
            worst_slice = sample
    return worst_slice


def _current_portfolio_value(backtest_result: Mapping[str, Any]) -> float:
    recorded = backtest_result.get("recorded_values", [])
    if recorded:
        last_value = recorded[-1].get("total_value")
        if last_value is not None:
            return float(last_value)
    context = backtest_result.get("context")
    portfolio = getattr(context, "portfolio", None)
    total_value = getattr(portfolio, "total_value", None)
    if total_value is not None:
        return float(total_value)
    starting_cash = getattr(portfolio, "starting_cash", 0.0)
    return float(starting_cash or 0.0)


def value_at_risk(
    returns: ReturnInput,
    confidence_level: float = 0.95,
    method: str = "historical",
) -> dict[str, Any]:
    """Calculate Value at Risk (VaR).

    Args:
        returns: Daily returns.
        confidence_level: Confidence level such as 0.95 or 0.99.
        method: ``historical``, ``parametric``, or ``cornish_fisher``.

    Returns:
        Dictionary containing VaR, calculation method, and confidence level.
    """
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")

    method = method.lower()
    if method not in {"historical", "parametric", "cornish_fisher"}:
        raise ValueError("method must be 'historical', 'parametric', or 'cornish_fisher'")

    series = _clean_returns(returns)
    if series.empty:
        return {"var": 0.0, "method": method, "confidence_level": confidence_level}

    alpha = 1.0 - confidence_level
    mean = float(series.mean())
    sigma = float(series.std(ddof=1))

    if method == "historical" or sigma == 0.0:
        threshold = float(series.quantile(alpha))
    elif method == "parametric":
        z_score = float(norm.ppf(alpha))
        threshold = mean + sigma * z_score
    else:
        z_score = float(norm.ppf(alpha))
        skewness = _safe_skewness(series)
        excess_kurtosis = _safe_kurtosis(series, fisher=True)
        z_cf = (
            z_score
            + (z_score**2 - 1.0) * skewness / 6.0
            + (z_score**3 - 3.0 * z_score) * excess_kurtosis / 24.0
            - (2.0 * z_score**3 - 5.0 * z_score) * (skewness**2) / 36.0
        )
        threshold = mean + sigma * z_cf

    return {
        "var": max(0.0, float(-threshold)),
        "method": method,
        "confidence_level": confidence_level,
    }


def conditional_var(
    returns: ReturnInput,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Calculate Conditional Value at Risk (CVaR / Expected Shortfall)."""
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")

    series = _clean_returns(returns)
    if series.empty:
        return {"cvar": 0.0, "var": 0.0, "confidence_level": confidence_level}

    alpha = 1.0 - confidence_level
    threshold = float(series.quantile(alpha))
    tail_losses = series[series <= threshold]
    cvar = float(-tail_losses.mean()) if not tail_losses.empty else max(0.0, -threshold)

    return {
        "cvar": max(0.0, cvar),
        "var": max(0.0, float(-threshold)),
        "confidence_level": confidence_level,
    }


def tail_risk_analysis(returns: ReturnInput) -> dict[str, Any]:
    """Compute tail-risk diagnostics for a return stream."""
    series = _clean_returns(returns)
    if series.empty:
        return {
            "skewness": 0.0,
            "excess_kurtosis": 0.0,
            "jarque_bera_stat": 0.0,
            "jarque_bera_pvalue": 1.0,
            "left_tail_ratio": 0.0,
            "max_consecutive_losses": 0,
            "tail_risk_rating": "LOW",
        }

    skewness = _safe_skewness(series)
    excess_kurtosis = _safe_kurtosis(series, fisher=True)
    if len(series) >= 4:
        jb_result = jarque_bera(series)
        jb_stat = float(getattr(jb_result, "statistic", jb_result[0]))
        jb_pvalue = float(getattr(jb_result, "pvalue", jb_result[1]))
    else:
        jb_stat, jb_pvalue = 0.0, 1.0

    sigma = float(series.std(ddof=1))
    expected_left_tail = float(norm.cdf(-2.0))
    if sigma > 0:
        observed_left_tail = float((series < (-2.0 * sigma)).mean())
        left_tail_ratio = observed_left_tail / expected_left_tail if expected_left_tail else 0.0
    else:
        left_tail_ratio = 0.0

    max_losses = _longest_losing_streak(series)
    if left_tail_ratio >= 2.5 or excess_kurtosis >= 3.0 or max_losses >= 7:
        rating = "HIGH"
    elif left_tail_ratio >= 1.5 or excess_kurtosis >= 1.0 or max_losses >= 4:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return {
        "skewness": skewness,
        "excess_kurtosis": excess_kurtosis,
        "jarque_bera_stat": jb_stat,
        "jarque_bera_pvalue": jb_pvalue,
        "left_tail_ratio": float(left_tail_ratio),
        "max_consecutive_losses": max_losses,
        "tail_risk_rating": rating,
    }


def stress_test(
    backtest_result: Mapping[str, Any],
    scenarios: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Estimate portfolio losses under predefined or custom stress scenarios."""
    returns = _extract_daily_returns(backtest_result)
    current_value = _current_portfolio_value(backtest_result)

    if scenarios is None:
        scenarios = (
            {"name": "2008_crisis", "shock_pct": -0.40, "horizon_days": 126, "liquidity_haircut": 0.00},
            {"name": "2015_crash", "shock_pct": -0.30, "horizon_days": 42, "liquidity_haircut": 0.00},
            {"name": "2020_covid", "shock_pct": -0.15, "horizon_days": 21, "liquidity_haircut": 0.00},
            {"name": "liquidity_crisis", "shock_pct": -0.20, "horizon_days": 10, "liquidity_haircut": 0.08},
        )

    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        name = str(scenario.get("name", "scenario"))
        shock_pct = float(scenario.get("shock_pct", 0.0))
        horizon_days = max(1, int(scenario.get("horizon_days", 1)))
        liquidity_haircut = max(0.0, float(scenario.get("liquidity_haircut", 0.0)))

        window_returns = _worst_window_returns(returns, horizon_days)
        daily_shock = (1.0 + shock_pct) ** (1.0 / horizon_days) - 1.0 if shock_pct > -1.0 else -0.999
        stressed_window = (1.0 + window_returns) * (1.0 + daily_shock) - 1.0
        stressed_cumulative = float(np.prod(1.0 + stressed_window) * (1.0 - liquidity_haircut) - 1.0)
        estimated_loss_pct = min(0.99, max(0.0, -stressed_cumulative))
        estimated_loss = current_value * estimated_loss_pct

        results.append(
            {
                "name": name,
                "estimated_loss": float(estimated_loss),
                "estimated_loss_pct": float(estimated_loss_pct),
                "stress_rating": _stress_rating(estimated_loss_pct),
            }
        )

    return {"scenarios": results}


def extended_risk_metrics(
    backtest_result: Mapping[str, Any],
    benchmark_returns: ReturnInput = None,
) -> dict[str, Any]:
    """Compute an extended set of professional-grade risk metrics."""
    returns = _extract_daily_returns(backtest_result)
    _ = benchmark_returns

    if returns.empty:
        return {
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "cvar_99": 0.0,
            "downside_deviation": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "max_consecutive_loss_days": 0,
            "best_day": 0.0,
            "worst_day": 0.0,
            "risk_rating": RiskRating.LOW_RISK,
        }

    annual_return = _annualized_return(returns)
    max_drawdown = _max_drawdown(returns)
    downside_deviation = _downside_deviation(returns)
    annualized_mean = float(returns.mean() * TRADING_DAYS_PER_YEAR)
    sortino_ratio = annualized_mean / downside_deviation if downside_deviation > 0 else 0.0
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

    var_95 = value_at_risk(returns, confidence_level=0.95)
    var_99 = value_at_risk(returns, confidence_level=0.99)
    cvar_95 = conditional_var(returns, confidence_level=0.95)
    cvar_99 = conditional_var(returns, confidence_level=0.99)

    return {
        "sortino_ratio": float(sortino_ratio),
        "calmar_ratio": float(calmar_ratio),
        "var_95": float(var_95["var"]),
        "var_99": float(var_99["var"]),
        "cvar_95": float(cvar_95["cvar"]),
        "cvar_99": float(cvar_99["cvar"]),
        "downside_deviation": float(downside_deviation),
        "skewness": _safe_skewness(returns),
        "kurtosis": _safe_kurtosis(returns, fisher=False),
        "max_consecutive_loss_days": _longest_losing_streak(returns),
        "best_day": float(returns.max()),
        "worst_day": float(returns.min()),
        "risk_rating": _risk_rating(max_drawdown, downside_deviation, float(cvar_95["cvar"])),
    }


__all__ = [
    "RiskRating",
    "RiskReport",
    "conditional_var",
    "extended_risk_metrics",
    "stress_test",
    "tail_risk_analysis",
    "value_at_risk",
]
