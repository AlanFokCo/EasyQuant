"""Audit logging for the EasyQuant AI optimization agent.

Writes a dual-format audit trail:
  • JSONL file  — one JSON object per line, machine-readable, queryable with jq
  • Markdown file — human-readable narrative summary

Both files share the same session ID (timestamp) and live in the audit_log/ dir.

Usage (from optimizer.py):
    from agent.audit_log import AuditLog
    log = AuditLog(output_dir="audit_log")
    log.log_iteration(0, params, periods_results, aggregate, requirements_met, failing)
    log.log_adjustment(0, diagnosis, changes)
    log.log_code_review(0, checks, corrections)
    log.log_final(total_iterations, stopping_reason, final_params, final_metrics, recommendation)
    log.write_summary_md()
"""

import datetime
import json
import os
from typing import Any


class AuditLog:
    """Writes structured optimization audit entries in JSONL and Markdown formats."""

    def __init__(self, output_dir: str = "audit_log"):
        os.makedirs(output_dir, exist_ok=True)
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._jsonl_path = os.path.join(output_dir, f"session_{self.session_id}.jsonl")
        self._md_path = os.path.join(output_dir, f"session_{self.session_id}.md")
        self._entries: list[dict] = []

        # Write Markdown header immediately so the file exists even if the run aborts
        with open(self._md_path, "w", encoding="utf-8") as fh:
            fh.write(f"# EasyQuant Strategy Optimization Audit\n\n")
            fh.write(f"**Session:** `{self.session_id}`  \n")
            fh.write(f"**Started:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")
            fh.write("---\n\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def log_iteration(
        self,
        iteration: int,
        params: dict,
        periods_results: list[dict],
        aggregate: dict,
        requirements_met: bool,
        failing: list[str],
    ) -> None:
        """Log one complete backtest iteration across all tested periods.

        Parameters
        ----------
        iteration:
            Zero-based iteration index (0 = baseline).
        params:
            The PARAMS dict used for this iteration.
        periods_results:
            List of per-period metric dicts, each containing keys like
            start, end, sharpe_ratio, max_drawdown, annual_return, etc.
        aggregate:
            Aggregate metrics across all periods (avg_sharpe, worst_drawdown, etc.).
        requirements_met:
            Whether all user requirements are satisfied in this iteration.
        failing:
            Human-readable list of failing requirement descriptions.
        """
        entry = {
            "type": "iteration",
            "session_id": self.session_id,
            "iteration": iteration,
            "timestamp": _now_iso(),
            "params": params,
            "periods": periods_results,
            "aggregate": aggregate,
            "requirements_met": requirements_met,
            "failing": failing,
        }
        self._write_jsonl(entry)
        self._append_md_iteration(entry)

    def log_adjustment(
        self,
        iteration: int,
        diagnosis: str,
        changes: list[dict],
    ) -> None:
        """Log a parameter adjustment decision with its data-driven rationale.

        Parameters
        ----------
        iteration:
            The iteration number that *produced* the data triggering this adjustment.
        diagnosis:
            Human-readable analysis of which metrics failed and why.
        changes:
            List of dicts, each with:
                parameter, old_value, new_value, data_evidence, expected_effect
        """
        entry = {
            "type": "adjustment",
            "session_id": self.session_id,
            "iteration": iteration,
            "timestamp": _now_iso(),
            "diagnosis": diagnosis,
            "changes": changes,
        }
        self._write_jsonl(entry)
        self._append_md_adjustment(entry)

    def log_code_review(
        self,
        iteration: int,
        checks: list[dict],
        corrections: list[str],
    ) -> None:
        """Log the result of the post-adjustment code review.

        Parameters
        ----------
        iteration:
            The iteration number whose adjustment triggered this review.
        checks:
            List of dicts with keys: check (name), passed (bool), detail (str).
        corrections:
            List of human-readable descriptions of any fixes applied.
        """
        overall_passed = all(c.get("passed", False) for c in checks)
        entry = {
            "type": "code_review",
            "session_id": self.session_id,
            "iteration": iteration,
            "timestamp": _now_iso(),
            "checks": checks,
            "overall_passed": overall_passed,
            "corrections": corrections,
        }
        self._write_jsonl(entry)
        self._append_md_code_review(entry)

    def log_final(
        self,
        total_iterations: int,
        stopping_reason: str,
        final_params: dict,
        final_metrics: dict,
        recommendation: str,
    ) -> None:
        """Log the final optimization result.

        Parameters
        ----------
        total_iterations:
            Total number of backtest iterations run.
        stopping_reason:
            One of: 'requirements_met', 'max_iterations_reached', 'no_improvement'.
        final_params:
            The best PARAMS dict found.
        final_metrics:
            Aggregate metrics dict for the final parameter set.
        recommendation:
            Human-readable summary and forward-looking advice.
        """
        entry = {
            "type": "final",
            "session_id": self.session_id,
            "timestamp": _now_iso(),
            "total_iterations": total_iterations,
            "stopping_reason": stopping_reason,
            "final_params": final_params,
            "final_metrics": final_metrics,
            "requirements_met": stopping_reason == "requirements_met",
            "recommendation": recommendation,
        }
        self._write_jsonl(entry)
        self._append_md_final(entry)
        self.write_summary_md()

    def write_summary_md(self) -> None:
        """Append a final summary table to the Markdown file."""
        with open(self._md_path, "a", encoding="utf-8") as fh:
            fh.write("\n---\n\n## How to replay this session\n\n")
            fh.write("```bash\n")
            fh.write(f"# Query all iterations\n")
            fh.write(
                f"jq 'select(.type==\"iteration\")' "
                f"audit_log/session_{self.session_id}.jsonl\n\n"
            )
            fh.write(f"# Show adjustment rationales only\n")
            fh.write(
                f"jq 'select(.type==\"adjustment\") | "
                f"{{iter: .iteration, diagnosis: .diagnosis}}' "
                f"audit_log/session_{self.session_id}.jsonl\n"
            )
            fh.write("```\n")

    @property
    def jsonl_path(self) -> str:
        return self._jsonl_path

    @property
    def md_path(self) -> str:
        return self._md_path

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _write_jsonl(self, entry: dict) -> None:
        """Append one JSON entry to the JSONL file (atomic line write)."""
        self._entries.append(entry)
        with open(self._jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=_json_default))
            fh.write("\n")

    def _append_md_iteration(self, entry: dict) -> None:
        iter_label = "Baseline" if entry["iteration"] == 0 else f"Iteration {entry['iteration']}"
        status = "✅ Requirements met" if entry["requirements_met"] else "❌ Requirements not met"
        with open(self._md_path, "a", encoding="utf-8") as fh:
            fh.write(f"## {iter_label}\n\n")
            fh.write(f"**Time:** {entry['timestamp']}  \n")
            fh.write(f"**Status:** {status}  \n\n")

            # Params table
            fh.write("### Parameters\n\n")
            fh.write("| Parameter | Value |\n|-----------|-------|\n")
            for k, v in entry["params"].items():
                fh.write(f"| `{k}` | `{v}` |\n")
            fh.write("\n")

            # Per-period results
            fh.write("### Period Results\n\n")
            fh.write(
                "| Period | Sharpe | Max DD | Ann Return | Win Rate | Trades |\n"
                "|--------|--------|--------|------------|----------|--------|\n"
            )
            for p in entry["periods"]:
                sharpe = p.get("sharpe_ratio", float("nan"))
                maxdd = p.get("max_drawdown", float("nan"))
                ret = p.get("annual_return", float("nan"))
                wr = p.get("win_rate_trade", float("nan"))
                tc = p.get("trade_count", "?")
                period_label = f"{p.get('start','?')} – {p.get('end','?')}"
                fh.write(
                    f"| {period_label} | {sharpe:.2f} | {maxdd*100:.1f}% "
                    f"| {ret*100:.1f}% | {wr*100:.1f}% | {tc} |\n"
                )

            # Aggregate
            agg = entry["aggregate"]
            fh.write("\n**Aggregate:**  \n")
            for k, v in agg.items():
                if isinstance(v, float):
                    fh.write(f"- `{k}` = `{v:.4f}`  \n")
                else:
                    fh.write(f"- `{k}` = `{v}`  \n")

            # Failing requirements
            if entry["failing"]:
                fh.write("\n**Failing requirements:**\n\n")
                for f in entry["failing"]:
                    fh.write(f"- {f}\n")
            fh.write("\n---\n\n")

    def _append_md_adjustment(self, entry: dict) -> None:
        with open(self._md_path, "a", encoding="utf-8") as fh:
            fh.write(f"### Adjustment after Iteration {entry['iteration']}\n\n")
            fh.write(f"**Diagnosis:** {entry['diagnosis']}\n\n")
            fh.write("| Parameter | Old Value | New Value | Data Evidence | Expected Effect |\n")
            fh.write("|-----------|-----------|-----------|---------------|-----------------|\n")
            for c in entry["changes"]:
                fh.write(
                    f"| `{c['parameter']}` | `{c['old_value']}` | `{c['new_value']}` "
                    f"| {c['data_evidence']} | {c['expected_effect']} |\n"
                )
            fh.write("\n")

    def _append_md_code_review(self, entry: dict) -> None:
        status = "✅ Passed" if entry["overall_passed"] else "⚠️ Issues found"
        with open(self._md_path, "a", encoding="utf-8") as fh:
            fh.write(f"### Code Review — {status}\n\n")
            for c in entry["checks"]:
                icon = "✅" if c.get("passed") else "❌"
                fh.write(f"- {icon} **{c['check']}**: {c.get('detail', '')}\n")
            if entry["corrections"]:
                fh.write("\n**Corrections applied:**\n")
                for corr in entry["corrections"]:
                    fh.write(f"- {corr}\n")
            fh.write("\n---\n\n")

    def _append_md_final(self, entry: dict) -> None:
        icon = "✅" if entry["requirements_met"] else "⚠️"
        with open(self._md_path, "a", encoding="utf-8") as fh:
            fh.write(f"## {icon} Final Result\n\n")
            fh.write(f"**Stopping reason:** `{entry['stopping_reason']}`  \n")
            fh.write(f"**Total iterations:** {entry['total_iterations']}  \n\n")
            fh.write("### Final Parameters\n\n")
            fh.write("| Parameter | Value |\n|-----------|-------|\n")
            for k, v in entry["final_params"].items():
                fh.write(f"| `{k}` | `{v}` |\n")
            fh.write("\n### Final Metrics\n\n")
            for k, v in entry["final_metrics"].items():
                if isinstance(v, float):
                    fh.write(f"- `{k}` = `{v:.4f}`  \n")
                else:
                    fh.write(f"- `{k}` = `{v}`  \n")
            fh.write(f"\n### Recommendation\n\n{entry['recommendation']}\n\n")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _json_default(obj: Any) -> Any:
    """JSON serializer for types not handled by default."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "item"):
        return obj.item()  # numpy scalar → Python scalar
    return str(obj)
