"""Replay value_factor on frozen price + frozen valuation inputs, offline.

One run per process; outputs are immutable. Reuses the offline harness of the
regime-momentum study so data handling cannot drift between studies.

    python research/value_factor_2026/run_value.py --period smoke      # mechanics
    python research/value_factor_2026/run_value.py --period evaluation # the gate
    python research/value_factor_2026/run_value.py --period evaluation --stress
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

from runner import (  # noqa: E402  (the regime study's shared offline harness)
    count_round_trips,
    frozen_prices,
    period_metrics,
    read_inputs,
)
from universe import BENCHMARK, KNOWN_LOSERS, UNIVERSE  # noqa: E402
from value_strategy import ValueConfig, make_value_strategy  # noqa: E402

CONFIG = ValueConfig()
# DESIGN.md: the evaluation window is run once; smoke is for mechanics only.
PERIODS = {
    "smoke": ("2023-01-03", "2023-12-29"),
    "evaluation": ("2024-01-01", "2026-10-27"),
}
PRICE_DIR = Path("data/regime_momentum")
VALUATION_DIR = Path("data/value_factor")
OUTPUT_DIR = Path("reports/value_factor")


def load_valuations(directory: Path, codes: list[str]) -> dict:
    """Load frozen PE/PB snapshots; verify against the prefetch manifest."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing {manifest_path}; run prefetch_valuation.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = {}
    for code in codes:
        parts = []
        for key in ("pe_ttm", "pb"):
            path = directory / f"{code}_{key}.csv"
            if not path.is_file():
                raise ValueError(f"missing {path}; run prefetch_valuation.py first")
            recorded = manifest["files"].get(code, {}).get(key, {})
            if recorded.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"sha256 mismatch: {path}")
            parts.append(
                pd.read_csv(path, index_col=0, parse_dates=True).rename(
                    columns={key: key}
                )
            )
        frame = parts[0].join(parts[1], how="inner").sort_index()
        if frame.empty or frame.index.tz is not None:
            raise ValueError(f"invalid valuation frame: {code}")
        frames[code] = frame
    return frames


def run(period: str, cash: float, stress: bool, price_dir: Path,
        valuation_dir: Path, output: Path, label: str = "value_factor") -> dict:
    config = CONFIG
    cost = DEFAULT_ORDER_COST
    if stress:
        config = ValueConfig(**{**asdict(config), "slippage": 0.003})
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
    frames, manifest, window = read_inputs(price_dir, codes + [BENCHMARK],
                                           start, end, config)
    valuations = load_valuations(valuation_dir, codes)

    initialize = make_value_strategy(codes, valuations, config,
                                     benchmark=BENCHMARK, order_cost=cost)
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
        state = result["context"].value_factor
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
        average_exposure=float(equity.vf_exposure.mean()),
        maximum_exposure=float(equity.vf_exposure.max()),
        flat_sessions=int(equity.vf_positions.eq(0).sum()),
        halted_sessions=int(equity.vf_halted.sum()),
        rebalances=int(state.rebalances),
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
                "research/value_factor_2026/run_value.py",
                "research/value_factor_2026/value_strategy.py",
                "research/regime_momentum_2026/universe.py",
                "eqlib/engine.py",
            )
        },
        "limitations": [
            "Static 44-name watchlist; no point-in-time membership/ST ledger.",
            "qfq normalized prices: corporate actions and raw-price limits are approximated.",
            "Vendor-sampled valuation series carried forward ≤21 calendar days.",
            "PE/PB reflect latest published reports, as a live trader would see them.",
            "The evaluation window follows a smoke run; design frozen in DESIGN.md beforehand.",
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
    (destination / "selections.json").write_text(
        json.dumps(state.selections, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    payload["_destination"] = str(destination.resolve())
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", choices=PERIODS, default="evaluation")
    parser.add_argument("--stress", action="store_true",
                        help="2x commissions and 0.3%% slippage")
    parser.add_argument("--label", default="value_factor",
                        help="output label; a new one per frozen code state, "
                             "existing evidence is never overwritten")
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--price-dir", type=Path, default=PRICE_DIR)
    parser.add_argument("--valuation-dir", type=Path, default=VALUATION_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not math.isfinite(args.cash) or args.cash <= 0:
        parser.error("cash must be finite and positive")
    payload = run(args.period, args.cash, args.stress, args.price_dir,
                  args.valuation_dir, args.output, args.label)
    print(json.dumps(payload["metrics"], indent=2, allow_nan=False))
    print(f"exit_reasons: {payload['exit_reasons']}")
    print(f"Research outputs: {payload['_destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
