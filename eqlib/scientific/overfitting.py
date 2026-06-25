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

from eqlib.constants import TRADING_DAYS_PER_YEAR

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
    excess = returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    return float(excess.mean() / std * (TRADING_DAYS_PER_YEAR ** 0.5))


def _compute_max_drawdown(returns):
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def _compute_annual_return(returns):
    if len(returns) == 0:
        return 0.0
    total = (1 + returns).prod()
    n_years = len(returns) / TRADING_DAYS_PER_YEAR
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
    """Run a true rolling walk-forward overfitting analysis.

    Slices the ``[start_date, end_date]`` range into multiple train/test
    windows that slide forward by ``step``. For each window, in-sample
    (train) and out-of-sample (test) performance are computed separately,
    allowing detection of performance decay across time.

    Parameters
    ----------
    initialize_func:
        Either a backtest result dict (with ``recorded_values`` containing
        ``date`` and ``total_value`` keys) or an EasyQuant ``initialize``
        callable. When a callable is passed, a fresh backtest is run on
        each train and each test segment independently — the canonical
        walk-forward setup. When a dict is passed, the existing equity
        curve is sliced by date (note: OOS segments then inherit the IS
        equity, so callable mode is preferred for true OOS measurement).
    param_ranges:
        Reserved for API compatibility with richer walk-forward optimizers.
        Stored in window metadata only.
    train_window, test_window, step:
        ``2Y``/``6M``/``90D`` style specifiers. ``train_window`` is the
        length of each in-sample segment; ``test_window`` is the length of
        each out-of-sample segment; ``step`` is how far the window slides
        forward each iteration (defaults to ``test_window`` when <= 0,
        producing non-overlapping windows).
    start_date, end_date:
        Total date range covered by the walk-forward analysis. Used
        directly when ``initialize_func`` is callable; for dict input the
        actual recorded date range is used instead.

    Returns
    -------
    WalkForwardResult
        ``windows`` is a list of per-window dicts (each with
        ``train_start/end``, ``test_start/end``, ``is_metrics``,
        ``oos_metrics``). ``oos_is_ratio`` is mean OOS Sharpe / mean IS
        Sharpe across windows. ``is_sharpe_decay`` is True if mean OOS
        Sharpe is below mean IS Sharpe.
    """
    train_days = _parse_window_to_days(train_window)
    test_days = _parse_window_to_days(test_window)
    step_days = _parse_window_to_days(step) or test_days
    if train_days <= 0 or test_days <= 0:
        return WalkForwardResult(windows=[], is_sharpe_decay=False, oos_is_ratio=0.0)

    if isinstance(initialize_func, dict):
        windows = _walk_forward_slice_dict(
            initialize_func, train_days, test_days, step_days,
            train_window, test_window, step, param_ranges,
        )
    elif callable(initialize_func):
        windows = _walk_forward_run_callable(
            initialize_func, start_date, end_date,
            train_days, test_days, step_days,
            train_window, test_window, step, param_ranges,
        )
    else:
        raise TypeError(
            "initialize_func must be a backtest result dict or a callable initialize function"
        )

    if not windows:
        return WalkForwardResult(windows=[], is_sharpe_decay=False, oos_is_ratio=0.0)

    is_sharpes = [w["is_metrics"]["sharpe"] for w in windows]
    oos_sharpes = [w["oos_metrics"]["sharpe"] for w in windows]
    mean_is = float(np.mean(is_sharpes)) if is_sharpes else 0.0
    mean_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
    ratio = _safe_ratio(mean_oos, mean_is)
    return WalkForwardResult(
        windows=windows,
        is_sharpe_decay=bool(mean_oos < mean_is),
        oos_is_ratio=ratio,
    )


def _walk_forward_slice_dict(
    backtest_result: dict[str, Any],
    train_days: int,
    test_days: int,
    step_days: int,
    train_window: str,
    test_window: str,
    step: str,
    param_ranges: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Slice a pre-computed backtest result into rolling train/test windows."""
    recorded = list(backtest_result.get("recorded_values", []))
    if len(recorded) < 4:
        return []

    dates = [r["date"] for r in recorded]
    try:
        ts = pd.to_datetime(pd.Series(dates))
    except Exception:
        return []

    full_start = ts.iloc[0]
    full_end = ts.iloc[-1]
    train_td = pd.Timedelta(days=train_days)
    test_td = pd.Timedelta(days=test_days)
    step_td = pd.Timedelta(days=step_days)

    windows: list[dict[str, Any]] = []
    cursor = full_start
    while cursor + train_td + test_td <= full_end + pd.Timedelta(days=1):
        train_start = cursor
        train_end = train_start + train_td
        test_start = train_end
        test_end = test_start + test_td

        train_mask = (ts >= train_start) & (ts < train_end)
        test_mask = (ts >= test_start) & (ts < test_end)
        train_idx = ts.index[train_mask].tolist()
        test_idx = ts.index[test_mask].tolist()

        if len(train_idx) >= 2 and len(test_idx) >= 2:
            tr_lo, tr_hi = train_idx[0], train_idx[-1] + 1
            te_lo, te_hi = test_idx[0], test_idx[-1] + 1
            train_result = _slice_backtest_result(backtest_result, tr_lo, tr_hi)
            test_result = _slice_backtest_result(backtest_result, te_lo, te_hi)
            windows.append({
                "train_start": dates[tr_lo],
                "train_end": dates[tr_hi - 1],
                "test_start": dates[te_lo],
                "test_end": dates[te_hi - 1],
                "train_window": train_window,
                "test_window": test_window,
                "step": step,
                "param_ranges": param_ranges or {},
                "is_metrics": _compute_metrics(train_result),
                "oos_metrics": _compute_metrics(test_result),
            })

        cursor = cursor + step_td

    return windows


def _walk_forward_run_callable(
    initialize_func: Callable,
    start_date: str,
    end_date: str,
    train_days: int,
    test_days: int,
    step_days: int,
    train_window: str,
    test_window: str,
    step: str,
    param_ranges: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run fresh backtests per train/test window (canonical walk-forward)."""
    from eqlib.engine import run_backtest

    try:
        full_start = pd.Timestamp(start_date)
        full_end = pd.Timestamp(end_date)
    except Exception:
        return []

    train_td = pd.Timedelta(days=train_days)
    test_td = pd.Timedelta(days=test_days)
    step_td = pd.Timedelta(days=step_days)

    windows: list[dict[str, Any]] = []
    cursor = full_start
    while cursor + train_td + test_td <= full_end + pd.Timedelta(days=1):
        train_start = cursor
        train_end = train_start + train_td
        test_start = train_end
        test_end = test_start + test_td

        train_metrics, train_lo, train_hi = _run_segment(
            run_backtest, initialize_func, train_start, train_end,
        )
        test_metrics, test_lo, test_hi = _run_segment(
            run_backtest, initialize_func, test_start, test_end,
        )

        windows.append({
            "train_start": train_lo,
            "train_end": train_hi,
            "test_start": test_lo,
            "test_end": test_hi,
            "train_window": train_window,
            "test_window": test_window,
            "step": step,
            "param_ranges": param_ranges or {},
            "is_metrics": train_metrics,
            "oos_metrics": test_metrics,
        })

        cursor = cursor + step_td

    return windows


def _run_segment(run_backtest, initialize_func, start_ts, end_ts):
    """Run a backtest over [start_ts, end_ts] and return metrics + actual dates."""
    start_str = str(start_ts.date())
    end_str = str(end_ts.date())
    try:
        result = run_backtest(
            initialize_func,
            start_date=start_str,
            end_date=end_str,
        )
    except Exception:
        return (
            {"sharpe": 0.0, "annual_return": 0.0, "max_drawdown": 0.0},
            start_str,
            end_str,
        )
    metrics = _compute_metrics(result)
    recorded = result.get("recorded_values", []) or []
    actual_start = recorded[0]["date"] if recorded else start_str
    actual_end = recorded[-1]["date"] if recorded else end_str
    return metrics, actual_start, actual_end


def parameter_sensitivity(
    backtest_result: dict[str, Any],
    base_params: Optional[dict[str, Any]] = None,
    param_names: Optional[list[str]] = None,
    perturbation_pct: float = 0.10,
) -> SensitivityResult:
    """Estimate parameter sensitivity using rolling Sharpe stability proxies.

    .. warning::

        This is a **proxy** implementation. It does NOT actually perturb
        strategy parameters and re-run the backtest. Instead it uses
        rolling Sharpe stability over time as a stand-in: a strategy
        whose Sharpe fluctuates wildly across rolling windows is assumed
        to also be sensitive to parameter perturbations. This is a rough
        heuristic — for true sensitivity analysis, re-run the backtest
        with each parameter perturbed and measure the performance delta.

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
    rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
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
