"""Overfitting detection helpers for backtest results.

This module provides lightweight, self-contained overfitting diagnostics for
EasyQuant backtests.  It intentionally avoids importing from ``eqlib`` at the
module level so it can be imported in isolation.  When an ``initialize_func``
is passed to :func:`walk_forward_analysis`, ``run_backtest`` is imported lazily
inside the function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

__all__ = [
    "OverfittingWarning",
    "WalkForwardResult",
    "SensitivityResult",
    "OOSResult",
    "OverfittingReport",
    "walk_forward_analysis",
    "parameter_sensitivity",
    "out_of_sample_test",
]


class OverfittingWarning:
    """Warning levels for out-of-sample performance decay."""

    HIGH_OVERFITTING = "样本外Sharpe衰减 > 50%"
    MEDIUM_OVERFITTING = "样本外Sharpe衰减 30-50%"
    LOW_OVERFITTING = "样本外Sharpe衰减 < 30%"
    STABLE = "样本外Sharpe衰减 < 10%"


@dataclass
class WalkForwardResult:
    """Summary of simplified walk-forward degradation analysis."""

    windows: list[dict[str, Any]]
    is_sharpe_decay: bool
    oos_is_ratio: float


@dataclass
class SensitivityResult:
    """Proxy parameter sensitivity based on rolling metric stability."""

    rolling_sharpe_std: float
    rolling_sharpe_cv: float
    is_stable: bool
    stability_score: float
    sensitivity_rating: str


@dataclass
class OOSResult:
    """Train/test comparison for out-of-sample validation."""

    train_sharpe: float
    test_sharpe: float
    train_return: float
    test_return: float
    train_max_dd: float
    test_max_dd: float
    sharpe_decay_pct: float
    overfitting_warning: str


@dataclass
class OverfittingReport:
    """Aggregated overfitting diagnostics report."""

    walk_forward: WalkForwardResult
    sensitivity: SensitivityResult
    out_of_sample: OOSResult

    def summary(self) -> str:
        """Return a compact human-readable summary."""
        return (
            f"Walk-forward OOS/IS Sharpe={self.walk_forward.oos_is_ratio:.2f}; "
            f"sensitivity={self.sensitivity.sensitivity_rating} "
            f"(score={self.sensitivity.stability_score:.1f}); "
            f"OOS={self.out_of_sample.overfitting_warning}"
        )


def _extract_daily_returns(backtest_result):
    import pandas as pd
    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)
    values = pd.Series(
        {r["date"]: r["total_value"] for r in recorded}
    ).sort_index()
    returns = values.pct_change().dropna()
    return returns


def _compute_sharpe(returns, risk_free_rate=0.0):
    std = returns.std()
    if len(returns) < 2 or std <= 1e-12:
        return 0.0
    excess = returns - risk_free_rate / 252
    return float(excess.mean() / std * (252 ** 0.5))


def _compute_max_drawdown(returns):
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def _compute_annual_return(returns):
    if len(returns) == 0:
        return 0.0
    total = (1 + returns).prod()
    n_years = len(returns) / 252
    if n_years <= 0:
        return 0.0
    return float(total ** (1 / n_years) - 1)


def _parse_window_to_days(window: str) -> int:
    """Parse ``2Y``/``6M`` style windows into approximate days."""
    if not window:
        return 0
    units = {"D": 1, "W": 7, "M": 30, "Y": 365}
    window = window.strip().upper()
    try:
        return int(float(window[:-1]) * units[window[-1]])
    except (KeyError, ValueError, IndexError):
        return 0


def _coerce_backtest_result(
    initialize_or_result: Any,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Accept either a backtest result dict or an initialize function."""
    if isinstance(initialize_or_result, dict):
        return initialize_or_result
    if callable(initialize_or_result):
        from eqlib.engine import run_backtest

        return run_backtest(
            initialize_or_result,
            start_date=start_date,
            end_date=end_date,
        )
    raise TypeError(
        "initialize_func must be a backtest result dict or a callable initialize function"
    )


def _slice_backtest_result(
    backtest_result: dict[str, Any],
    start: int,
    end: int,
) -> dict[str, Any]:
    """Return a shallow result slice using a subset of recorded values."""
    recorded = list(backtest_result.get("recorded_values", []))[start:end]
    return {
        "recorded_values": recorded,
        "trade_log": list(backtest_result.get("trade_log", [])),
    }


def _compute_metrics(backtest_result: dict[str, Any]) -> dict[str, float]:
    """Compute basic return diagnostics for a backtest result."""
    returns = _extract_daily_returns(backtest_result)
    if returns.empty:
        return {"sharpe": 0.0, "annual_return": 0.0, "max_drawdown": 0.0}
    return {
        "sharpe": _compute_sharpe(returns),
        "annual_return": _compute_annual_return(returns),
        "max_drawdown": _compute_max_drawdown(returns),
    }


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return a finite ratio for potentially zero denominators."""
    if abs(denominator) < 1e-12:
        return 0.0 if abs(numerator) < 1e-12 else float(np.sign(numerator))
    return float(numerator / denominator)


def _compute_decay_pct(train_value: float, test_value: float) -> float:
    """Compute percentage decay using train value as the baseline."""
    baseline = abs(train_value)
    if baseline < 1e-12:
        return 0.0 if test_value >= train_value else 100.0
    return float((train_value - test_value) / baseline * 100.0)


def _warning_from_decay(decay_pct: float) -> str:
    """Map Sharpe decay to a warning label."""
    if decay_pct < 10:
        return OverfittingWarning.STABLE
    if decay_pct < 30:
        return OverfittingWarning.LOW_OVERFITTING
    if decay_pct <= 50:
        return OverfittingWarning.MEDIUM_OVERFITTING
    return OverfittingWarning.HIGH_OVERFITTING


def walk_forward_analysis(
    initialize_func: Any,
    param_ranges: Optional[dict[str, Any]],
    train_window: str = "2Y",
    test_window: str = "6M",
    step: str = "6M",
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31",
) -> WalkForwardResult:
    """Run a simplified walk-forward style overfitting analysis.

    Parameters
    ----------
    initialize_func:
        Either a backtest result dict or an EasyQuant ``initialize`` function.
        When a callable is passed, the backtest is executed once across the full
        date range and then split into in-sample / out-of-sample segments.
    param_ranges:
        Reserved for API compatibility with richer walk-forward optimizers.
        The simplified implementation stores it in window metadata only.
    train_window, test_window, step:
        ``2Y``/``6M`` style settings.  The train/test ratio is approximated from
        ``train_window`` and ``test_window``.  ``step`` is kept for metadata.
    start_date, end_date:
        Backtest date range used only when ``initialize_func`` is callable.

    Returns
    -------
    WalkForwardResult
        One-window proxy walk-forward result comparing IS and OOS performance.
    """
    backtest_result = _coerce_backtest_result(initialize_func, start_date, end_date)
    recorded = list(backtest_result.get("recorded_values", []))
    if len(recorded) < 4:
        return WalkForwardResult(windows=[], is_sharpe_decay=False, oos_is_ratio=0.0)

    train_days = _parse_window_to_days(train_window)
    test_days = _parse_window_to_days(test_window)
    total_days = train_days + test_days
    train_pct = train_days / total_days if total_days > 0 else 0.5
    split_idx = min(max(int(len(recorded) * train_pct), 2), len(recorded) - 2)

    train_result = _slice_backtest_result(backtest_result, 0, split_idx)
    test_result = _slice_backtest_result(backtest_result, split_idx, len(recorded))
    train_metrics = _compute_metrics(train_result)
    test_metrics = _compute_metrics(test_result)

    is_sharpe = train_metrics["sharpe"]
    oos_sharpe = test_metrics["sharpe"]
    ratio = _safe_ratio(oos_sharpe, is_sharpe)

    window = {
        "train_start": recorded[0]["date"],
        "train_end": recorded[split_idx - 1]["date"],
        "test_start": recorded[split_idx]["date"],
        "test_end": recorded[-1]["date"],
        "train_window": train_window,
        "test_window": test_window,
        "step": step,
        "param_ranges": param_ranges or {},
        "is_metrics": train_metrics,
        "oos_metrics": test_metrics,
    }
    return WalkForwardResult(
        windows=[window],
        is_sharpe_decay=oos_sharpe < is_sharpe,
        oos_is_ratio=ratio,
    )


def parameter_sensitivity(
    backtest_result: dict[str, Any],
    base_params: Optional[dict[str, Any]] = None,
    param_names: Optional[list[str]] = None,
    perturbation_pct: float = 0.10,
) -> SensitivityResult:
    """Estimate parameter sensitivity using rolling Sharpe stability proxies.

    Because this function does not re-run the strategy under perturbed
    parameters, it treats instability across rolling time windows as a proxy for
    likely parameter sensitivity.

    Args ``base_params``, ``param_names``, and ``perturbation_pct`` are
    accepted for API compatibility but unused in the proxy implementation.
    """
    _ = (base_params, param_names, perturbation_pct)  # reserved for future use

    returns = _extract_daily_returns(backtest_result)
    if len(returns) < 10:
        return SensitivityResult(
            rolling_sharpe_std=0.0,
            rolling_sharpe_cv=0.0,
            is_stable=True,
            stability_score=100.0,
            sensitivity_rating="LOW",
        )

    window = min(63, max(10, len(returns) // 4))
    rolling_mean = returns.rolling(window).mean()
    rolling_std = returns.rolling(window).std().where(lambda s: s > 1e-12)
    rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(252)
    rolling_sharpe = rolling_sharpe.replace([np.inf, -np.inf], np.nan).dropna()

    if rolling_sharpe.empty:
        rolling_std_value = 0.0
        cv = 0.0
    else:
        rolling_std_value = float(rolling_sharpe.std())
        mean_abs = float(abs(rolling_sharpe.mean()))
        cv = float(rolling_std_value / mean_abs) if mean_abs > 1e-12 else float("inf")

    is_stable = cv < 0.5
    stability_score = 0.0 if not np.isfinite(cv) else float(max(0.0, min(100.0, 100.0 / (1.0 + cv))))
    if cv < 0.3:
        sensitivity_rating = "LOW"
    elif cv < 0.7:
        sensitivity_rating = "MEDIUM"
    else:
        sensitivity_rating = "HIGH"

    return SensitivityResult(
        rolling_sharpe_std=rolling_std_value,
        rolling_sharpe_cv=cv,
        is_stable=is_stable,
        stability_score=stability_score,
        sensitivity_rating=sensitivity_rating,
    )


def out_of_sample_test(
    backtest_result: dict[str, Any],
    train_pct: float = 0.7,
) -> OOSResult:
    """Compare train and test splits to flag possible overfitting."""
    recorded = list(backtest_result.get("recorded_values", []))
    if len(recorded) < 4:
        return OOSResult(
            train_sharpe=0.0,
            test_sharpe=0.0,
            train_return=0.0,
            test_return=0.0,
            train_max_dd=0.0,
            test_max_dd=0.0,
            sharpe_decay_pct=0.0,
            overfitting_warning=OverfittingWarning.STABLE,
        )

    train_pct = float(min(max(train_pct, 0.1), 0.9))
    split_idx = min(max(int(len(recorded) * train_pct), 2), len(recorded) - 2)

    train_result = _slice_backtest_result(backtest_result, 0, split_idx)
    test_result = _slice_backtest_result(backtest_result, split_idx, len(recorded))
    train_metrics = _compute_metrics(train_result)
    test_metrics = _compute_metrics(test_result)

    decay_pct = _compute_decay_pct(train_metrics["sharpe"], test_metrics["sharpe"])
    return OOSResult(
        train_sharpe=train_metrics["sharpe"],
        test_sharpe=test_metrics["sharpe"],
        train_return=train_metrics["annual_return"],
        test_return=test_metrics["annual_return"],
        train_max_dd=train_metrics["max_drawdown"],
        test_max_dd=test_metrics["max_drawdown"],
        sharpe_decay_pct=decay_pct,
        overfitting_warning=_warning_from_decay(decay_pct),
    )
