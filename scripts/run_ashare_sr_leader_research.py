#!/usr/bin/env python3
"""Run A-share industry leader support/resistance strategy research.

The full run fetches daily A-share data through eqlib/akshare and may take a
while. Use --quick for a smaller smoke run.
"""

from __future__ import annotations

import argparse
import csv
import html
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
        grid.append(
            (
                kind,
                StrategyParams(
                    level_window=120,
                    short_level_window=60,
                    atr_multiplier=0.5,
                    volume_ratio_min=1.0,
                    top_n=12,
                    max_stock_weight=0.07,
                    max_industry_weight=0.21,
                    strong_market_exposure=0.70,
                    neutral_market_exposure=0.45,
                    weak_market_exposure=0.20,
                    rebalance_threshold=0.10,
                ),
            )
        )
    return grid


def _benchmark_total_return(result: dict) -> float:
    recorded = result.get("recorded_values", [])
    benchmark_values = result.get("benchmark_values", [])
    if recorded and benchmark_values:
        start = _date_key(recorded[0].get("date"))
        end = _date_key(recorded[-1].get("date"))
        values = [
            float(row["value"])
            for row in benchmark_values
            if row.get("value") is not None
            and start <= _date_key(row.get("date")) <= end
            and float(row["value"]) > 0
        ]
        if len(values) >= 2:
            return round(values[-1] / values[0] - 1, 12)

    if not recorded:
        return 0.0
    first = recorded[0].get("bench_value")
    last = recorded[-1].get("bench_value")
    if first in (None, 0) or last is None:
        return 0.0
    return round(float(last / first - 1), 12)


def _date_key(value: object) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def stability_score(metrics: dict) -> float:
    """Score risk-adjusted quality while penalizing drawdown and churn."""

    annual_return = float(metrics.get("annual_return", 0.0))
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    max_drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    trade_count = int(metrics.get("trade_count", 0))
    excess_return = float(metrics.get("excess_return", 0.0))
    churn_penalty = max(0, trade_count - 120) / 120 * 0.15
    drawdown_penalty = max(0.0, max_drawdown - 0.20) * 3.0
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
        "raw_trade_count": len(result.get("trade_log", [])),
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


def audit_rows(rows: list[dict]) -> list[dict[str, str]]:
    """Return report-quality issues that should be investigated before use."""

    issues: list[dict[str, str]] = []
    if not rows:
        return [
            {
                "severity": "error",
                "code": "empty_result",
                "message": "没有生成任何回测结果，报告不可用。",
            }
        ]

    full_rows = [row for row in rows if row.get("period_name") == "full"]
    if full_rows and all(
        abs(float(row.get("benchmark_return", 0.0))) < 1e-12 for row in full_rows
    ):
        issues.append(
            {
                "severity": "error",
                "code": "benchmark_missing",
                "message": "全周期候选策略的基准收益全部为 0，需要检查大盘基准序列是否接入。",
            }
        )

    ranked_full = sorted(
        full_rows,
        key=lambda row: row.get("stability_score", -999),
        reverse=True,
    )
    if ranked_full and abs(float(ranked_full[0].get("max_drawdown", 0.0))) > 0.30:
        issues.append(
            {
                "severity": "warning",
                "code": "deep_drawdown",
                "message": "当前最优全周期策略最大回撤超过 30%，与稳定收益目标冲突，需要降低仓位或重新调参。",
            }
        )

    for row in rows:
        if row.get("period_name") != "full" and float(row.get("excess_return", 0.0)) < -0.10:
            issues.append(
                {
                    "severity": "warning",
                    "code": "subperiod_underperformance",
                    "message": f"{row.get('period_name')} 阶段明显跑输基准，需要检查该市场环境下的入场/仓位过滤。",
                }
            )
            break

    if any(int(row.get("trade_count", 0)) > 120 for row in rows):
        issues.append(
            {
                "severity": "warning",
                "code": "trade_churn",
                "message": "存在交易次数超过 120 的回测结果，需要检查是否偏离中低频目标。",
            }
        )

    if any(int(row.get("raw_trade_count", row.get("trade_count", 0))) > 150 for row in rows):
        issues.append(
            {
                "severity": "warning",
                "code": "execution_fragmentation",
                "message": "存在原始成交笔数过高的结果，可能由复权低价、成交量限制或拆单造成，需要降低单次交易容量。",
            }
        )

    return issues


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


def audit_markdown(rows: list[dict]) -> str:
    """Render audit findings for the Markdown report."""

    issues = audit_rows(rows)
    lines = ["## 回测审计", ""]
    lines.append(f"- 审计结论: {recommendation_text(issues)}")
    if not issues:
        lines.append("- 未发现基准缺失、深回撤、明显分阶段跑输或交易频率偏高问题。")
        return "\n".join(lines) + "\n"
    for issue in issues:
        lines.append(
            f"- `{issue['severity']}` `{issue['code']}`: {issue['message']}"
        )
    return "\n".join(lines) + "\n"


def recommendation_text(issues: list[dict[str, str]]) -> str:
    """Return a plain-language recommendation gated by audit findings."""

    blocking_codes = {"benchmark_missing", "deep_drawdown", "subperiod_underperformance"}
    if any(
        issue.get("severity") == "error" or issue.get("code") in blocking_codes
        for issue in issues
    ):
        return "审计未完全通过，不建议直接实盘；应继续降低回撤、修正失效阶段或扩大稳健参数验证。"
    return "审计未发现关键阻断问题，可作为候选策略继续观察和小规模验证。"


def _html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt_num(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "0.00"


def _metric_card(label: str, value: str, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return (
        f'<section class="metric{tone_class}">'
        f"<span>{_html_escape(label)}</span>"
        f"<strong>{_html_escape(value)}</strong>"
        "</section>"
    )


def _profile_name(row: dict) -> str:
    params = row.get("params", {}) or {}
    if float(params.get("strong_market_exposure", 0.90)) <= 0.70:
        return "guarded"
    return "balanced"


def render_html_report(rows: list[dict]) -> str:
    """Render a self-contained HTML report for strategy research results."""

    sorted_rows = sorted(
        rows,
        key=lambda row: row.get("stability_score", -999),
        reverse=True,
    )
    full_rows = [row for row in sorted_rows if row.get("period_name") == "full"]
    best = full_rows[0] if full_rows else (sorted_rows[0] if sorted_rows else {})
    display_rows = full_rows if full_rows else sorted_rows
    benchmark_missing = bool(sorted_rows) and all(
        abs(float(row.get("benchmark_return", 0.0))) < 1e-12 for row in sorted_rows
    )
    audit_issues = audit_rows(sorted_rows)

    cards = "\n".join(
        [
            _metric_card("最优策略", best.get("kind", "N/A")),
            _metric_card("稳定性评分", _fmt_num(best.get("stability_score", 0), 4)),
            _metric_card("年化收益", _fmt_pct(float(best.get("annual_return", 0.0))), "good"),
            _metric_card("基准收益", _fmt_pct(float(best.get("benchmark_return", 0.0))), "blue"),
            _metric_card("超额收益", _fmt_pct(float(best.get("excess_return", 0.0))), "good"),
            _metric_card("最大回撤", _fmt_pct(float(best.get("max_drawdown", 0.0))), "risk"),
            _metric_card("Sharpe", _fmt_num(best.get("sharpe_ratio", 0), 2)),
            _metric_card("交易次数", str(best.get("trade_count", 0))),
        ]
    )

    table_rows = []
    for idx, row in enumerate(display_rows[:10], start=1):
        table_rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{_html_escape(row.get('kind', 'N/A'))}</td>"
            f"<td>{_html_escape(_profile_name(row))}</td>"
            f"<td>{_html_escape(row.get('period_name', 'N/A'))}</td>"
            f"<td>{_html_escape(row.get('start', ''))} 至 {_html_escape(row.get('end', ''))}</td>"
            f"<td>{_fmt_pct(float(row.get('annual_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('total_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('benchmark_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('excess_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('max_drawdown', 0.0)))}</td>"
            f"<td>{_fmt_num(row.get('sharpe_ratio', 0), 2)}</td>"
            f"<td>{_html_escape(row.get('trade_count', 0))}</td>"
            f"<td>{_html_escape(row.get('raw_trade_count', row.get('trade_count', 0)))}</td>"
            "</tr>"
        )

    best_by_period = _best_by_period(sorted_rows)
    period_rows = []
    for period in ("2020-2021", "2022", "2023-2024", "2025-2026"):
        row = best_by_period.get(period)
        if not row:
            continue
        period_rows.append(
            "<tr>"
            f"<td>{_html_escape(period)}</td>"
            f"<td>{_html_escape(row.get('kind', 'N/A'))}</td>"
            f"<td>{_fmt_pct(float(row.get('annual_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('total_return', 0.0)))}</td>"
            f"<td>{_fmt_pct(float(row.get('max_drawdown', 0.0)))}</td>"
            f"<td>{_html_escape(row.get('trade_count', 0))}</td>"
            f"<td>{_html_escape(_period_reason(row))}</td>"
            "</tr>"
        )

    benchmark_note = (
        """
        <p class="notice">注意：本次结果中基准收益为 0，说明大盘基准序列没有有效接入。
        因此本报告当前优先看策略自身收益、回撤和交易频率，超额收益暂不作为跑赢大盘证据。</p>
        """
        if benchmark_missing
        else ""
    )
    audit_items = "".join(
        f"<li><code>{_html_escape(issue['severity'])}</code> "
        f"<code>{_html_escape(issue['code'])}</code>: "
        f"{_html_escape(issue['message'])}</li>"
        for issue in audit_issues
    )
    audit_html = (
        f"<ul>{audit_items}</ul>"
        if audit_issues
        else "<p>未发现基准缺失、深回撤、明显分阶段跑输或交易频率偏高问题。</p>"
    )
    recommendation = recommendation_text(audit_issues)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A股行业龙头支撑压力策略研究报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172026;
      --muted: #66717a;
      --line: #d9e0e4;
      --band: #f4f7f8;
      --accent: #0b6b5c;
      --blue: #255c99;
      --risk: #a43d2c;
      --paper: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #eef3f5;
      font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    header {{
      margin-bottom: 24px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 30px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    p {{ margin: 8px 0; }}
    .subtitle {{ color: var(--muted); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
      margin: 18px 0 6px;
    }}
    .metric {{
      min-height: 86px;
      padding: 13px 14px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric span {{
      display: block;
      margin-bottom: 7px;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{
      display: block;
      overflow-wrap: anywhere;
      font-size: 20px;
      line-height: 1.25;
    }}
    .metric.good strong {{ color: var(--accent); }}
    .metric.blue strong {{ color: var(--blue); }}
    .metric.risk strong {{ color: var(--risk); }}
    .notice {{
      margin: 16px 0 0;
      padding: 12px 14px;
      background: #fff8e6;
      border: 1px solid #ebd48a;
      border-radius: 8px;
      color: #6b5618;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 11px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      background: var(--band);
      color: #34434d;
      font-weight: 650;
      white-space: nowrap;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .section {{
      padding: 18px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    @media (max-width: 900px) {{
      main {{ padding: 20px 12px 32px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      table {{ display: block; overflow-x: auto; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>A股行业龙头支撑压力策略研究报告</h1>
      <p class="subtitle">回测区间：{_html_escape(best.get('start', START_DATE))} 至 {_html_escape(best.get('end', END_DATE))}；策略池排除科创板与北交所，偏中低频交易。</p>
      <div class="metrics">
        {cards}
      </div>
      {benchmark_note}
    </header>

    <h2>全周期候选排名</h2>
    <table>
      <thead>
        <tr>
          <th>Rank</th><th>Strategy</th><th>Profile</th><th>Period</th><th>Range</th>
          <th>Annual</th><th>Total</th><th>Benchmark</th><th>Excess</th>
          <th>Max DD</th><th>Sharpe</th><th>Trades</th><th>Raw Trades</th>
        </tr>
      </thead>
      <tbody>
        {''.join(table_rows)}
      </tbody>
    </table>

    <h2>分阶段解释</h2>
    <table>
      <thead>
        <tr>
          <th>阶段</th><th>最优候选</th><th>年化收益</th><th>总收益</th>
          <th>最大回撤</th><th>交易次数</th><th>解释</th>
        </tr>
      </thead>
      <tbody>
        {''.join(period_rows)}
      </tbody>
    </table>

    <h2>最终推荐</h2>
    <section class="section">
      <p>最终推荐策略：<strong>{_html_escape(best.get('kind', 'N/A'))}</strong></p>
      <p>推荐依据：稳定性评分 {_fmt_num(best.get('stability_score', 0), 4)}，年化收益 {_fmt_pct(float(best.get('annual_return', 0.0)))}，最大回撤 {_fmt_pct(float(best.get('max_drawdown', 0.0)))}，交易次数 {_html_escape(best.get('trade_count', 0))}。策略选择依据为稳定性评分、回撤、Sharpe、收益和交易次数的综合表现，而不是单次最高收益。</p>
      <p><strong>审计结论：</strong>{_html_escape(recommendation)}</p>
    </section>

    <h2>回测审计</h2>
    <section class="section">
      {audit_html}
    </section>

    <h2>风险提示</h2>
    <section class="section">
      <ul>
        <li>历史回测不代表未来收益。</li>
        <li>行业龙头池仍可能存在幸存者偏差。</li>
        <li>akshare 数据源可用性、复权处理和基准序列会影响结果。</li>
        <li>支撑压力不是确定性价格预测，只是结构化风险收益判断。</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


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
    """Write JSON, CSV, Markdown, and HTML summary reports."""

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
        "raw_trade_count",
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
        f"- 基准收益: `{best.get('benchmark_return', 0):.2%}`",
        f"- 超额收益: `{best.get('excess_return', 0):.2%}`",
        f"- 最大回撤: `{best.get('max_drawdown', 0):.2%}`",
        f"- Sharpe: `{best.get('sharpe_ratio', 0):.2f}`",
        f"- 交易次数: `{best.get('trade_count', 0)}`",
        "",
        "## 全周期候选排名",
        "",
        "| Rank | Strategy | Profile | Period | Annual | Benchmark | Excess | Max DD | Sharpe | Trades | Raw Trades |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    display_rows = full_rows if full_rows else sorted_rows
    for idx, row in enumerate(display_rows[:10], start=1):
        lines.append(
            f"| {idx} | {row.get('kind')} | {_profile_name(row)} | {row.get('start')} to {row.get('end')} | "
            f"{row.get('annual_return', 0):.2%} | {row.get('benchmark_return', 0):.2%} | "
            f"{row.get('excess_return', 0):.2%} | {row.get('max_drawdown', 0):.2%} | "
            f"{row.get('sharpe_ratio', 0):.2f} | "
            f"{row.get('trade_count', 0)} | {row.get('raw_trade_count', row.get('trade_count', 0))} |"
        )
    lines.append("")
    lines.append(period_interpretation(sorted_rows))
    lines.append(audit_markdown(sorted_rows))
    (REPORT_DIR / "final_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    (REPORT_DIR / "final_report.html").write_text(
        render_html_report(sorted_rows),
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
