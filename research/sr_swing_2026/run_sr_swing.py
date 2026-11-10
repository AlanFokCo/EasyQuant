"""Replay sr_swing on the frozen regime_momentum inputs, offline.

One run per process; outputs are immutable (existing evidence is never
overwritten). Reuses the offline harness of the regime-momentum study so the
data-handling code cannot drift between studies.

    python research/sr_swing_2026/run_sr_swing.py --period smoke      # mechanics
    python research/sr_swing_2026/run_sr_swing.py --period evaluation # the gate
    python research/sr_swing_2026/run_sr_swing.py --period evaluation --stress
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGIME = ROOT / "research" / "regime_momentum_2026"
for path in (str(HERE), str(ROOT), str(REGIME)):
    if path not in sys.path:
        sys.path.insert(0, path)

from eqlib import OrderCost, analyze_returns, log, run_backtest  # noqa: E402
from examples._defaults import DEFAULT_ORDER_COST  # noqa: E402

# the regime study's runner is the shared offline harness (read_inputs,
# frozen_prices, period_metrics, count_round_trips); its CONFIGS/PERIODS
# belong to that study and are not used here.
from runner import (  # noqa: E402
    count_round_trips,
    frozen_prices,
    period_metrics,
    read_inputs,
)
from sr_swing_strategy import SRSwingConfig, make_sr_swing_strategy  # noqa: E402
from universe import BENCHMARK, KNOWN_LOSERS, UNIVERSE  # noqa: E402

CONFIG = SRSwingConfig()
# DESIGN.md: the evaluation window is run once; smoke is for mechanics only.
PERIODS = {
    "smoke": ("2023-01-03", "2023-12-29"),
    "evaluation": ("2024-01-01", "2026-10-27"),
}
DATA_DIR = Path("data/regime_momentum")
OUTPUT_DIR = Path("reports/sr_swing")


def run(period: str, cash: float, stress: bool, data_dir: Path,
        output: Path, label: str = "sr_swing") -> dict:
    config = CONFIG
    cost = DEFAULT_ORDER_COST
    if stress:
        config = SRSwingConfig(**{**asdict(config), "slippage": 0.003})
        cost = OrderCost(
            **{
                **vars(cost),
                "open_commission": cost.open_commission * 2,
                "close_commission": cost.close_commission * 2,
                "min_commission": cost.min_commission * 2,
            }
        )
    start, end = PERIODS[period]
    codes = list(UNIVERSE)
    frames, manifest, window = read_inputs(data_dir, codes + [BENCHMARK],
                                           start, end, config)

    initialize = make_sr_swing_strategy(codes, config, benchmark=BENCHMARK,
                                        order_cost=cost)
    log.set_quiet(True)
    with frozen_prices(frames), patch(
        "requests.sessions.Session.request",
        side_effect=AssertionError("research runs must use frozen local inputs"),
    ):
        result = run_backtest(
            initialize, start, end, starting_cash=cash,
            securities=codes + [BENCHMARK], benchmark=BENCHMARK, use_local=True,
        )
        if result is None:
            raise ValueError("backtest produced no result")
        state = result["context"].sr_swing
        trade_log = list(result["trade_log"])
        round_trips = count_round_trips(trade_log)
        metrics = period_metrics(result, frames[BENCHMARK], start, end,
                                 round_trips)
        if metrics is None:
            raise ValueError("backtest produced no daily records")
        analysis = analyze_returns(result) or {}

    equity = pd.DataFrame(result["recorded_values"])
    per_stock = {str(k): float(v)
                 for k, v in (analysis.get("per_stock_pnl") or {}).items()}
    loser_pnl = sum(v for k, v in per_stock.items()
                    if k.split(".")[0] in KNOWN_LOSERS)
    metrics.update(
        average_exposure=float(equity.ss_exposure.mean()),
        maximum_exposure=float(equity.ss_exposure.max()),
        flat_sessions=int(equity.ss_positions.eq(0).sum()),
        halted_sessions=int(equity.ss_halted.sum()),
        paid_costs=float(sum(float(t.get("commission", 0.0))
                             for t in trade_log)),
        end_positions=int(sum(1 for p in result["context"].portfolio.positions.values()
                              if p.amount > 0)),
        pending_orders=int(sum(1 for o in state.exits.values()
                               if o is not None and o.status in {"pending",
                                                                 "submitted",
                                                                 "partial_fill"})),
        core_total_return=float(analysis.get("total_return", float("nan"))),
        core_sharpe=analysis.get("sharpe_ratio"),
        core_win_rate=analysis.get("win_rate_trade"),
        known_loser_pnl=loser_pnl,
    )
    exit_reasons: dict[str, int] = {}
    for row in state.events:
        if row["action"] == "exit_order":
            reason = row.get("reason", "unknown")
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    payload = {
        "strategy": label,
        "period": period,
        "stress": stress,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "starting_cash": cash,
        "window_trading_days": int(len(window)),
        "config": asdict(config),
        "costs": vars(cost),
        "data": manifest,
        "metrics": metrics,
        "exit_reasons": exit_reasons,
        "per_stock_pnl": per_stock,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "research/sr_swing_2026/run_sr_swing.py",
                "research/sr_swing_2026/sr_swing_strategy.py",
                "research/regime_momentum_2026/universe.py",
                "eqlib/engine.py",
            )
        },
        "limitations": [
            "Static 44-name watchlist; no point-in-time membership/ST ledger.",
            "qfq normalized prices: corporate actions and raw-price limits are approximated.",
            "Stop/target decisions use closes and fill next open; intraday stop slippage is approximated.",
            "The evaluation window follows a smoke run; signal logic was frozen in DESIGN.md beforehand.",
        ],
    }
    destination = output / period / (label + ("_stress" if stress else ""))
    if destination.exists():
        raise FileExistsError(
            f"output exists; never overwrite earlier evidence: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    equity.to_csv(destination / "equity.csv", index=False)
    pd.DataFrame(trade_log).to_csv(destination / "trades.csv", index=False)
    pd.DataFrame(state.events).to_csv(destination / "events.csv", index=False)
    (destination / "entries.json").write_text(
        json.dumps(state.entries, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    payload["_destination"] = str(destination.resolve())
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", choices=PERIODS, default="evaluation")
    parser.add_argument("--stress", action="store_true",
                        help="2x commissions and 0.3%% slippage")
    parser.add_argument("--label", default="sr_swing",
                        help="output label; use a new one per frozen code state, "
                             "existing evidence is never overwritten")
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not math.isfinite(args.cash) or args.cash <= 0:
        parser.error("cash must be finite and positive")
    payload = run(args.period, args.cash, args.stress, args.data_dir,
                  args.output, args.label)
    print(json.dumps(payload["metrics"], indent=2, allow_nan=False))
    print(f"exit_reasons: {payload['exit_reasons']}")
    print(f"Research outputs: {payload['_destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
