"""Replay the pre-registered regime-momentum candidates on frozen inputs.

One candidate and one chronological period per process. No downloads, no
automatic parameter search, no return-driven promotion. Candidates include
ablations that are expected to fail; the gate lives in PLAN.md and is evaluated
by ``aggregate.py``, not here.

    python research/regime_momentum_2026/runner.py --candidate base --period development
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from eqlib import OrderCost, analyze_returns, log, run_backtest  # noqa: E402
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR  # noqa: E402
from examples._defaults import DEFAULT_ORDER_COST  # noqa: E402
from strategy import FIELDS, RegimeMomentumConfig, valid_bars  # noqa: E402
from universe import BENCHMARK, KNOWN_LOSERS, UNIVERSE  # noqa: E402

BASE = RegimeMomentumConfig()
# Pre-registered in PLAN.md §5. Round numbers from literature conventions.
CONFIGS = {
    "base": BASE,
    "no_regime": replace(BASE, use_regime_filter=False, exit_on_regime_filter=False),
    "breadth": replace(BASE, breadth_min=0.5),
    "risk_adjusted": replace(BASE, risk_adjusted=True),
    "inverse_vol": replace(BASE, inverse_vol=True),
    "slow_10_1": replace(BASE, momentum_window=200),
    "monthly": replace(BASE, rebalance_days=20),
}
# Frozen protocol. Re-cutting or reusing these windows to retune is NOT a new
# out-of-sample test and must be labelled in-sample if it ever happens.
PERIODS = {
    "development": ("2023-01-03", "2024-12-31"),
    "validation": ("2025-01-01", "2025-12-31"),
    "later_check": ("2026-01-01", "2026-10-27"),
    "full": ("2023-01-03", "2026-10-27"),
}
DATA_DIR = Path("data/regime_momentum")
OUTPUT_DIR = Path("reports/regime_momentum")


def read_inputs(directory: Path, codes: list[str], start: str, end: str,
                config: RegimeMomentumConfig):
    """Validate frozen snapshots before running; never silently shorten a test."""
    frames, manifest = {}, {}
    for code in codes:
        path = directory / f"{code}_daily_qfq.csv"
        if not path.is_file():
            raise ValueError(f"missing {path}; run freeze_inputs.py first")
        raw = path.read_bytes()
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        if not valid_bars(frame, config.history_bars):
            raise ValueError(f"invalid OHLCV history: {path}")
        if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
            raise ValueError(f"dates must be timezone-naive midnight: {path}")
        frames[code] = frame
        manifest[code] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": int(len(frame)),
            "first": str(frame.index.min().date()),
            "last": str(frame.index.max().date()),
        }
    # The authoritative calendar is the benchmark's own trading days.
    calendar = frames[BENCHMARK].index
    window = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))]
    if window.empty:
        raise ValueError("requested interval contains no trading days")
    warmup = frames[BENCHMARK].loc[frames[BENCHMARK].index < window[0]]
    if len(warmup) < config.history_bars:
        raise ValueError(
            f"insufficient benchmark warm-up before {start}: "
            f"{len(warmup)} < {config.history_bars} bars"
        )
    for code, frame in frames.items():
        pre = frame.loc[frame.index < window[0]]
        if code != BENCHMARK and len(pre) < config.history_bars:
            raise ValueError(f"insufficient warm-up before {start}: {code}")
        if frame.index.max() < window[-1]:
            raise ValueError(f"history ends before the final trading day: {code}")
        missing = window.difference(frame.index)
        manifest[code]["missing_period_days"] = int(len(missing))
        if code == BENCHMARK and len(missing):
            raise ValueError("benchmark is missing trading days inside the period")
    return frames, manifest, window


@contextmanager
def frozen_prices(frames: dict):
    """Scoped offline provider: same immutable frames for every code path."""

    def fetch(code, start_date=None, end_date=None, adjust="qfq"):
        if adjust not in ("qfq", "pre", None, ""):
            raise ValueError("this snapshot contains qfq prices only")
        # Never use `a or b` on frames: DataFrame truth value is ambiguous.
        frame = frames.get(code)
        if frame is None:
            frame = frames.get(str(code).split(".")[0])
        if frame is None:
            return pd.DataFrame()
        result = frame
        if start_date is not None:
            result = result.loc[result.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            result = result.loc[result.index <= pd.Timestamp(end_date)]
        return result.copy()

    with ExitStack() as stack:
        for name in (
            "eqlib.data.fetch_stock_data",
            "eqlib.engine.fetch_stock_data",
            "eqlib.report.fetch_stock_data",
            "eqlib.data_cache.load_stock_local",
        ):
            stack.enter_context(patch(name, side_effect=fetch))
        stack.enter_context(patch("eqlib.report._fetch_index_returns", return_value=[]))
        yield


def period_metrics(result, benchmark_frame: pd.DataFrame, start: str, end: str,
                   round_trips: int | None = None):
    """Slice one continuous run, preserving the preceding equity observation."""
    records = pd.DataFrame(result["recorded_values"])
    if records.empty:
        return None
    records.index = pd.to_datetime(records.date)
    values = records.total_value.astype(float)
    initial = float(result["context"].portfolio.starting_cash)
    returns = values.pct_change()
    returns.iloc[0] = values.iloc[0] / initial - 1
    selected = returns.loc[start:end]
    if selected.empty:
        return None
    equity = (1 + selected).cumprod()
    wealth = pd.concat([pd.Series([1.0]), equity.reset_index(drop=True)],
                       ignore_index=True)
    total = float(equity.iloc[-1] - 1)
    days = len(selected)
    annual = float((1 + total) ** (TRADING_DAYS_PER_YEAR / days) - 1) if days else None
    vol = float(selected.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    excess = selected - RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    sharpe = (
        float(excess.mean() * TRADING_DAYS_PER_YEAR / vol)
        if math.isfinite(vol) and vol > 0 else None
    )
    downside = selected[selected < 0]
    sortino = None
    if len(downside) > 1:
        dvol = float(downside.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if dvol > 0:
            sortino = float(excess.mean() * TRADING_DAYS_PER_YEAR / dvol)
    benchmark_returns = benchmark_frame.close.pct_change().reindex(selected.index)
    benchmark_total = (
        float((1 + benchmark_returns).prod() - 1)
        if benchmark_returns.notna().all() else None
    )
    benchmark_wealth = (1 + benchmark_returns.fillna(0)).cumprod()
    benchmark_dd = (
        float((benchmark_wealth / benchmark_wealth.cummax() - 1).min())
        if len(benchmark_wealth) else None
    )
    years = days / TRADING_DAYS_PER_YEAR
    return {
        "start": str(selected.index[0].date()),
        "end": str(selected.index[-1].date()),
        "trading_days": days,
        "years": round(years, 3),
        "total_return": total,
        "annual_return": annual,
        "annual_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "benchmark_return": benchmark_total,
        "benchmark_max_drawdown": benchmark_dd,
        "excess_return": (
            total - benchmark_total if benchmark_total is not None else None
        ),
        "round_trips": round_trips,
        "round_trips_per_year": (
            round(round_trips / years, 2) if round_trips is not None and years else None
        ),
    }


def count_round_trips(trade_log) -> int:
    """Completed SELL fills — the conservative trade-count caliber."""
    return sum(1 for row in trade_log if row.get("type") == "SELL")


def run_candidate(candidate: str, period: str, cash: float, stress: bool,
                  data_dir: Path, output: Path) -> dict:
    config = CONFIGS[candidate]
    cost = DEFAULT_ORDER_COST
    if stress:
        config = replace(config, slippage=0.003)
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
    frames, manifest, window = read_inputs(data_dir, codes + [BENCHMARK], start, end,
                                           config)
    from strategy import make_regime_momentum_strategy

    initialize = make_regime_momentum_strategy(codes, config, benchmark=BENCHMARK,
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
        state = result["context"].regime_momentum
        trade_log = list(result["trade_log"])
        round_trips = count_round_trips(trade_log)
        metrics = period_metrics(result, frames[BENCHMARK], start, end, round_trips)
        if metrics is None:
            raise ValueError("backtest produced no daily records")
        analysis = analyze_returns(result, risk_free_rate=RISK_FREE_RATE) or {}

    equity = pd.DataFrame(result["recorded_values"])
    per_stock = {str(k): float(v) for k, v in (analysis.get("per_stock_pnl") or {}).items()}
    loser_pnl = sum(v for k, v in per_stock.items() if k.split(".")[0] in KNOWN_LOSERS)
    metrics.update(
        average_exposure=float(equity.rm_exposure.mean()),
        maximum_exposure=float(equity.rm_exposure.max()),
        flat_sessions=int(equity.rm_positions.eq(0).sum()),
        risk_on_sessions=int(equity.rm_regime.sum()),
        halted_sessions=int(equity.rm_halted.sum()),
        rebalances=int(state.rebalances),
        paid_costs=float(sum(float(t.get("commission", 0.0)) for t in trade_log)),
        end_positions=int(sum(1 for p in result["context"].portfolio.positions.values()
                              if p.amount > 0)),
        pending_orders=int(sum(1 for o in state.exits.values()
                               if o is not None and o.status in {"pending", "submitted",
                                                                 "partial_fill"})),
        core_total_return=float(analysis.get("total_return", float("nan"))),
        core_sharpe=analysis.get("sharpe_ratio"),
        core_win_rate=analysis.get("win_rate_trade"),
        known_loser_pnl=loser_pnl,
        known_loser_share=(
            loser_pnl / sum(abs(v) for v in per_stock.values())
            if per_stock and sum(abs(v) for v in per_stock.values()) > 0 else None
        ),
    )
    exit_reasons: dict[str, int] = {}
    for row in state.events:
        if row["action"] == "exit_order":
            reason = row.get("reason", "unknown")
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    payload = {
        "candidate": candidate,
        "period": period,
        "stress": stress,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "starting_cash": cash,
        "window_trading_days": int(len(window)),
        "profitability_proven": False,
        "promotion_gate_passed": None,
        "config": asdict(config),
        "costs": vars(cost),
        "data": manifest,
        "metrics": metrics,
        "exit_reasons": exit_reasons,
        "per_stock_pnl": per_stock,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "research/regime_momentum_2026/runner.py",
                "research/regime_momentum_2026/strategy.py",
                "research/regime_momentum_2026/universe.py",
                "eqlib/engine.py",
            )
        },
        "limitations": [
            "Static 44-name watchlist; no point-in-time membership/ST ledger.",
            "qfq normalized prices: corporate actions and raw-price limits are approximated.",
            "Adjusted-price fills do not model raw prices or intraday liquidity.",
            "Periods restart from cash; yearly slices of a full run do not.",
            "Selection used the development window over 7 candidates (multiple testing).",
            "Do not retune against validation or later_check; one shot each.",
        ],
    }
    destination = output / period / (candidate + ("_stress" if stress else ""))
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
        json.dumps(state.selections, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    payload["_destination"] = str(destination.resolve())
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CONFIGS, required=True)
    parser.add_argument("--period", choices=PERIODS, default="development")
    parser.add_argument("--stress", action="store_true",
                        help="2x commissions and 0.3%% slippage")
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not math.isfinite(args.cash) or args.cash <= 0:
        parser.error("cash must be finite and positive")
    payload = run_candidate(args.candidate, args.period, args.cash, args.stress,
                            args.data_dir, args.output)
    print(json.dumps(payload["metrics"], indent=2, allow_nan=False))
    print(f"exit_reasons: {payload['exit_reasons']}")
    print(f"Research outputs: {payload['_destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
