"""Regression tests for agent/ acceptance-gate and audit-trail hardening.

Covers the adversarial-review findings P1-12:
- ``StrategyOptimizer._evaluate_requirements`` must treat non-finite metrics
  (NaN/inf) as failing instead of passing them through ``<`` comparisons.
- ``_compute_aggregate`` must propagate non-finite period metrics as NaN.
- ``AuditLog`` must never emit invalid JSON (bare NaN) and must generate
  collision-resistant session IDs.
"""

from __future__ import annotations

import json
import math
import re

from agent.audit_log import AuditLog
from agent.optimizer import (
    _DEFAULT_REQUIREMENTS,
    StrategyOptimizer,
    _compute_aggregate,
)


def _optimizer() -> StrategyOptimizer:
    """Build an optimizer instance without loading a strategy from disk."""
    optimizer = StrategyOptimizer.__new__(StrategyOptimizer)
    optimizer.requirements = dict(_DEFAULT_REQUIREMENTS)
    return optimizer


def _period(**overrides) -> dict:
    period = {
        "start": "2023-01-01",
        "end": "2023-12-31",
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.10,
        "annual_return": 0.12,
        "win_rate_trade": 0.55,
        "trade_count": 20,
    }
    period.update(overrides)
    return period


class TestOptimizerRejectsNonFiniteMetrics:
    def test_nan_sharpe_fails_acceptance(self):
        periods = [_period(sharpe_ratio=float("nan"))]
        met, failing = _optimizer()._evaluate_requirements(
            periods, _compute_aggregate(periods)
        )
        assert met is False
        assert any("sharpe" in item for item in failing)

    def test_inf_annual_return_fails_acceptance(self):
        periods = [_period(annual_return=float("inf"))]
        met, failing = _optimizer()._evaluate_requirements(
            periods, _compute_aggregate(periods)
        )
        assert met is False
        assert any("annual_return" in item for item in failing)

    def test_nan_aggregate_sharpe_fails_acceptance(self):
        """A NaN avg_sharpe must not satisfy the aggregate sharpe gate."""
        periods = [
            _period(
                sharpe_ratio=float("nan"), start="2022-01-01", end="2022-12-31"
            )
        ]
        aggregate = _compute_aggregate(periods)
        assert math.isnan(aggregate["avg_sharpe"])
        met, _ = _optimizer()._evaluate_requirements(periods, aggregate)
        assert met is False

    def test_aggregate_propagates_nan_instead_of_min_ignoring_it(self):
        """min() with a NaN operand can silently drop it; the gate must not."""
        periods = [
            _period(max_drawdown=float("nan")),
            _period(max_drawdown=-0.05, start="2024-01-01", end="2024-12-31"),
        ]
        aggregate = _compute_aggregate(periods)
        assert math.isnan(aggregate["worst_drawdown"])

    def test_finite_passing_metrics_still_meet_requirements(self):
        periods = [_period()]
        met, failing = _optimizer()._evaluate_requirements(
            periods, _compute_aggregate(periods)
        )
        assert met is True
        assert failing == []


class TestAuditLogJsonlValidity:
    def test_non_finite_metrics_are_serialized_as_null(self, tmp_path):
        log = AuditLog(output_dir=str(tmp_path))
        log.log_iteration(
            0,
            {"fast": 5},
            [_period(sharpe_ratio=float("nan"), annual_return=float("inf"))],
            {"avg_sharpe": float("nan")},
            False,
            ["sharpe is not finite"],
        )

        with open(log.jsonl_path, encoding="utf-8") as fh:
            line = fh.read().strip()
        parsed = json.loads(
            line,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {constant}")
            ),
        )
        assert parsed["periods"][0]["sharpe_ratio"] is None
        assert parsed["periods"][0]["annual_return"] is None
        assert parsed["aggregate"]["avg_sharpe"] is None

    def test_nested_non_finite_floats_are_sanitized(self, tmp_path):
        log = AuditLog(output_dir=str(tmp_path))
        log.log_adjustment(
            0,
            "diagnosis",
            [
                {
                    "parameter": "stop_loss_pct",
                    "old_value": float("nan"),
                    "new_value": [0.1, float("-inf")],
                    "data_evidence": "probe",
                    "expected_effect": "none",
                }
            ],
        )

        with open(log.jsonl_path, encoding="utf-8") as fh:
            line = fh.read().strip()
        assert "NaN" not in line and "Infinity" not in line
        parsed = json.loads(line)
        assert parsed["changes"][0]["old_value"] is None
        assert parsed["changes"][0]["new_value"] == [0.1, None]

    def test_session_ids_do_not_collide_within_the_same_second(self, tmp_path):
        first = AuditLog(output_dir=str(tmp_path))
        second = AuditLog(output_dir=str(tmp_path))

        assert first.session_id != second.session_id
        assert re.fullmatch(r"\d{8}_\d{6}_\d{6}_[0-9a-f]{8}", first.session_id)
        assert first.jsonl_path != second.jsonl_path
