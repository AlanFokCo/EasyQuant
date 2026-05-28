from __future__ import annotations

"""Platform comparison tools for validating backtest consistency.

This module is intentionally self-contained so it can compare the result
returned by ``run_backtest()`` with outputs from external platforms such as
JoinQuant without importing the rest of ``eqlib``.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BenchmarkAlignResult:
    """Result of benchmark-series alignment analysis."""

    correlation: float
    max_deviation_pct: float
    mean_deviation_pct: float
    is_aligned: bool
    details: str


@dataclass(frozen=True)
class MetricComparison:
    """Comparison output for one metric."""

    metric_name: str
    local_value: float
    platform_value: float
    abs_diff: float
    relative_diff_pct: float


@dataclass(frozen=True)
class MetricsComparisonResult:
    """Aggregate comparison across a set of strategy metrics."""

    comparisons: list[MetricComparison]
    max_deviation_pct: float
    judgment: str


@dataclass(frozen=True)
class ComparisonResult:
    """Overall comparison result against an external platform."""

    platform_name: str
    metric_comparisons: list[MetricComparison]
    equity_correlation: Optional[float]
    judgment: str


@dataclass(frozen=True)
class TradeVerificationResult:
    """Trade-level consistency verification output."""

    matched_count: int
    unmatched_local: list[dict[str, Any]]
    unmatched_platform: list[dict[str, Any]]
    price_discrepancies: list[dict[str, Any]]
    is_consistent: bool


class ComparisonJudgment:
    """Judgment labels used across platform-comparison helpers."""

    RESULT_ALIGNED = "关键指标差异 < 5%，结果可信"
    RESULT_ACCEPTABLE = "关键指标差异 5-15%，可能为设置差异"
    RESULT_SUSPICIOUS = "关键指标差异 > 15%，建议核查"
    RESULT_MISMATCHED = "交易记录不一致，可能存在逻辑问题"

    @classmethod
    def from_deviation(cls, max_deviation_pct: Optional[float]) -> str:
        """Infer a judgment from the largest relative deviation."""
        if max_deviation_pct is None or not np.isfinite(max_deviation_pct):
            return cls.RESULT_SUSPICIOUS
        if max_deviation_pct < 5.0:
            return cls.RESULT_ALIGNED
        if max_deviation_pct <= 15.0:
            return cls.RESULT_ACCEPTABLE
        return cls.RESULT_SUSPICIOUS


@dataclass
class ComparisonReport:
    """Structured report combining multiple comparison perspectives."""

    benchmark_alignment: Optional[BenchmarkAlignResult] = None
    metrics_comparison: Optional[MetricsComparisonResult] = None
    trade_verification: Optional[TradeVerificationResult] = None
    comparison_result: Optional[ComparisonResult] = None
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a concise human-readable summary."""
        parts: list[str] = []

        if self.comparison_result is not None:
            parts.append(
                f"platform={self.comparison_result.platform_name}; judgment={self.comparison_result.judgment}"
            )
            if self.comparison_result.equity_correlation is not None:
                parts.append(f"equity_corr={self.comparison_result.equity_correlation:.4f}")

        if self.metrics_comparison is not None:
            parts.append(f"metric_max_dev={self.metrics_comparison.max_deviation_pct:.2f}%")

        if self.benchmark_alignment is not None:
            parts.append(
                "benchmark="
                f"{'aligned' if self.benchmark_alignment.is_aligned else 'not aligned'}"
                f"(corr={self.benchmark_alignment.correlation:.4f}, "
                f"max_dev={self.benchmark_alignment.max_deviation_pct:.2f}%)"
            )

        if self.trade_verification is not None:
            parts.append(
                "trades="
                f"{'consistent' if self.trade_verification.is_consistent else 'inconsistent'}"
                f"(matched={self.trade_verification.matched_count}, "
                f"local_unmatched={len(self.trade_verification.unmatched_local)}, "
                f"platform_unmatched={len(self.trade_verification.unmatched_platform)}, "
                f"price_issues={len(self.trade_verification.price_discrepancies)})"
            )

        if self.notes:
            parts.append("notes=" + "; ".join(self.notes))

        return " | ".join(parts) if parts else "No comparison results available."


def _extract_daily_returns(backtest_result: Mapping[str, Any]) -> pd.Series:
    """Extract daily return series from a ``run_backtest`` result."""
    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)
    values = pd.Series({r["date"]: r["total_value"] for r in recorded}).sort_index()
    return values.pct_change().dropna()


def _extract_metrics_from_result(backtest_result: Mapping[str, Any]) -> dict[str, float]:
    """Compute comparable headline metrics from a backtest result."""
    returns = _extract_daily_returns(backtest_result)
    if len(returns) < 2:
        return {}

    total_return = float((1 + returns).prod() - 1)
    n_years = len(returns) / 252
    annual_return = float((1 + total_return) ** (1 / max(n_years, 0.01)) - 1)
    std = float(returns.std())
    sharpe = float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    cumulative = (1 + returns).cumprod()
    max_dd = float(((cumulative - cumulative.cummax()) / cumulative.cummax()).min())
    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
    }


def _normalize_indexed_series(series: Optional[pd.Series]) -> pd.Series:
    """Coerce a series into a numeric time-indexed series."""
    if series is None:
        return pd.Series(dtype=float)
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    if series.empty:
        return pd.Series(dtype=float)

    normalized = pd.Series(series.copy(), dtype=float)
    try:
        normalized.index = pd.to_datetime(normalized.index)
    except Exception:
        normalized.index = pd.Index(normalized.index)
    normalized = normalized.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    return normalized


def _extract_daily_values(backtest_result: Mapping[str, Any]) -> pd.Series:
    """Extract total-value equity curve from backtest result."""
    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)

    values: dict[pd.Timestamp, float] = {}
    for row in recorded:
        if row.get("date") is None or row.get("total_value") is None:
            continue
        try:
            values[pd.Timestamp(row["date"])] = float(row["total_value"])
        except (TypeError, ValueError):
            continue
    if not values:
        return pd.Series(dtype=float)
    return pd.Series(values).sort_index()


def _filter_series_by_date(
    series: pd.Series,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
) -> pd.Series:
    if series.empty:
        return series
    filtered = series
    if start_date is not None:
        filtered = filtered[filtered.index >= pd.Timestamp(start_date)]
    if end_date is not None:
        filtered = filtered[filtered.index <= pd.Timestamp(end_date)]
    return filtered


def _normalize_curve(series: pd.Series) -> pd.Series:
    if series.empty:
        return series.astype(float)
    first = float(series.iloc[0])
    if np.isclose(first, 0.0):
        scale = float(np.nanmean(np.abs(series.to_numpy(dtype=float))))
        if not np.isfinite(scale) or np.isclose(scale, 0.0):
            scale = 1.0
        return series.astype(float) / scale
    return series.astype(float) / first


def _safe_relative_diff_pct(local_value: float, platform_value: float) -> float:
    base = max(abs(float(platform_value)), 1e-12)
    return float(abs(local_value - platform_value) / base * 100.0)


def _series_correlation(left: pd.Series, right: pd.Series) -> float:
    if len(left) < 2 or len(right) < 2:
        return float("nan")
    corr = float(left.corr(right))
    if np.isfinite(corr):
        return corr
    left_values = left.to_numpy(dtype=float)
    right_values = right.to_numpy(dtype=float)
    if np.allclose(left_values, right_values, equal_nan=True):
        return 1.0
    return float("nan")


def align_benchmark(
    local_benchmark: pd.Series,
    platform_benchmark: pd.Series,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
) -> BenchmarkAlignResult:
    """Compare two benchmark series and assess whether they are aligned."""
    local_series = _filter_series_by_date(_normalize_indexed_series(local_benchmark), start_date, end_date)
    platform_series = _filter_series_by_date(_normalize_indexed_series(platform_benchmark), start_date, end_date)

    if local_series.empty or platform_series.empty:
        return BenchmarkAlignResult(
            correlation=float("nan"),
            max_deviation_pct=float("nan"),
            mean_deviation_pct=float("nan"),
            is_aligned=False,
            details="One or both benchmark series are empty after filtering.",
        )

    aligned = pd.concat([local_series.rename("local"), platform_series.rename("platform")], axis=1, join="inner").dropna()
    if len(aligned) < 2:
        return BenchmarkAlignResult(
            correlation=float("nan"),
            max_deviation_pct=float("nan"),
            mean_deviation_pct=float("nan"),
            is_aligned=False,
            details="Not enough overlapping benchmark observations to compare.",
        )

    local_curve = _normalize_curve(aligned["local"])
    platform_curve = _normalize_curve(aligned["platform"])
    correlation = _series_correlation(local_curve, platform_curve)

    base = platform_curve.abs().replace(0.0, np.nan)
    deviation_pct = ((local_curve - platform_curve).abs() / base * 100.0).replace([np.inf, -np.inf], np.nan)
    max_deviation_pct = float(deviation_pct.max()) if not deviation_pct.dropna().empty else 0.0
    mean_deviation_pct = float(deviation_pct.mean()) if not deviation_pct.dropna().empty else 0.0
    is_aligned = bool(np.isfinite(correlation) and correlation > 0.99 and max_deviation_pct < 1.0)
    details = (
        f"Compared {len(aligned)} overlapping points from {aligned.index.min().date()} to {aligned.index.max().date()}; "
        f"correlation={correlation:.4f}, max deviation={max_deviation_pct:.2f}%, mean deviation={mean_deviation_pct:.2f}%."
    )
    return BenchmarkAlignResult(
        correlation=correlation,
        max_deviation_pct=max_deviation_pct,
        mean_deviation_pct=mean_deviation_pct,
        is_aligned=is_aligned,
        details=details,
    )


def compare_metrics(
    local_metrics: Mapping[str, float],
    platform_metrics: Mapping[str, float],
) -> MetricsComparisonResult:
    """Compare common metrics between local and platform results."""
    comparisons: list[MetricComparison] = []
    common_keys = sorted(set(local_metrics) & set(platform_metrics))

    for key in common_keys:
        local_value = local_metrics.get(key)
        platform_value = platform_metrics.get(key)
        if local_value is None or platform_value is None:
            continue
        try:
            local_float = float(local_value)
            platform_float = float(platform_value)
        except (TypeError, ValueError):
            continue
        if not (np.isfinite(local_float) and np.isfinite(platform_float)):
            continue

        abs_diff = float(abs(local_float - platform_float))
        comparisons.append(
            MetricComparison(
                metric_name=key,
                local_value=local_float,
                platform_value=platform_float,
                abs_diff=abs_diff,
                relative_diff_pct=_safe_relative_diff_pct(local_float, platform_float),
            )
        )

    max_deviation_pct = (
        float(max(item.relative_diff_pct for item in comparisons)) if comparisons else float("nan")
    )
    judgment = ComparisonJudgment.from_deviation(max_deviation_pct)
    return MetricsComparisonResult(
        comparisons=comparisons,
        max_deviation_pct=max_deviation_pct,
        judgment=judgment,
    )


def _trade_key(trade: Mapping[str, Any]) -> tuple[pd.Timestamp, str, str]:
    date_val = trade.get("date")
    if date_val is None:
        raise ValueError("Trade record missing required 'date' field")
    return (
        pd.Timestamp(date_val).normalize(),
        str(trade.get("security", "")).strip(),
        str(trade.get("type", "")).strip().upper(),
    )


def _sort_trade_bucket(trades: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    def _sort_key(trade: Mapping[str, Any]) -> tuple[float, float]:
        amount = trade.get("amount", 0)
        price = trade.get("price", 0)
        try:
            return float(amount), float(price)
        except (TypeError, ValueError):
            return 0.0, 0.0

    return sorted(trades, key=_sort_key)


def verify_trades(
    local_trades: list[dict[str, Any]],
    platform_trades: list[dict[str, Any]],
    price_tolerance: float = 0.01,
) -> TradeVerificationResult:
    """Match and compare trades between local and platform records."""
    local_groups: dict[tuple[pd.Timestamp, str, str], list[dict[str, Any]]] = {}
    platform_groups: dict[tuple[pd.Timestamp, str, str], list[dict[str, Any]]] = {}

    for trade in local_trades or []:
        if trade.get("date") is None:
            continue
        local_groups.setdefault(_trade_key(trade), []).append(dict(trade))
    for trade in platform_trades or []:
        if trade.get("date") is None:
            continue
        platform_groups.setdefault(_trade_key(trade), []).append(dict(trade))

    matched_count = 0
    unmatched_local: list[dict[str, Any]] = []
    unmatched_platform: list[dict[str, Any]] = []
    price_discrepancies: list[dict[str, Any]] = []

    all_keys = sorted(set(local_groups) | set(platform_groups))
    for key in all_keys:
        local_bucket = _sort_trade_bucket(local_groups.get(key, []))
        platform_bucket = _sort_trade_bucket(platform_groups.get(key, []))
        pair_count = min(len(local_bucket), len(platform_bucket))

        for idx in range(pair_count):
            local_trade = local_bucket[idx]
            platform_trade = platform_bucket[idx]
            matched_count += 1

            try:
                local_price = float(local_trade.get("price", 0.0))
                platform_price = float(platform_trade.get("price", 0.0))
            except (TypeError, ValueError):
                local_price = 0.0
                platform_price = 0.0

            if np.isclose(platform_price, 0.0):
                deviation_pct = 0.0 if np.isclose(local_price, platform_price) else float("inf")
            else:
                deviation_pct = abs(local_price - platform_price) / abs(platform_price)

            amounts_match = local_trade.get("amount") == platform_trade.get("amount")
            if deviation_pct > price_tolerance or not amounts_match:
                price_discrepancies.append(
                    {
                        "date": key[0],
                        "security": key[1],
                        "type": key[2],
                        "local_price": local_price,
                        "platform_price": platform_price,
                        "local_amount": local_trade.get("amount"),
                        "platform_amount": platform_trade.get("amount"),
                        "deviation_pct": float(deviation_pct * 100.0) if np.isfinite(deviation_pct) else float("inf"),
                        "reason": "amount_mismatch" if not amounts_match and deviation_pct <= price_tolerance else "price_mismatch",
                    }
                )

        unmatched_local.extend(local_bucket[pair_count:])
        unmatched_platform.extend(platform_bucket[pair_count:])

    is_consistent = not unmatched_local and not unmatched_platform and not price_discrepancies
    return TradeVerificationResult(
        matched_count=matched_count,
        unmatched_local=unmatched_local,
        unmatched_platform=unmatched_platform,
        price_discrepancies=price_discrepancies,
        is_consistent=is_consistent,
    )


def compare_with_platform(
    local_result: Mapping[str, Any],
    platform_result: Mapping[str, Any],
    platform_name: str = "External",
) -> ComparisonResult:
    """Compare local backtest output with an external platform result."""
    local_metrics = _extract_metrics_from_result(local_result)
    platform_metrics = {
        key: float(value)
        for key in ("total_return", "sharpe_ratio", "max_drawdown", "annual_return")
        if (value := platform_result.get(key)) is not None
    }
    metrics_result = compare_metrics(local_metrics, platform_metrics)

    equity_correlation: Optional[float] = None
    platform_daily_values = platform_result.get("daily_values")
    if isinstance(platform_daily_values, pd.Series):
        local_values = _extract_daily_values(local_result)
        platform_values = _normalize_indexed_series(platform_daily_values)
        aligned_values = pd.concat(
            [
                _normalize_curve(local_values).rename("local"),
                _normalize_curve(platform_values).rename("platform"),
            ],
            axis=1,
            join="inner",
        ).dropna()
        if len(aligned_values) >= 2:
            equity_correlation = _series_correlation(aligned_values["local"], aligned_values["platform"])

    judgment = metrics_result.judgment
    if not metrics_result.comparisons and equity_correlation is None:
        judgment = ComparisonJudgment.RESULT_SUSPICIOUS
    elif equity_correlation is not None:
        if np.isfinite(equity_correlation) and equity_correlation < 0.90:
            judgment = ComparisonJudgment.RESULT_SUSPICIOUS
        elif np.isfinite(equity_correlation) and equity_correlation < 0.97 and judgment == ComparisonJudgment.RESULT_ALIGNED:
            judgment = ComparisonJudgment.RESULT_ACCEPTABLE

    return ComparisonResult(
        platform_name=platform_name,
        metric_comparisons=metrics_result.comparisons,
        equity_correlation=equity_correlation,
        judgment=judgment,
    )


__all__ = [
    "BenchmarkAlignResult",
    "ComparisonJudgment",
    "ComparisonReport",
    "ComparisonResult",
    "MetricComparison",
    "MetricsComparisonResult",
    "TradeVerificationResult",
    "align_benchmark",
    "compare_metrics",
    "compare_with_platform",
    "verify_trades",
]
