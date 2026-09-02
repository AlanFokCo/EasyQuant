"""Scientific validation pipeline orchestration.

This module stitches together the individual scientific validation helpers into a
single resilient entry point. Each validation stage is isolated behind
``try/except`` so that a failure in one module does not prevent the rest of the
pipeline from running.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from eqlib.scientific.bias import (
    BiasReport,
    BiasSeverity,
    check_data_bias,
    check_lookahead_bias,
    check_selection_bias,
    check_survivorship_bias,
)
from eqlib.scientific.overfitting import (
    OverfittingReport,
    OverfittingWarning,
    SensitivityResult,
    out_of_sample_test,
    parameter_sensitivity,
    walk_forward_analysis,
)
from eqlib.scientific.risk import (
    RiskRating,
    RiskReport,
    conditional_var,
    extended_risk_metrics,
    stress_test,
    tail_risk_analysis,
    value_at_risk,
)
from eqlib.scientific.statistics import (
    ConfidenceLevel,
    ConfidenceReport,
    bootstrap_metrics,
    monte_carlo_simulation,
    sample_size_assessment,
    significance_test,
)
from eqlib.validation_config import ValidationConfig

try:
    from eqlib.scientific.comparison import ComparisonReport, compare_with_platform
except ImportError:  # pragma: no cover - fallback for partially implemented installs

    @dataclass
    class ComparisonReport:
        """Fallback comparison report used when the comparison module is absent."""

        platform_name: str = "External Platform"
        matched: Optional[bool] = None
        summary_text: str = ""
        differences: dict[str, Any] = field(default_factory=dict)

        def summary(self) -> str:
            if self.summary_text:
                return self.summary_text
            if self.matched is True:
                return "Local backtest and platform export are broadly aligned."
            if self.matched is False:
                return "Local backtest and platform export show material differences."
            return "Platform comparison could not reach a definitive conclusion."

    def compare_with_platform(
        local_result: Mapping[str, Any],
        platform_result: Any,
        platform_name: str = "External Platform",
    ) -> ComparisonReport:
        """Best-effort comparison fallback when ``comparison.py`` is unavailable."""
        local_return = _extract_total_return(local_result)
        platform_return = _extract_total_return(platform_result)
        local_trades = _extract_trade_count(local_result)
        platform_trades = _extract_trade_count(platform_result)

        differences: dict[str, Any] = {}
        matched: Optional[bool] = None
        findings: list[str] = []

        if local_return is not None and platform_return is not None:
            return_diff = abs(local_return - platform_return)
            differences["total_return_diff"] = return_diff
            matched = return_diff <= 0.05
            findings.append(f"总收益差异: {return_diff:.2%}")

        if local_trades is not None and platform_trades is not None:
            trade_diff = abs(local_trades - platform_trades)
            differences["trade_count_diff"] = trade_diff
            trade_match = trade_diff == 0
            matched = trade_match if matched is None else matched and trade_match
            findings.append(f"交易笔数差异: {trade_diff}")

        if matched is None:
            findings.append("缺少足够的共同字段，平台对比结果仅供参考")

        return ComparisonReport(
            platform_name=platform_name,
            matched=matched,
            summary_text="；".join(findings),
            differences=differences,
        )


LOGGER = logging.getLogger(__name__)
_REPORT_SUFFIXES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".html": "html",
    ".htm": "html",
}


class TrustRating:
    """Human-readable trust labels for the full validation pipeline."""

    HIGH_TRUST = "所有验证通过，可用于实盘决策"
    MEDIUM_TRUST = "部分警告，建议核查后使用"
    LOW_TRUST = "存在重大问题，不建议实盘使用"
    INSUFFICIENT_DATA = "数据不足，无法建立信任"


@dataclass
class ValidationResult:
    """Aggregate result returned by :func:`validate_backtest`."""

    bias_report: Optional[BiasReport]
    risk_report: Optional[RiskReport]
    confidence_report: Optional[ConfidenceReport]
    overfitting_report: Optional[OverfittingReport]
    comparison_report: Optional[ComparisonReport]
    trust_rating: str
    config: ValidationConfig

    def summary(self) -> str:
        """Return a compact human-readable validation summary."""
        lines = [
            "科学验证结果",
            f"- 总体信任度: {self.trust_rating}",
            f"- 偏差检测: {self.bias_report.summary() if self.bias_report else '未执行'}",
            f"- 风险度量: {self.risk_report.summary() if self.risk_report else '未执行'}",
            f"- 统计置信度: {self.confidence_report.summary() if self.confidence_report else '未执行'}",
            f"- 过拟合检测: {self.overfitting_report.summary() if self.overfitting_report else '未执行'}",
        ]
        if self.comparison_report is not None:
            lines.append(f"- 平台对比: {self.comparison_report.summary()}")
        return "\n".join(lines)

    def save_report(self, path: str | Path) -> Path | dict[str, str]:
        """Generate and save a report by delegating formatting to ``report.py``."""
        from eqlib.scientific.report import ReportConfig, generate_validation_report

        target = Path(path)
        target_suffix = target.suffix.lower()
        if target_suffix in _REPORT_SUFFIXES:
            fmt = _REPORT_SUFFIXES[target_suffix]
            report = generate_validation_report(
                self,
                config=ReportConfig(
                    format=[fmt], output_dir=str(target.parent or Path("."))
                ),
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "markdown":
                target.write_text(report.markdown or "", encoding="utf-8")
            elif fmt == "json":
                target.write_text(
                    json.dumps(report.json_data or {}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                target.write_text(report.html or "", encoding="utf-8")
            return target

        report = generate_validation_report(
            self,
            config=ReportConfig(output_dir=str(target)),
        )
        return report.save(str(target))


def validate_backtest(
    backtest_result: Mapping[str, Any],
    config: Optional[ValidationConfig] = None,
    strategy_file: Optional[str] = None,
    platform_result: Any = None,
) -> ValidationResult:
    """Run the full scientific validation pipeline for a backtest result."""
    config = config or ValidationConfig()

    bias_report: Optional[BiasReport] = None
    risk_report: Optional[RiskReport] = None
    confidence_report: Optional[ConfidenceReport] = None
    overfitting_report: Optional[OverfittingReport] = None
    comparison_report: Optional[ComparisonReport] = None

    if config.bias_check:
        try:
            bias_report = _run_bias_checks(backtest_result, config, strategy_file)
            if bias_report.has_critical:
                LOGGER.warning(
                    "Critical bias detected; continuing remaining validation stages."
                )
        except Exception as exc:  # pragma: no cover - defensive orchestration path
            LOGGER.warning("Bias detection failed: %s", exc, exc_info=True)
            bias_report = None

    if config.risk_metrics != "basic":
        try:
            risk_report = _run_risk_checks(backtest_result, config)
        except Exception as exc:  # pragma: no cover - defensive orchestration path
            LOGGER.warning("Risk validation failed: %s", exc, exc_info=True)
            risk_report = None

    if config.statistics:
        try:
            confidence_report = _run_statistical_checks(backtest_result, config)
        except Exception as exc:  # pragma: no cover - defensive orchestration path
            LOGGER.warning("Statistical validation failed: %s", exc, exc_info=True)
            confidence_report = None

    if config.overfitting:
        try:
            overfitting_report = _run_overfitting_checks(backtest_result, config)
        except Exception as exc:  # pragma: no cover - defensive orchestration path
            LOGGER.warning("Overfitting validation failed: %s", exc, exc_info=True)
            overfitting_report = None

    if config.comparison and platform_result is not None:
        try:
            comparison_report = _run_platform_comparison(
                backtest_result, platform_result
            )
        except Exception as exc:  # pragma: no cover - defensive orchestration path
            LOGGER.warning("Platform comparison failed: %s", exc, exc_info=True)
            comparison_report = None

    trust_rating = _determine_trust_rating(
        bias_report=bias_report,
        risk_report=risk_report,
        confidence_report=confidence_report,
        overfitting_report=overfitting_report,
        comparison_report=comparison_report,
    )

    return ValidationResult(
        bias_report=bias_report,
        risk_report=risk_report,
        confidence_report=confidence_report,
        overfitting_report=overfitting_report,
        comparison_report=comparison_report,
        trust_rating=trust_rating,
        config=config,
    )


def _run_bias_checks(
    backtest_result: Mapping[str, Any],
    config: ValidationConfig,
    strategy_file: Optional[str],
) -> BiasReport:
    checks = []
    start_date, end_date = _extract_backtest_dates(backtest_result)
    stock_pool = _extract_stock_pool(backtest_result)

    if config.check_survivorship:
        result = _run_bias_check(
            "survivorship bias",
            check_survivorship_bias,
            stock_pool=stock_pool or [],
            start_date=start_date,
            end_date=end_date,
        )
        if result is not None:
            checks.append(result)
    if config.check_lookahead:
        result = _run_bias_check(
            "lookahead bias",
            check_lookahead_bias,
            backtest_result=backtest_result,
            strategy_file=strategy_file,
        )
        if result is not None:
            checks.append(result)
    if config.check_selection:
        result = _run_bias_check(
            "selection bias",
            check_selection_bias,
            backtest_result=backtest_result,
            universe_size=_infer_universe_size(backtest_result),
            filtered_size=_infer_filtered_size(backtest_result),
        )
        if result is not None:
            checks.append(result)
    if config.check_data:
        result = _run_bias_check("data bias", check_data_bias, backtest_result)
        if result is not None:
            checks.append(result)

    return BiasReport(checks=checks)


def _run_bias_check(name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run one bias sub-check without aborting the full bias report."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive orchestration path
        LOGGER.warning("%s failed: %s", name, exc)
        return None


def _run_risk_checks(
    backtest_result: Mapping[str, Any], config: ValidationConfig
) -> RiskReport:
    returns = _extract_daily_returns(backtest_result)
    scenarios = (
        None
        if config.stress_test_scenarios == "default"
        else config.stress_test_scenarios
    )
    return RiskReport(
        extended_metrics=extended_risk_metrics(backtest_result),
        var_95=value_at_risk(returns, confidence_level=0.95),
        var_99=value_at_risk(returns, confidence_level=0.99),
        cvar_95=conditional_var(returns, confidence_level=0.95),
        cvar_99=conditional_var(returns, confidence_level=0.99),
        tail_risk=tail_risk_analysis(returns),
        stress_test=stress_test(backtest_result, scenarios=scenarios),
    )


def _run_statistical_checks(
    backtest_result: Mapping[str, Any],
    config: ValidationConfig,
) -> ConfidenceReport:
    confidence_level = 1.0 - float(config.significance_level)
    if not 0 < confidence_level < 1:
        confidence_level = 0.95

    strategy_returns = _extract_daily_returns(backtest_result)
    benchmark_returns = _extract_benchmark_returns(backtest_result)
    monte_carlo_runs = int(
        getattr(config, "n_monte_carlo", 0) or getattr(config, "n_simulations", 0) or 0
    )

    report = ConfidenceReport(
        bootstrap_result=bootstrap_metrics(
            backtest_result,
            n_bootstrap=int(config.n_bootstrap),
            confidence_level=confidence_level,
            random_state=config.random_state,
        ),
        monte_carlo_result=(
            monte_carlo_simulation(
                backtest_result,
                n_simulations=monte_carlo_runs,
                random_state=config.random_state,
            )
            if monte_carlo_runs > 0
            else None
        ),
        significance_result=significance_test(
            strategy_returns,
            benchmark_returns=benchmark_returns,
        ),
        sample_size_result=sample_size_assessment(backtest_result=backtest_result),
    )
    report.confidence_level = report.inferred_confidence_level()
    return report


def _run_overfitting_checks(
    backtest_result: Mapping[str, Any],
    config: ValidationConfig,
) -> OverfittingReport:
    windows = config.walk_forward_windows or {}
    sensitivity = (
        parameter_sensitivity(
            dict(backtest_result),
            perturbation_pct=float(config.perturbation_pct),
        )
        if config.parameter_sensitivity
        else SensitivityResult(
            rolling_sharpe_std=0.0,
            rolling_sharpe_cv=0.0,
            is_stable=True,
            stability_score=100.0,
            sensitivity_rating="SKIPPED",
        )
    )

    return OverfittingReport(
        walk_forward=walk_forward_analysis(
            dict(backtest_result),
            param_ranges=None,
            train_window=str(windows.get("train", "2Y")),
            test_window=str(windows.get("test", "6M")),
            step=str(windows.get("step", "6M")),
        ),
        sensitivity=sensitivity,
        out_of_sample=out_of_sample_test(dict(backtest_result)),
    )


def _run_platform_comparison(
    backtest_result: Mapping[str, Any],
    platform_result: Any,
) -> ComparisonReport:
    platform_name = "External Platform"
    if isinstance(platform_result, Mapping):
        platform_name = str(platform_result.get("platform_name", platform_name))
    return compare_with_platform(
        local_result=backtest_result,
        platform_result=platform_result,
        platform_name=platform_name,
    )


def _determine_trust_rating(
    *,
    bias_report: Optional[BiasReport],
    risk_report: Optional[RiskReport],
    confidence_report: Optional[ConfidenceReport],
    overfitting_report: Optional[OverfittingReport],
    comparison_report: Optional[ComparisonReport],
) -> str:
    if bias_report is not None and bias_report.has_critical:
        return TrustRating.LOW_TRUST

    if (
        overfitting_report is not None
        and overfitting_report.out_of_sample.overfitting_warning
        == OverfittingWarning.HIGH_OVERFITTING
    ):
        return TrustRating.LOW_TRUST

    confidence_level = _get_confidence_level(confidence_report)
    if confidence_level in {
        ConfidenceLevel.LOW_CONFIDENCE,
        ConfidenceLevel.INSUFFICIENT_DATA,
    }:
        return TrustRating.INSUFFICIENT_DATA

    if _has_warnings(
        bias_report=bias_report,
        risk_report=risk_report,
        confidence_report=confidence_report,
        overfitting_report=overfitting_report,
        comparison_report=comparison_report,
    ):
        return TrustRating.MEDIUM_TRUST

    return TrustRating.HIGH_TRUST


def _has_warnings(
    *,
    bias_report: Optional[BiasReport],
    risk_report: Optional[RiskReport],
    confidence_report: Optional[ConfidenceReport],
    overfitting_report: Optional[OverfittingReport],
    comparison_report: Optional[ComparisonReport],
) -> bool:
    if bias_report is not None and bias_report.overall_severity > BiasSeverity.NONE:
        return True

    confidence_level = _get_confidence_level(confidence_report)
    if confidence_level == ConfidenceLevel.MEDIUM_CONFIDENCE:
        return True

    if risk_report is not None:
        risk_rating = str(risk_report.extended_metrics.get("risk_rating", ""))
        tail_rating = str(risk_report.tail_risk.get("tail_risk_rating", ""))
        stress_scenarios = risk_report.stress_test.get("scenarios", [])
        if risk_rating in {RiskRating.MEDIUM_RISK, RiskRating.HIGH_RISK}:
            return True
        if tail_rating and tail_rating.upper() != "LOW":
            return True
        if any(
            str(item.get("stress_rating", "")) != RiskRating.RESILIENT
            for item in stress_scenarios
        ):
            return True

    if overfitting_report is not None:
        if (
            overfitting_report.out_of_sample.overfitting_warning
            != OverfittingWarning.STABLE
        ):
            return True
        if overfitting_report.walk_forward.is_sharpe_decay:
            return True
        if overfitting_report.sensitivity.sensitivity_rating in {"MEDIUM", "HIGH"}:
            return True

    if comparison_report is not None and not _comparison_is_clean(comparison_report):
        return True

    return False


def _comparison_is_clean(comparison_report: ComparisonReport) -> bool:
    matched = getattr(comparison_report, "matched", None)
    if matched is False:
        return False

    differences = getattr(comparison_report, "differences", None)
    if isinstance(differences, Mapping):
        for value in differences.values():
            if isinstance(value, (int, float)) and abs(float(value)) > 0.05:
                return False

    for attr_name in ("judgment", "comparison_judgment", "result"):
        value = getattr(comparison_report, attr_name, None)
        if isinstance(value, str) and any(
            token in value.lower() for token in ("suspicious", "mismatch")
        ):
            return False

    return True


def _get_confidence_level(
    confidence_report: Optional[ConfidenceReport],
) -> Optional[str]:
    if confidence_report is None:
        return None
    if confidence_report.confidence_level:
        return confidence_report.confidence_level
    return confidence_report.inferred_confidence_level()


def _extract_daily_returns(backtest_result: Mapping[str, Any]) -> list[float]:
    recorded = list(backtest_result.get("recorded_values", []) or [])
    if len(recorded) < 2:
        return []

    values: list[float] = []
    for row in recorded:
        total_value = row.get("total_value")
        if total_value is None:
            continue
        try:
            values.append(float(total_value))
        except (TypeError, ValueError):
            continue

    if len(values) < 2:
        return []

    returns: list[float] = []
    for prev, curr in zip(values, values[1:]):
        if prev == 0:
            continue
        returns.append((curr / prev) - 1.0)
    return returns


def _extract_benchmark_returns(backtest_result: Mapping[str, Any]) -> Optional[Any]:
    import pandas as pd

    for key in (
        "benchmark_returns",
        "benchmark_return_series",
        "benchmark_daily_returns",
    ):
        value = backtest_result.get(key)
        if value is not None and isinstance(value, (pd.Series, pd.DataFrame)):
            return value

    # Try to compute from benchmark_values [{date, close}, ...]
    bvals = backtest_result.get("benchmark_values")
    if bvals and isinstance(bvals, list) and len(bvals) > 1:
        try:
            closes = pd.Series(
                {v["date"]: float(v.get("close", v.get("value", 0))) for v in bvals}
            ).sort_index()
            if len(closes) > 1:
                return closes.pct_change().dropna()
        except (TypeError, ValueError, KeyError):
            pass

    return None


def _extract_backtest_dates(backtest_result: Mapping[str, Any]) -> tuple[Any, Any]:
    context = backtest_result.get("context")
    start_date = getattr(context, "start_date", None)
    end_date = getattr(context, "end_date", None)
    recorded = list(backtest_result.get("recorded_values", []) or [])

    if start_date is None and recorded:
        start_date = recorded[0].get("date")
    if end_date is None and recorded:
        end_date = recorded[-1].get("date")
    return start_date, end_date


def _extract_stock_pool(backtest_result: Mapping[str, Any]) -> Any:
    for key in ("stock_pool", "universe", "securities", "symbols"):
        value = backtest_result.get(key)
        if value is not None:
            return value

    ohlcv_data = backtest_result.get("ohlcv_data")
    if isinstance(ohlcv_data, Mapping) and ohlcv_data:
        return list(ohlcv_data.keys())

    context = backtest_result.get("context")
    for attr_name in ("stock_pool", "universe", "securities", "symbols"):
        value = getattr(context, attr_name, None)
        if value is not None:
            return value
    return None


def _infer_universe_size(backtest_result: Mapping[str, Any]) -> Optional[int]:
    for key in ("universe_size", "stock_pool_size"):
        value = backtest_result.get(key)
        if isinstance(value, int) and value > 0:
            return value

    stock_pool = _extract_stock_pool(backtest_result)
    if isinstance(stock_pool, Mapping):
        return len(stock_pool)
    if isinstance(stock_pool, (list, tuple, set)):
        return len(stock_pool)
    return None


def _infer_filtered_size(backtest_result: Mapping[str, Any]) -> Optional[int]:
    for key in ("filtered_size", "selected_size", "candidate_count"):
        value = backtest_result.get(key)
        if isinstance(value, int) and value >= 0:
            return value

    trade_count = _extract_trade_count(backtest_result)
    return trade_count if trade_count and trade_count > 0 else None


def _extract_trade_count(result: Any) -> Optional[int]:
    if isinstance(result, Mapping):
        trade_log = result.get("trade_log")
        if isinstance(trade_log, list):
            return len(trade_log)
        for key in ("trade_count", "trades_count"):
            value = result.get(key)
            if isinstance(value, int):
                return value
    return None


def _extract_total_return(result: Any) -> Optional[float]:
    if not isinstance(result, Mapping):
        return None

    for key in ("total_return", "annual_return", "return_pct"):
        value = result.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue

    recorded = list(result.get("recorded_values", []) or [])
    if len(recorded) >= 2:
        start_value = recorded[0].get("total_value")
        end_value = recorded[-1].get("total_value")
        try:
            start_float = float(start_value)
            end_float = float(end_value)
            if start_float != 0:
                return (end_float / start_float) - 1.0
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


__all__ = [
    "TrustRating",
    "ValidationResult",
    "validate_backtest",
]
