"""Statistical and mathematical utilities for quantitative analysis.

Provides:
- Rolling statistics: rolling_corr, rolling_beta, rolling_sharpe
- Distributions: zscore, percentile_rank
- Regression: linear_regression
- Risk: downside_deviation, value_at_risk, conditional_var
- Math: fibonacci, factorial, combinations, permutations
- Series: drawdown, max_drawdown, consecutive_wins, consecutive_losses
"""

import numpy as np
import pandas as pd
from math import sqrt, factorial
from typing import Optional

from eqlib.constants import TRADING_DAYS_PER_YEAR


# ============================================================
# Rolling Statistics
# ============================================================


def rolling_corr(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    """Rolling correlation between two series."""
    return x.rolling(window).corr(y)


def rolling_beta(
    series: pd.Series, benchmark: pd.Series, window: int, risk_free: float = 0.0
) -> pd.Series:
    """Rolling beta against a benchmark."""
    cov = series.rolling(window).cov(benchmark)
    var = benchmark.rolling(window).var()
    return cov / var.replace(0, np.nan)


def rolling_sharpe(
    returns: pd.Series,
    window: int,
    risk_free: float = 0.0,
    annualize: int = TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """Rolling annualized Sharpe ratio."""
    # mean * annualize = annualized return (daily mean scaled to yearly)
    mean = returns.rolling(window).mean() * annualize
    std = returns.rolling(window).std() * np.sqrt(annualize)
    return (mean - risk_free) / std.replace(0, np.nan)


# ============================================================
# Distributions
# ============================================================


def zscore(series: pd.Series, window: Optional[int] = None) -> pd.Series:
    """Z-score normalization.

    Parameters:
        series: input data
        window: if set, use rolling mean/std; otherwise use full series
    """
    if window:
        mu = series.rolling(window).mean()
        sigma = series.rolling(window).std()
    else:
        mu = series.mean()
        sigma = series.std()
    return (series - mu) / sigma.replace(0, np.nan)


def percentile_rank(series: pd.Series, window: Optional[int] = None) -> pd.Series:
    """Percentile rank within rolling window or full series.

    Returns values 0-100 indicating the percentile position.
    """
    if window:
        return series.rolling(window).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=True
        )
    return series.rank(pct=True) * 100


# ============================================================
# Linear Regression
# ============================================================


def linear_regression(x: pd.Series, y: pd.Series):
    """Simple linear regression: y = alpha + beta * x.

    Returns:
        dict: alpha, beta, r_squared, t_stat, residuals
    """
    x_arr = x.values
    y_arr = y.values

    n = len(x_arr)
    if n < 2:
        return None

    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)

    ss_xx = np.sum((x_arr - x_mean) ** 2)
    ss_yy = np.sum((y_arr - y_mean) ** 2)
    ss_xy = np.sum((x_arr - x_mean) * (y_arr - y_mean))

    if ss_xx < 1e-15:
        return None

    beta = ss_xy / ss_xx
    alpha = y_mean - beta * x_mean

    y_pred = alpha + beta * x_arr
    residuals = y_arr - y_pred

    ss_res = np.sum(residuals**2)
    r_squared = 1 - ss_res / ss_yy if ss_yy > 0 else 0

    # Standard error
    se = sqrt(ss_res / (n - 2)) if n > 2 else float("inf")
    se_beta = se / sqrt(ss_xx) if ss_xx > 0 else float("inf")
    t_stat = beta / se_beta if se_beta > 0 else 0

    return {
        "alpha": alpha,
        "beta": beta,
        "r_squared": r_squared,
        "t_stat": t_stat,
        "residuals": pd.Series(residuals, index=x.index),
    }


# ============================================================
# Risk Metrics
# ============================================================


def downside_deviation(
    returns: pd.Series, target: float = 0.0, annualize: int = TRADING_DAYS_PER_YEAR
) -> float:
    """Downside deviation (semi-standard deviation).

    Computes ``sqrt(mean(min(r - target, 0)^2)) * sqrt(annualize)``, the
    square root of the mean squared deviation below the target return.

    Parameters:
        returns: series of periodic (e.g. daily) returns
        target: minimum acceptable return per period (default 0.0).
            For the Sortino ratio, pass the risk-free rate expressed in the
            same frequency as ``returns`` (e.g. ``0.03 / 244`` for daily).
        annualize: number of periods per year for annualization (default 244)
    """
    values = _validated_returns(returns)
    downside = np.minimum(values.to_numpy() - target, 0.0)
    return float(np.sqrt(np.mean(downside**2)) * sqrt(annualize))


def value_at_risk(
    returns: pd.Series, confidence: float = 0.05, method: str = "historical"
) -> float:
    """Value at Risk at a given confidence level.

    Parameters:
        returns: return series
        confidence: tail probability (default 5%)
        method: one of 'historical', 'parametric', 'cornish_fisher'.

            - 'historical': empirical quantile of the return series.
            - 'parametric': normal-distribution quantile (underestimates
              fat tails).
            - 'cornish_fisher': parametric VaR adjusted for sample skew
              and excess kurtosis. Better suited for A-share returns,
              which are typically negatively skewed and heavy-tailed.

    Returns:
        VaR as a nonnegative loss.
    """
    _validate_confidence(confidence)
    loss_quantile = _quantile_by_method(_validated_returns(returns), confidence, method)
    return float(max(0.0, -loss_quantile))


def conditional_var(returns: pd.Series, confidence: float = 0.05) -> float:
    """Conditional Value at Risk (Expected Shortfall)."""
    _validate_confidence(confidence)
    values = _validated_returns(returns)
    loss_quantile = _quantile_by_method(values, confidence, "historical")
    if loss_quantile >= 0:
        return 0.0
    tail = values[values <= loss_quantile]
    return float(max(0.0, -tail.mean())) if len(tail) > 0 else 0.0


def _validated_returns(returns: pd.Series) -> pd.Series:
    """Convert returns to finite numeric observations or fail visibly."""
    values = pd.to_numeric(returns, errors="coerce").dropna()
    if values.empty or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("returns must contain finite observations")
    return values.astype(float)


def _validate_confidence(confidence: float) -> None:
    """Validate the lower-tail probability shared by VaR and CVaR."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")


def _quantile_by_method(values: pd.Series, confidence: float, method: str) -> float:
    """Return the return-space lower-tail quantile for one supported method."""
    if method == "historical":
        return float(values.quantile(confidence))
    from scipy.stats import norm

    mu = float(values.mean())
    sigma = float(values.std(ddof=1))
    if not np.isfinite(sigma):
        raise ValueError("returns must contain at least two finite observations")
    if method == "parametric":
        return float(mu + norm.ppf(confidence) * sigma)
    if method == "cornish_fisher":
        skew = float(values.skew())
        kurt = float(values.kurtosis())  # Fisher kurtosis (excess)
        z = norm.ppf(confidence)
        z_cf = (
            z
            + (z**2 - 1) * skew / 6
            + (z**3 - 3 * z) * kurt / 24
            - (2 * z**3 - 5 * z) * skew**2 / 36
        )
        return float(mu + z_cf * sigma)
    raise ValueError(f"unsupported VaR method: {method}")


# ============================================================
# Drawdown Analysis
# ============================================================


def drawdown(equity: pd.Series) -> pd.Series:
    """Drawdown series from an equity curve."""
    peak = equity.cummax()
    return (equity - peak) / peak.replace(0, np.nan)


def max_drawdown(equity: pd.Series):
    """Calculate max drawdown and its start/end dates.

    Returns:
        tuple: (max_dd, start_date, end_date)
    """
    dd = drawdown(equity)
    idx_min = dd.idxmin()
    dd_val = dd.loc[idx_min]
    idx_max = equity[:idx_min].idxmax()
    return dd_val, idx_max, idx_min


# ============================================================
# Win/Loss Streaks
# ============================================================


def consecutive_wins(returns: pd.Series) -> pd.Series:
    """Count consecutive winning days up to each point.

    Uses a vectorized implementation: group returns into contiguous win/non-win
    blocks and compute the cumulative count within each block.
    """
    is_win = (returns > 0).astype(int)
    # New group starts whenever the win flag changes
    group = (is_win != is_win.shift(1)).cumsum()
    return is_win.groupby(group).cumsum()


def consecutive_losses(returns: pd.Series) -> pd.Series:
    """Count consecutive losing days up to each point.

    Uses a vectorized implementation: group returns into contiguous loss/non-loss
    blocks and compute the cumulative count within each block.
    """
    is_loss = (returns < 0).astype(int)
    # New group starts whenever the loss flag changes
    group = (is_loss != is_loss.shift(1)).cumsum()
    return is_loss.groupby(group).cumsum()


# ============================================================
# Math Utilities
# ============================================================


def fibonacci(n: int) -> list[int]:
    """Generate first n Fibonacci numbers."""
    if n <= 0:
        return []
    if n == 1:
        return [1]
    seq = [1, 1]
    for _ in range(n - 2):
        seq.append(seq[-1] + seq[-2])
    return seq


def comb(n: int, k: int) -> int:
    """Number of combinations: C(n, k)."""
    if k < 0 or k > n:
        return 0
    return factorial(n) // (factorial(k) * factorial(n - k))


def perm(n: int, k: int) -> int:
    """Number of permutations: P(n, k)."""
    if k < 0 or k > n:
        return 0
    return factorial(n) // factorial(n - k)


def compound_return(returns: pd.Series) -> float:
    """Calculate compound (cumulative) return from a return series."""
    return float((1 + returns).prod() - 1)


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound Annual Growth Rate."""
    if years <= 0 or start_value <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def log_return(prices: pd.Series) -> pd.Series:
    """Convert price series to log returns."""
    return np.log(prices / prices.shift(1))
