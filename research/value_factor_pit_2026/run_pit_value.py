"""Replay the PIT value factor on frozen BaoStock inputs, offline.

    python research/value_factor_pit_2026/run_pit_value.py --period smoke
    python research/value_factor_pit_2026/run_pit_value.py --period development
    python research/value_factor_pit_2026/run_pit_value.py --period validation
    python research/value_factor_pit_2026/run_pit_value.py --period validation --stress
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
for path in (str(HERE), str(ROOT),
             str(ROOT / "research" / "regime_momentum_2026"),
             str(ROOT / "research" / "value_factor_2026")):
    if path not in sys.path:
        sys.path.insert(0, path)

from eqlib import OrderCost, analyze_returns, log, run_backtest  # noqa: E402
from examples._defaults import DEFAULT_ORDER_COST  # noqa: E402

from baostock_freeze import BENCHMARK, load_manifest  # noqa: E402
from runner import (  # noqa: E402  (regime study's shared offline harness)
    count_round_trips,
    frozen_prices,
    period_metrics,
)
from pit_value_strategy import PITValueConfig, make_pit_value_strategy  # noqa: E402

OHLCV = ("open", "high", "low", "close", "volume")
DATA_DIR = Path("data/value_factor_pit")
OUTPUT_DIR = Path("reports/value_factor_pit")
# DESIGN.md: smoke is mechanics-only, development is scored once for pipeline
# validation, validation is the one-shot gate.
PERIODS = {
    "smoke": ("2012-01-04", "2012-12-31"),
    "development": ("2010-01-04", "2012-12-31"),
    "validation": ("2013-01-04", "2015-12-31"),
}


def ensure_new_destination(output: Path, name: str) -> Path:
    """Immutable evidence: a destination that exists aborts the run."""
    destination = output / name
    if destination.exists():
        raise FileExistsError(
            f"output exists; never overwrite earlier evidence: {destination}"
        )
    return destination


def apply_stress(config: PITValueConfig, cost) -> tuple[PITValueConfig, OrderCost]:
    """Double commissions, keep stamp duty, triple slippage (2x comm + 0.3%)."""
    return (
        PITValueConfig(**{**asdict(config), "slippage": 0.003}),
        OrderCost(
            **{
                **vars(cost),
                "open_commission": cost.open_commission * 2,
                "close_commission": cost.close_commission * 2,
                "min_commission": cost.min_commission * 2,
            }
        ),
    )


def extract_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Engine price path: OHLCV only; research-only columns stay strategy-side."""
    return frame.loc[:, list(OHLCV)]


def load_frozen_inputs(data_dir: Path):
    """Verify hashes, then return (membership, histories, benchmark, files)."""
    manifest = load_manifest(data_dir)
    membership = {
        date: set(codes) for date, codes in manifest["members"].items()
    }
    histories = {}
    for relative in manifest["files"]:
        if relative.startswith("membership_"):
            continue
        frame = pd.read_csv(data_dir / relative, index_col=0, parse_dates=True)
        code = relative[: -len("_daily_qfq.csv")]
        histories[code] = frame
    if BENCHMARK not in histories:
        raise ValueError(f"benchmark frame missing from {data_dir}")
    return membership, histories, manifest


def run(period: str, cash: float, stress: bool, data_dir: Path,
        output: Path, label: str = "pit_value") -> dict:
    config = PITValueConfig()
    cost = DEFAULT_ORDER_COST
    if stress:
        config, cost = apply_stress(config, cost)
    start, end = PERIODS[period]
    membership, histories, manifest = load_frozen_inputs(data_dir)
    benchmark = histories[BENCHMARK]
    window = benchmark.index[
        (benchmark.index >= pd.Timestamp(start))
        & (benchmark.index <= pd.Timestamp(end))
    ]
    if window.empty:
        raise ValueError("requested interval contains no trading days")
    warmup = benchmark.index[benchmark.index < window[0]]
    if len(warmup) < config.turnover_window:
        raise ValueError(f"insufficient benchmark warm-up before {start}")

    price_frames = {code: extract_ohlcv(f) for code, f in histories.items()}
    initialize = make_pit_value_strategy(
        membership, histories, config, benchmark=BENCHMARK, order_cost=cost,
    )
    codes = sorted(c for c in histories if c != BENCHMARK)
    log.set_quiet(True)
    with frozen_prices(price_frames), patch(
        "requests.sessions.Session.request",
        side_effect=AssertionError("research runs must use frozen local inputs"),
    ):
        result = run_backtest(
            initialize, start, end, starting_cash=cash,
            securities=codes + [BENCHMARK], benchmark=BENCHMARK, use_local=True,
        )
        if result is None:
            raise ValueError("backtest produced no result")
        state = result["context"].pit_value
        trade_log = list(result["trade_log"])
        round_trips = count_round_trips(trade_log)
        metrics = period_metrics(result, benchmark, start, end, round_trips)
        if metrics is None:
            raise ValueError("backtest produced no daily records")
        analysis = analyze_returns(result) or {}

    equity = pd.DataFrame(result["recorded_values"])
    per_stock = {str(k): float(v)
                 for k, v in (analysis.get("per_stock_pnl") or {}).items()}
    metrics.update(
        average_exposure=float(equity.pv_exposure.mean()),
        maximum_exposure=float(equity.pv_exposure.max()),
        flat_sessions=int(equity.pv_positions.eq(0).sum()),
        halted_sessions=int(equity.pv_halted.sum()),
        rebalances=int(state.rebalances),
        paid_costs=float(sum(float(t.get("commission", 0.0))
                             for t in trade_log)),
        end_positions=int(sum(1 for p in result["context"].portfolio.positions.values()
                              if p.amount > 0)),
        core_total_return=float(analysis.get("total_return", float("nan"))),
        core_sharpe=analysis.get("sharpe_ratio"),
        core_win_rate=analysis.get("win_rate_trade"),
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
        "data": {
            "manifest_sha256": hashlib.sha256(
                (data_dir / "manifest.json").read_bytes()
            ).hexdigest(),
            "downloaded_at_utc": manifest["downloaded_at_utc"],
            "source": manifest["source"],
            "history_files": len(manifest["files"]),
        },
        "metrics": metrics,
        "exit_reasons": exit_reasons,
        "per_stock_pnl": per_stock,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "research/value_factor_pit_2026/run_pit_value.py",
                "research/value_factor_pit_2026/pit_value_strategy.py",
                "research/value_factor_pit_2026/baostock_freeze.py",
                "eqlib/engine.py",
            )
        },
        "limitations": [
            "BaoStock secondary vendor; adjustment conventions differ from akshare.",
            "Membership sampled on rebalance dates only.",
            "Daily PE/PB as published by the vendor; restatements not modelled.",
            "Frictionless equal-weight reference is diagnostic, not investable at this size.",
            "One regime sequence (2013-2015 gate) is not universal proof.",
        ],
    }
    destination = ensure_new_destination(
        output, f"{period}/{label}" + ("_stress" if stress else "")
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
    parser.add_argument("--period", choices=PERIODS, required=True)
    parser.add_argument("--stress", action="store_true",
                        help="2x commissions and 0.3%% slippage")
    parser.add_argument("--label", default="pit_value")
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
