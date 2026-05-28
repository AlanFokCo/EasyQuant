"""eqlib.scientific — Scientific validation layer for backtest diagnostics.

Provides overfitting detection, statistical confidence testing, bias
detection, extended risk metrics, platform comparison, and unified
validation orchestration.  All modules are optional add-ons that leave
the core ``run_backtest()`` API unchanged.

Typical usage::

    from eqlib.scientific import validate_backtest, ValidationConfig

    validation_result = validate_backtest(backtest_result)
    validation_result.summary()
"""

# ── Configuration ────────────────────────────────────────────────────────
from eqlib.validation_config import ValidationConfig

# ── Overfitting detection ────────────────────────────────────────────────
from .overfitting import (
    OverfittingReport,
    OverfittingWarning,
    OOSResult,
    SensitivityResult,
    WalkForwardResult,
    out_of_sample_test,
    parameter_sensitivity,
    walk_forward_analysis,
)

# ── Statistical confidence ───────────────────────────────────────────────
from .statistics import (
    BootstrapResult,
    ConfidenceLevel,
    ConfidenceReport,
    MonteCarloResult,
    SampleSizeResult,
    SignificanceResult,
    bootstrap_metrics,
    monte_carlo_simulation,
    sample_size_assessment,
    significance_test,
)

# ── Bias detection ───────────────────────────────────────────────────────
from .bias import (
    BiasCheckResult,
    BiasReport,
    BiasSeverity,
    SurvivorshipCorrectedData,
    check_data_bias,
    check_lookahead_bias,
    check_selection_bias,
    check_survivorship_bias,
)

# ── Extended risk metrics ────────────────────────────────────────────────
from .risk import (
    RiskRating,
    RiskReport,
    conditional_var,
    extended_risk_metrics,
    stress_test,
    tail_risk_analysis,
    value_at_risk,
)

# ── Platform comparison ──────────────────────────────────────────────────
from .comparison import (
    BenchmarkAlignResult,
    ComparisonJudgment,
    ComparisonReport,
    ComparisonResult,
    MetricComparison,
    MetricsComparisonResult,
    TradeVerificationResult,
    align_benchmark,
    compare_metrics,
    compare_with_platform,
    verify_trades,
)

# ── Validation orchestration ─────────────────────────────────────────────
from .validation_runner import TrustRating, ValidationResult, validate_backtest

# ── Report generation ────────────────────────────────────────────────────
from .report import ReportConfig, ValidationReport, generate_validation_report

__all__ = [
    # Config
    "ValidationConfig",
    # Overfitting
    "OverfittingReport", "OverfittingWarning", "OOSResult",
    "SensitivityResult", "WalkForwardResult",
    "out_of_sample_test", "parameter_sensitivity", "walk_forward_analysis",
    # Statistics
    "BootstrapResult", "ConfidenceLevel", "ConfidenceReport",
    "MonteCarloResult", "SampleSizeResult", "SignificanceResult",
    "bootstrap_metrics", "monte_carlo_simulation",
    "sample_size_assessment", "significance_test",
    # Bias
    "BiasCheckResult", "BiasReport", "BiasSeverity",
    "SurvivorshipCorrectedData",
    "check_data_bias", "check_lookahead_bias",
    "check_selection_bias", "check_survivorship_bias",
    # Risk
    "RiskRating", "RiskReport",
    "conditional_var", "extended_risk_metrics",
    "stress_test", "tail_risk_analysis", "value_at_risk",
    # Comparison
    "BenchmarkAlignResult", "ComparisonJudgment", "ComparisonReport",
    "ComparisonResult", "MetricComparison", "MetricsComparisonResult",
    "TradeVerificationResult",
    "align_benchmark", "compare_metrics",
    "compare_with_platform", "verify_trades",
    # Orchestration
    "TrustRating", "ValidationResult", "validate_backtest",
    # Report
    "ReportConfig", "ValidationReport", "generate_validation_report",
]
