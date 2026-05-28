"""Human-readable reporting for scientific validation results."""

from __future__ import annotations

import html
import json
import datetime
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover
    from eqlib.scientific.validation_runner import ValidationResult


@dataclass
class ReportConfig:
    """Configuration for validation report generation."""

    format: list[str] = field(default_factory=lambda: ["markdown"])
    include_charts: bool = False
    language: str = "zh"
    output_dir: str = "./validation_reports/"


@dataclass
class ValidationReport:
    """Container for generated validation report content."""

    markdown: Optional[str] = None
    json_data: Optional[dict[str, Any]] = None
    html: Optional[str] = None
    _default_output_dir: str = "./validation_reports/"

    def save(self, output_dir: Optional[str] = None) -> dict[str, str]:
        """Save generated report artefacts to disk."""
        destination = Path(output_dir or self._default_output_dir)
        destination.mkdir(parents=True, exist_ok=True)

        saved_paths: dict[str, str] = {}
        if self.markdown is not None:
            markdown_path = destination / "validation_report.md"
            markdown_path.write_text(self.markdown, encoding="utf-8")
            saved_paths["markdown"] = str(markdown_path)

        if self.json_data is not None:
            json_path = destination / "validation_report.json"
            json_path.write_text(
                json.dumps(self.json_data, ensure_ascii=False, indent=2, default=_json_default),
                encoding="utf-8",
            )
            saved_paths["json"] = str(json_path)

        if self.html is not None:
            html_path = destination / "validation_report.html"
            html_path.write_text(self.html, encoding="utf-8")
            saved_paths["html"] = str(html_path)

        return saved_paths


def _json_default(obj: Any) -> Any:
    """Custom JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def generate_validation_report(
    validation_result: "ValidationResult",
    config: Optional[ReportConfig] = None,
) -> ValidationReport:
    """Generate validation reports in one or more output formats."""
    config = config or ReportConfig()
    requested_formats = {item.lower() for item in config.format}
    supported_formats = {"markdown", "json", "html"}
    active_formats = [item for item in requested_formats if item in supported_formats] or ["markdown"]

    markdown_text = _build_markdown_report(validation_result)
    json_payload = _build_json_payload(validation_result)
    html_text = _build_html_report(markdown_text)

    return ValidationReport(
        markdown=markdown_text if "markdown" in active_formats else None,
        json_data=json_payload if "json" in active_formats else None,
        html=html_text if "html" in active_formats else None,
        _default_output_dir=config.output_dir,
    )


def _build_markdown_report(validation_result: "ValidationResult") -> str:
    key_findings = _collect_key_findings(validation_result)
    lines = [
        "# 科学验证报告",
        "",
        "## 1. 执行摘要",
        f"- 总体信任度: {validation_result.trust_rating}",
        f"- 关键发现: {'；'.join(key_findings) if key_findings else '未发现显著异常'}",
        "",
        "## 2. 偏差检测",
        *_format_bias_section(validation_result.bias_report),
        "",
        "## 3. 风险度量",
        *_format_risk_section(validation_result.risk_report),
        "",
        "## 4. 统计置信度",
        *_format_confidence_section(validation_result.confidence_report),
        "",
        "## 5. 过拟合检测",
        *_format_overfitting_section(validation_result.overfitting_report),
    ]

    if validation_result.comparison_report is not None:
        lines.extend([
            "",
            "## 6. 平台对比",
            *_format_comparison_section(validation_result.comparison_report),
        ])

    lines.extend([
        "",
        "## 7. 附录",
        "- 验证配置",
        *_format_config_lines(validation_result.config),
    ])
    return "\n".join(lines)


def _build_json_payload(validation_result: "ValidationResult") -> dict[str, Any]:
    return {
        "title": "科学验证报告",
        "execution_summary": {
            "trust_rating": validation_result.trust_rating,
            "key_findings": _collect_key_findings(validation_result),
        },
        "bias_detection": _serialize(validation_result.bias_report),
        "risk_metrics": _serialize(validation_result.risk_report),
        "statistical_confidence": _serialize(validation_result.confidence_report),
        "overfitting_detection": _serialize(validation_result.overfitting_report),
        "platform_comparison": _serialize(validation_result.comparison_report),
        "appendix": {
            "validation_config": _serialize(validation_result.config),
        },
    }


def _build_html_report(markdown_text: str) -> str:
    escaped = html.escape(markdown_text)
    return f"""<!DOCTYPE html>
<html lang=\"zh\">
<head>
  <meta charset=\"utf-8\">
  <title>科学验证报告</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; background: #f7f9fb; color: #1f2937; }}
    .report {{ max-width: 980px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }}
    pre {{ white-space: pre-wrap; word-break: break-word; line-height: 1.6; margin: 0; }}
  </style>
</head>
<body>
  <div class=\"report\">
    <pre>{escaped}</pre>
  </div>
</body>
</html>
"""


def _format_bias_section(bias_report: Any) -> list[str]:
    if bias_report is None:
        return ["未执行偏差检测。"]

    severity_obj = getattr(bias_report, 'overall_severity', None)
    severity_name = getattr(severity_obj, 'name', 'UNKNOWN')
    lines = [
        f"- 总体严重程度: {severity_name}",
        f"- 是否存在关键偏差: {'是' if getattr(bias_report, 'has_critical', False) else '否'}",
    ]
    checks = getattr(bias_report, "checks", []) or []
    for check in checks:
        check_severity = getattr(getattr(check, "severity", None), "name", "UNKNOWN")
        lines.append(f"- {getattr(check, 'bias_type', 'unknown')}: {check_severity} — {getattr(check, 'details', '')}")
        for recommendation in getattr(check, "recommendations", []) or []:
            lines.append(f"  - 建议: {recommendation}")
    return lines


def _format_risk_section(risk_report: Any) -> list[str]:
    if risk_report is None:
        return ["未执行风险度量。"]

    lines = [
        "| 指标 | 数值 |",
        "| --- | --- |",
    ]
    for key, value in (getattr(risk_report, "extended_metrics", {}) or {}).items():
        lines.append(f"| {key} | {_format_scalar(value)} |")

    for label, payload in (
        ("VaR 95%", getattr(risk_report, "var_95", None)),
        ("VaR 99%", getattr(risk_report, "var_99", None)),
        ("CVaR 95%", getattr(risk_report, "cvar_95", None)),
        ("CVaR 99%", getattr(risk_report, "cvar_99", None)),
    ):
        if payload:
            lines.append(f"- {label}: {_format_scalar(payload.get('var', payload.get('cvar')))}")

    tail_risk = getattr(risk_report, "tail_risk", None)
    if tail_risk:
        lines.append(f"- 尾部风险评级: {tail_risk.get('tail_risk_rating', 'N/A')}")

    stress_test = getattr(risk_report, "stress_test", {}) or {}
    scenarios = stress_test.get("scenarios", [])
    if scenarios:
        lines.append("- 压力测试:")
        for scenario in scenarios:
            lines.append(
                f"  - {scenario.get('name', 'scenario')}: 损失 {_format_scalar(scenario.get('estimated_loss_pct'))}, 评级 {scenario.get('stress_rating', 'N/A')}"
            )
    return lines


def _format_confidence_section(confidence_report: Any) -> list[str]:
    if confidence_report is None:
        return ["未执行统计置信度分析。"]

    lines = [
        f"- 总体置信度: {_confidence_level(confidence_report)}",
    ]

    significance = getattr(confidence_report, "significance_result", None)
    if significance is not None:
        lines.append(f"- 显著性检验: {getattr(significance, 'conclusion', '')}")

    sample_size = getattr(confidence_report, "sample_size_result", None)
    if sample_size is not None:
        lines.append(f"- 样本量评估: {getattr(sample_size, 'assessment', 'UNKNOWN')}")
        for warning in getattr(sample_size, "warnings", []) or []:
            lines.append(f"  - 警告: {warning}")

    bootstrap = getattr(confidence_report, "bootstrap_result", None)
    if bootstrap is not None:
        lines.extend([
            "- Bootstrap 置信区间:",
            "  | 指标 | 点估计 | 下限 | 上限 | 标准误 |",
            "  | --- | --- | --- | --- | --- |",
        ])
        for name, metric_ci in getattr(bootstrap, "metrics", {}).items():
            lines.append(
                "  | {name} | {point} | {low} | {high} | {stderr} |".format(
                    name=name,
                    point=_format_scalar(getattr(metric_ci, "point_estimate", None)),
                    low=_format_scalar(getattr(metric_ci, "ci_lower", None)),
                    high=_format_scalar(getattr(metric_ci, "ci_upper", None)),
                    stderr=_format_scalar(getattr(metric_ci, "std_error", None)),
                )
            )

    monte_carlo = getattr(confidence_report, "monte_carlo_result", None)
    if monte_carlo is not None:
        lines.append(f"- Monte Carlo p-value: {_format_scalar(getattr(monte_carlo, 'p_value_vs_random', None))}")

    for note in getattr(confidence_report, "notes", []) or []:
        lines.append(f"- 备注: {note}")
    return lines


def _format_overfitting_section(overfitting_report: Any) -> list[str]:
    if overfitting_report is None:
        return ["未执行过拟合检测。"]

    lines: list[str] = []
    walk_forward = getattr(overfitting_report, "walk_forward", None)
    if walk_forward is not None:
        lines.append(f"- Walk-forward OOS/IS 比率: {_format_scalar(getattr(walk_forward, 'oos_is_ratio', None))}")
        lines.append(f"- 是否存在 Sharpe 衰减: {'是' if getattr(walk_forward, 'is_sharpe_decay', False) else '否'}")

    sensitivity = getattr(overfitting_report, "sensitivity", None)
    if sensitivity is not None:
        lines.append(f"- 参数敏感性评级: {getattr(sensitivity, 'sensitivity_rating', 'N/A')}")
        lines.append(f"- 稳定性得分: {_format_scalar(getattr(sensitivity, 'stability_score', None))}")

    oos = getattr(overfitting_report, "out_of_sample", None)
    if oos is not None:
        lines.append(f"- 样本外警告: {getattr(oos, 'overfitting_warning', 'N/A')}")
        lines.append(f"- 样本外 Sharpe 衰减: {_format_scalar(getattr(oos, 'sharpe_decay_pct', None))}")
    return lines


def _format_comparison_section(comparison_report: Any) -> list[str]:
    if comparison_report is None:
        return ["未执行平台对比。"]

    lines = [f"- 摘要: {comparison_report.summary() if hasattr(comparison_report, 'summary') else str(comparison_report)}"]
    serialized = _serialize(comparison_report)
    if isinstance(serialized, dict):
        for key, value in serialized.items():
            if key == "summary_text":
                continue
            lines.append(f"- {key}: {_format_scalar(value) if not isinstance(value, (dict, list)) else json.dumps(value, ensure_ascii=False)}")
    return lines


def _format_config_lines(config: Any) -> list[str]:
    serialized = _serialize(config)
    if not isinstance(serialized, dict):
        return [f"  - {serialized}"]
    return [f"  - {key}: {_format_scalar(value) if not isinstance(value, (dict, list)) else json.dumps(value, ensure_ascii=False)}" for key, value in serialized.items()]


def _collect_key_findings(validation_result: "ValidationResult") -> list[str]:
    findings = [f"总体评级为：{validation_result.trust_rating}"]

    bias_report = getattr(validation_result, "bias_report", None)
    if bias_report is not None and getattr(bias_report, "has_critical", False):
        findings.append("检测到关键偏差风险")

    confidence_report = getattr(validation_result, "confidence_report", None)
    if confidence_report is not None:
        findings.append(f"统计置信度为：{_confidence_level(confidence_report)}")

    overfitting_report = getattr(validation_result, "overfitting_report", None)
    if overfitting_report is not None:
        warning = getattr(getattr(overfitting_report, "out_of_sample", None), "overfitting_warning", None)
        if warning:
            findings.append(f"过拟合结论：{warning}")

    comparison_report = getattr(validation_result, "comparison_report", None)
    if comparison_report is not None and hasattr(comparison_report, "summary"):
        findings.append(f"平台对比：{comparison_report.summary()}")

    return findings[:5]


def _confidence_level(confidence_report: Any) -> str:
    level = getattr(confidence_report, "confidence_level", None)
    if level:
        return str(level)
    inferred = getattr(confidence_report, "inferred_confidence_level", None)
    return str(inferred()) if callable(inferred) else "UNKNOWN"


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return {key: _serialize(val) for key, val in asdict(value).items()}
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dict):
        return {str(key): _serialize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    if hasattr(value, "name") and hasattr(value, "value"):
        return getattr(value, "name")
    return value


def _format_scalar(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


__all__ = [
    "ReportConfig",
    "ValidationReport",
    "generate_validation_report",
]
