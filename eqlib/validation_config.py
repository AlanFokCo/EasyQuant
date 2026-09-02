"""Global validation configuration defaults for the scientific validation layer.

This module provides :class:`ValidationConfig` — a dataclass holding all
configuration knobs for the scientific validation pipeline.  Users may
override any default when calling :func:`eqlib.scientific.validate_backtest`.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional


@dataclasses.dataclass
class ValidationConfig:
    """Configuration for the scientific validation pipeline.

    All flags default to a conservative, local-machine-friendly setup.
    Set individual flags to ``False`` to skip specific validation steps.

    Parameters
    ----------
    overfitting : bool
        Enable overfitting detection (walk-forward, parameter sensitivity).
    walk_forward_windows : dict | None
        ``{"train": "2Y", "test": "6M", "step": "6M"}`` style config.
    parameter_sensitivity : bool
        Run parameter perturbation analysis.
    perturbation_pct : float
        Fraction to perturb each parameter (default 10 %).

    statistics : bool
        Enable bootstrap / Monte-Carlo / significance testing.
    n_bootstrap : int
        Number of bootstrap resamples.
    n_monte_carlo : int
        Number of Monte-Carlo simulations.
    random_state : int | None
        Seed used by bootstrap and Monte-Carlo statistical checks. Set to
        ``None`` to opt into non-deterministic resampling.
    significance_level : float
        p-value threshold for significance tests.

    bias_check : bool
        Enable bias detection module.
    check_survivorship : bool
        Check for survivorship bias.
    check_lookahead : bool
        Check for look-ahead bias.
    check_selection : bool
        Check for selection bias.
    check_data : bool
        Check for data bias (missing data, anomalies).

    risk_metrics : str
        ``"basic"`` or ``"extended"``.
    stress_test_scenarios : str | list
        ``"default"`` to use built-in scenarios, or a list of dicts.

    comparison : bool
        Enable platform comparison module.

    parallel_workers : int
        Max number of parallel workers for heavy computation.
    timeout_minutes : int
        Global timeout for the full validation pipeline.
    """

    # ── Overfitting ──────────────────────────────────────────────────────
    overfitting: bool = True
    walk_forward_windows: Optional[Dict[str, str]] = None
    parameter_sensitivity: bool = True
    perturbation_pct: float = 0.10

    # ── Statistics ───────────────────────────────────────────────────────
    statistics: bool = True
    n_bootstrap: int = 1000
    n_monte_carlo: int = 500
    random_state: Optional[int] = 42
    significance_level: float = 0.05

    # ── Bias ─────────────────────────────────────────────────────────────
    bias_check: bool = True
    check_survivorship: bool = True
    check_lookahead: bool = True
    check_selection: bool = True
    check_data: bool = True

    # ── Risk ─────────────────────────────────────────────────────────────
    risk_metrics: str = "extended"
    stress_test_scenarios: Any = "default"

    # ── Comparison ───────────────────────────────────────────────────────
    comparison: bool = False

    # ── Execution ────────────────────────────────────────────────────────
    parallel_workers: int = 4
    timeout_minutes: int = 30

    # ── Report ───────────────────────────────────────────────────────────
    n_simulations: int = 1000  # convenience alias for n_bootstrap

    def __post_init__(self) -> None:
        if self.walk_forward_windows is None:
            self.walk_forward_windows = {
                "train": "2Y",
                "test": "6M",
                "step": "6M",
            }
