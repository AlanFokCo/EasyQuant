"""Replay value_sector_cap on frozen inputs, offline.

One run per process; outputs are immutable. Reuses the regime study's
frozen_prices/period_metrics harness; input validation here differs from the
regime study because late-IPO names legitimately lack early history — the
strategy admits them only when history, valuation freshness, and filters all
pass.

    python research/value_sector_cap_2026/run_capped.py --period smoke
    python research/value_sector_cap_2026/run_capped.py --period development
    python research/value_sector_cap_2026/run_capped.py --period validation
    python research/value_sector_cap_2026/run_capped.py --period validation --stress
    python research/value_sector_cap_2026/run_capped.py --period later_check
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
)
from universe import (  # noqa: E402
    BENCHMARK,
    KNOWN_LOSERS,
    UNIVERSE,
    UNIVERSE_BY_SECTOR,
)
from value_capped_strategy import (  # noqa: E402
    CappedValueConfig,
    make_value_capped_strategy,
)

CONFIG = CappedValueConfig()
# DESIGN.md: development is scored and iterable; validation is one shot;
# later_check is contaminated by construction and labelled as such.
PERIODS = {
    "smoke": ("2019-01-02", "2019-12-31"),
    "development": ("2016-01-04", "2020-12-31"),
    "validation": ("2021-01-04", "2022-12-30"),
    "later_check": ("2024-01-01", "2026-10-27"),
}
PRICE_DIR = Path("data/value_pool_prices")
VALUATION_DIR = Path("data/value_factor")
OUTPUT_DIR = Path("reports/value_sector_cap")

SECTORS = {code: sector
           for sector, codes in UNIVERSE_BY_SECTOR.items() for code in codes}


def read_pool_inputs(directory: Path, codes: list[str], start: str, end: str,
                     history_bars: int):
    """Validate frozen snapshots; late IPOs are allowed to start late."""
    frames, manifest = {}, {}
    for code in codes:
        path = directory / f"{code}_daily_qfq.csv"
        if not path.is_file():
            raise ValueError(f"missing {path}; run prefetch_prices.py first")
        raw = path.read_bytes()
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
            raise ValueError(f"dates must be timezone-naive midnight: {path}")
        frames[code] = frame
        manifest[code] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": int(len(frame)),
            "first": str(frame.index.min().date()),
            "last": str(frame.index.max().date()),
        }
    calendar = frames[BENCHMARK].index
    window = calendar[(calendar >= pd.Timestamp(start))
                      & (calendar <= pd.Timestamp(end))]
    if window.empty:
        raise ValueError("requested interval contains no trading days")
    warmup = frames[BENCHMARK].loc[frames[BENCHMARK].index < window[0]]
    if len(warmup) < history_bars:
        raise ValueError(f"insufficient benchmark warm-up before {start}")
    for code, frame in frames.items():
        if frame.index.max() < window[-1]:
            raise ValueError(f"history ends before the final trading day: {code}")
        missing = window.difference(frame.index)
        manifest[code]["missing_period_days"] = int(len(missing))
        if code == BENCHMARK and len(missing):
            raise ValueError("benchmark is missing trading days inside the period")
        if code != BENCHMARK and frame.index.min() >= window[0]:
            manifest[code]["late_start"] = manifest[code]["first"]
    return frames, manifest, window


def load_valuations(directory: Path, codes: list[str]) -> dict:
    """Load frozen PE/PB snapshots; verify against the prefetch manifest."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = {}
    for code in codes:
        parts = []
        for key in ("pe_ttm", "pb"):
            path = directory / f"{code}_{key}.csv"
            if not path.is_file():
                raise ValueError(f"missing {path}")
            recorded = manifest["files"].get(code, {}).get(key, {})
            if recorded.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"sha256 mismatch: {path}")
            parts.append(pd.read_csv(path, index_col=0, parse_dates=True))
        frame = parts[0].join(parts[1], how="inner").sort_index()
        if frame.empty or frame.index.tz is not None:
            raise ValueError(f"invalid valuation frame: {code}")
        frames[code] = frame
    return frames


def run(period: str, cash: float, stress: bool, price_dir: Path,
        valuation_dir: Path, output: Path, label: str = "value_sector_cap",
        no_kill_switch: bool = False) -> dict:
    config = CONFIG
    cost = DEFAULT_ORDER_COST
    if no_kill_switch:
        config = CappedValueConfig(**{**asdict(config), "use_kill_switch": False})
    if stress:
        config = CappedValueConfig(**{**asdict(config), "slippage": 0.003})
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
    frames, manifest, window = read_pool_inputs(price_dir, codes + [BENCHMARK],
                                                start, end, config.history_bars)
    valuations = load_valuations(valuation_dir, codes)

    initialize = make_value_capped_strategy(codes, valuations, SECTORS, config,
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
        state = result["context"].value_capped
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
        average_exposure=float(equity.vc_exposure.mean()),
        maximum_exposure=float(equity.vc_exposure.max()),
        flat_sessions=int(equity.vc_positions.eq(0).sum()),
        halted_sessions=int(equity.vc_halted.sum()),
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
                "research/value_sector_cap_2026/run_capped.py",
                "research/value_sector_cap_2026/value_capped_strategy.py",
                "research/regime_momentum_2026/universe.py",
                "eqlib/engine.py",
            )
        },
        "limitations": [
            "Static 44-name watchlist; no point-in-time membership/ST ledger.",
            "Late-IPO names admitted when history suffices; pool membership is today's list.",
            "qfq normalized prices; anchor recomputed at download — approximate vs the 2022 freeze.",
            "Vendor-sampled valuation series carried forward ≤21 calendar days.",
            "Sector labels are today's labels applied historically.",
            "Hypothesis informed by value_factor's 2024-2026 result; the 2021-2022 gate is the clean test.",
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
    parser.add_argument("--period", choices=PERIODS, required=True)
    parser.add_argument("--stress", action="store_true",
                        help="2x commissions and 0.3%% slippage")
    parser.add_argument("--no-kill-switch", action="store_true",
                        help="development iteration: disable the portfolio kill switch")
    parser.add_argument("--label", default="value_sector_cap",
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
                  args.valuation_dir, args.output, args.label,
                  args.no_kill_switch)
    print(json.dumps(payload["metrics"], indent=2, allow_nan=False))
    print(f"exit_reasons: {payload['exit_reasons']}")
    print(f"Research outputs: {payload['_destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
