"""
05 - Report Generation
======================

Demonstrates generating backtest reports in all four formats:
PNG chart, interactive HTML, Markdown summary, and JSON data.
Also serves as a reference for every metric key returned by
analyze_returns().

Teaching Objectives:
    - generate_chart(): cumulative return + drawdown PNG
    - generate_html_report(): interactive K-line HTML
    - generate_report_md(): professional Markdown summary
    - generate_report_json(): machine-readable metrics + trades
    - analyze_returns(): every metric key explained

Expected Output:
    - 4 report files generated in reports/ directory
    - JSON report sections printed and explained
    - Complete metric key reference with descriptions

Run:
    python examples/05_reports.py
"""

import json
import os

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_daily, attribute_history, order_value, order_target,
    record, log, g,
    analyze_returns,
    generate_chart, generate_html_report,
    generate_report_md, generate_report_json,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available,
)


# ============================================================
# Minimal strategy for report demonstration
# ============================================================

SECURITY = STOCKS["liquor"]
SECURITY_TRADE = STOCKS_TRADE["liquor"]


def initialize(context):
    """Simple MA crossover strategy for report generation demo."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = SECURITY
    g.security_trade = SECURITY_TRADE

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")


def market_open(context):
    """MA 10/30 crossover."""
    security = g.security
    security_trade = g.security_trade

    hist = attribute_history(security, 35, "1d", ["close"])
    if hist is None or hist.empty or len(hist) < 30:
        return

    close = hist["close"]
    current_price = close.iloc[-1]

    fast_ma = close.rolling(10).mean()
    slow_ma = close.rolling(30).mean()

    if len(fast_ma.dropna()) < 2 or len(slow_ma.dropna()) < 2:
        return

    golden_cross = (fast_ma.iloc[-2] <= slow_ma.iloc[-2]
                    and fast_ma.iloc[-1] > slow_ma.iloc[-1])
    death_cross = (fast_ma.iloc[-2] >= slow_ma.iloc[-2]
                   and fast_ma.iloc[-1] < slow_ma.iloc[-1])

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if golden_cross and not has_position:
        cash = context.portfolio.available_cash
        if cash > current_price * 100:
            order_value(security_trade, cash * 0.95)
    elif death_cross and has_position:
        order_target(security_trade, 0)

    record(total_value=context.portfolio.total_value,
           price=current_price)


# ============================================================
# Main: run backtest and generate reports
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("05 - Report Generation")
    print("=" * 55)

    actual_start, actual_end = verify_data_available(
        SECURITY, START_DATE, END_DATE)

    os.makedirs("reports", exist_ok=True)

    # Run backtest (low-level, so we control report generation)
    result = run_backtest(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[SECURITY],
        use_local=True,
    )

    if result is None:
        print("Backtest failed — no results.")
        raise SystemExit(1)

    # --- Generate all 4 report formats ---
    print(f"\n{'='*55}")
    print("Generating Reports")
    print(f"{'='*55}")

    generate_chart(result, "reports/05_chart.png")
    print(f"  PNG chart:   reports/05_chart.png")

    generate_html_report(result, "reports/05_report.html")
    print(f"  HTML report: reports/05_report.html")

    generate_report_md(result, "reports/05_report.md")
    print(f"  Markdown:    reports/05_report.md")

    generate_report_json(result, "reports/05_report.json")
    print(f"  JSON:        reports/05_report.json")

    # --- Inspect JSON report ---
    print(f"\n{'='*55}")
    print("JSON Report Summary")
    print(f"{'='*55}")

    with open("reports/05_report.json", "r") as f:
        report = json.load(f)

    print(f"  Top-level keys: {list(report.keys())}")

    if "risk_metrics" in report:
        print(f"\n  Risk metrics:")
        for key, val in report["risk_metrics"].items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")

    if "benchmark_comparison" in report:
        bm = report["benchmark_comparison"]
        print(f"\n  Benchmark comparison:")
        for key, val in bm.items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")

    # --- Complete metric key reference ---
    print(f"\n{'='*55}")
    print("analyze_returns() — Complete Key Reference")
    print(f"{'='*55}")

    metrics = analyze_returns(result, risk_free_rate=0.03)
    if metrics:
        descriptions = {
            "total_return": "Total portfolio return (fraction)",
            "annual_return": "Annualized return (geometric)",
            "annual_volatility": "Annualized daily return std dev",
            "sharpe_ratio": "(annual_return - rf) / annual_volatility",
            "sortino_ratio": "Like Sharpe but only downside volatility",
            "max_drawdown": "Largest peak-to-trough decline (negative)",
            "calmar_ratio": "annual_return / abs(max_drawdown)",
            "alpha": "Excess return vs benchmark (CAPM alpha)",
            "beta": "Sensitivity to benchmark movements",
            "information_ratio": "Excess return / tracking error",
            "win_rate_daily": "Fraction of profitable days",
            "win_rate_trade": "Fraction of profitable round-trip trades",
            "trade_count": "Number of completed round-trip trades",
            "profit_loss_ratio": "Avg winning P&L / avg losing P&L",
            "annual_turnover": "Traded value / avg portfolio / years",
            "total_commission": "Sum of all commissions paid",
            "excess_return": "Strategy return - benchmark return",
            "benchmark_return": "Benchmark total return",
        }
        for key, desc in descriptions.items():
            val = metrics.get(key)
            if val is not None:
                if isinstance(val, float):
                    if abs(val) < 10:
                        print(f"  {key:<25} {val:>10.4f}  # {desc}")
                    else:
                        print(f"  {key:<25} {val:>10.2f}  # {desc}")
                else:
                    print(f"  {key:<25} {str(val):>10}  # {desc}")
            else:
                print(f"  {key:<25} {'N/A':>10}  # {desc}")
