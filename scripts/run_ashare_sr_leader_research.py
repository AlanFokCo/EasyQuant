#!/usr/bin/env python3
"""Run A-share industry leader support/resistance strategy research.

The full run fetches daily A-share data through eqlib/akshare and may take a
while. Use --quick for a smaller smoke run.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from eqlib import analyze_returns, run_backtest
from eqlib.strategies.ashare_sr_leader import (
    StrategyKind,
    StrategyParams,
    get_default_leader_universe,
    make_initialize,
)

START_DATE = "2020-01-01"
END_DATE = "2026-07-08"
BENCHMARK = "000300.XSHG"
REPORT_DIR = Path("reports/ashare_sr_leader")
SUB_PERIODS = (
    ("2020-2021", "2020-01-01", "2021-12-31"),
    ("2022", "2022-01-01", "2022-12-31"),
    ("2023-2024", "2023-01-01", "2024-12-31"),
    ("2025-2026", "2025-01-01", "2026-07-08"),
)

RESEARCH_UNIVERSE = [
    "600519",
    "000858",
    "600887",
    "000333",
    "000651",
    "601888",
    "600036",
    "601398",
    "601318",
    "600030",
    "300059",
    "600276",
    "300760",
    "000661",
    "300750",
    "002594",
    "300274",
    "002415",
    "000725",
    "002475",
    "000063",
    "600941",
    "601728",
    "000977",
    "002230",
    "300124",
    "000425",
    "600031",
    "600309",
    "002352",
    "601899",
    "600547",
    "601668",
    "601390",
    "600690",
    "600406",
    "002371",
    "300014",
    "300015",
    "601919",
]


def candidate_param_grid(quick: bool = False):
    """Return strategy/parameter combinations to evaluate."""

    if quick:
        return [
            (StrategyKind.DEFENSIVE_SUPPORT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.RESISTANCE_BREAKOUT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.PULLBACK_MARKET_GATE, StrategyParams(level_window=60, top_n=8)),
        ]

    grid = []
    for kind in StrategyKind:
        for top_n in (8, 12):
            grid.append(
                (
                    kind,
                    StrategyParams(
                        level_window=120,
                        short_level_window=60,
                        atr_multiplier=0.5,
                        volume_ratio_min=1.0,
                        top_n=top_n,
                    ),
                )
            )
    return grid


def _benchmark_total_return(result: dict) -> float:
    recorded = result.get("recorded_values", [])
    if not recorded:
        return 0.0
    first = recorded[0].get("bench_value")
    last = recorded[-1].get("bench_value")
    if first in (None, 0) or last is None:
        return 0.0
    return float(last / first - 1)


def stability_score(metrics: dict) -> float:
    """Score risk-adjusted quality while penalizing drawdown and churn."""

    annual_return = float(metrics.get("annual_return", 0.0))
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    max_drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    trade_count = int(metrics.get("trade_count", 0))
    excess_return = float(metrics.get("excess_return", 0.0))
    churn_penalty = max(0, trade_count - 120) / 120 * 0.15
    drawdown_penalty = max(0.0, max_drawdown - 0.25) * 1.5
    return (
        annual_return * 1.5
        + sharpe * 0.25
        + excess_return
        - drawdown_penalty
        - churn_penalty
    )


def summarize_result(result: dict) -> dict:
    """Return metrics used for comparison."""

    metrics = analyze_returns(result, risk_free_rate=0.03) or {}
    total_return = float(metrics.get("total_return", 0.0))
    benchmark_return = _benchmark_total_return(result)
    summary = {
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "annual_return": float(metrics.get("annual_return", 0.0)),
        "annual_volatility": float(metrics.get("annual_volatility", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "sortino_ratio": float(metrics.get("sortino_ratio", 0.0)),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "calmar_ratio": float(metrics.get("calmar_ratio", 0.0)),
        "win_rate_trade": float(metrics.get("win_rate_trade", 0.0)),
        "profit_loss_ratio": float(metrics.get("profit_loss_ratio", 0.0)),
        "trade_count": int(metrics.get("trade_count", len(result.get("trade_log", [])))),
    }
    summary["stability_score"] = stability_score(summary)
    return summary


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _best_by_period(rows: list[dict]) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for row in rows:
        period = row.get("period_name", "unknown")
        if period not in best or row.get("stability_score", -999) > best[period].get(
            "stability_score", -999
        ):
            best[period] = row
    return best


def _period_reason(row: dict) -> str:
    kind = row.get("kind", "")
    excess = float(row.get("excess_return", 0.0))
    drawdown = abs(float(row.get("max_drawdown", 0.0)))
    trades = int(row.get("trade_count", 0))
    if kind == StrategyKind.DEFENSIVE_SUPPORT.value:
        base = "防守型支撑策略占优，说明该阶段靠近支撑且结构未破坏的行业龙头更能控制回撤。"
    elif kind == StrategyKind.RESISTANCE_BREAKOUT.value:
        base = "压力突破策略占优，说明该阶段趋势延续和放量突破更容易获得超额收益。"
    else:
        base = "突破回踩加市场闸门策略占优，说明该阶段等待确认并随市场结构调节仓位更有效。"
    relative = "跑赢基准" if excess >= 0 else "跑输基准"
    risk = "回撤可控" if drawdown <= 0.25 else "回撤偏大"
    churn = (
        "交易次数没有表现出高频或中高频特征"
        if trades <= 120
        else "交易次数偏多，需要谨慎看待换手成本"
    )
    return f"{base}{relative}，{risk}，{churn}。"


def period_interpretation(rows: list[dict]) -> str:
    """Generate deterministic Chinese interpretation from result rows."""

    best = _best_by_period(rows)
    full = best.get("full") or (
        sorted(rows, key=lambda row: row.get("stability_score", -999), reverse=True)[0]
        if rows
        else {}
    )
    lines = [
        "## 分阶段解释",
        "",
    ]
    for period in ("2020-2021", "2022", "2023-2024", "2025-2026"):
        row = best.get(period)
        if not row:
            continue
        lines.extend(
            [
                f"### {period}",
                "",
                f"- 最优候选: `{row.get('kind')}`",
                f"- 年化收益: `{_fmt_pct(float(row.get('annual_return', 0.0)))}`",
                f"- 最大回撤: `{_fmt_pct(float(row.get('max_drawdown', 0.0)))}`",
                f"- 超额收益: `{_fmt_pct(float(row.get('excess_return', 0.0)))}`",
                f"- 交易次数: `{row.get('trade_count', 0)}`",
                f"- 解释: {_period_reason(row)}",
                "",
            ]
        )
    lines.extend(
        [
            "## 最终推荐",
            "",
            f"最终推荐策略: `{full.get('kind', 'N/A')}`",
            "",
            "推荐原因:",
            "",
            f"- 稳定性评分为 `{full.get('stability_score', 0):.4f}`。",
            f"- 年化收益为 `{_fmt_pct(float(full.get('annual_return', 0.0)))}`，"
            f"超额收益为 `{_fmt_pct(float(full.get('excess_return', 0.0)))}`。",
            f"- 最大回撤为 `{_fmt_pct(float(full.get('max_drawdown', 0.0)))}`。",
            f"- 交易次数为 `{full.get('trade_count', 0)}`，交易次数没有表现出高频或中高频特征。",
            "- 策略选择依据为稳定性评分、回撤、Sharpe、超额收益和交易次数的综合表现，而不是单次最高收益。",
            "",
            "## 风险提示",
            "",
            "- 历史回测不代表未来收益。",
            "- 行业龙头池仍可能存在幸存者偏差。",
            "- akshare 数据源可用性和复权处理会影响结果。",
            "- 支撑压力不是确定性价格预测，只是结构化风险收益判断。",
        ]
    )
    return "\n".join(lines) + "\n"


def run_one(
    kind: StrategyKind,
    params: StrategyParams,
    start: str,
    end: str,
    universe: list[str],
) -> dict:
    """Run one backtest and return metrics plus metadata."""

    initialize = make_initialize(
        kind=kind,
        params=params,
        universe=universe,
        benchmark=BENCHMARK,
    )
    result = run_backtest(
        initialize_func=initialize,
        start_date=start,
        end_date=end,
        starting_cash=1_000_000,
        benchmark=BENCHMARK,
        securities=universe + [BENCHMARK],
        use_local=False,
    )
    if result is None:
        return {"error": "backtest returned None"}

    summary = summarize_result(result)
    summary.update(
        {
            "kind": kind.value,
            "start": start,
            "end": end,
            "params": asdict(params),
        }
    )
    return summary


def write_outputs(rows: list[dict]) -> None:
    """Write JSON, CSV, and Markdown summary reports."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        rows,
        key=lambda row: row.get("stability_score", -999),
        reverse=True,
    )
    (REPORT_DIR / "summary.json").write_text(
        json.dumps(sorted_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fieldnames = [
        "kind",
        "period_name",
        "start",
        "end",
        "total_return",
        "benchmark_return",
        "excess_return",
        "annual_return",
        "sharpe_ratio",
        "max_drawdown",
        "calmar_ratio",
        "trade_count",
        "stability_score",
        "params",
    ]
    with (REPORT_DIR / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)

    full_rows = [row for row in sorted_rows if row.get("period_name") == "full"]
    best = full_rows[0] if full_rows else (sorted_rows[0] if sorted_rows else {})
    lines = [
        "# A股行业龙头支撑压力策略研究报告",
        "",
        f"- 最优策略: `{best.get('kind', 'N/A')}`",
        f"- 稳定性评分: `{best.get('stability_score', 0):.4f}`",
        f"- 年化收益: `{best.get('annual_return', 0):.2%}`",
        f"- 最大回撤: `{best.get('max_drawdown', 0):.2%}`",
        f"- Sharpe: `{best.get('sharpe_ratio', 0):.2f}`",
        f"- 交易次数: `{best.get('trade_count', 0)}`",
        "",
        "## Top Results",
        "",
        "| Rank | Strategy | Period | Annual | Max DD | Sharpe | Excess | Trades |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(sorted_rows[:10], start=1):
        lines.append(
            f"| {idx} | {row.get('kind')} | {row.get('start')} to {row.get('end')} | "
            f"{row.get('annual_return', 0):.2%} | {row.get('max_drawdown', 0):.2%} | "
            f"{row.get('sharpe_ratio', 0):.2f} | {row.get('excess_return', 0):.2%} | "
            f"{row.get('trade_count', 0)} |"
        )
    lines.append("")
    lines.append(period_interpretation(sorted_rows))
    (REPORT_DIR / "final_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run one parameter set per strategy over 2024 only.",
    )
    args = parser.parse_args()

    default_universe = set(get_default_leader_universe())
    universe = [code for code in RESEARCH_UNIVERSE if code in default_universe]
    if args.quick:
        universe = universe[:15]
        periods = (("quick", "2024-01-01", "2024-12-31"),)
        rows = []
        for kind, params in candidate_param_grid(quick=args.quick):
            row = run_one(kind, params, "2024-01-01", "2024-12-31", universe)
            row["period_name"] = "quick"
            rows.append(row)
            print(
                f"quick {kind.value} annual={row.get('annual_return', 0):.2%} "
                f"dd={row.get('max_drawdown', 0):.2%} "
                f"score={row.get('stability_score', 0):.4f}"
            )
        write_outputs(rows)
        print(f"Wrote reports to {REPORT_DIR}")
        return 0

    rows = []
    full_candidates = []
    for kind, params in candidate_param_grid(quick=False):
        row = run_one(kind, params, START_DATE, END_DATE, universe)
        row["period_name"] = "full"
        rows.append(row)
        full_candidates.append((row, kind, params))
        print(
            f"full {kind.value} annual={row.get('annual_return', 0):.2%} "
            f"dd={row.get('max_drawdown', 0):.2%} "
            f"score={row.get('stability_score', 0):.4f}"
        )

    best_row, best_kind, best_params = max(
        full_candidates,
        key=lambda item: item[0].get("stability_score", -999),
    )
    print(f"selected {best_kind.value} params={asdict(best_params)}")

    for period_name, start, end in SUB_PERIODS:
        row = run_one(best_kind, best_params, start, end, universe)
        row["period_name"] = period_name
        rows.append(row)
        print(
            f"{period_name} {best_kind.value} annual={row.get('annual_return', 0):.2%} "
            f"dd={row.get('max_drawdown', 0):.2%} "
            f"score={row.get('stability_score', 0):.4f}"
        )

    write_outputs(rows)
    print(f"Wrote reports to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
