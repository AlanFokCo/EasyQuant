"""EasyQuant AI Agent — Reference Rule-Based Strategy Optimizer.

This module provides a **standalone, rule-based parameter search** for comparison
with the AI-driven optimization workflow orchestrated by Claude Code.  It is **not**
the primary optimization driver — Claude Code performs the full self-optimization
loop directly (running backtests, analyzing results, editing strategy files, spawning
code-review sub-agents), as documented in CLAUDE.md.

Use this module to:
  • Benchmark against the AI-driven approach
  • Understand how a programmatic parameter search is implemented
  • Run quick rule-based optimization without AI agent involvement

The AI-driven workflow (Claude Code) uses only agent/audit_log.py from the agent/
directory for structured logging.  All analysis, decision-making, and file editing
are performed by Claude Code itself.

Usage (command-line, optional — reference only):

    # Rule-based optimization of a parameterized strategy:
    python agent/optimizer.py \\
        --strategy path/to/my_strategy.py \\
        --min-sharpe 1.0 \\
        --max-drawdown 0.20 \\
        --periods "2021-01-01:2022-12-31" "2022-01-01:2023-12-31"

Usage (programmatic):

    from agent.optimizer import StrategyOptimizer

    optimizer = StrategyOptimizer(
        strategy_path="agent/strategy_template.py",
        requirements={"min_sharpe": 1.0, "max_drawdown": 0.20},
        periods=[("2022-01-01", "2022-12-31"), ("2023-01-01", "2023-12-31")],
        max_iterations=10,
        audit_dir="audit_log",
    )
    best_params = optimizer.run()
"""

from __future__ import annotations

import argparse
import copy
import datetime
import importlib.util
import os
import sys
import types
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so eqlib can be imported
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agent.audit_log import AuditLog  # noqa: E402  (after path fixup)


# ---------------------------------------------------------------------------
# Default periods (used when the caller does not specify any)
# ---------------------------------------------------------------------------
_DEFAULT_PERIODS = [
    ("2021-01-01", "2021-12-31"),
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
]

# Default acceptance requirements
_DEFAULT_REQUIREMENTS: dict[str, float] = {
    "min_sharpe":          1.0,
    "max_drawdown":        0.20,   # maximum allowed abs(max_drawdown)
    "min_annual_return":   0.00,   # minimum acceptable annualized return
    "min_win_rate":        0.40,   # minimum round-trip trade win rate
}


# ===========================================================================
# Core optimizer class
# ===========================================================================

class StrategyOptimizer:
    """Autonomous strategy optimization loop.

    Parameters
    ----------
    strategy_path:
        Path to the Python strategy file.  Must define PARAMS and PARAM_RANGES
        at module level, and an ``initialize(context)`` function.
    requirements:
        Dict with any subset of: min_sharpe, max_drawdown, min_annual_return,
        min_win_rate.  Missing keys fall back to _DEFAULT_REQUIREMENTS.
    periods:
        List of (start_date, end_date) tuples (ISO strings).
    max_iterations:
        Maximum number of backtest + adjustment cycles.
    starting_cash:
        Initial capital for each backtest (default 100,000).
    benchmark:
        Benchmark security code (default '000300.XSHG').
    output_strategy:
        If given, write the final optimized strategy to this path.
    audit_dir:
        Directory where audit log files are written.
    """

    def __init__(
        self,
        strategy_path: str,
        requirements: dict[str, float] | None = None,
        periods: list[tuple[str, str]] | None = None,
        max_iterations: int = 15,
        starting_cash: float = 100_000.0,
        benchmark: str = "000300.XSHG",
        output_strategy: str | None = None,
        audit_dir: str = "audit_log",
    ):
        self.strategy_path = os.path.abspath(strategy_path)
        self.requirements = {**_DEFAULT_REQUIREMENTS, **(requirements or {})}
        self.periods = periods or _DEFAULT_PERIODS
        self.max_iterations = max_iterations
        self.starting_cash = starting_cash
        self.benchmark = benchmark
        self.output_strategy = output_strategy
        self.audit = AuditLog(output_dir=audit_dir)

        # Load the strategy module once; we mutate its PARAMS between iterations
        self._strategy_mod = _load_strategy_module(self.strategy_path)
        self._validate_strategy_module()

        # Track best params seen (by avg_sharpe)
        self._best_params: dict = copy.deepcopy(self._strategy_mod.PARAMS)
        self._best_aggregate: dict = {}
        self._best_sharpe: float = float("-inf")

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self) -> dict:
        """Execute the self-optimization loop.

        Returns the best PARAMS dict found.
        """
        print(f"\n{'='*65}")
        print("EasyQuant Autonomous Strategy Optimizer")
        print(f"{'='*65}")
        print(f"Strategy   : {self.strategy_path}")
        print(f"Periods    : {len(self.periods)} × {[f'{s}→{e}' for s, e in self.periods]}")
        print(f"Max iters  : {self.max_iterations}")
        print(f"Requirements:")
        for k, v in self.requirements.items():
            print(f"  {k:<22} = {v}")
        print(f"Audit log  : {self.audit.jsonl_path}")
        print()

        for iteration in range(self.max_iterations + 1):
            print(f"{'─'*65}")
            label = "Baseline" if iteration == 0 else f"Iteration {iteration}"
            print(f"[{label}] params: {dict(self._strategy_mod.PARAMS)}")

            # 1. Run backtests across all periods
            periods_results = self._run_all_periods()

            # 2. Compute aggregate metrics
            aggregate = _compute_aggregate(periods_results)

            # 3. Track best
            avg_sharpe = aggregate.get("avg_sharpe", float("-inf"))
            if avg_sharpe > self._best_sharpe:
                self._best_sharpe = avg_sharpe
                self._best_params = copy.deepcopy(dict(self._strategy_mod.PARAMS))
                self._best_aggregate = copy.deepcopy(aggregate)

            # 4. Evaluate requirements
            met, failing = self._evaluate_requirements(periods_results, aggregate)

            # 5. Log iteration
            self.audit.log_iteration(
                iteration=iteration,
                params=dict(self._strategy_mod.PARAMS),
                periods_results=periods_results,
                aggregate=aggregate,
                requirements_met=met,
                failing=failing,
            )

            _print_aggregate(aggregate, met, failing)

            # 6. If requirements met → done
            if met:
                print(f"\n✅  All requirements met after {iteration} iteration(s).")
                self._finish("requirements_met", iteration)
                return self._best_params

            # 7. If last iteration → stop
            if iteration == self.max_iterations:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached.")
                self._finish("max_iterations_reached", iteration)
                return self._best_params

            # 8. Generate adjustments
            diagnosis, changes = self._generate_adjustments(periods_results, aggregate)
            if not changes:
                print("\n⚠️  No further adjustments possible within PARAM_RANGES.")
                self._finish("no_improvement", iteration)
                return self._best_params

            # 9. Log adjustment
            self.audit.log_adjustment(
                iteration=iteration,
                diagnosis=diagnosis,
                changes=changes,
            )

            # 10. Code review
            corrections = self._apply_and_review(changes, iteration=iteration)

            adj_summary = [f"{c['parameter']}: {c['old_value']}->{c['new_value']}" for c in changes]
            print("  -> Adjustment:", adj_summary)

        return self._best_params

    # -----------------------------------------------------------------------
    # Backtest execution
    # -----------------------------------------------------------------------

    def _run_all_periods(self) -> list[dict]:
        """Run one backtest per period and return per-period metric dicts."""
        from eqlib import run_backtest, analyze_returns

        results = []
        for start, end in self.periods:
            securities = getattr(self._strategy_mod, "SECURITIES", None) or \
                         getattr(self._strategy_mod, "STOCK_POOL", None)
            try:
                result = run_backtest(
                    self._strategy_mod.initialize,
                    start_date=start,
                    end_date=end,
                    starting_cash=self.starting_cash,
                    benchmark=self.benchmark,
                    securities=securities,
                )
            except Exception as exc:
                print(f"  [WARNING] Backtest {start}→{end} failed: {exc}")
                results.append({
                    "start": start, "end": end,
                    "error": str(exc),
                    "sharpe_ratio": 0.0, "max_drawdown": -1.0, "annual_return": -1.0,
                    "win_rate_trade": 0.0, "trade_count": 0, "alpha": -1.0, "beta": 1.0,
                    "sortino_ratio": 0.0, "calmar_ratio": 0.0,
                })
                continue

            if result is None:
                results.append({
                    "start": start, "end": end, "error": "no_result",
                    "sharpe_ratio": 0.0, "max_drawdown": -1.0, "annual_return": -1.0,
                    "win_rate_trade": 0.0, "trade_count": 0, "alpha": -1.0, "beta": 1.0,
                    "sortino_ratio": 0.0, "calmar_ratio": 0.0,
                })
                continue

            try:
                metrics = analyze_returns(result, risk_free_rate=0.03) or {}
            except Exception:
                metrics = {}

            ctx = result.get("context")
            trade_count = len(result.get("trade_log", []))
            pmetrics = {
                "start": start,
                "end": end,
                "sharpe_ratio":   float(metrics.get("sharpe_ratio", 0.0)),
                "sortino_ratio":  float(metrics.get("sortino_ratio", 0.0)),
                "max_drawdown":   float(metrics.get("max_drawdown", -1.0)),
                "annual_return":  float(metrics.get("annual_return", -1.0)),
                "calmar_ratio":   float(metrics.get("calmar_ratio", 0.0)),
                "alpha":          float(metrics.get("alpha", 0.0)),
                "beta":           float(metrics.get("beta", 1.0)),
                "win_rate_trade": float(metrics.get("win_rate_trade", 0.0)),
                "trade_count":    int(trade_count),
                "total_return":   float(metrics.get("total_return", 0.0)),
            }
            if ctx is not None:
                pmetrics["final_value"] = float(ctx.portfolio.total_value)
            results.append(pmetrics)

        return results

    # -----------------------------------------------------------------------
    # Requirements evaluation
    # -----------------------------------------------------------------------

    def _evaluate_requirements(
        self,
        periods_results: list[dict],
        aggregate: dict,
    ) -> tuple[bool, list[str]]:
        """Return (all_met, list_of_failing_descriptions)."""
        failing: list[str] = []
        req = self.requirements

        # Per-period checks
        for p in periods_results:
            period_label = f"{p['start']}–{p['end']}"
            if "error" in p:
                failing.append(f"{period_label}: backtest error — {p['error']}")
                continue
            sharpe = p.get("sharpe_ratio", 0.0)
            drawdown = p.get("max_drawdown", -1.0)
            ann_ret = p.get("annual_return", -1.0)
            wr = p.get("win_rate_trade", 0.0)
            if sharpe < req["min_sharpe"]:
                failing.append(f"{period_label}: sharpe {sharpe:.2f} < {req['min_sharpe']}")
            if abs(drawdown) > req["max_drawdown"]:
                failing.append(
                    f"{period_label}: max_drawdown {drawdown*100:.1f}% worse than "
                    f"-{req['max_drawdown']*100:.0f}%"
                )
            if ann_ret < req["min_annual_return"]:
                failing.append(
                    f"{period_label}: annual_return {ann_ret*100:.1f}% < "
                    f"{req['min_annual_return']*100:.0f}%"
                )
            if wr < req["min_win_rate"]:
                failing.append(
                    f"{period_label}: win_rate {wr*100:.1f}% < "
                    f"{req['min_win_rate']*100:.0f}%"
                )

        # Aggregate check
        avg_sharpe = aggregate.get("avg_sharpe", 0.0)
        if avg_sharpe < req["min_sharpe"] and not any("sharpe" in f for f in failing):
            failing.append(f"avg_sharpe {avg_sharpe:.2f} < {req['min_sharpe']}")

        return len(failing) == 0, failing

    # -----------------------------------------------------------------------
    # Adjustment generation (data-driven, rule-based)
    # -----------------------------------------------------------------------

    def _generate_adjustments(
        self,
        periods_results: list[dict],
        aggregate: dict,
    ) -> tuple[str, list[dict]]:
        """Produce (diagnosis_str, list_of_changes) based on failing metrics."""
        params = self._strategy_mod.PARAMS
        ranges = self._strategy_mod.PARAM_RANGES
        req = self.requirements

        # Summarise which metrics are failing and by how much
        avg_sharpe   = aggregate.get("avg_sharpe", 0.0)
        worst_dd     = aggregate.get("worst_drawdown", -1.0)
        avg_ret      = aggregate.get("avg_annual_return", 0.0)
        avg_wr       = aggregate.get("avg_win_rate", 0.0)
        avg_trades   = aggregate.get("avg_trades_per_year", 0.0)
        avg_vol      = aggregate.get("avg_annual_volatility", 0.2)

        diagnosis_parts: list[str] = []
        changes: list[dict] = []

        # Priority 1: max drawdown violation (risk control first)
        if abs(worst_dd) > req["max_drawdown"]:
            diagnosis_parts.append(
                f"Max drawdown {worst_dd*100:.1f}% exceeds -{req['max_drawdown']*100:.0f}% limit."
            )
            adj = _try_adjust(params, ranges, "stop_loss_pct", direction=-1)
            if adj:
                changes.append({
                    "parameter": "stop_loss_pct",
                    "old_value": adj[0], "new_value": adj[1],
                    "data_evidence": f"worst_drawdown={worst_dd*100:.1f}%; tightening stop to reduce tail loss",
                    "expected_effect": "Reduce max drawdown by cutting losing positions earlier",
                })
            elif _has_param(params, "position_pct"):
                adj = _try_adjust(params, ranges, "position_pct", direction=-1)
                if adj:
                    changes.append({
                        "parameter": "position_pct",
                        "old_value": adj[0], "new_value": adj[1],
                        "data_evidence": f"worst_drawdown={worst_dd*100:.1f}%; reducing position size",
                        "expected_effect": "Lower per-trade exposure reduces portfolio drawdown magnitude",
                    })

        # Priority 2: sharpe too low — diagnose root cause
        if avg_sharpe < req["min_sharpe"] and len(changes) < 2:
            diagnosis_parts.append(
                f"Avg Sharpe {avg_sharpe:.2f} < {req['min_sharpe']}."
            )
            if avg_ret >= 0.05 and avg_vol > 0.18:
                # Decent return but high volatility → reduce position size
                diagnosis_parts.append("Return adequate but volatility high; reducing exposure.")
                adj = _try_adjust(params, ranges, "position_pct", direction=-1)
                if adj and len(changes) < 2:
                    changes.append({
                        "parameter": "position_pct",
                        "old_value": adj[0], "new_value": adj[1],
                        "data_evidence": (
                            f"avg_sharpe={avg_sharpe:.2f}, avg_vol≈{avg_vol*100:.0f}%; "
                            "volatility is the binding constraint"
                        ),
                        "expected_effect": "Lower portfolio volatility, improving risk-adjusted return",
                    })
            else:
                # Low return → try to improve signal quality with longer slow MA
                diagnosis_parts.append("Return insufficient; increasing slow period for better trend filter.")
                adj = _try_adjust(params, ranges, "slow_period", direction=+1)
                if adj and len(changes) < 2:
                    changes.append({
                        "parameter": "slow_period",
                        "old_value": adj[0], "new_value": adj[1],
                        "data_evidence": (
                            f"avg_annual_return={avg_ret*100:.1f}%; "
                            "longer slow MA reduces false crossovers"
                        ),
                        "expected_effect": "Fewer but higher-quality trades; improved signal-to-noise",
                    })

        # Priority 3: win rate too low → require stronger confirmation
        if avg_wr < req["min_win_rate"] and len(changes) < 2:
            diagnosis_parts.append(
                f"Avg win rate {avg_wr*100:.1f}% < {req['min_win_rate']*100:.0f}%."
            )
            adj = _try_adjust(params, ranges, "vol_confirm_mul", direction=+1)
            if adj and len(changes) < 2:
                changes.append({
                    "parameter": "vol_confirm_mul",
                    "old_value": adj[0], "new_value": adj[1],
                    "data_evidence": (
                        f"win_rate_trade={avg_wr*100:.1f}%; many low-volume false signals detected"
                    ),
                    "expected_effect": "Require stronger volume confirmation; fewer but higher-quality entries",
                })
            else:
                adj = _try_adjust(params, ranges, "fast_period", direction=+1)
                if adj and len(changes) < 2:
                    changes.append({
                        "parameter": "fast_period",
                        "old_value": adj[0], "new_value": adj[1],
                        "data_evidence": (
                            f"win_rate_trade={avg_wr*100:.1f}%; "
                            "slightly slower fast MA reduces whipsaws"
                        ),
                        "expected_effect": "Fewer false crossovers; improved trade quality",
                    })

        # Priority 4: too few trades → relax confirmation
        if avg_trades < 3.0 and len(changes) < 2:
            diagnosis_parts.append(
                f"Only ~{avg_trades:.1f} trades/year; strategy is too restrictive."
            )
            adj = _try_adjust(params, ranges, "vol_confirm_mul", direction=-1)
            if adj and len(changes) < 2:
                changes.append({
                    "parameter": "vol_confirm_mul",
                    "old_value": adj[0], "new_value": adj[1],
                    "data_evidence": (
                        f"avg_trades_per_year≈{avg_trades:.1f}; "
                        "relaxing volume filter to allow more entries"
                    ),
                    "expected_effect": "More entry opportunities while keeping trend direction filter",
                })

        # Fallback: nudge slow_period if nothing else triggered
        if not changes:
            diagnosis_parts.append(
                "No dominant failing metric; exploring slow_period neighbourhood."
            )
            # Alternate between increasing and decreasing based on current iteration
            # Use a simple heuristic: if avg_return > 0 try increasing, else decreasing
            direction = +1 if avg_ret >= 0 else -1
            adj = _try_adjust(params, ranges, "slow_period", direction=direction)
            if adj:
                changes.append({
                    "parameter": "slow_period",
                    "old_value": adj[0], "new_value": adj[1],
                    "data_evidence": (
                        f"avg_annual_return={avg_ret*100:.1f}%, avg_sharpe={avg_sharpe:.2f}; "
                        "exploratory adjustment"
                    ),
                    "expected_effect": "Explore parameter neighbourhood for better Sharpe/return trade-off",
                })
            else:
                # Nothing more to adjust
                return " ".join(diagnosis_parts), []

        return " ".join(diagnosis_parts), changes

    # -----------------------------------------------------------------------
    # Code review + apply
    # -----------------------------------------------------------------------

    def _apply_and_review(self, changes: list[dict], iteration: int) -> list[str]:
        """Apply parameter changes and log a code review; return correction list."""
        params = self._strategy_mod.PARAMS
        ranges = self._strategy_mod.PARAM_RANGES
        checks: list[dict] = []
        corrections: list[str] = []

        # Check 1: values in range
        in_range = True
        for c in changes:
            p = c["parameter"]
            v = c["new_value"]
            lo, hi, _ = ranges[p]
            if not (lo <= v <= hi):
                in_range = False
                corrections.append(
                    f"Parameter '{p}' new value {v} out of range [{lo}, {hi}]; clamped."
                )
                c["new_value"] = max(lo, min(hi, v))
        checks.append({
            "check": "values_in_range",
            "passed": in_range,
            "detail": "All new values within PARAM_RANGES" if in_range else f"{len(corrections)} values clamped",
        })

        # Apply the changes
        for c in changes:
            params[c["parameter"]] = c["new_value"]

        # Check 2: cross-parameter constraints
        constraint_issues: list[str] = []
        if "fast_period" in params and "slow_period" in params:
            if params["fast_period"] >= params["slow_period"]:
                # Fix: bump slow_period by one step
                lo, hi, step = ranges.get("slow_period", (10, 60, 5))
                new_slow = min(hi, params["fast_period"] + step)
                msg = (
                    f"fast_period ({params['fast_period']}) >= slow_period "
                    f"({params['slow_period']}); adjusted slow_period to {new_slow}"
                )
                constraint_issues.append(msg)
                corrections.append(msg)
                params["slow_period"] = new_slow
        if "rsi_oversold" in params and "rsi_overbought" in params:
            if params["rsi_oversold"] >= params["rsi_overbought"]:
                lo, hi, step = ranges.get("rsi_overbought", (60, 80, 5))
                new_ob = min(hi, params["rsi_oversold"] + step)
                msg = (
                    f"rsi_oversold ({params['rsi_oversold']}) >= rsi_overbought "
                    f"({params['rsi_overbought']}); adjusted rsi_overbought to {new_ob}"
                )
                constraint_issues.append(msg)
                corrections.append(msg)
                params["rsi_overbought"] = new_ob
        checks.append({
            "check": "cross_param_constraints",
            "passed": len(constraint_issues) == 0,
            "detail": "; ".join(constraint_issues) if constraint_issues else "All constraints satisfied",
        })

        # Check 3: params referenced in strategy source
        missing_refs: list[str] = []
        with open(self.strategy_path, "r", encoding="utf-8") as fh:
            source = fh.read()
        for c in changes:
            p = c["parameter"]
            if f"PARAMS['{p}']" not in source and f'PARAMS["{p}"]' not in source:
                missing_refs.append(p)
        checks.append({
            "check": "params_used_in_code",
            "passed": len(missing_refs) == 0,
            "detail": (
                f"Parameters {missing_refs} not found as PARAMS[key] in strategy source. "
                "Changes applied to PARAMS dict but may have no effect on strategy logic."
                if missing_refs
                else f"All changed parameters referenced via PARAMS[key]"
            ),
        })
        if missing_refs:
            corrections.append(
                f"Parameters {missing_refs} changed but not referenced via PARAMS[key] "
                "in strategy source — verify strategy reads these values from PARAMS."
            )

        self.audit.log_code_review(
            iteration=iteration,
            checks=checks,
            corrections=corrections,
        )
        return corrections

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _validate_strategy_module(self) -> None:
        mod = self._strategy_mod
        if not hasattr(mod, "PARAMS"):
            raise AttributeError(
                f"Strategy module '{self.strategy_path}' must define a module-level PARAMS dict."
            )
        if not hasattr(mod, "PARAM_RANGES"):
            raise AttributeError(
                f"Strategy module '{self.strategy_path}' must define a module-level PARAM_RANGES dict."
            )
        if not hasattr(mod, "initialize"):
            raise AttributeError(
                f"Strategy module '{self.strategy_path}' must define an initialize(context) function."
            )

    def _finish(self, stopping_reason: str, total_iterations: int) -> None:
        """Write final audit entry and optionally output the optimized strategy file."""
        recommendation = _build_recommendation(
            stopping_reason, self._best_params, self._best_aggregate, self.requirements
        )
        self.audit.log_final(
            total_iterations=total_iterations,
            stopping_reason=stopping_reason,
            final_params=self._best_params,
            final_metrics=self._best_aggregate,
            recommendation=recommendation,
        )
        print(f"\nAudit log  : {self.audit.jsonl_path}")
        print(f"Summary MD : {self.audit.md_path}")

        if self.output_strategy:
            _write_optimized_strategy(
                self.strategy_path, self.output_strategy, self._best_params
            )
            print(f"Optimized  : {self.output_strategy}")

        print(f"\nFinal params: {self._best_params}")
        print(f"Best avg Sharpe: {self._best_sharpe:.3f}")


# ===========================================================================
# Module loading
# ===========================================================================

def _load_strategy_module(strategy_path: str) -> types.ModuleType:
    """Import a strategy Python file as a module."""
    strategy_dir = os.path.dirname(strategy_path)
    if strategy_dir and strategy_dir not in sys.path:
        sys.path.insert(0, strategy_dir)

    spec = importlib.util.spec_from_file_location("_eq_strategy_module", strategy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load strategy from '{strategy_path}'")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# Metric aggregation
# ===========================================================================

def _compute_aggregate(periods_results: list[dict]) -> dict:
    """Compute aggregate metrics across all periods."""
    valid = [p for p in periods_results if "error" not in p]
    if not valid:
        return {}

    def _avg(key: str) -> float:
        vals = [p[key] for p in valid if key in p]
        return sum(vals) / len(vals) if vals else 0.0

    def _min(key: str) -> float:
        vals = [p[key] for p in valid if key in p]
        return min(vals) if vals else 0.0

    avg_annual_ret = _avg("annual_return")
    consistency = sum(1 for p in valid if p.get("annual_return", 0) > 0) / len(valid) if valid else 0.0

    # Approximate avg annual volatility from Sharpe and return
    # sharpe = (ret - rf) / vol  → vol ≈ (ret - 0.03) / sharpe  when sharpe > 0
    vols = []
    for p in valid:
        sr = p.get("sharpe_ratio", 0.0)
        ar = p.get("annual_return", 0.0)
        if sr > 0.01:
            vols.append(max(0.0, (ar - 0.03) / sr))
    avg_vol = sum(vols) / len(vols) if vols else 0.2

    # Estimate trades per year
    trades_per_year_list = []
    for p in valid:
        try:
            start = datetime.date.fromisoformat(p["start"])
            end = datetime.date.fromisoformat(p["end"])
            years = max(0.001, (end - start).days / 365.25)
            trades_per_year_list.append(p.get("trade_count", 0) / years)
        except Exception:
            pass
    avg_trades_per_year = sum(trades_per_year_list) / len(trades_per_year_list) if trades_per_year_list else 0.0

    return {
        "avg_sharpe":          _avg("sharpe_ratio"),
        "avg_sortino":         _avg("sortino_ratio"),
        "worst_drawdown":      _min("max_drawdown"),
        "avg_annual_return":   avg_annual_ret,
        "avg_calmar":          _avg("calmar_ratio"),
        "avg_alpha":           _avg("alpha"),
        "avg_beta":            _avg("beta"),
        "avg_win_rate":        _avg("win_rate_trade"),
        "avg_trades_per_year": avg_trades_per_year,
        "consistency_score":   consistency,
        "avg_annual_volatility": avg_vol,
        "periods_count":       len(valid),
    }


# ===========================================================================
# Parameter adjustment helpers
# ===========================================================================

def _has_param(params: dict, key: str) -> bool:
    return key in params


_FLOAT_ROUND_DIGITS = 6  # decimal places used when rounding adjusted parameter values


def _try_adjust(
    params: dict,
    ranges: dict,
    key: str,
    direction: int,  # +1 or -1
) -> tuple[Any, Any] | None:
    """Try to adjust params[key] by one step in the given direction.

    Returns (old_value, new_value) if adjustment is valid, else None.
    Does NOT apply the change; caller must do that.
    """
    if key not in params or key not in ranges:
        return None
    lo, hi, step = ranges[key]
    old = params[key]
    new = old + direction * step
    # Round to avoid float precision issues
    new = round(new, _FLOAT_ROUND_DIGITS)
    if new < lo or new > hi:
        return None
    return (old, new)


# ===========================================================================
# Output helpers
# ===========================================================================

def _print_aggregate(aggregate: dict, met: bool, failing: list[str]) -> None:
    status = "✅ MET" if met else "❌ NOT MET"
    print(f"  avg_sharpe={aggregate.get('avg_sharpe', 0):.2f}  "
          f"worst_dd={aggregate.get('worst_drawdown', -1)*100:.1f}%  "
          f"avg_ret={aggregate.get('avg_annual_return', 0)*100:.1f}%  "
          f"avg_wr={aggregate.get('avg_win_rate', 0)*100:.1f}%  "
          f"→ {status}")
    if failing:
        for f in failing[:3]:
            print(f"    ✗ {f}")
        if len(failing) > 3:
            print(f"    ... and {len(failing)-3} more")


def _build_recommendation(
    stopping_reason: str,
    best_params: dict,
    best_aggregate: dict,
    requirements: dict,
) -> str:
    lines: list[str] = []
    if stopping_reason == "requirements_met":
        lines.append("Strategy meets all user-defined requirements.")
    elif stopping_reason == "max_iterations_reached":
        lines.append(
            "Max iterations reached without fully meeting all requirements. "
            "The best parameter set found so far is reported. "
            "Consider relaxing requirements or increasing max_iterations."
        )
    else:
        lines.append("Optimization stopped: no further parameter improvements possible within the defined ranges.")

    avg_sharpe = best_aggregate.get("avg_sharpe", 0.0)
    consistency = best_aggregate.get("consistency_score", 0.0)
    worst_dd = best_aggregate.get("worst_drawdown", -1.0)

    lines.append(
        f"Best avg Sharpe: {avg_sharpe:.2f}. "
        f"Profitable in {consistency*100:.0f}% of tested periods. "
        f"Worst drawdown: {worst_dd*100:.1f}%."
    )

    if avg_sharpe < requirements.get("min_sharpe", 1.0):
        lines.append(
            "Sharpe target not fully achieved. Consider: (1) adding index/market filter, "
            "(2) using RSI or Bollinger Band confirmation, "
            "(3) testing on a different stock or longer history."
        )
    if abs(worst_dd) > requirements.get("max_drawdown", 0.20):
        lines.append(
            "Drawdown exceeds target. Consider: (1) tighter stop-loss, "
            "(2) position sizing based on ATR, (3) market regime filter."
        )

    return " ".join(lines)


def _write_optimized_strategy(
    source_path: str,
    output_path: str,
    final_params: dict,
) -> None:
    """Write a copy of the strategy with PARAMS block updated to final_params."""
    with open(source_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    # Build new PARAMS block
    lines = ["PARAMS = {"]
    for k, v in final_params.items():
        lines.append(f"    {k!r}: {v!r},")
    lines.append("}")
    new_params_block = "\n".join(lines)

    # Replace existing PARAMS = { ... } block
    import re
    pattern = r"^PARAMS\s*=\s*\{[^}]*\}"
    replacement = new_params_block
    new_source, n = re.subn(pattern, replacement, source, flags=re.MULTILINE | re.DOTALL)
    if n == 0:
        # Could not find/replace; append a note at the end
        new_source = source + f"\n\n# Optimized by EasyQuant agent\n{new_params_block}\n"

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(new_source)


# ===========================================================================
# CLI entry point
# ===========================================================================

def _parse_period(s: str) -> tuple[str, str]:
    """Parse 'YYYY-MM-DD:YYYY-MM-DD' into a (start, end) tuple."""
    parts = s.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"Period must be 'start:end' (e.g. '2022-01-01:2022-12-31'), got: {s!r}"
        )
    return (parts[0].strip(), parts[1].strip())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EasyQuant AI Agent — autonomous strategy self-optimization loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--strategy",
        default=os.path.join(_HERE, "strategy_template.py"),
        help="Path to strategy .py file (must define PARAMS, PARAM_RANGES, initialize)",
    )
    parser.add_argument("--min-sharpe",         type=float, default=None)
    parser.add_argument("--max-drawdown",        type=float, default=None,
                        help="Maximum allowed drawdown as a positive fraction, e.g. 0.20 for 20%%")
    parser.add_argument("--min-annual-return",   type=float, default=None)
    parser.add_argument("--min-win-rate",        type=float, default=None)
    parser.add_argument("--max-iterations",      type=int,   default=15)
    parser.add_argument("--starting-cash",       type=float, default=100_000.0)
    parser.add_argument("--benchmark",           default="000300.XSHG")
    parser.add_argument(
        "--periods",
        nargs="*",
        type=_parse_period,
        default=None,
        metavar="START:END",
        help="One or more 'YYYY-MM-DD:YYYY-MM-DD' period strings",
    )
    parser.add_argument("--output-strategy", default=None, help="Write optimized strategy to this file")
    parser.add_argument("--audit-dir",       default="audit_log")
    args = parser.parse_args()

    requirements: dict[str, float] = {}
    if args.min_sharpe        is not None: requirements["min_sharpe"]        = args.min_sharpe
    if args.max_drawdown      is not None: requirements["max_drawdown"]      = args.max_drawdown
    if args.min_annual_return is not None: requirements["min_annual_return"] = args.min_annual_return
    if args.min_win_rate      is not None: requirements["min_win_rate"]      = args.min_win_rate

    optimizer = StrategyOptimizer(
        strategy_path=args.strategy,
        requirements=requirements or None,
        periods=args.periods,
        max_iterations=args.max_iterations,
        starting_cash=args.starting_cash,
        benchmark=args.benchmark,
        output_strategy=args.output_strategy,
        audit_dir=args.audit_dir,
    )
    optimizer.run()


if __name__ == "__main__":
    main()
