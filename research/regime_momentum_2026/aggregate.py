"""Evaluate the pre-registered gate in PLAN.md §6 against frozen run outputs.

Reads ``reports/regime_momentum/<period>/<candidate>/summary.json`` produced by
``runner.py`` and decides, deterministically:

1. development selection — whether any candidate qualifies, and which one wins;
2. validation promotion — if a selected candidate has its one-shot validation
   and stress runs on disk;
3. later_check — reported as-is when present, never used to select or retune.

This script never runs backtests and never rewrites inputs. A research failure
(no qualifier, or a failed gate) is a normal outcome and exits 0; malformed or
missing artifacts for a *required* step exit non-zero, because silent gaps are
how failed studies get rescued. Writes the verdict to
``research/regime_momentum_2026/verdict.json`` (committed) while the full run
evidence stays in the gitignored ``reports/regime_momentum/`` tree.

    python research/regime_momentum_2026/aggregate.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# runner is the single source of truth for the candidate list and windows.
from runner import CONFIGS, PERIODS, period_metrics  # noqa: E402
from universe import BENCHMARK, KNOWN_LOSERS  # noqa: E402

# Frozen criteria, PLAN.md §6. Changing these after seeing results would be
# re-writing the gate; do not.
DEV_DRAWDOWN_FLOOR = -0.25
DEV_MIN_ROUND_TRIPS_PER_YEAR = 3.0
PROMOTION_MIN_SHARPE = 1.0
PROMOTION_MIN_ROUND_TRIPS_PER_YEAR = 3.0

REPORTS_DIR = Path("reports/regime_momentum")
DATA_DIR = Path("data/regime_momentum")
VERDICT_PATH = HERE / "verdict.json"


class ArtifactError(RuntimeError):
    """A required input is missing or malformed; the gate cannot be judged."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_summary(reports: Path, period: str, candidate: str) -> dict | None:
    path = reports / period / candidate / "summary.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("candidate") != candidate or payload.get("period") != period:
        raise ArtifactError(f"candidate/period mismatch in {path}")
    return payload


def development_selection(reports: Path) -> dict:
    """Apply the PLAN.md §6 selection rule to the development window."""
    found = {p.parent.name for p in reports.glob("development/*/summary.json")}
    expected = set(CONFIGS)
    missing = expected - found
    if missing:
        raise ArtifactError(
            f"missing development runs: {sorted(missing)}; run runner.py first"
        )
    unknown = found - expected
    if unknown:
        raise ArtifactError(f"unregistered candidates on disk: {sorted(unknown)}")

    table = {}
    for name in sorted(expected):
        payload = load_summary(reports, "development", name)
        m = payload["metrics"]
        checks = {
            "drawdown_above_floor": m["max_drawdown"] >= DEV_DRAWDOWN_FLOOR,
            "round_trips_sufficient": (
                m["round_trips_per_year"] is not None
                and m["round_trips_per_year"] >= DEV_MIN_ROUND_TRIPS_PER_YEAR
            ),
            "beat_benchmark": m["total_return"] > m["benchmark_return"],
        }
        table[name] = {
            "sharpe": m["sharpe"],
            "total_return": m["total_return"],
            "benchmark_return": m["benchmark_return"],
            "max_drawdown": m["max_drawdown"],
            "round_trips_per_year": m["round_trips_per_year"],
            "checks": checks,
            "qualified": all(checks.values()),
        }

    qualified = [name for name, row in table.items() if row["qualified"]]
    # Highest development Sharpe; ties break alphabetically (PLAN.md §6).
    selected = (
        sorted(qualified, key=lambda n: (-table[n]["sharpe"], n))[0]
        if qualified
        else None
    )
    return {"rule": {
                "max_drawdown_floor": DEV_DRAWDOWN_FLOOR,
                "min_round_trips_per_year": DEV_MIN_ROUND_TRIPS_PER_YEAR,
                "must_beat_benchmark": True,
                "pick": "highest development Sharpe, ties alphabetical",
            },
            "candidates": table, "qualified": qualified, "selected": selected}


def promotion_gate(reports: Path, selected: str) -> dict:
    """PLAN.md §6 validation gate: one shot, plus the stress run."""
    plain = load_summary(reports, "validation", selected)
    if plain is None:
        raise ArtifactError(
            f"selected candidate {selected!r} has no validation run; execute: "
            f"python research/regime_momentum_2026/runner.py "
            f"--candidate {selected} --period validation"
        )
    stress = load_summary(reports, "validation", f"{selected}_stress")
    if stress is None:
        raise ArtifactError(
            f"selected candidate {selected!r} has no stress run; execute: "
            f"python research/regime_momentum_2026/runner.py "
            f"--candidate {selected} --period validation --stress"
        )
    m, s = plain["metrics"], stress["metrics"]
    checks = {
        "sharpe_at_least_1": m["sharpe"] is not None
        and m["sharpe"] >= PROMOTION_MIN_SHARPE,
        "beat_benchmark": m["total_return"] > m["benchmark_return"],
        "drawdown_less_severe_than_benchmark": (
            m["max_drawdown"] > m["benchmark_max_drawdown"]
        ),
        "round_trips_sufficient": (
            m["round_trips_per_year"] is not None
            and m["round_trips_per_year"] >= PROMOTION_MIN_ROUND_TRIPS_PER_YEAR
        ),
        "stress_positive": s["total_return"] > 0,
    }
    return {
        "candidate": selected,
        "validation_metrics": m,
        "stress_total_return": s["total_return"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def yearly_slices(reports: Path, period: str, candidates: list[str],
                  benchmark_frame: pd.DataFrame) -> dict:
    """Per-calendar-year slices of each continuous run (re-based, per PLAN §4).

    Reuses ``runner.period_metrics`` on the recorded equity curve so the slice
    math cannot drift from the full-window math.
    """
    start, end = PERIODS[period]
    years = range(int(start[:4]), int(end[:4]) + 1)
    out = {}
    for name in candidates:
        payload = load_summary(reports, period, name)
        equity = pd.read_csv(reports / period / name / "equity.csv")
        shim = {
            "recorded_values": equity.to_dict("list"),
            "context": types.SimpleNamespace(
                portfolio=types.SimpleNamespace(
                    starting_cash=payload["starting_cash"]
                )
            ),
        }
        rows = []
        for year in years:
            m = period_metrics(shim, benchmark_frame,
                               f"{year}-01-01", f"{year}-12-31")
            if m is None:
                continue
            rows.append({
                "year": year,
                "total_return": m["total_return"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "benchmark_return": m["benchmark_return"],
                "benchmark_max_drawdown": m["benchmark_max_drawdown"],
            })
        out[name] = rows
    return out


def known_loser_attribution(reports: Path, data_dir: Path, candidate: str,
                            period: str) -> dict:
    """Strategy PnL on KNOWN_LOSERS vs what buy-and-hold would have lost.

    Separates *avoidance* from *selection*, as PLAN.md §7 requires.
    """
    payload = load_summary(reports, period, candidate)
    pnl = {k.split(".")[0]: v for k, v in payload["per_stock_pnl"].items()}
    start, end = PERIODS[period]
    rows = {}
    for code in sorted(KNOWN_LOSERS):
        path = data_dir / f"{code}_daily_qfq.csv"
        if not path.is_file():
            raise ArtifactError(f"missing frozen input {path}")
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        window = frame.loc[(frame.index >= start) & (frame.index <= end)]
        bh = (
            float(window["close"].iloc[-1] / window["close"].iloc[0] - 1)
            if len(window) >= 2 else None
        )
        rows[code] = {
            "strategy_pnl": pnl.get(code, 0.0),
            "buy_and_hold_return": bh,
        }
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=VERDICT_PATH)
    args = parser.parse_args(argv)
    if not args.reports.is_dir():
        print(f"no reports tree at {args.reports}; run runner.py first",
              file=sys.stderr)
        return 2

    try:
        selection = development_selection(args.reports)
        selected = selection["selected"]
        if selected is None:
            outcome = "failed_development_selection"
            promotion = None
            # A validation run without a selected candidate would mean the
            # one-shot window was burned out of protocol.
            stray = list(args.reports.glob("validation/*/summary.json"))
            if stray:
                raise ArtifactError(
                    "validation runs exist although no candidate was selected: "
                    f"{[str(p) for p in stray]}"
                )
        else:
            promotion = promotion_gate(args.reports, selected)
            outcome = "promoted" if promotion["passed"] else "failed_validation_gate"
        later = (
            load_summary(args.reports, "later_check", selected)
            if selected is not None else None
        )
        benchmark = pd.read_csv(args.data_dir / f"{BENCHMARK}_daily_qfq.csv",
                                index_col=0, parse_dates=True)
        slices = yearly_slices(args.reports, "development",
                               sorted(CONFIGS), benchmark)
        attribution = known_loser_attribution(
            args.reports, args.data_dir,
            selected if selected is not None else "base", "development",
        )
    except ArtifactError as exc:
        print(f"artifact error: {exc}", file=sys.stderr)
        return 2

    verdict = {
        "plan": "research/regime_momentum_2026/PLAN.md",
        "recorded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "outcome": outcome,
        "selection": selection,
        "promotion_gate": promotion,
        "later_check": (
            {"note": "reported as-is; never used to select or retune",
             "metrics": later["metrics"]} if later else None
        ),
        "development_yearly_slices": slices,
        "known_loser_attribution_development": attribution,
        "inputs_sha256": {
            str(p.resolve().relative_to(ROOT)): sha256(p)
            for p in sorted(args.reports.glob("*/*/summary.json"))
        },
        "source_sha256": {
            p: sha256(ROOT / p)
            for p in ("research/regime_momentum_2026/aggregate.py",
                      "research/regime_momentum_2026/runner.py",
                      "research/regime_momentum_2026/strategy.py",
                      "research/regime_momentum_2026/universe.py")
        },
    }
    args.output.write_text(json.dumps(verdict, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")

    hdr = f"{'candidate':<14} {'sharpe':>7} {'tot_ret':>9} {'bench':>9} {'max_dd':>9} {'rt/yr':>6}  gate"
    print(hdr)
    print("-" * len(hdr))
    for name, row in selection["candidates"].items():
        print(f"{name:<14} {row['sharpe']:>7.3f} {row['total_return']:>9.2%} "
              f"{row['benchmark_return']:>9.2%} {row['max_drawdown']:>9.2%} "
              f"{row['round_trips_per_year']:>6.1f}  "
              f"{'QUALIFIES' if row['qualified'] else 'fails'}")
    print(f"\nselected: {selected or '(none — no candidate qualified)'}")
    if promotion is not None:
        print(f"promotion gate: {'PASSED' if promotion['passed'] else 'FAILED'} "
              f"{promotion['checks']}")
    print(f"outcome: {outcome}")
    print(f"verdict written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
