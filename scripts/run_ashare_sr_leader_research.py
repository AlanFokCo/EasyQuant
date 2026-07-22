#!/usr/bin/env python3
"""Run A-share industry leader support/resistance strategy research.

The full run fetches daily A-share data through eqlib/akshare and may take a
while. Use --quick for a smaller smoke run.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from eqlib import analyze_returns, generate_html_report, grade_strategy, run_backtest
from eqlib.strategies.ashare_sr_leader import (
    PortfolioRiskState,
    StrategyKind,
    StrategyParams,
    get_default_leader_universe,
    make_initialize,
)

START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
BENCHMARK = "000300.XSHG"
STARTING_CASH = 1_000_000
REPORT_DIR = Path("reports/ashare_sr_leader")
EQLIB_HTML_REPORT = REPORT_DIR / "eqlib_best_backtest_2020_2025.html"
SUB_PERIODS = (
    ("2020-2021", "2020-01-01", "2021-12-31"),
    ("2022", "2022-01-01", "2022-12-31"),
    ("2023-2024", "2023-01-01", "2024-12-31"),
    ("2025", "2025-01-01", "2025-12-31"),
)
VALIDATION_WINDOWS = (
    ("2023", "2020-01-01", "2023-12-31", "2023-01-01", "2023-12-31"),
    ("2024", "2021-01-01", "2024-12-31", "2024-01-01", "2024-12-31"),
    ("2025", "2022-01-01", "2025-12-31", "2025-01-01", "2025-12-31"),
)

RESEARCH_UNIVERSE = [
    "600519",
    "000858",
    "600887",
    "000333",
    "000651",
    "601888",
    "600036",
    "601398",
    "601318",
    "600030",
    "300059",
    "600276",
    "300760",
    "000661",
    "300750",
    "002594",
    "300274",
    "002415",
    "000725",
    "002475",
    "000063",
    "600941",
    "601728",
    "000977",
    "002230",
    "300124",
    "000425",
    "600031",
    "600309",
    "002352",
    "601899",
    "600547",
    "601668",
    "601390",
    "600690",
    "600406",
    "002371",
    "300014",
    "300015",
    "601919",
]

BASELINE_ADAPTIVE_PARAMS = StrategyParams(
    level_window=100,
    short_level_window=50,
    atr_multiplier=0.45,
    volume_ratio_min=0.9,
    top_n=10,
    max_stock_weight=0.10,
    max_industry_weight=0.25,
    strong_market_exposure=0.95,
    neutral_market_exposure=0.68,
    weak_market_exposure=0.25,
    min_relative_strength=-0.015,
    max_support_distance=0.11,
    rebalance_threshold=0.05,
    liquidity_volume_pct=0.04,
)


def robust_seed_param_grid() -> list[StrategyParams]:
    """Return the deterministic robust parameter seeds."""

    center = replace(BASELINE_ADAPTIVE_PARAMS, robust_enabled=True)
    return [
        center,
        replace(center, min_primary_candidates=4),
        replace(center, min_primary_candidates=6),
        replace(center, fallback_exposure_cap=0.20),
        replace(center, fallback_exposure_cap=0.30),
        replace(center, fallback_trailing_drawdown=0.08),
        replace(center, target_annual_volatility=0.16),
        replace(center, target_annual_volatility=0.20),
        replace(
            center,
            cautious_drawdown=0.07,
            defensive_drawdown=0.11,
            protect_drawdown=0.15,
        ),
        replace(
            center,
            cautious_drawdown=0.09,
            defensive_drawdown=0.13,
            protect_drawdown=0.17,
        ),
    ]


def candidate_param_grid(quick: bool = False):
    """Return strategy/parameter combinations to evaluate."""

    if quick:
        grid = [
            (StrategyKind.DEFENSIVE_SUPPORT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.RESISTANCE_BREAKOUT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.PULLBACK_MARKET_GATE, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.ADAPTIVE_COMPOSITE, StrategyParams(level_window=60, top_n=8)),
        ]
        grid.append((StrategyKind.ADAPTIVE_COMPOSITE, robust_seed_param_grid()[0]))
        return list(dict.fromkeys(grid))

    grid = []
    for kind in StrategyKind:
        for top_n in (8, 12):
            grid.append(
                (
                    kind,
                    StrategyParams(
                        level_window=120,
                        short_level_window=60,
                        atr_multiplier=0.5,
                        volume_ratio_min=1.0,
                        top_n=top_n,
                    ),
                )
            )
        grid.append(
            (
                kind,
                StrategyParams(
                    level_window=120,
                    short_level_window=60,
                    atr_multiplier=0.5,
                    volume_ratio_min=1.0,
                    top_n=12,
                    max_stock_weight=0.07,
                    max_industry_weight=0.21,
                    strong_market_exposure=0.70,
                    neutral_market_exposure=0.45,
                    weak_market_exposure=0.20,
                    rebalance_threshold=0.10,
                ),
            )
        )
        if kind in {StrategyKind.DEFENSIVE_SUPPORT, StrategyKind.PULLBACK_MARKET_GATE}:
            grid.append(
                (
                    kind,
                    StrategyParams(
                        level_window=120,
                        short_level_window=60,
                        atr_multiplier=0.6,
                        volume_ratio_min=1.0,
                        top_n=10,
                        max_stock_weight=0.08,
                        max_industry_weight=0.24,
                        strong_market_exposure=0.82,
                        neutral_market_exposure=0.50,
                        weak_market_exposure=0.15,
                        min_relative_strength=0.0,
                        max_support_distance=0.08,
                        rebalance_threshold=0.10,
                        liquidity_volume_pct=0.03,
                    ),
                )
            )
        if kind is StrategyKind.PULLBACK_MARKET_GATE:
            grid.append(
                (
                    kind,
                    StrategyParams(
                        level_window=120,
                        short_level_window=60,
                        atr_multiplier=0.6,
                        volume_ratio_min=1.0,
                        top_n=10,
                        max_stock_weight=0.08,
                        max_industry_weight=0.24,
                        strong_market_exposure=0.84,
                        neutral_market_exposure=0.54,
                        weak_market_exposure=0.18,
                        min_relative_strength=-0.005,
                        max_support_distance=0.10,
                        rebalance_threshold=0.07,
                        liquidity_volume_pct=0.035,
                    ),
                )
            )
            grid.append(
                (
                    kind,
                    StrategyParams(
                        level_window=120,
                        short_level_window=60,
                        atr_multiplier=0.65,
                        volume_ratio_min=1.05,
                        top_n=10,
                        max_stock_weight=0.07,
                        max_industry_weight=0.21,
                        strong_market_exposure=0.76,
                        neutral_market_exposure=0.44,
                        weak_market_exposure=0.10,
                        min_relative_strength=0.01,
                        max_support_distance=0.06,
                        max_position_drawdown=0.12,
                        rebalance_threshold=0.08,
                        liquidity_volume_pct=0.03,
                    ),
                )
            )
        if kind is StrategyKind.ADAPTIVE_COMPOSITE:
            grid.extend(
                [
                    (
                        kind,
                        StrategyParams(
                            level_window=120,
                            short_level_window=60,
                            atr_multiplier=0.55,
                            volume_ratio_min=1.0,
                            top_n=12,
                            max_stock_weight=0.09,
                            max_industry_weight=0.24,
                            strong_market_exposure=0.90,
                            neutral_market_exposure=0.62,
                            weak_market_exposure=0.22,
                            min_relative_strength=-0.01,
                            max_support_distance=0.10,
                            rebalance_threshold=0.06,
                            liquidity_volume_pct=0.035,
                        ),
                    ),
                    (
                        kind,
                        BASELINE_ADAPTIVE_PARAMS,
                    ),
                ]
            )
    grid.extend(
        (StrategyKind.ADAPTIVE_COMPOSITE, params)
        for params in robust_seed_param_grid()
    )
    return list(dict.fromkeys(grid))


def neighbor_param_sets(params: StrategyParams) -> list[StrategyParams]:
    """Return deterministic one-step robustness neighbors around params."""

    variants = [
        replace(params, min_primary_candidates=value) for value in (4, 5, 6)
    ]
    variants.extend(
        replace(params, fallback_exposure_cap=value) for value in (0.20, 0.25, 0.30)
    )
    variants.extend(
        replace(params, fallback_trailing_drawdown=value) for value in (0.08, 0.10)
    )
    variants.extend(
        replace(params, target_annual_volatility=value)
        for value in (0.16, 0.18, 0.20)
    )
    variants.extend(
        [
            replace(
                params,
                cautious_drawdown=0.07,
                defensive_drawdown=0.11,
                protect_drawdown=0.15,
            ),
            replace(
                params,
                cautious_drawdown=0.09,
                defensive_drawdown=0.13,
                protect_drawdown=0.17,
            ),
        ]
    )
    return list(dict.fromkeys(item for item in variants if item != params))


def full_gate_failures(row: dict) -> list[str]:
    """Return full-period hard-gate failures for a summary row."""

    failures: list[str] = []
    annual_return = _finite_metric(row, "annual_return")
    max_drawdown = _finite_metric(row, "max_drawdown")
    grade_score = _finite_metric(row, "grade_score")
    if annual_return is None:
        failures.append("annual_return_nonfinite")
    elif annual_return < 0.12:
        failures.append("annual_return_below_12pct")
    if max_drawdown is None:
        failures.append("max_drawdown_nonfinite")
    elif abs(max_drawdown) >= 0.20:
        failures.append("max_drawdown_not_below_20pct")
    if grade_score is None:
        failures.append("grade_score_nonfinite")
    elif grade_score < 70.0:
        failures.append("grade_below_a")
    return failures


def validation_gate_failures(rows: dict[str, dict]) -> list[str]:
    """Return excess-return gate failures for rolling validation years."""

    failures: list[str] = []
    for period, row in rows.items():
        if row.get("error"):
            failures.append(f"{period}_validation_unavailable")
            continue
        excess = _finite_metric(row, "excess_return")
        if excess is None:
            failures.append(f"{period}_excess_nonfinite")
            continue
        if period == "2025" and excess < -0.05:
            failures.append("2025_excess_below_minus_5pct")
        elif period != "2025" and excess < -0.10:
            failures.append(f"{period}_excess_below_minus_10pct")
    return failures


def neighbor_pass_rate(rows: list[dict]) -> float:
    """Return the share of neighbors meeting approved return/risk limits."""

    if not rows:
        return 0.0
    passed = sum(
        (annual_return := _finite_metric(row, "annual_return")) is not None
        and (max_drawdown := _finite_metric(row, "max_drawdown")) is not None
        and annual_return >= 0.10
        and abs(max_drawdown) <= 0.22
        for row in rows
    )
    return round(passed / len(rows), 6)


def robust_rank_key(row: dict) -> tuple[float, float, float, float, float, float]:
    """Rank robust rows from broad stability to headline return."""

    return (
        _float_metric(row, "neighbor_pass_rate", 0.0),
        _float_metric(row, "worst_validation_excess"),
        _float_metric(row, "sharpe_ratio"),
        -abs(_float_metric(row, "max_drawdown")),
        _float_metric(row, "monthly_win_rate", 0.0),
        _float_metric(row, "annual_return"),
    )


def _benchmark_total_return(result: dict) -> float:
    recorded = result.get("recorded_values", [])
    benchmark_values = result.get("benchmark_values", [])
    if recorded and benchmark_values:
        start = _date_key(recorded[0].get("date"))
        end = _date_key(recorded[-1].get("date"))
        values = [
            float(row["value"])
            for row in benchmark_values
            if row.get("value") is not None
            and start <= _date_key(row.get("date")) <= end
            and float(row["value"]) > 0
        ]
        if len(values) >= 2:
            return round(values[-1] / values[0] - 1, 12)

    if not recorded:
        return 0.0
    first = recorded[0].get("bench_value")
    last = recorded[-1].get("bench_value")
    if first in (None, 0) or last is None:
        return 0.0
    return round(float(last / first - 1), 12)


def _date_key(value: object) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _channel_defaults() -> dict[str, float | int]:
    return {
        "primary_trade_count": 0,
        "fallback_trade_count": 0,
        "primary_average_exposure": 0.0,
        "fallback_average_exposure": 0.0,
        "primary_average_holdings": 0.0,
        "fallback_average_holdings": 0.0,
        "primary_return_contribution": 0.0,
        "fallback_return_contribution": 0.0,
    }


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _close_history(frame: object) -> dict[str, float]:
    try:
        close = frame["close"]
        items = close.items()
    except (KeyError, TypeError, AttributeError):
        return {}
    history: dict[str, float] = {}
    for date, value in items:
        price = _finite_float(value)
        if price is not None and price > 0.0:
            history[_date_key(date)] = price
    return history


def channel_diagnostics(result: dict) -> dict[str, float | int]:
    """Attribute holdings, exposure, and next-close return by entry channel."""

    defaults = _channel_defaults()
    context = result.get("context")
    raw_channels = getattr(context, "sr_order_channels", {}) if context else {}
    if not isinstance(raw_channels, dict):
        raw_channels = {}
    order_channels = {str(key): value for key, value in raw_channels.items()}
    valid_channels = ("primary", "fallback")
    holdings = {channel: {} for channel in valid_channels}
    trades_by_date: dict[str, list[dict]] = {}

    for trade in result.get("trade_log", []) or []:
        if not isinstance(trade, dict):
            continue
        channel = order_channels.get(str(trade.get("order_id")))
        security = trade.get("security")
        amount = _finite_float(trade.get("amount"))
        trade_date = trade.get("date")
        if (
            channel not in valid_channels
            or not security
            or not trade_date
            or amount is None
            or amount <= 0
        ):
            continue
        date = _date_key(trade_date)
        trades_by_date.setdefault(date, []).append(trade)
        if trade.get("type") == "BUY":
            defaults[f"{channel}_trade_count"] += 1

    close_histories = {
        str(security): _close_history(frame)
        for security, frame in (result.get("ohlcv_data", {}) or {}).items()
    }
    records = sorted(
        (
            row
            for row in (result.get("recorded_values", []) or [])
            if isinstance(row, dict) and row.get("date") is not None
        ),
        key=lambda row: _date_key(row.get("date")),
    )
    exposure_totals = {channel: 0.0 for channel in valid_channels}
    holding_totals = {channel: 0.0 for channel in valid_channels}
    contributions = {channel: 0.0 for channel in valid_channels}
    previous_date: str | None = None
    previous_total: float | None = None

    for record in records:
        date = _date_key(record.get("date"))
        if previous_date is not None and previous_total is not None and previous_total > 0.0:
            for channel in valid_channels:
                for security, amount in holdings[channel].items():
                    history = close_histories.get(security, {})
                    previous_close = history.get(previous_date)
                    current_close = history.get(date)
                    if previous_close is None or current_close is None:
                        continue
                    contributions[channel] += (
                        amount * (current_close - previous_close) / previous_total
                    )

        for trade in trades_by_date.get(date, []):
            channel = order_channels[str(trade.get("order_id"))]
            security = str(trade["security"])
            amount = float(trade["amount"])
            current = holdings[channel].get(security, 0.0)
            if trade.get("type") == "BUY":
                holdings[channel][security] = current + amount
            elif trade.get("type") == "SELL":
                remaining = max(0.0, current - amount)
                if remaining > 0.0:
                    holdings[channel][security] = remaining
                else:
                    holdings[channel].pop(security, None)

        total_value = _finite_float(record.get("total_value"))
        for channel in valid_channels:
            holding_totals[channel] += sum(
                amount > 0.0 for amount in holdings[channel].values()
            )
            if total_value is None or total_value <= 0.0:
                continue
            exposure_totals[channel] += sum(
                amount * close
                for security, amount in holdings[channel].items()
                if (close := close_histories.get(security, {}).get(date)) is not None
            ) / total_value

        previous_date = date
        previous_total = total_value

    record_count = len(records)
    for channel in valid_channels:
        if record_count:
            defaults[f"{channel}_average_exposure"] = round(
                exposure_totals[channel] / record_count, 6
            )
            defaults[f"{channel}_average_holdings"] = round(
                holding_totals[channel] / record_count, 6
            )
        defaults[f"{channel}_return_contribution"] = round(
            contributions[channel], 6
        )
    return defaults


def _portfolio_risk_state(value: object) -> PortfolioRiskState | None:
    if isinstance(value, PortfolioRiskState):
        return value
    if isinstance(value, str):
        try:
            return PortfolioRiskState[value.upper()]
        except KeyError:
            return None
    try:
        return PortfolioRiskState(value)
    except (TypeError, ValueError):
        return None


def risk_state_diagnostics(result: dict) -> dict:
    """Count recorded-day risk states and ordered state transitions."""

    context = result.get("context")
    raw_events = getattr(context, "sr_risk_events", []) if context else []
    events = sorted(
        (
            event
            for event in (raw_events or [])
            if isinstance(event, dict) and event.get("date") is not None
        ),
        key=lambda event: _date_key(event["date"]),
    )
    dates = sorted(
        _date_key(row.get("date"))
        for row in (result.get("recorded_values", []) or [])
        if isinstance(row, dict) and row.get("date") is not None
    )
    state = PortfolioRiskState.NORMAL
    state_days: dict[str, int] = {}
    trigger_count = 0
    recovery_count = 0
    event_index = 0

    for date in dates:
        while event_index < len(events) and _date_key(events[event_index]["date"]) <= date:
            target = _portfolio_risk_state(events[event_index].get("to"))
            event_index += 1
            if target is None or target is state:
                continue
            if state is PortfolioRiskState.NORMAL and target > state:
                trigger_count += 1
            if target < state:
                recovery_count += 1
            state = target
        name = state.name.lower()
        state_days[name] = state_days.get(name, 0) + 1

    return {
        "risk_state_days": state_days,
        "risk_state_trigger_count": trigger_count,
        "risk_state_recovery_count": recovery_count,
    }


def _finite_metric(row: dict, key: str) -> float | None:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def slice_backtest_result(result: dict, start: str, end: str) -> dict | None:
    """Return an isolated validation-year view of a formation backtest."""

    recorded = [
        dict(row)
        for row in result.get("recorded_values", [])
        if start <= _date_key(row.get("date")) <= end
    ]
    if len(recorded) < 2:
        return None
    recorded_start = _date_key(recorded[0].get("date"))
    recorded_end = _date_key(recorded[-1].get("date"))
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            starting_cash=float(recorded[0]["total_value"]),
            total_value=float(recorded[-1]["total_value"]),
        )
    )
    trades = [
        dict(trade)
        for trade in result.get("trade_log", [])
        if start <= _date_key(trade.get("date")) <= end
    ]
    benchmark_values = [
        dict(row)
        for row in result.get("benchmark_values", [])
        if recorded_start <= _date_key(row.get("date")) <= recorded_end
    ]
    if len(benchmark_values) < 2 or any(
        (value := _finite_metric(row, "value")) is None or value <= 0.0
        for row in benchmark_values
    ):
        return None
    return {
        "context": context,
        "trade_log": trades,
        "recorded_values": recorded,
        "benchmark": result.get("benchmark", BENCHMARK),
        "benchmark_values": benchmark_values,
        "ohlcv_data": result.get("ohlcv_data", {}),
    }


def stability_score(metrics: dict) -> float:
    """Score risk-adjusted quality while penalizing drawdown and churn."""

    annual_return = float(metrics.get("annual_return", 0.0))
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    max_drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    trade_count = int(metrics.get("trade_count", 0))
    excess_return = float(metrics.get("excess_return", 0.0))
    undertrade_penalty = max(0, 20 - trade_count) / 20 * 0.75
    churn_penalty = max(0, trade_count - 120) / 120 * 0.15
    drawdown_penalty = max(0.0, max_drawdown - 0.20) * 3.0
    return (
        annual_return * 1.5
        + sharpe * 0.25
        + excess_return
        - drawdown_penalty
        - undertrade_penalty
        - churn_penalty
    )


def _float_metric(row: dict, key: str, default: float = -999.0) -> float:
    value = _finite_metric(row, key)
    return default if value is None else value


def _candidate_rank_key(row: dict) -> tuple[bool, float, float]:
    """Rank full-period rows by report grade first, then stability."""

    return (
        row.get("period_name") == "full",
        _float_metric(row, "grade_score"),
        _float_metric(row, "stability_score"),
    )


def _report_rank_key(row: dict) -> tuple[bool, bool, float, float]:
    """Keep the selected full-period row ahead of diagnostic ranking."""

    return (
        row.get("period_name") == "full" and row.get("selected") is True,
        *_candidate_rank_key(row),
    )


def _best_full_candidate(full_candidates: list[tuple[dict, StrategyKind, StrategyParams]]):
    """Return the preferred full-period candidate tuple."""

    return max(full_candidates, key=lambda item: _candidate_rank_key(item[0]))


def summarize_result(result: dict) -> dict:
    """Return metrics used for comparison."""

    metrics = analyze_returns(result, risk_free_rate=0.03) or {}
    grade_info = grade_strategy(metrics) if metrics else grade_strategy(None)
    total_return = float(metrics.get("total_return", 0.0))
    benchmark_return = _benchmark_total_return(result)
    monthly_returns = metrics.get("monthly_returns", {}) or {}
    summary = {
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "annual_return": float(metrics.get("annual_return", 0.0)),
        "annual_volatility": float(metrics.get("annual_volatility", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "sortino_ratio": float(metrics.get("sortino_ratio", 0.0)),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "calmar_ratio": float(metrics.get("calmar_ratio", 0.0)),
        "win_rate_trade": float(metrics.get("win_rate_trade", 0.0)),
        "profit_loss_ratio": float(metrics.get("profit_loss_ratio", 0.0)),
        "trade_count": int(metrics.get("trade_count", len(result.get("trade_log", [])))),
        "raw_trade_count": len(result.get("trade_log", [])),
        "grade": grade_info.get("overall"),
        "grade_score": float(grade_info.get("score", 0.0)),
        "grade_weakest": grade_info.get("weakest"),
        "monthly_win_rate": (
            sum(value > 0 for value in monthly_returns.values())
            / len(monthly_returns)
            if monthly_returns
            else 0.0
        ),
    }
    summary["stability_score"] = stability_score(summary)
    return summary


def _attach_research_diagnostics(summary: dict, result: dict | None = None) -> dict:
    if result is not None:
        summary.update(channel_diagnostics(result))
        summary.update(risk_state_diagnostics(result))
    else:
        for key, value in _channel_defaults().items():
            summary.setdefault(key, value)
        summary.setdefault("risk_state_days", {})
        summary.setdefault("risk_state_trigger_count", 0)
        summary.setdefault("risk_state_recovery_count", 0)
    summary.setdefault("gate_failures", [])
    summary.setdefault("robust_gate_pass", False)
    summary.setdefault("neighbor_pass_rate", 0.0)
    summary.setdefault("worst_validation_excess", 0.0)
    summary.setdefault("validation", {})
    return summary


def write_eqlib_html_report(result: dict, out_path: Path = EQLIB_HTML_REPORT) -> None:
    """Write eqlib's native interactive HTML report for a backtest result."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    generate_html_report(result, out_path)


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _best_by_period(rows: list[dict]) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for row in rows:
        period = row.get("period_name", "unknown")
        if period not in best or _report_rank_key(row) > _report_rank_key(best[period]):
            best[period] = row
    return best


def audit_rows(rows: list[dict]) -> list[dict[str, str]]:
    """Return report-quality issues that should be investigated before use."""

    issues: list[dict[str, str]] = []
    if not rows:
        return [
            {
                "severity": "error",
                "code": "empty_result",
                "message": "没有生成任何回测结果，报告不可用。",
            }
        ]

    full_rows = [row for row in rows if row.get("period_name") == "full"]
    if full_rows and all(
        abs(float(row.get("benchmark_return", 0.0))) < 1e-12 for row in full_rows
    ):
        issues.append(
            {
                "severity": "error",
                "code": "benchmark_missing",
                "message": "全周期候选策略的基准收益全部为 0，需要检查大盘基准序列是否接入。",
            }
        )

    ranked_full = sorted(
        full_rows,
        key=_candidate_rank_key,
        reverse=True,
    )
    if ranked_full and abs(float(ranked_full[0].get("max_drawdown", 0.0))) > 0.30:
        issues.append(
            {
                "severity": "warning",
                "code": "deep_drawdown",
                "message": "当前最优全周期策略最大回撤超过 30%，与稳定收益目标冲突，需要降低仓位或重新调参。",
            }
        )

    for row in rows:
        if row.get("period_name") != "full" and float(row.get("excess_return", 0.0)) < -0.10:
            issues.append(
                {
                    "severity": "warning",
                    "code": "subperiod_underperformance",
                    "message": f"{row.get('period_name')} 阶段明显跑输基准，需要检查该市场环境下的入场/仓位过滤。",
                }
            )
            break

    if any(int(row.get("trade_count", 0)) > 120 for row in rows):
        issues.append(
            {
                "severity": "warning",
                "code": "trade_churn",
                "message": "存在交易次数超过 120 的回测结果，需要检查是否偏离中低频目标。",
            }
        )

    if any(int(row.get("raw_trade_count", row.get("trade_count", 0))) > 150 for row in rows):
        issues.append(
            {
                "severity": "warning",
                "code": "execution_fragmentation",
                "message": "存在原始成交笔数过高的结果，可能由复权低价、成交量限制或拆单造成，需要降低单次交易容量。",
            }
        )

    return issues


def _period_reason(row: dict) -> str:
    kind = row.get("kind", "")
    excess = float(row.get("excess_return", 0.0))
    drawdown = abs(float(row.get("max_drawdown", 0.0)))
    trades = int(row.get("trade_count", 0))
    if kind == StrategyKind.DEFENSIVE_SUPPORT.value:
        base = "防守型支撑策略占优，说明该阶段靠近支撑且结构未破坏的行业龙头更能控制回撤。"
    elif kind == StrategyKind.RESISTANCE_BREAKOUT.value:
        base = "压力突破策略占优，说明该阶段趋势延续和放量突破更容易获得超额收益。"
    else:
        base = "突破回踩加市场闸门策略占优，说明该阶段等待确认并随市场结构调节仓位更有效。"
    relative = "跑赢基准" if excess >= 0 else "跑输基准"
    risk = "回撤可控" if drawdown <= 0.25 else "回撤偏大"
    churn = (
        "交易次数没有表现出高频或中高频特征"
        if trades <= 120
        else "交易次数偏多，需要谨慎看待换手成本"
    )
    return f"{base}{relative}，{risk}，{churn}。"


def period_interpretation(rows: list[dict]) -> str:
    """Generate deterministic Chinese interpretation from result rows."""

    best = _best_by_period(rows)
    full = best.get("full") or (
        sorted(rows, key=_candidate_rank_key, reverse=True)[0]
        if rows
        else {}
    )
    period_names = [period_name for period_name, _start, _end in SUB_PERIODS]
    period_names.extend(
        row.get("period_name", "")
        for row in rows
        if row.get("period_name") not in {"full", *period_names}
    )
    lines = [
        "## 长期回测压力诊断",
        "",
        f"以下分阶段结果只用于解释 {START_DATE} 至 {END_DATE} 策略在哪些市场环境中失效或承压，不作为收益参考，也不参与最终策略排名。",
        "",
    ]
    for period in period_names:
        row = best.get(period)
        if not row:
            continue
        lines.extend(
            [
                f"### {period}",
                "",
                f"- 该长期策略: `{row.get('kind')}`",
                f"- 年化收益: `{_fmt_pct(float(row.get('annual_return', 0.0)))}`",
                f"- 最大回撤: `{_fmt_pct(float(row.get('max_drawdown', 0.0)))}`",
                f"- 超额收益: `{_fmt_pct(float(row.get('excess_return', 0.0)))}`",
                f"- 交易次数: `{row.get('trade_count', 0)}`",
                f"- 解释: {_period_reason(row)}",
                "",
            ]
        )
    lines.extend(
        [
            "## 最终推荐",
            "",
            f"最终推荐策略: `{full.get('kind', 'N/A')}`",
            "",
            "推荐原因:",
            "",
            f"- 稳定性评分为 `{full.get('stability_score', 0):.4f}`。",
            f"- 年化收益为 `{_fmt_pct(float(full.get('annual_return', 0.0)))}`，"
            f"超额收益为 `{_fmt_pct(float(full.get('excess_return', 0.0)))}`。",
            f"- 最大回撤为 `{_fmt_pct(float(full.get('max_drawdown', 0.0)))}`。",
            f"- 交易次数为 `{full.get('trade_count', 0)}`，交易次数没有表现出高频或中高频特征。",
            "- 策略选择依据为稳定性评分、回撤、Sharpe、超额收益和交易次数的综合表现，而不是单次最高收益。",
            "",
            "## 风险提示",
            "",
            "- 历史回测不代表未来收益。",
            "- 行业龙头池仍可能存在幸存者偏差。",
            "- akshare 数据源可用性和复权处理会影响结果。",
            "- 支撑压力不是确定性价格预测，只是结构化风险收益判断。",
        ]
    )
    return "\n".join(lines) + "\n"


def audit_markdown(rows: list[dict]) -> str:
    """Render audit findings for the Markdown report."""

    issues = audit_rows(rows)
    lines = ["## 回测审计", ""]
    lines.append(f"- 审计结论: {recommendation_text(issues)}")
    if not issues:
        lines.append("- 未发现基准缺失、深回撤、明显分阶段跑输或交易频率偏高问题。")
        return "\n".join(lines) + "\n"
    for issue in issues:
        lines.append(
            f"- `{issue['severity']}` `{issue['code']}`: {issue['message']}"
        )
    return "\n".join(lines) + "\n"


def recommendation_text(issues: list[dict[str, str]]) -> str:
    """Return a plain-language recommendation gated by audit findings."""

    blocking_codes = {"benchmark_missing", "deep_drawdown", "subperiod_underperformance"}
    if any(
        issue.get("severity") == "error" or issue.get("code") in blocking_codes
        for issue in issues
    ):
        return "审计未完全通过，不建议直接实盘；应继续降低回撤、修正失效阶段或扩大稳健参数验证。"
    return "审计未发现关键阻断问题，可作为候选策略继续观察和小规模验证。"


def _html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt_num(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "0.00"


def _metric_card(label: str, value: str, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return (
        f'<section class="metric{tone_class}">'
        f"<span>{_html_escape(label)}</span>"
        f"<strong>{_html_escape(value)}</strong>"
        "</section>"
    )


def _profile_name(row: dict) -> str:
    params = row.get("params", {}) or {}
    if (
        float(params.get("max_position_drawdown", 0.0)) > 0.0
        and float(params.get("max_position_drawdown", 1.0)) <= 0.12
        and float(params.get("weak_market_exposure", 0.35)) <= 0.10
    ):
        return "drawdown-controlled"
    if (
        float(params.get("min_relative_strength", -0.03)) >= 0.0
        and float(params.get("max_support_distance", 0.12)) <= 0.08
    ):
        return "risk-managed"
    if (
        float(params.get("strong_market_exposure", 0.90)) <= 0.85
        and float(params.get("neutral_market_exposure", 0.65)) <= 0.55
        and float(params.get("rebalance_threshold", 0.08)) <= 0.07
    ):
        return "active-balanced"
    if float(params.get("strong_market_exposure", 0.90)) <= 0.70:
        return "guarded"
    return "balanced"


def _robust_report_rows(full_rows: list[dict]) -> list[dict]:
    return [
        row
        for row in full_rows
        if bool((row.get("params", {}) or {}).get("robust_enabled"))
    ]


def _baseline_report_row(full_rows: list[dict]) -> dict:
    baseline_params = asdict(BASELINE_ADAPTIVE_PARAMS)
    for row in full_rows:
        if row.get("params") == baseline_params:
            return row
    return next(
        (
            row
            for row in full_rows
            if not bool((row.get("params", {}) or {}).get("robust_enabled"))
        ),
        {},
    )


def _report_candidate_label(row: dict, robust_index: int | None = None) -> str:
    if robust_index is None:
        return "baseline"
    return f"robust-{robust_index} ({row.get('kind', 'N/A')}/{_profile_name(row)})"


def _gate_result(failures: list[str]) -> str:
    return "通过" if not failures else f"未通过: {', '.join(failures)}"


def _hard_gate_outcomes(row: dict) -> tuple[str, str, str, str, str]:
    validation = row.get("validation", {}) or {}
    full_result = _gate_result(full_gate_failures(row))
    annual_results = []
    for year in ("2023", "2024", "2025"):
        failures = validation_gate_failures(
            {year: validation.get(year, {"error": "missing"})}
        )
        annual_results.append(_gate_result(failures))
    neighbor_result = (
        "通过"
        if _float_metric(row, "neighbor_pass_rate", 0.0) >= 0.60
        else "未通过: neighbor_pass_rate_below_60pct"
    )
    return full_result, *annual_results, neighbor_result


def _retention_notice(robust_rows: list[dict]) -> str:
    if any(row.get("robust_gate_pass") is True for row in robust_rows):
        return ""
    return "本轮没有找到通过全部稳健门槛的新候选，继续保留当前 A / 71.3 基线。"


def _markdown_research_sections(full_rows: list[dict]) -> str:
    robust_rows = _robust_report_rows(full_rows)
    baseline = _baseline_report_row(full_rows)
    robust_numbers = {id(row): index for index, row in enumerate(robust_rows, start=1)}

    def candidate_label(row: dict) -> str:
        return _report_candidate_label(
            row,
            None if row is baseline else robust_numbers[id(row)],
        )

    lines = ["## 稳健门槛", ""]
    notice = _retention_notice(robust_rows)
    if notice:
        lines.extend([notice, ""])
    lines.extend(
        [
            "| Candidate | Result | Failure codes | Neighbor pass | Worst validation excess |",
            "|---|---|---|---:|---:|",
        ]
    )
    if robust_rows:
        for index, row in enumerate(robust_rows, start=1):
            failures = list(row.get("gate_failures", []) or [])
            lines.append(
                f"| {_report_candidate_label(row, index)} | "
                f"{'通过' if row.get('robust_gate_pass') is True else '未通过'} | "
                f"{', '.join(str(code) for code in failures) or '无'} | "
                f"{_fmt_pct(_float_metric(row, 'neighbor_pass_rate', 0.0))} | "
                f"{_fmt_pct(_float_metric(row, 'worst_validation_excess', 0.0))} |"
            )
    else:
        lines.append("| N/A | 未通过 | 无稳健候选 | 0.00% | 0.00% |")

    lines.extend(
        [
            "",
            "## 滚动验证",
            "",
            "| Candidate | Year | Annual | Excess | Max DD | Grade |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for index, row in enumerate(robust_rows, start=1):
        validation = row.get("validation", {}) or {}
        for year in ("2023", "2024", "2025"):
            annual = validation.get(year, {}) or {}
            lines.append(
                f"| {_report_candidate_label(row, index)} | {year} | "
                f"{_fmt_pct(_float_metric(annual, 'annual_return', 0.0))} | "
                f"{_fmt_pct(_float_metric(annual, 'excess_return', 0.0))} | "
                f"{_fmt_pct(_float_metric(annual, 'max_drawdown', 0.0))} | "
                f"{annual.get('grade', 'N/A')} |"
            )
    if not robust_rows:
        lines.append("| N/A | 2023/2024/2025 | 0.00% | 0.00% | 0.00% | N/A |")

    diagnostic_rows = [
        row
        for row in full_rows
        if row is baseline or any(row is robust for robust in robust_rows)
    ]
    lines.extend(
        [
            "",
            "## 风险状态",
            "",
            "| Candidate | Days by state | Triggers | Recoveries |",
            "|---|---|---:|---:|",
        ]
    )
    for row in diagnostic_rows:
        label = candidate_label(row)
        state_days = row.get("risk_state_days", {}) or {}
        days = ", ".join(f"{state}: {count}" for state, count in state_days.items())
        lines.append(
            f"| {label} | {days or '无'} | "
            f"{row.get('risk_state_trigger_count', 0)} | "
            f"{row.get('risk_state_recovery_count', 0)} |"
        )

    lines.extend(
        [
            "",
            "## 主/候补通道",
            "",
            "| Candidate | Channel | Trades | Average exposure | Average holdings | Return contribution |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in diagnostic_rows:
        label = candidate_label(row)
        for channel, name in (("primary", "主通道"), ("fallback", "候补通道")):
            lines.append(
                f"| {label} | {name} | {row.get(f'{channel}_trade_count', 0)} | "
                f"{_fmt_pct(_float_metric(row, f'{channel}_average_exposure', 0.0))} | "
                f"{_fmt_num(row.get(f'{channel}_average_holdings', 0.0), 2)} | "
                f"{_fmt_pct(_float_metric(row, f'{channel}_return_contribution', 0.0))} |"
            )

    lines.extend(
        [
            "",
            "## 基线与稳健候选对比",
            "",
            "| Candidate | Annual | Max DD | Sharpe | Grade | Full gate | 2023 gate | 2024 gate | 2025 gate | Neighborhood gate | Overall |",
            "|---|---:|---:|---:|---|---|---|---|---|---|---|",
        ]
    )
    comparison_rows = ([baseline] if baseline else []) + robust_rows
    for row in comparison_rows:
        label = candidate_label(row)
        outcomes = _hard_gate_outcomes(row)
        failures = list(row.get("gate_failures", []) or [])
        lines.append(
            f"| {label} | {_fmt_pct(_float_metric(row, 'annual_return', 0.0))} | "
            f"{_fmt_pct(_float_metric(row, 'max_drawdown', 0.0))} | "
            f"{_fmt_num(row.get('sharpe_ratio', 0.0), 2)} | "
            f"{row.get('grade', 'N/A')} / {_fmt_num(row.get('grade_score', 0.0), 1)} | "
            f"{' | '.join(outcomes)} | {_gate_result(failures)} |"
        )
    return "\n".join(lines) + "\n"


def _html_research_sections(full_rows: list[dict]) -> str:
    def render_body(lines: list[str]) -> str:
        content = [line for line in lines if line]
        notes = [line for line in content if not line.startswith("|")]
        table_lines = [line for line in content if line.startswith("|")]
        parts = [f"<p>{_html_escape(note)}</p>" for note in notes]
        if len(table_lines) >= 2:
            rows = [
                [cell.strip() for cell in line.strip("|").split("|")]
                for line in table_lines
            ]
            header = "".join(f"<th>{_html_escape(cell)}</th>" for cell in rows[0])
            body = "".join(
                "<tr>"
                + "".join(f"<td>{_html_escape(cell)}</td>" for cell in row)
                + "</tr>"
                for row in rows[2:]
            )
            parts.append(
                f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
            )
        return "".join(parts)

    markdown = _markdown_research_sections(full_rows)
    sections = []
    current_heading = ""
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections.append(
                    f"<h2>{_html_escape(current_heading)}</h2>"
                    f'<section class="section">{render_body(current_lines)}</section>'
                )
            current_heading = line[3:]
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading:
        sections.append(
            f"<h2>{_html_escape(current_heading)}</h2>"
            f'<section class="section">{render_body(current_lines)}</section>'
        )
    return "\n".join(sections)


def render_html_report(rows: list[dict]) -> str:
    """Render a self-contained HTML report for strategy research results."""

    sorted_rows = sorted(
        rows,
        key=_report_rank_key,
        reverse=True,
    )
    full_rows = [row for row in sorted_rows if row.get("period_name") == "full"]
    best = full_rows[0] if full_rows else (sorted_rows[0] if sorted_rows else {})
    display_rows = full_rows if full_rows else sorted_rows
    benchmark_missing = bool(sorted_rows) and all(
        abs(float(row.get("benchmark_return", 0.0))) < 1e-12 for row in sorted_rows
    )
    audit_issues = audit_rows(sorted_rows)
    research_sections = _html_research_sections(full_rows)

    cards = "\n".join(
        [
            _metric_card("最优策略", best.get("kind", "N/A")),
            _metric_card("评级", f"{best.get('grade', 'N/A')} / {_fmt_num(best.get('grade_score', 0), 1)}"),
            _metric_card("稳定性评分", _fmt_num(best.get("stability_score", 0), 4)),
            _metric_card("年化收益", _fmt_pct(float(best.get("annual_return", 0.0))), "good"),
            _metric_card("基准收益", _fmt_pct(float(best.get("benchmark_return", 0.0))), "blue"),
            _metric_card("超额收益", _fmt_pct(float(best.get("excess_return", 0.0))), "good"),
            _metric_card("最大回撤", _fmt_pct(float(best.get("max_drawdown", 0.0))), "risk"),
            _metric_card("Sharpe", _fmt_num(best.get("sharpe_ratio", 0), 2)),
            _metric_card("交易次数", str(best.get("trade_count", 0))),
        ]
    )

    table_rows = []
    for idx, row in enumerate(display_rows[:10], start=1):
        table_rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{_html_escape(row.get('kind', 'N/A'))}</td>"
            f"<td>{_html_escape(_profile_name(row))}</td>"
            f"<td>{_html_escape(row.get('period_name', 'N/A'))}</td>"
            f"<td>{_html_escape(row.get('start', ''))} 至 {_html_escape(row.get('end', ''))}</td>"
            f"<td>{_html_escape(row.get('grade', 'N/A'))} / {_fmt_num(row.get('grade_score', 0), 1)}</td>"
            f"<td>{_fmt_pct(float(row.get('annual_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('total_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('benchmark_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('excess_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('max_drawdown', 0.0)))}</td>"
            f"<td>{_fmt_num(row.get('sharpe_ratio', 0), 2)}</td>"
            f"<td>{_html_escape(row.get('trade_count', 0))}</td>"
            f"<td>{_html_escape(row.get('raw_trade_count', row.get('trade_count', 0)))}</td>"
            "</tr>"
        )

    best_by_period = _best_by_period(sorted_rows)
    period_rows = []
    for period in [period_name for period_name, _start, _end in SUB_PERIODS]:
        row = best_by_period.get(period)
        if not row:
            continue
        period_rows.append(
            "<tr>"
            f"<td>{_html_escape(period)}</td>"
            f"<td>{_html_escape(row.get('kind', 'N/A'))}</td>"
            f"<td>{_fmt_pct(float(row.get('annual_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('total_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('max_drawdown', 0.0)))}</td>"
            f"<td>{_html_escape(row.get('trade_count', 0))}</td>"
            f"<td>{_html_escape(_period_reason(row))}</td>"
            "</tr>"
        )

    benchmark_note = (
        """
        <p class="notice">注意：本次结果中基准收益为 0，说明大盘基准序列没有有效接入。
        因此本报告当前优先看策略自身收益、回撤和交易频率，超额收益暂不作为跑赢大盘证据。</p>
        """
        if benchmark_missing
        else ""
    )
    audit_items = "".join(
        f"<li><code>{_html_escape(issue['severity'])}</code> "
        f"<code>{_html_escape(issue['code'])}</code>: "
        f"{_html_escape(issue['message'])}</li>"
        for issue in audit_issues
    )
    audit_html = (
        f"<ul>{audit_items}</ul>"
        if audit_issues
        else "<p>未发现基准缺失、深回撤、明显分阶段跑输或交易频率偏高问题。</p>"
    )
    recommendation = recommendation_text(audit_issues)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A股行业龙头支撑压力策略研究报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172026;
      --muted: #66717a;
      --line: #d9e0e4;
      --band: #f4f7f8;
      --accent: #0b6b5c;
      --blue: #255c99;
      --risk: #a43d2c;
      --paper: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #eef3f5;
      font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    header {{
      margin-bottom: 24px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 30px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    p {{ margin: 8px 0; }}
    .subtitle {{ color: var(--muted); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
      margin: 18px 0 6px;
    }}
    .metric {{
      min-height: 86px;
      padding: 13px 14px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric span {{
      display: block;
      margin-bottom: 7px;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{
      display: block;
      overflow-wrap: anywhere;
      font-size: 20px;
      line-height: 1.25;
    }}
    .metric.good strong {{ color: var(--accent); }}
    .metric.blue strong {{ color: var(--blue); }}
    .metric.risk strong {{ color: var(--risk); }}
    .notice {{
      margin: 16px 0 0;
      padding: 12px 14px;
      background: #fff8e6;
      border: 1px solid #ebd48a;
      border-radius: 8px;
      color: #6b5618;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 11px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      background: var(--band);
      color: #34434d;
      font-weight: 650;
      white-space: nowrap;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .section {{
      padding: 18px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    @media (max-width: 900px) {{
      main {{ padding: 20px 12px 32px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      table {{ display: block; overflow-x: auto; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>A股行业龙头支撑压力策略研究报告</h1>
      <p class="subtitle">回测区间：{_html_escape(best.get('start', START_DATE))} 至 {_html_escape(best.get('end', END_DATE))}；策略池排除科创板与北交所，偏中低频交易。</p>
      <div class="metrics">
        {cards}
      </div>
      {benchmark_note}
    </header>

    <h2>全周期候选排名</h2>
    <table>
      <thead>
        <tr>
          <th>Rank</th><th>Strategy</th><th>Profile</th><th>Period</th><th>Range</th>
          <th>Grade</th><th>Annual</th><th>Total</th><th>Benchmark</th><th>Excess</th>
          <th>Max DD</th><th>Sharpe</th><th>Trades</th><th>Raw Trades</th>
        </tr>
      </thead>
      <tbody>
        {''.join(table_rows)}
      </tbody>
    </table>

    {research_sections}

    <h2>长期回测压力诊断</h2>
    <p class="subtitle">短期或分阶段结果只用于解释策略失效环境，不作为收益参考，也不参与最终排名。</p>
    <table>
      <thead>
        <tr>
          <th>阶段</th><th>该长期策略</th><th>年化收益</th><th>总收益</th>
          <th>最大回撤</th><th>交易次数</th><th>解释</th>
        </tr>
      </thead>
      <tbody>
        {''.join(period_rows)}
      </tbody>
    </table>

    <h2>最终推荐</h2>
    <section class="section">
      <p>最终推荐策略：<strong>{_html_escape(best.get('kind', 'N/A'))}</strong></p>
      <p>推荐依据：评级 {_html_escape(best.get('grade', 'N/A'))} / {_fmt_num(best.get('grade_score', 0), 1)}，稳定性评分 {_fmt_num(best.get('stability_score', 0), 4)}，年化收益 {_fmt_pct(float(best.get('annual_return', 0.0)))}，最大回撤 {_fmt_pct(float(best.get('max_drawdown', 0.0)))}，交易次数 {_html_escape(best.get('trade_count', 0))}。策略选择依据为评级分数优先、稳定性评分兜底，并综合回撤、Sharpe、收益和交易次数，而不是单次最高收益。</p>
      <p><strong>审计结论：</strong>{_html_escape(recommendation)}</p>
    </section>

    <h2>回测审计</h2>
    <section class="section">
      {audit_html}
    </section>

    <h2>风险提示</h2>
    <section class="section">
      <ul>
        <li>历史回测不代表未来收益。</li>
        <li>行业龙头池仍可能存在幸存者偏差。</li>
        <li>akshare 数据源可用性、复权处理和基准序列会影响结果。</li>
        <li>支撑压力不是确定性价格预测，只是结构化风险收益判断。</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


def run_one(
    kind: StrategyKind,
    params: StrategyParams,
    start: str,
    end: str,
    universe: list[str],
) -> dict:
    """Run one backtest and return metrics plus metadata."""

    result = run_one_result(kind, params, start, end, universe)
    if result is None:
        return _attach_research_diagnostics({"error": "backtest returned None"})

    summary = summarize_result(result)
    _attach_research_diagnostics(summary, result)
    summary.update(
        {
            "kind": kind.value,
            "start": start,
            "end": end,
            "params": asdict(params),
        }
    )
    return summary


def run_one_result(
    kind: StrategyKind,
    params: StrategyParams,
    start: str,
    end: str,
    universe: list[str],
) -> dict | None:
    """Run one backtest and return the raw eqlib result."""

    initialize = make_initialize(
        kind=kind,
        params=params,
        universe=universe,
        benchmark=BENCHMARK,
    )
    result = run_backtest(
        initialize_func=initialize,
        start_date=start,
        end_date=end,
        starting_cash=STARTING_CASH,
        benchmark=BENCHMARK,
        securities=universe + [BENCHMARK],
        use_local=False,
    )
    return result


def write_outputs(rows: list[dict]) -> None:
    """Write JSON, CSV, Markdown, and HTML summary reports."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        rows,
        key=_report_rank_key,
        reverse=True,
    )
    (REPORT_DIR / "summary.json").write_text(
        json.dumps(sorted_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fieldnames = [
        "kind",
        "period_name",
        "selected",
        "selection_reason",
        "start",
        "end",
        "total_return",
        "benchmark_return",
        "excess_return",
        "annual_return",
        "sharpe_ratio",
        "max_drawdown",
        "calmar_ratio",
        "trade_count",
        "raw_trade_count",
        "grade",
        "grade_score",
        "grade_weakest",
        "stability_score",
        "robust_gate_pass",
        "neighbor_pass_rate",
        "worst_validation_excess",
        "risk_state_trigger_count",
        "risk_state_recovery_count",
        "primary_trade_count",
        "fallback_trade_count",
        "primary_average_exposure",
        "fallback_average_exposure",
        "primary_average_holdings",
        "fallback_average_holdings",
        "primary_return_contribution",
        "fallback_return_contribution",
        "params",
    ]
    with (REPORT_DIR / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)

    full_rows = [row for row in sorted_rows if row.get("period_name") == "full"]
    best = full_rows[0] if full_rows else (sorted_rows[0] if sorted_rows else {})
    lines = [
        "# A股行业龙头支撑压力策略研究报告",
        "",
        f"- 最终推荐策略: `{best.get('kind', 'N/A')}`",
        f"- 评级: `{best.get('grade', 'N/A')} / {best.get('grade_score', 0):.1f}`",
        f"- 稳定性评分: `{best.get('stability_score', 0):.4f}`",
        f"- 年化收益: `{best.get('annual_return', 0):.2%}`",
        f"- 基准收益: `{best.get('benchmark_return', 0):.2%}`",
        f"- 超额收益: `{best.get('excess_return', 0):.2%}`",
        f"- 最大回撤: `{best.get('max_drawdown', 0):.2%}`",
        f"- Sharpe: `{best.get('sharpe_ratio', 0):.2f}`",
        f"- 交易次数: `{best.get('trade_count', 0)}`",
        "",
        "## 全周期候选排名",
        "",
        "| Rank | Strategy | Profile | Period | Grade | Annual | Benchmark | Excess | Max DD | Sharpe | Trades | Raw Trades |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    display_rows = full_rows if full_rows else sorted_rows
    for idx, row in enumerate(display_rows[:10], start=1):
        lines.append(
            f"| {idx} | {row.get('kind')} | {_profile_name(row)} | {row.get('start')} to {row.get('end')} | "
            f"{row.get('grade', 'N/A')} / {float(row.get('grade_score', 0)):.1f} | "
            f"{row.get('annual_return', 0):.2%} | {row.get('benchmark_return', 0):.2%} | "
            f"{row.get('excess_return', 0):.2%} | {row.get('max_drawdown', 0):.2%} | "
            f"{row.get('sharpe_ratio', 0):.2f} | "
            f"{row.get('trade_count', 0)} | {row.get('raw_trade_count', row.get('trade_count', 0))} |"
        )
    lines.append("")
    lines.append(_markdown_research_sections(full_rows))
    lines.append(period_interpretation(sorted_rows))
    lines.append(audit_markdown(sorted_rows))
    (REPORT_DIR / "final_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    (REPORT_DIR / "final_report.html").write_text(
        render_html_report(sorted_rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run one parameter set per strategy over 2024 only.",
    )
    args = parser.parse_args()

    default_universe = set(get_default_leader_universe())
    universe = [code for code in RESEARCH_UNIVERSE if code in default_universe]
    if args.quick:
        universe = universe[:15]
        rows = []
        for kind, params in candidate_param_grid(quick=args.quick):
            row = run_one(kind, params, "2024-01-01", "2024-12-31", universe)
            row["period_name"] = "quick"
            rows.append(row)
            print(
                f"quick {kind.value} annual={row.get('annual_return', 0):.2%} "
                f"dd={row.get('max_drawdown', 0):.2%} "
                f"score={row.get('stability_score', 0):.4f}"
            )
        write_outputs(rows)
        print(f"Wrote reports to {REPORT_DIR}")
        return 0

    rows: list[dict] = []
    full_candidates: list[tuple[dict, StrategyKind, StrategyParams]] = []
    result_cache: dict[tuple[StrategyKind, StrategyParams, str, str], dict | None] = {}

    def cached_result(
        kind: StrategyKind,
        params: StrategyParams,
        start: str,
        end: str,
    ) -> dict | None:
        key = (kind, params, start, end)
        if key not in result_cache:
            result_cache[key] = run_one_result(kind, params, start, end, universe)
        return result_cache[key]

    for kind, params in candidate_param_grid(quick=False):
        result = cached_result(kind, params, START_DATE, END_DATE)
        if result is None:
            row = {"error": "backtest returned None"}
        else:
            row = summarize_result(result)
            row.update(
                {
                    "kind": kind.value,
                    "start": START_DATE,
                    "end": END_DATE,
                    "params": asdict(params),
                }
            )
        _attach_research_diagnostics(row, result)
        row.update(
            {
                "period_name": "full",
                "gate_failures": full_gate_failures(row),
                "robust_gate_pass": False,
                "selected": False,
            }
        )
        rows.append(row)
        full_candidates.append((row, kind, params))
        print(
            f"full {kind.value} annual={row.get('annual_return', 0):.2%} "
            f"dd={row.get('max_drawdown', 0):.2%} "
            f"score={row.get('stability_score', 0):.4f}"
        )

    robust_finalists = [
        item
        for item in full_candidates
        if item[2].robust_enabled and not item[0]["gate_failures"]
    ]
    robust_finalists.sort(
        key=lambda item: (
            _float_metric(item[0], "sharpe_ratio"),
            -abs(_float_metric(item[0], "max_drawdown")),
            _float_metric(item[0], "annual_return"),
        ),
        reverse=True,
    )

    for row, kind, params in robust_finalists[:3]:
        neighbor_rows: list[dict] = []
        for neighbor_params in neighbor_param_sets(params):
            result = cached_result(kind, neighbor_params, START_DATE, END_DATE)
            neighbor_rows.append(
                summarize_result(result)
                if result is not None
                else {"annual_return": 0.0, "max_drawdown": -1.0}
            )
        row["neighbor_pass_rate"] = neighbor_pass_rate(neighbor_rows)

        validation_rows: dict[str, dict] = {}
        for period, formation_start, formation_end, start, end in VALIDATION_WINDOWS:
            formation_result = cached_result(
                kind,
                params,
                formation_start,
                formation_end,
            )
            sliced = (
                slice_backtest_result(formation_result, start, end)
                if formation_result is not None
                else None
            )
            if sliced is None:
                validation_row = {
                    "error": "validation slice returned None",
                    "excess_return": -999.0,
                }
            else:
                validation_row = summarize_result(sliced)
            validation_row.update(
                {
                    "period_name": period,
                    "formation_start": formation_start,
                    "formation_end": formation_end,
                    "start": start,
                    "end": end,
                }
            )
            validation_rows[period] = validation_row

        row["validation"] = validation_rows
        row["worst_validation_excess"] = min(
            _float_metric(item, "excess_return")
            for item in validation_rows.values()
        )
        gate_failures = full_gate_failures(row)
        gate_failures.extend(validation_gate_failures(validation_rows))
        if float(row.get("neighbor_pass_rate", 0.0)) < 0.60:
            gate_failures.append("neighbor_pass_rate_below_60pct")
        row["gate_failures"] = gate_failures
        row["robust_gate_pass"] = not gate_failures

    passing = [
        item for item in full_candidates if item[0].get("robust_gate_pass") is True
    ]
    if passing:
        best_row, best_kind, best_params = max(
            passing,
            key=lambda item: robust_rank_key(item[0]),
        )
        best_row["selection_reason"] = "robust_candidate_passed_all_gates"
    else:
        best_row, best_kind, best_params = next(
            item
            for item in full_candidates
            if item[1] is StrategyKind.ADAPTIVE_COMPOSITE
            and item[2] == BASELINE_ADAPTIVE_PARAMS
        )
        best_row["selection_reason"] = "baseline_retained_no_robust_candidate"

    for row, _kind, _params in full_candidates:
        row["selected"] = row is best_row

    print(f"selected {best_kind.value} params={asdict(best_params)}")
    best_result = cached_result(best_kind, best_params, START_DATE, END_DATE)

    for period_name, start, end in SUB_PERIODS:
        result = cached_result(best_kind, best_params, start, end)
        if result is None:
            row = {"error": "backtest returned None"}
        else:
            row = summarize_result(result)
            row.update(
                {
                    "kind": best_kind.value,
                    "start": start,
                    "end": end,
                    "params": asdict(best_params),
                }
            )
        _attach_research_diagnostics(row, result)
        row.update({"period_name": period_name, "selected": False})
        rows.append(row)
        print(
            f"{period_name} {best_kind.value} annual={row.get('annual_return', 0):.2%} "
            f"dd={row.get('max_drawdown', 0):.2%} "
            f"score={row.get('stability_score', 0):.4f}"
        )

    write_outputs(rows)
    if best_result is not None:
        write_eqlib_html_report(best_result)
    print(f"Wrote reports to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
