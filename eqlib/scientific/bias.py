"""Heuristic bias detection utilities for backtest result analysis.

This module is intentionally self-contained so it can be imported without
pulling in the broader ``eqlib`` package graph.  The checks here are heuristic:
they do not prove a bias exists, but they can flag suspicious patterns that
warrant manual review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import numpy as np
import pandas as pd


class BiasSeverity(IntEnum):
    """Severity scale for bias warnings."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BiasCheckResult:
    """Structured result from a single bias check."""

    bias_type: str
    severity: BiasSeverity
    detected: bool
    details: str
    recommendations: list[str] = field(default_factory=list)


@dataclass
class BiasReport:
    """Aggregate report across multiple bias checks."""

    checks: list[BiasCheckResult]
    overall_severity: BiasSeverity = field(init=False)
    has_critical: bool = field(init=False)

    def __post_init__(self) -> None:
        severities = [check.severity for check in self.checks] or [BiasSeverity.NONE]
        self.overall_severity = max(severities)
        self.has_critical = any(sev == BiasSeverity.CRITICAL for sev in severities)

    def summary(self) -> str:
        """Return a human-readable report summary."""
        lines = [
            f"Overall severity: {self.overall_severity.name}",
            f"Critical bias detected: {'yes' if self.has_critical else 'no'}",
        ]
        if not self.checks:
            lines.append("No bias checks were run.")
            return "\n".join(lines)

        for check in self.checks:
            status = "DETECTED" if check.detected else "clear"
            lines.append(
                f"- {check.bias_type}: {check.severity.name} ({status}) - {check.details}"
            )
        return "\n".join(lines)


class SurvivorshipCorrectedData:
    def __init__(self, start_date: Any, end_date: Any):
        self.start_date = start_date
        self.end_date = end_date
        self.note = (
            "Survivorship correction requires historical delisted stock data. "
            "Use with caution."
        )


class _SeverityAccumulator:
    """Small helper for combining heuristic signals into one result."""

    def __init__(self) -> None:
        self.severity = BiasSeverity.NONE
        self.findings: list[str] = []
        self.recommendations: list[str] = []

    def add(
        self,
        severity: BiasSeverity,
        detail: str,
        recommendation: Optional[str] = None,
    ) -> None:
        self.severity = max(self.severity, severity)
        self.findings.append(detail)
        if recommendation and recommendation not in self.recommendations:
            self.recommendations.append(recommendation)

    def build(self, bias_type: str, default_detail: str) -> BiasCheckResult:
        return BiasCheckResult(
            bias_type=bias_type,
            severity=self.severity,
            detected=self.severity > BiasSeverity.NONE,
            details=" ".join(self.findings) if self.findings else default_detail,
            recommendations=self.recommendations,
        )


DATE_COLUMNS = ("date", "datetime", "trade_date")
OHLC_COLUMNS = ("open", "high", "low", "close")


def _not_enough_data(bias_type: str, extra: str = "") -> BiasCheckResult:
    detail = "Not enough data to assess bias reliably."
    if extra:
        detail = f"{detail} {extra}".strip()
    return BiasCheckResult(
        bias_type=bias_type,
        severity=BiasSeverity.NONE,
        detected=False,
        details=detail,
        recommendations=["Collect a longer and more complete backtest history before relying on this check."],
    )


def _to_timestamp(value: Any) -> pd.Timestamp:
    """Convert a date-like value to a normalized pandas timestamp."""
    return pd.Timestamp(value).normalize()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _as_date_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy indexed by normalized dates when possible."""
    if frame.empty:
        return frame.copy()

    df = frame.copy()
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = df.index.normalize()
        return df

    for col in DATE_COLUMNS:
        if col in df.columns:
            df.index = pd.to_datetime(df[col]).normalize()
            return df

    return df


def _find_bar_for_date(frame: pd.DataFrame, trade_date: Any) -> Optional[pd.Series]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None

    df = _as_date_index(frame)
    ts = _to_timestamp(trade_date)
    if ts in df.index:
        row = df.loc[ts]
        if isinstance(row, pd.DataFrame):
            return row.iloc[-1]
        return row
    return None


def _business_day_count(start: pd.Timestamp, end: pd.Timestamp) -> int:
    try:
        return len(pd.bdate_range(start, end))
    except Exception:
        return max((end - start).days + 1, 0)


def _first_available_date(data: Any) -> Optional[pd.Timestamp]:
    if isinstance(data, pd.DataFrame) and not data.empty:
        df = _as_date_index(data)
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
            return pd.Timestamp(df.index.min()).normalize()
    return None


def _coerce_stock_pool(stock_pool: Any) -> tuple[list[str], dict[str, Any]]:
    """Normalize stock_pool into security identifiers plus optional metadata."""
    if stock_pool is None:
        return [], {}

    if isinstance(stock_pool, Mapping):
        return [str(sec) for sec in stock_pool.keys()], dict(stock_pool)

    securities: list[str] = []
    metadata: dict[str, Any] = {}
    if isinstance(stock_pool, Iterable) and not isinstance(stock_pool, (str, bytes)):
        for idx, item in enumerate(stock_pool):
            if isinstance(item, Mapping):
                sec = str(item.get("security") or item.get("symbol") or item.get("code") or idx)
                securities.append(sec)
                metadata[sec] = item
            else:
                sec = str(item)
                securities.append(sec)
                metadata[sec] = item
    else:
        securities = [str(stock_pool)]
        metadata = {str(stock_pool): stock_pool}
    return securities, metadata


def _extract_trade_dates(backtest_result: Optional[Mapping[str, Any]]) -> pd.Series:
    trades = [] if backtest_result is None else backtest_result.get("trade_log", [])
    if not trades:
        return pd.Series(dtype="datetime64[ns]")
    dates = [pd.Timestamp(t.get("date")) for t in trades if t.get("date") is not None]
    if not dates:
        return pd.Series(dtype="datetime64[ns]")
    return pd.Series(pd.to_datetime(dates)).dt.normalize()


def _extract_total_values(backtest_result: Optional[Mapping[str, Any]]) -> pd.Series:
    recorded = [] if backtest_result is None else backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)

    values: dict[pd.Timestamp, float] = {}
    for row in recorded:
        if row.get("date") is None or row.get("total_value") is None:
            continue
        price = _safe_float(row.get("total_value"))
        if np.isnan(price):
            continue
        values[_to_timestamp(row["date"])] = price
    if not values:
        return pd.Series(dtype=float)
    return pd.Series(values).sort_index()


def _context_period_days(backtest_result: Optional[Mapping[str, Any]]) -> Optional[int]:
    context = None if backtest_result is None else backtest_result.get("context")
    if context is None:
        return None

    start = getattr(context, "start_date", None)
    end = getattr(context, "end_date", None)
    if start is None or end is None:
        return None
    return int((_to_timestamp(end) - _to_timestamp(start)).days) + 1


def _consistent_extreme_returns(returns: pd.Series, threshold: float = 0.20) -> int:
    if returns.empty:
        return 0
    mask = returns.abs() > threshold
    if not mask.any():
        return 0
    count = int(mask.sum())
    fraction = count / max(len(returns), 1)
    return count if count >= 2 or fraction >= 0.10 else 0


def _best_severity(count: int, medium_cutoff: int = 1, high_cutoff: int = 3) -> BiasSeverity:
    if count >= high_cutoff:
        return BiasSeverity.HIGH
    if count >= medium_cutoff:
        return BiasSeverity.MEDIUM
    return BiasSeverity.LOW if count > 0 else BiasSeverity.NONE


def _read_strategy_text(strategy_file: Optional[str]) -> str:
    if not strategy_file:
        return ""
    try:
        return Path(strategy_file).read_text(encoding="utf-8")
    except OSError:
        return ""


def _coerce_data_usage_log(data_usage_log: Any) -> str:
    if data_usage_log is None:
        return ""
    if isinstance(data_usage_log, str):
        return data_usage_log
    if isinstance(data_usage_log, Iterable):
        return "\n".join(str(item) for item in data_usage_log)
    return str(data_usage_log)


def _finalize_check(acc: _SeverityAccumulator, bias_type: str, ok_detail: str) -> BiasCheckResult:
    result = acc.build(bias_type=bias_type, default_detail=ok_detail)
    if not result.recommendations and result.detected:
        result.recommendations = ["Review the backtest assumptions and rerun with stricter data handling controls."]
    return result


def _extract_daily_returns(backtest_result: Mapping[str, Any]) -> pd.Series:
    import pandas as pd

    recorded = backtest_result.get("recorded_values", [])
    if not recorded:
        return pd.Series(dtype=float)
    values = pd.Series(
        {_to_timestamp(r["date"]): r["total_value"] for r in recorded if "date" in r and "total_value" in r}
    ).sort_index()
    returns = values.pct_change().dropna()
    return returns


def check_survivorship_bias(
    stock_pool: Any,
    start_date: Any,
    end_date: Any,
    data_source: str = "akshare",
) -> BiasCheckResult:
    """Heuristically flag survivorship bias in a stock universe.

    Parameters:
        stock_pool: Iterable of securities, or mapping/security metadata.
        start_date: Backtest start date.
        end_date: Backtest end date.
        data_source: Data source label for the diagnostic message.
    """
    securities, metadata = _coerce_stock_pool(stock_pool)
    if not securities:
        return _not_enough_data("survivorship", "Stock pool is empty.")

    start_ts = _to_timestamp(start_date)
    end_ts = _to_timestamp(end_date)
    expected_days = max(_business_day_count(start_ts, end_ts), 1)

    acc = _SeverityAccumulator()
    pool_size = len(set(securities))
    if pool_size <= 5:
        acc.add(
            BiasSeverity.HIGH,
            f"Stock pool contains only {pool_size} names, which is unusually small for survivorship-safe universe analysis.",
            "Compare against the historical universe membership at the backtest start date.",
        )
    elif pool_size <= 20:
        acc.add(
            BiasSeverity.MEDIUM,
            f"Stock pool contains only {pool_size} names; confirm the universe was not built from currently listed stocks only.",
            "Validate the universe against archived index constituents or historical listings.",
        )

    late_additions: list[str] = []
    sparse_histories: list[str] = []
    for sec in securities:
        meta = metadata.get(sec)
        listed_since = None
        data_obj = None

        if isinstance(meta, Mapping):
            listed_since = meta.get("listing_date") or meta.get("start_date")
            data_obj = meta.get("data") or meta.get("ohlcv") or meta.get("prices")
        elif isinstance(meta, pd.DataFrame):
            data_obj = meta

        if listed_since is not None:
            try:
                listed_ts = _to_timestamp(listed_since)
                if listed_ts > start_ts + pd.Timedelta(days=30):
                    late_additions.append(sec)
                    continue
            except Exception:
                pass

        first_date = _first_available_date(data_obj)
        if first_date is not None:
            if first_date > start_ts + pd.Timedelta(days=30):
                late_additions.append(sec)
            elif isinstance(data_obj, pd.DataFrame):
                coverage = len(_as_date_index(data_obj).index.unique()) / expected_days
                if coverage < 0.60:
                    sparse_histories.append(sec)

    if late_additions:
        sev = BiasSeverity.HIGH if len(late_additions) >= max(2, pool_size // 5) else BiasSeverity.MEDIUM
        acc.add(
            sev,
            f"{len(late_additions)} securities appear to enter the dataset well after the requested start date, suggesting a current-membership universe or late additions ({', '.join(late_additions[:5])}).",
            "Use historical constituent lists and delisted securities where available.",
        )
    if sparse_histories:
        acc.add(
            BiasSeverity.MEDIUM,
            f"{len(sparse_histories)} securities have sparse early histories relative to the requested window, which can mask delistings or late listings.",
            "Inspect securities with incomplete early history and document inclusion rules.",
        )

    return _finalize_check(
        acc,
        "survivorship",
        f"No strong survivorship-bias signal detected from the supplied stock pool ({pool_size} names, source={data_source}).",
    )


def check_lookahead_bias(
    backtest_result: Optional[Mapping[str, Any]] = None,
    strategy_file: Optional[str] = None,
    data_usage_log: Any = None,
) -> BiasCheckResult:
    """Heuristically flag signs of look-ahead bias.

    Parameters:
        backtest_result: Result dictionary returned by ``run_backtest()``.
        strategy_file: Optional strategy source path for simple text heuristics.
        data_usage_log: Optional textual log describing data access patterns.
    """
    if backtest_result is None and not strategy_file and data_usage_log is None:
        return _not_enough_data("lookahead")

    acc = _SeverityAccumulator()
    ohlcv_data = {} if backtest_result is None else backtest_result.get("ohlcv_data", {}) or {}
    trades = [] if backtest_result is None else backtest_result.get("trade_log", []) or []

    suspicious_prices: list[str] = []
    checked_prices = 0
    for trade in trades:
        trade_date = trade.get("date")
        security = trade.get("security")
        price = _safe_float(trade.get("price"))
        if trade_date is None or not security or np.isnan(price):
            continue
        bar = _find_bar_for_date(ohlcv_data.get(security, pd.DataFrame()), trade_date)
        if bar is None:
            continue
        low = _safe_float(bar.get("low"))
        high = _safe_float(bar.get("high"))
        if np.isnan(low) or np.isnan(high):
            continue
        checked_prices += 1
        tol = max(abs(price), abs(high), abs(low), 1.0) * 1e-6
        if price < low - tol or price > high + tol:
            suspicious_prices.append(f"{security}@{trade_date}")

    if suspicious_prices:
        sev = BiasSeverity.CRITICAL if len(suspicious_prices) >= 3 else BiasSeverity.HIGH
        acc.add(
            sev,
            f"{len(suspicious_prices)} trades executed outside the same day's OHLC range, which is a strong look-ahead or execution-timing warning ({', '.join(suspicious_prices[:5])}).",
            "Ensure trades are filled using prices observable at the decision timestamp, usually next-bar open or a realistic intraday model.",
        )
    elif trades and not checked_prices:
        acc.add(
            BiasSeverity.LOW,
            "Trade prices could not be cross-checked against OHLC data because matching bars were unavailable.",
            "Export OHLC data alongside the backtest result for stronger look-ahead validation.",
        )

    trade_dates = _extract_trade_dates(backtest_result)
    if not trade_dates.empty:
        start = None
        context = None if backtest_result is None else backtest_result.get("context")
        if context is not None:
            start = getattr(context, "start_date", None)
        if start is None:
            start = trade_dates.min()
        start_ts = _to_timestamp(start)
        first_day_trade_count = int((trade_dates == start_ts).sum())
        if first_day_trade_count > 0:
            sev = BiasSeverity.MEDIUM if first_day_trade_count > 1 else BiasSeverity.LOW
            acc.add(
                sev,
                f"{first_day_trade_count} trade(s) occurred on the first backtest day; this can be valid, but it can also indicate decisions made with future information.",
                "Confirm the strategy uses only pre-start history when generating first-day trades.",
            )

    if backtest_result is not None:
        returns = _extract_daily_returns(backtest_result)
        extreme_count = _consistent_extreme_returns(returns, threshold=0.20)
        if extreme_count:
            sev = BiasSeverity.CRITICAL if extreme_count >= 5 else BiasSeverity.HIGH
            acc.add(
                sev,
                f"Portfolio daily returns exceed ±20% on {extreme_count} days, a pattern often associated with future leakage or unrealistic fills.",
                "Re-check execution assumptions, position sizing, and whether the strategy can access same-day close information.",
            )

    text = (_read_strategy_text(strategy_file) + "\n" + _coerce_data_usage_log(data_usage_log)).lower()
    suspicious_tokens = ["shift(-1)", ".shift(-1)", "future", "lead(", "tomorrow"]
    matched_tokens = [token for token in suspicious_tokens if token in text]
    if matched_tokens:
        acc.add(
            BiasSeverity.MEDIUM,
            f"Strategy source or data-usage notes contain future-looking patterns ({', '.join(matched_tokens)}).",
            "Audit any forward-looking transformations and replace them with lagged features.",
        )

    return _finalize_check(
        acc,
        "lookahead",
        "No strong look-ahead bias signal detected from trades, returns, or supplied strategy diagnostics.",
    )


def check_selection_bias(
    backtest_result: Optional[Mapping[str, Any]] = None,
    filter_conditions: Optional[Iterable[Any]] = None,
    universe_size: Optional[int] = None,
    filtered_size: Optional[int] = None,
) -> BiasCheckResult:
    """Heuristically flag overly selective stock-universe construction."""
    acc = _SeverityAccumulator()

    if universe_size is not None and universe_size <= 0:
        universe_size = None
    if filtered_size is not None and filtered_size < 0:
        filtered_size = None

    if universe_size is not None and filtered_size is not None and universe_size > 0:
        retention = filtered_size / universe_size
        if retention <= 0.02:
            acc.add(
                BiasSeverity.HIGH,
                f"Only {filtered_size} of {universe_size} names survive the stated filters ({retention:.1%} retention), which is extremely selective.",
                "Test the strategy on broader universes and report sensitivity to the screening threshold.",
            )
        elif retention <= 0.10:
            acc.add(
                BiasSeverity.MEDIUM,
                f"The filters retain only {filtered_size} of {universe_size} names ({retention:.1%} retention), which may introduce selection bias.",
                "Document the rationale for each filter and compare performance before and after filtering.",
            )

    if filter_conditions is not None:
        conditions = list(filter_conditions)
        if len(conditions) >= 8:
            acc.add(
                BiasSeverity.LOW,
                f"{len(conditions)} explicit filter conditions were supplied; complex screening stacks can overfit the universe definition.",
                "Remove or relax individual filters and compare out-of-sample stability.",
            )

    unique_traded = 0
    if backtest_result is not None:
        unique_traded = len({t.get("security") for t in backtest_result.get("trade_log", []) if t.get("security")})
        if universe_size is not None and universe_size > 0 and unique_traded > 0:
            trade_share = unique_traded / universe_size
            if trade_share <= 0.01:
                acc.add(
                    BiasSeverity.HIGH,
                    f"The strategy traded only {unique_traded} unique stocks out of a universe of {universe_size} ({trade_share:.1%}), indicating very concentrated selection.",
                    "Check whether the screen unintentionally narrows to a few names and evaluate robustness on wider universes.",
                )
            elif trade_share <= 0.05:
                acc.add(
                    BiasSeverity.MEDIUM,
                    f"The strategy traded only {unique_traded} unique stocks out of {universe_size} ({trade_share:.1%}).",
                    "Measure performance after loosening the entry screen or increasing position breadth.",
                )

    if acc.severity == BiasSeverity.NONE and universe_size is None and filtered_size is None and backtest_result is None:
        return _not_enough_data("selection")

    return _finalize_check(
        acc,
        "selection",
        "No obvious selection-bias signal detected from the provided universe and trading breadth information.",
    )


def check_data_bias(backtest_result: Mapping[str, Any]) -> BiasCheckResult:
    """Heuristically flag data quality issues that can distort backtest results."""
    if not backtest_result:
        return _not_enough_data("data")

    values = _extract_total_values(backtest_result)
    if values.empty:
        return _not_enough_data("data", "No recorded portfolio values were supplied.")

    acc = _SeverityAccumulator()

    if len(values.index) >= 2:
        gaps = values.index.to_series().diff().dropna().dt.days
        large_gaps = gaps[gaps > 7]
        if not large_gaps.empty:
            sev = BiasSeverity.HIGH if len(large_gaps) >= 3 else BiasSeverity.MEDIUM
            acc.add(
                sev,
                f"Recorded portfolio values contain {len(large_gaps)} gaps longer than 7 calendar days.",
                "Check for missing market data, dropped trading days, or interrupted backtest recording.",
            )

        expected_bdays = _business_day_count(values.index.min(), values.index.max())
        if expected_bdays > len(values) + 5:
            missing = expected_bdays - len(values)
            acc.add(
                BiasSeverity.MEDIUM,
                f"Approximately {missing} business-day observations are missing from the equity curve.",
                "Rebuild the recorded value series and confirm each trading day is captured.",
            )

    returns = values.pct_change().dropna()
    if len(values) >= 5:
        near_zero_moves = int((returns.abs() < 1e-9).sum())
        if near_zero_moves >= max(3, int(len(returns) * 0.8)):
            acc.add(
                BiasSeverity.MEDIUM,
                "Portfolio value is suspiciously constant across most recorded days, suggesting stale prices or missing mark-to-market updates.",
                "Verify daily portfolio valuation uses the latest available market prices for every held security.",
            )

    anomalous = returns[returns.abs() > 0.20]
    if not anomalous.empty:
        sev = BiasSeverity.HIGH if len(anomalous) >= 3 else BiasSeverity.MEDIUM
        acc.add(
            sev,
            f"Detected {len(anomalous)} anomalous daily returns above ±20% in absolute value.",
            "Inspect raw data for splits, missing adjustments, or incorrect trade fills around the flagged dates.",
        )

    period_days = _context_period_days(backtest_result)
    if period_days is None:
        period_days = int((values.index.max() - values.index.min()).days) + 1 if len(values) >= 2 else len(values)
    if period_days < 14 or len(values) < 10:
        acc.add(
            BiasSeverity.LOW,
            f"Backtest period is very short ({period_days} calendar days, {len(values)} recorded values), limiting confidence in data-quality diagnostics.",
            "Extend the backtest window before drawing strong conclusions from the results.",
        )

    return _finalize_check(
        acc,
        "data",
        "No strong data-quality bias signal detected from the recorded portfolio value series.",
    )


__all__ = [
    "BiasCheckResult",
    "BiasReport",
    "BiasSeverity",
    "SurvivorshipCorrectedData",
    "check_data_bias",
    "check_lookahead_bias",
    "check_selection_bias",
    "check_survivorship_bias",
    "_extract_daily_returns",
]
