"""25 - Support/Resistance with a Portfolio Risk Budget.

Teaching objectives: completed-bar signals, stop-distance position sizing,
next-open execution, immutable CSV inputs and chronological cost stress tests.

Run from the repository root after ``pip install -e .``::

    python examples/25_sr_risk_budget.py --download
    python examples/25_sr_risk_budget.py --stress
    python examples/25_sr_risk_budget.py --allow-breakout --stress

No parameter search or live broker orders are performed. Backtest returns do
not establish reliable future profits; see docs/explanation/sr-risk-budget.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from importlib import resources
from pathlib import Path
from unittest.mock import patch

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from eqlib import OrderCost, analyze_returns, log, run_backtest
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
from eqlib.data import fetch_stock_data
from eqlib.strategies.sr_risk_budget import (
    SRRiskConfig,
    make_sr_risk_budget_strategy,
    valid_bars,
)
from examples._defaults import DEFAULT_ORDER_COST, INDEX_HS300, STOCKS


def exchange_calendar(start, end):
    """Read the packaged calendar without invoking an online calendar API."""
    calendar = json.loads(
        resources.files("eqlib.static")
        .joinpath("ashare_trading_days.json")
        .read_text(encoding="utf-8")
    )
    coverage = calendar["coverage"]
    if pd.Timestamp(start) < pd.Timestamp(coverage["start"]) or pd.Timestamp(
        end
    ) > pd.Timestamp(coverage["end"]):
        raise ValueError("requested interval is outside the packaged calendar coverage")
    days = pd.DatetimeIndex(calendar["trading_days"])
    return days[(days >= pd.Timestamp(start)) & (days <= pd.Timestamp(end))]


def read_inputs(directory, codes, start, end, config):
    """Validate snapshots before running; never silently shorten the test."""
    frames, manifest = {}, {}
    calendar = exchange_calendar(start, end)
    if calendar.empty:
        raise ValueError("requested interval contains no trading days")
    for code in codes:
        path = directory / f"{code}_daily_qfq.csv"
        if not path.is_file():
            raise ValueError(f"missing {path}; supply CSV data or run with --download")
        raw = path.read_bytes()
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        if not valid_bars(frame, config.history_bars):
            raise ValueError(f"invalid OHLCV history: {path}")
        if frame.index.tz is not None or not frame.index.equals(
            frame.index.normalize()
        ):
            raise ValueError(
                f"daily CSV dates must be timezone-naive midnight dates: {path}"
            )
        if len(frame.loc[frame.index < calendar[0]]) < config.history_bars:
            raise ValueError(f"insufficient warm-up before {start}: {path}")
        if frame.index.max() < calendar[-1]:
            raise ValueError(f"history ends before requested final trading day: {path}")
        missing = calendar.difference(frame.index)
        if code == INDEX_HS300 and len(missing):
            raise ValueError("benchmark is missing trading days")
        frames[code] = frame
        manifest[code] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(frame),
            "first": str(frame.index.min().date()),
            "last": str(frame.index.max().date()),
            "missing_test_days": len(missing),
        }
    return frames, manifest


@contextmanager
def local_prices(frames):
    """Scoped CSV provider for a single offline research run.

    eqlib's use_local flag still allows network fallback and reporting fetches.
    Route its public loading functions to the same immutable frames as well.
    This process-scoped adapter is not intended for concurrent backtest threads.
    Missing auxiliary chart indices remain missing instead of being invented.
    """

    def fetch(code, start_date=None, end_date=None, adjust="qfq"):
        if adjust != "qfq":
            raise ValueError("this input snapshot contains qfq prices only")
        frame = frames.get(code)
        if frame is None:
            frame = frames.get(code.split(".")[0])
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
        # This ancillary chart helper calls akshare directly, bypassing fetch.
        # Omit those charts; benchmark metrics still use the supplied snapshot.
        stack.enter_context(patch("eqlib.report._fetch_index_returns", return_value=[]))
        yield


def period_metrics(result, benchmark, start, end):
    """Slice one continuous run, preserving the preceding equity observation."""
    records = pd.DataFrame(result["recorded_values"])
    records.index = pd.to_datetime(records.date)
    values = records.total_value.astype(float)
    initial = float(result["context"].portfolio.starting_cash)
    returns = values.pct_change()
    returns.iloc[0] = values.iloc[0] / initial - 1
    selected = returns.loc[start:end]
    if selected.empty:
        return None
    equity = (1 + selected).cumprod()
    wealth = pd.concat(
        [pd.Series([1.0]), equity.reset_index(drop=True)], ignore_index=True
    )
    total = float(equity.iloc[-1] - 1)
    annual = float((1 + total) ** (TRADING_DAYS_PER_YEAR / len(selected)) - 1)
    vol = float(selected.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    excess_daily = selected - RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    sharpe = (
        float(excess_daily.mean() * TRADING_DAYS_PER_YEAR / vol)
        if math.isfinite(vol) and vol > 0
        else None
    )
    benchmark_returns = benchmark.close.pct_change().reindex(selected.index)
    benchmark_return = (
        float((1 + benchmark_returns).prod() - 1)
        if benchmark_returns.notna().all()
        else None
    )
    return {
        "start": str(selected.index[0].date()),
        "end": str(selected.index[-1].date()),
        "trading_days": len(selected),
        "total_return": total,
        "annual_return": annual,
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "sharpe": sharpe,
        "benchmark_return": benchmark_return,
    }


def run_snapshot(frames, codes, start, end, cash, config, cost):
    initialize = make_sr_risk_budget_strategy(codes, config, order_cost=cost)
    with local_prices(frames):
        result = run_backtest(
            initialize,
            start,
            end,
            starting_cash=cash,
            securities=codes + [INDEX_HS300],
            benchmark=INDEX_HS300,
            use_local=True,
        )
    if result is None:
        raise ValueError("backtest produced no result")
    metrics = period_metrics(result, frames[INDEX_HS300], start, end)
    if metrics is None:
        raise ValueError("backtest produced no daily records")
    metrics["fill_count"] = len(result["trade_log"])
    metrics["completed_exits"] = sum(
        event["action"] == "exit_filled"
        for event in result["context"].sr_risk_budget.events
    )
    metrics["paid_costs"] = sum(float(t["commission"]) for t in result["trade_log"])
    metrics["end_positions"] = len(result["context"].portfolio.positions)
    state = result["context"].sr_risk_budget
    metrics["pending_orders"] = sum(
        order.status in {"pending", "submitted", "partial_fill"}
        for order in [
            *(item[0] for item in state.entries.values()),
            *state.exits.values(),
        ]
    )
    # Core metrics are also exercised, but period returns use one consistent
    # prior-close baseline for both the strategy and the benchmark.
    analysis = analyze_returns(result)
    metrics["core_total_return"] = float(analysis["total_return"])
    return result, metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--data-dir", type=Path, default=Path("data/sr_risk_budget"))
    parser.add_argument("--output", type=Path, default=Path("reports/sr_risk_budget"))
    parser.add_argument(
        "--allow-breakout",
        action="store_true",
        help="research direct pressure-level breakouts; validation has NOT passed",
    )
    parser.add_argument(
        "--download", action="store_true", help="fetch and overwrite input snapshots"
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help="rerun with 2x commissions and 0.3%% slippage",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="label supplied synthetic data as an execution test",
    )
    args = parser.parse_args(argv)
    config = SRRiskConfig(allow_breakout=args.allow_breakout)
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    if pd.isna(start) or pd.isna(end) or start >= end:
        parser.error("start must precede end")
    if not math.isfinite(args.cash) or args.cash <= 0:
        parser.error("cash must be finite and positive")
    codes = list(STOCKS.values())
    all_codes = codes + [INDEX_HS300]
    if args.download:
        args.data_dir.mkdir(parents=True, exist_ok=True)
        warmup = (start - pd.Timedelta(days=365)).date().isoformat()
        for code in all_codes:
            frame = fetch_stock_data(code, warmup, args.end, adjust="qfq")
            if frame.empty:
                raise ValueError(f"data download failed: {code}")
            # eqlib's main-board stock providers return lots (100 shares).
            # This strategy and the engine fill budget consume share counts.
            # Copy first: do not mutate the provider's cached frame. Index
            # volume is unused by this strategy and keeps its source units.
            if code != INDEX_HS300:
                frame = frame.copy()
                frame["volume"] = pd.to_numeric(frame["volume"]) * 100.0
            frame.to_csv(args.data_dir / f"{code}_daily_qfq.csv")
    frames, manifest = read_inputs(
        args.data_dir, all_codes, args.start, args.end, config
    )
    log.set_quiet(True)
    result, metrics = run_snapshot(
        frames, codes, args.start, args.end, args.cash, config, DEFAULT_ORDER_COST
    )
    years = {
        str(year): period_metrics(
            result, frames[INDEX_HS300], f"{year}-01-01", f"{year}-12-31"
        )
        for year in range(start.year, end.year + 1)
    }
    payload = {
        "strategy": "sr_risk_budget",
        "evidence": "synthetic_execution_test"
        if args.synthetic
        else "historical_static_watchlist_research",
        "profitability_proven": False,
        "config": asdict(config),
        "costs": vars(DEFAULT_ORDER_COST),
        "universe": codes,
        "data": manifest,
        "full_period": metrics,
        "calendar_years": years,
        "limitations": [
            "Static watchlist: membership/survivorship bias is not removed.",
            "No point-in-time ST/delisting or corporate-action ledger supplied.",
            "qfq execution prices, estimated board limits, and daily volume caps are approximations.",
            "Daily close exits execute at a later open; stop thresholds do not bound realized losses.",
            "Calendar slices share one position path; they are not independent or certified untouched OOS tests.",
        ],
    }
    if args.stress:
        stress_cost = OrderCost(
            **{
                **vars(DEFAULT_ORDER_COST),
                "open_commission": DEFAULT_ORDER_COST.open_commission * 2,
                "close_commission": DEFAULT_ORDER_COST.close_commission * 2,
                "min_commission": DEFAULT_ORDER_COST.min_commission * 2,
            }
        )
        _, payload["cost_stress"] = run_snapshot(
            frames,
            codes,
            args.start,
            args.end,
            args.cash,
            replace(config, slippage=0.003),
            stress_cost,
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(result["recorded_values"]).to_csv(
        args.output / "equity.csv", index=False
    )
    pd.DataFrame(result["trade_log"]).to_csv(args.output / "trades.csv", index=False)
    pd.DataFrame(result["context"].sr_risk_budget.events).to_csv(
        args.output / "events.csv", index=False
    )
    print(
        json.dumps(
            {
                "full_period": metrics,
                "cost_stress": payload.get("cost_stress"),
                "profitability_proven": False,
            },
            indent=2,
            allow_nan=False,
        )
    )
    print(f"Research outputs: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
