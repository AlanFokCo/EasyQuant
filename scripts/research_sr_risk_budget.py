#!/usr/bin/env python3
"""Replay the declared support/resistance experiments on frozen CSV inputs.

Run one candidate and one chronological period per process. No downloads,
automatic parameter search, or return-driven promotion are performed.
The 11 candidates include failed hypotheses; none passed the original gate.
See docs/explanation/sr-risk-budget.md for evidence and data limitations.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    # examples is repository code, not part of the installed eqlib package.
    sys.path.insert(0, str(ROOT))

import pandas as pd

from eqlib import OrderCost, log
from eqlib.strategies.sr_risk_budget import SRRiskConfig
from examples._defaults import DEFAULT_ORDER_COST, INDEX_HS300, STOCKS

BASE = SRRiskConfig()
SHORT = replace(BASE, level_window=20)
BREAKOUT = replace(SHORT, allow_breakout=True)
TREND = replace(
    BREAKOUT,
    stop_atr=2.5,
    trailing_atr=4.0,
    breakout_target_r=6.0,
    max_holding_days=120,
    max_stop_pct=0.12,
)
EARLY = replace(BREAKOUT, require_market_slope=False)
CONFIGS = {
    "baseline": BASE,
    "short_levels": SHORT,
    "breakout": BREAKOUT,
    "trend_exit": TREND,
    "early_market": EARLY,
    "long_trend": replace(EARLY, trend_window=120),
    "early_trend_exit": replace(TREND, require_market_slope=False),
    "channel60": replace(BASE, allow_breakout=True),
    "stock_exits": replace(BREAKOUT, exit_on_market_filter=False),
    "channel60_stock_exits": replace(
        BASE, allow_breakout=True, exit_on_market_filter=False
    ),
    "patient_exits": replace(BREAKOUT, breakout_target_r=6.0, max_holding_days=120),
}
# Frozen historical protocol. Reusing these periods to retune is NOT a new OOS test.
PERIODS = {
    "development": ("2020-01-01", "2022-12-31"),
    "validation": ("2023-01-01", "2024-12-31"),
    "later_check": ("2025-01-01", "2026-09-10"),
    "full": ("2020-01-01", "2026-09-10"),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CONFIGS, required=True)
    parser.add_argument("--period", choices=PERIODS, default="development")
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--data-dir", type=Path, default=Path("data/sr_risk_budget"))
    parser.add_argument("--output", type=Path, default=Path("reports/sr_optimization"))
    args = parser.parse_args(argv)
    if not math.isfinite(args.cash) or args.cash <= 0:
        parser.error("cash must be finite and positive")
    destination = (
        args.output
        / args.period
        / (args.candidate + ("_stress" if args.stress else ""))
    )
    if destination.exists():
        parser.error(f"output exists; choose a new --output directory: {destination}")
    spec = importlib.util.spec_from_file_location(
        "sr_research_example", ROOT / "examples/25_sr_risk_budget.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    config = CONFIGS[args.candidate]
    cost = DEFAULT_ORDER_COST
    if args.stress:
        config = replace(config, slippage=0.003)
        cost = OrderCost(
            **{
                **vars(cost),
                "open_commission": cost.open_commission * 2,
                "close_commission": cost.close_commission * 2,
                "min_commission": cost.min_commission * 2,
            }
        )
    start, end = PERIODS[args.period]
    codes = list(STOCKS.values())
    frames, manifest = runner.read_inputs(
        args.data_dir, codes + [INDEX_HS300], start, end, config
    )
    log.set_quiet(True)
    with patch(
        "requests.sessions.Session.request",
        side_effect=AssertionError("research runs must use frozen local inputs"),
    ):
        result, metrics = runner.run_snapshot(
            frames, codes, start, end, args.cash, config, cost
        )
    equity = pd.DataFrame(result["recorded_values"])
    metrics.update(
        average_exposure=float(equity.sr_exposure.mean()),
        maximum_exposure=float(equity.sr_exposure.max()),
        invested_sessions=int((equity.sr_exposure > 0).sum()),
        halted_sessions=int(equity.sr_halted.sum()),
    )
    source_paths = [
        "scripts/research_sr_risk_budget.py",
        "examples/25_sr_risk_budget.py",
        "eqlib/strategies/sr_risk_budget.py",
        "eqlib/engine.py",
    ]
    payload = {
        "candidate": args.candidate,
        "period": args.period,
        "stress": args.stress,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "starting_cash": args.cash,
        "profitability_proven": False,
        "original_experiment_gate_passed": False,
        "config": asdict(config),
        "costs": vars(cost),
        "data": manifest,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths
        },
        "metrics": metrics,
        "years": {
            str(year): runner.period_metrics(
                result, frames[INDEX_HS300], f"{year}-01-01", f"{year}-12-31"
            )
            for year in range(int(start[:4]), int(end[:4]) + 1)
        },
        "limitations": [
            "Static eight-stock watchlist; no point-in-time membership/ST ledger.",
            "Record the adjustment source; normalized hfq is not native qfq.",
            "Adjusted-price fills do not model raw prices and corporate actions.",
            "Periods restart from cash; full-period yearly slices do not.",
            "Baseline history was inspected; later_check is not pristine OOS.",
            "Three rounds, 11 candidates; validation was reused.",
            "Do not retune against later_check or promote on full-period return.",
        ],
    }
    # Reserve only after a successful run; never overwrite earlier evidence.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    equity.to_csv(destination / "equity.csv", index=False)
    pd.DataFrame(result["trade_log"]).to_csv(destination / "trades.csv", index=False)
    pd.DataFrame(result["context"].sr_risk_budget.events).to_csv(
        destination / "events.csv", index=False
    )
    print(json.dumps(metrics, indent=2, allow_nan=False))
    print(f"Research outputs: {destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
