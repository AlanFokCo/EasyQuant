"""Walk-forward analysis (WFA) framework for out-of-sample strategy validation.

Walk-forward analysis splits a historical period into alternating **in-sample**
(IS) training windows and **out-of-sample** (OOS) test windows, runs the
backtest on each OOS window using parameters optimized on the preceding IS
window, and stitches the OOS equity curves together.

This helps detect overfitting: a strategy that is profitable in-sample but
underperforms on the OOS windows is likely over-optimized.

Example usage::

    from eqlib.wfa import walk_forward
    from eqlib import run_backtest, set_benchmark

    def make_initialize(fast_period, slow_period):
        def initialize(context):
            set_benchmark('000300.XSHG')
            context.fast = fast_period
            context.slow = slow_period
            from eqlib import run_daily
            run_daily(handle, time='every_bar')
        return initialize

    def handle(context):
        ...  # strategy logic using context.fast / context.slow

    # Optimize: try all (fast, slow) combinations and pick best Sharpe
    def optimize(train_result):
        return {'fast_period': 5, 'slow_period': 20}  # simplified

    wfa_result = walk_forward(
        make_initialize,
        optimize_fn=optimize,
        start_date='2020-01-01',
        end_date='2024-12-31',
        train_months=12,
        test_months=3,
        step_months=3,
        starting_cash=100_000,
    )
    print(wfa_result['summary'])
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Optional

import pandas as pd

__all__ = ["walk_forward", "WFAResult"]


class WFAResult:
    """Container for walk-forward analysis results.

    Attributes:
        windows: list of per-window dicts with keys:
            ``train_start``, ``train_end``, ``test_start``, ``test_end``,
            ``params``, ``oos_result`` (run_backtest result dict),
            ``oos_metrics`` (analyze_returns dict or None).
        oos_equity: stitched OOS equity curve as a pandas Series (daily).
        summary: dict with aggregated statistics over all OOS windows.
    """

    def __init__(self, windows: list[dict[str, Any]], oos_equity: pd.Series,
                 summary: dict[str, Any]) -> None:
        self.windows = windows
        self.oos_equity = oos_equity
        self.summary = summary

    def __repr__(self) -> str:
        n = len(self.windows)
        ret = self.summary.get("total_oos_return", float("nan"))
        sharpe = self.summary.get("oos_sharpe", float("nan"))
        return (
            f"WFAResult(windows={n}, "
            f"oos_return={ret:.1%}, "
            f"oos_sharpe={sharpe:.2f})"
        )


def _add_months(d: datetime.date, months: int) -> datetime.date:
    """Add *months* calendar months to date *d*, clamping to month-end."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def walk_forward(
    make_initialize: Callable,
    optimize_fn: Optional[Callable] = None,
    start_date: str | datetime.date = "2020-01-01",
    end_date: str | datetime.date = "2023-12-31",
    train_months: int = 12,
    test_months: int = 3,
    step_months: int = 3,
    starting_cash: float = 100_000,
    benchmark: str = "000300.XSHG",
    securities: Optional[list[str]] = None,
    use_local: bool = False,
    **backtest_kwargs,
) -> WFAResult:
    """Run a walk-forward analysis.

    Parameters
    ----------
    make_initialize:
        A factory function that accepts the parameter dict returned by
        *optimize_fn* as keyword arguments and returns an ``initialize``
        function suitable for ``run_backtest``.  When *optimize_fn* is
        ``None``, *make_initialize* is called with no arguments.
    optimize_fn:
        Optional callable ``(train_result: dict) -> dict`` that selects
        the best parameters from the in-sample backtest result.  When
        ``None``, the same no-argument ``make_initialize()`` is used for
        both IS and OOS windows (no parameter optimization).
    start_date:
        Start of the full analysis period.
    end_date:
        End of the full analysis period.
    train_months:
        Length of each in-sample training window in calendar months.
    test_months:
        Length of each out-of-sample test window in calendar months.
    step_months:
        How far to advance the window between iterations.  Setting
        ``step_months == test_months`` (the default) gives non-overlapping
        OOS windows.
    starting_cash:
        Initial capital for each window backtest.
    benchmark:
        Benchmark code.
    securities:
        Stock universe.  Pass ``None`` to let the initialize function
        set the universe itself.
    use_local:
        Whether to use locally cached CSV data.
    **backtest_kwargs:
        Extra keyword arguments forwarded to ``run_backtest``.

    Returns
    -------
    WFAResult
        Object with per-window results and a stitched OOS equity curve.
    """
    from eqlib.engine import run_backtest
    from eqlib.attribution import analyze_returns

    if isinstance(start_date, str):
        start_date = datetime.date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.date.fromisoformat(end_date)

    windows: list[dict[str, Any]] = []
    oos_series_list: list[pd.Series] = []

    win_start = start_date
    while True:
        train_end = _add_months(win_start, train_months) - datetime.timedelta(days=1)
        test_start = train_end + datetime.timedelta(days=1)
        test_end = _add_months(test_start, test_months) - datetime.timedelta(days=1)

        if test_start > end_date:
            break
        test_end = min(test_end, end_date)

        # ── In-sample (parameter selection) ───────────────────────────────
        params: dict[str, Any] = {}
        if optimize_fn is not None:
            train_init = make_initialize()
            train_result = run_backtest(
                train_init,
                start_date=win_start,
                end_date=train_end,
                starting_cash=starting_cash,
                benchmark=benchmark,
                securities=securities,
                use_local=use_local,
                **backtest_kwargs,
            )
            if train_result is not None:
                try:
                    params = optimize_fn(train_result) or {}
                except Exception:
                    params = {}

        # ── Out-of-sample ──────────────────────────────────────────────────
        oos_init = make_initialize(**params) if optimize_fn is not None else make_initialize()
        oos_result = run_backtest(
            oos_init,
            start_date=test_start,
            end_date=test_end,
            starting_cash=starting_cash,
            benchmark=benchmark,
            securities=securities,
            use_local=use_local,
            **backtest_kwargs,
        )

        oos_metrics: Optional[dict[str, Any]] = None
        if oos_result is not None:
            try:
                oos_metrics = analyze_returns(oos_result)
            except Exception:
                pass

            # Collect OOS equity curve
            recorded = oos_result.get("recorded_values", {})
            if recorded:
                dates = sorted(recorded.keys())
                values = [recorded[d].get("total_value", starting_cash) for d in dates]
                s = pd.Series(values, index=pd.DatetimeIndex([pd.Timestamp(d) for d in dates]))
                # Normalize to 1.0 at start of each OOS window so curves stitch
                if len(s) > 0 and s.iloc[0] > 0:
                    s = s / s.iloc[0]
                oos_series_list.append(s)

        windows.append({
            "train_start": win_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "params": params,
            "oos_result": oos_result,
            "oos_metrics": oos_metrics,
        })

        win_start = _add_months(win_start, step_months)
        if win_start > end_date:
            break

    # ── Stitch OOS equity curves ───────────────────────────────────────────
    oos_equity = _stitch_equity(oos_series_list, starting_cash)

    # ── Summary statistics ─────────────────────────────────────────────────
    summary = _summarize(windows, oos_equity)

    return WFAResult(windows=windows, oos_equity=oos_equity, summary=summary)


def _stitch_equity(series_list: list[pd.Series], starting_cash: float) -> pd.Series:
    """Chain normalized OOS equity curves into a single absolute series."""
    if not series_list:
        return pd.Series(dtype=float)

    result_values: list[float] = []
    result_index: list[pd.Timestamp] = []
    cumulative = starting_cash

    for s in series_list:
        if s.empty:
            continue
        for ts, ratio in zip(s.index, s.values):
            if not result_index or ts > result_index[-1]:
                result_values.append(cumulative * float(ratio))
                result_index.append(ts)
        cumulative = result_values[-1] if result_values else starting_cash

    return pd.Series(result_values, index=pd.DatetimeIndex(result_index))


def _summarize(windows: list[dict[str, Any]], oos_equity: pd.Series) -> dict[str, Any]:
    """Compute summary statistics across all OOS windows."""
    import numpy as np

    sharpe_values = []
    returns = []
    max_dds = []

    for w in windows:
        m = w.get("oos_metrics")
        if m:
            s = m.get("sharpe_ratio", float("nan"))
            r = m.get("total_return", float("nan"))
            dd = m.get("max_drawdown", float("nan"))
            if not (s != s):  # not NaN
                sharpe_values.append(s)
            if not (r != r):
                returns.append(r)
            if not (dd != dd):
                max_dds.append(dd)

    profitable_windows = sum(1 for r in returns if r > 0)

    # Compute overall OOS return and drawdown from stitched curve
    total_oos_return = float("nan")
    oos_max_drawdown = float("nan")
    if not oos_equity.empty and oos_equity.iloc[0] > 0:
        total_oos_return = float(oos_equity.iloc[-1] / oos_equity.iloc[0] - 1)
        cum_max = oos_equity.cummax()
        dd_series = oos_equity / cum_max - 1
        oos_max_drawdown = float(dd_series.min())

    return {
        "n_windows": len(windows),
        "profitable_windows": profitable_windows,
        "profitable_pct": profitable_windows / len(windows) if windows else float("nan"),
        "avg_oos_sharpe": float(np.mean(sharpe_values)) if sharpe_values else float("nan"),
        "oos_sharpe": float(np.mean(sharpe_values)) if sharpe_values else float("nan"),
        "avg_oos_return": float(np.mean(returns)) if returns else float("nan"),
        "total_oos_return": total_oos_return,
        "oos_max_drawdown": oos_max_drawdown,
        "avg_max_drawdown": float(np.mean(max_dds)) if max_dds else float("nan"),
    }
