"""
09 - Attribution Analysis
=========================

Demonstrates the full performance attribution pipeline:
- analyze_returns: comprehensive risk/return metrics
- brinson_attribution: allocation, selection, interaction effects
- simple_factor_analysis: market beta, alpha, factor exposure
- grade_strategy: 6-dimension strategy scoring (S/A/B/C/D)
- diagnose_bottleneck: identify failing metrics and root causes
- recommend_params: parameter tuning suggestions

Uses a multi-stock momentum strategy to generate diverse
trades for meaningful attribution results.

Teaching Objectives:
    - Running a multi-stock backtest with weekly rebalancing
    - Interpreting analyze_returns() metric dictionary
    - Understanding Brinson attribution effects
    - Factor analysis: market beta and alpha
    - Strategy grading and diagnostic workflow

Expected Output:
    - Complete risk/return metrics
    - Brinson allocation/selection/interaction effects
    - Market beta and alpha from factor analysis
    - Strategy grade with dimension breakdown
    - Diagnostic findings for failing metrics
    - PNG and MD reports generated

Run:
    python examples/09_attribution.py
"""

import os

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_weekly, attribute_history, order_value, order_target,
    record, log, g,
    analyze_returns, brinson_attribution, simple_factor_analysis,
    grade_strategy, diagnose_bottleneck, recommend_params,
    generate_chart, generate_report_md,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available,
)


# ============================================================
# Strategy configuration
# ============================================================

# 5 stocks across different sectors for meaningful attribution
UNIVERSE_KEYS = ["bank", "liquor", "ev", "pharma", "cement"]
UNIVERSE_BARE = [STOCKS[k] for k in UNIVERSE_KEYS]
UNIVERSE_TRADE = [STOCKS_TRADE[k] for k in UNIVERSE_KEYS]

LOOKBACK = 20   # 20-day momentum window
TOP_N = 3       # Buy top 3 by momentum


# ============================================================
# Strategy: multi-stock momentum (weekly rebalance)
# ============================================================

def initialize(context):
    """Set up benchmark, costs, universe, and weekly schedule."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.universe_bare = UNIVERSE_BARE
    g.universe_trade = UNIVERSE_TRADE
    g.lookback = LOOKBACK
    g.top_n = TOP_N

    context.universe = UNIVERSE_BARE

    # Rebalance every Monday at open
    run_weekly(weekly_rebalance, day_of_week=0, time="09:30")


def weekly_rebalance(context):
    """Rank stocks by 20-day return, buy top-3 equal-weight."""
    # Compute momentum for each stock
    momentum = {}
    for bare, trade in zip(g.universe_bare, g.universe_trade):
        df = attribute_history(bare, g.lookback + 5, "1d", ["close"])
        if df is None or df.empty or len(df) < g.lookback:
            continue
        close = df["close"]
        ret = close.iloc[-1] / close.iloc[-g.lookback] - 1
        momentum[trade] = ret

    if not momentum:
        return

    # Sort by momentum descending, take top N
    ranked = sorted(momentum.items(), key=lambda x: x[1], reverse=True)
    top_picks = [sec for sec, _ in ranked[:g.top_n]]

    # Sell positions not in top picks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_picks:
            order_target(sec, 0)

    # Equal-weight allocation across top picks
    per_stock = context.portfolio.available_cash / len(top_picks)
    for sec in top_picks:
        if per_stock > 1000:
            order_value(sec, per_stock)

    record(total_value=context.portfolio.total_value)


# ============================================================
# Main: run backtest and perform attribution
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("09 - Attribution Analysis")
    print("=" * 60)
    print(f"  Universe: {UNIVERSE_KEYS}")
    print(f"  Period:   {START_DATE} → {END_DATE}")
    print(f"  Capital:  ¥{INITIAL_CASH:,.0f}")
    print(f"  Strategy: top-{TOP_N} by {LOOKBACK}-day momentum, weekly rebalance")

    # Verify data for the first stock; if it works, others likely will too
    actual_start, actual_end = verify_data_available(
        UNIVERSE_BARE[0], START_DATE, END_DATE)

    # Run backtest with all securities preloaded for speed
    result = run_backtest(
        initialize_func=initialize,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=UNIVERSE_BARE,
        use_local=True,
    )

    if result is None:
        print("Backtest failed — no results.")
        raise SystemExit(1)

    ctx = result["context"]
    trade_log = result["trade_log"]

    print(f"\n  Backtest complete: {len(trade_log)} trades executed")
    print(f"  Final value: ¥{ctx.portfolio.total_value:,.2f}")

    # ============================================================
    # 1. Comprehensive Risk/Return Metrics (analyze_returns)
    # ============================================================

    print(f"\n{'=' * 60}")
    print("1. Risk/Return Metrics (analyze_returns)")
    print(f"{'=' * 60}")

    metrics = analyze_returns(result, risk_free_rate=0.03)
    if metrics:
        metric_descriptions = {
            "total_return":      ("Total Return",      ">.2%",  "cumulative P&L over full period"),
            "annual_return":     ("Annual Return",     ">0%",   "annualized compound growth rate"),
            "annual_volatility": ("Annual Volatility", "<25%",  "annualized std of daily returns"),
            "sharpe_ratio":      ("Sharpe Ratio",      ">1.0",  "excess return per unit of risk"),
            "sortino_ratio":     ("Sortino Ratio",     ">1.5",  "like Sharpe but only penalizes downside vol"),
            "max_drawdown":      ("Max Drawdown",      ">-20%", "worst peak-to-trough decline"),
            "calmar_ratio":      ("Calmar Ratio",      ">1.0",  "annual return / max drawdown"),
            "win_rate_trade":    ("Win Rate (trade)",  ">40%",  "% of trades that were profitable"),
            "profit_loss_ratio": ("Profit/Loss Ratio", ">1.5",  "avg win / avg loss per trade"),
            "trade_count":       ("Trade Count",       "≥3/yr", "total round-trip trades"),
            "alpha":             ("Alpha",             ">0%",   "excess return vs benchmark (CAPM)"),
            "beta":              ("Beta",              "0.3–1.3","sensitivity to benchmark moves"),
        }
        for key, (label, target, desc) in metric_descriptions.items():
            val = metrics.get(key)
            if val is None:
                continue
            if key in ("total_return", "annual_return", "annual_volatility",
                        "max_drawdown", "win_rate_trade", "alpha"):
                formatted = f"{val:>+10.2%}" if key != "annual_volatility" else f"{val:>10.2%}"
            elif key == "trade_count":
                formatted = f"{val:>10.0f}"
            else:
                formatted = f"{val:>+10.2f}" if key in ("sharpe_ratio", "sortino_ratio",
                    "calmar_ratio", "beta", "profit_loss_ratio") else f"{val:>10.2f}"
            print(f"  {label:<22s} {formatted}  (target: {target}) — {desc}")
    else:
        print("  Could not compute metrics (insufficient recorded data)")

    # ============================================================
    # 2. Brinson Attribution (allocation / selection / interaction)
    # ============================================================

    print(f"\n{'=' * 60}")
    print("2. Brinson Attribution")
    print(f"{'=' * 60}")

    brinson = brinson_attribution(result)
    if brinson:
        alloc = brinson["allocation_effect"]
        select = brinson["selection_effect"]
        interact = brinson["interaction_effect"]
        total_active = brinson["total_active_return"]

        print(f"  Allocation effect:    {alloc:>+10.4f}  "
              f"({'positive' if alloc > 0 else 'negative'} — "
              f"did overweighting outperformers help?)")
        print(f"  Selection effect:     {select:>+10.4f}  "
              f"({'positive' if select > 0 else 'negative'} — "
              f"did stock picks beat the average?)")
        print(f"  Interaction effect:   {interact:>+10.4f}  "
              f"({'positive' if interact > 0 else 'negative'} — "
              f"combined weight+selection synergy)")
        print(f"  Total active return:  {total_active:>+10.4f}  "
              f"(sum of all three effects)")
        print(f"\n  Interpretation:")
        dominant = max(
            ("Allocation", abs(alloc)),
            ("Selection", abs(select)),
            ("Interaction", abs(interact)),
            key=lambda x: x[1],
        )
        print(f"    Dominant effect: {dominant[0]} "
              f"(|{dominant[1]:.4f}|)")
    else:
        print("  Insufficient data for Brinson attribution")

    # ============================================================
    # 3. Simple Factor Analysis (market beta + alpha)
    # ============================================================

    print(f"\n{'=' * 60}")
    print("3. Factor Analysis (simple_factor_analysis)")
    print(f"{'=' * 60}")

    ff = simple_factor_analysis(result)
    if ff:
        print(f"  Market beta:          {ff['market_beta']:>10.2f}  "
              f"({'aggressive' if ff['market_beta'] > 1.0 else 'defensive' if ff['market_beta'] < 0.8 else 'market-like'} — "
              f"sensitivity to market moves)")
        print(f"  Market exposure:      {ff.get('market_exposure', 0):>+10.2f}  "
              f"(raw market factor loading)")
        print(f"  Alpha (annual):       {ff['alpha_annual']:>+10.2%}  "
              f"({'positive alpha — strategy adds value' if ff['alpha_annual'] > 0 else 'negative alpha — underperforms on risk-adjusted basis'} "
              f"beyond market exposure)")
        print(f"  Momentum corr:        {ff['momentum_correlation']:>10.2f}  "
              f"({'significant' if abs(ff['momentum_correlation']) > 0.1 else 'weak'} — "
              f"lag-5 return autocorrelation)")
        print(f"  Vol-of-vol:           {ff['vol_of_vol']:>10.4f}  "
              f"({'high' if ff['vol_of_vol'] > 0.01 else 'low'} — "
              f"volatility clustering / regime changes)")
        print(f"  Explained variance:   {ff.get('explained_variance', 0):>10.2%}  "
              f"({'market explains most variance' if ff.get('explained_variance', 0) > 0.5 else 'idiosyncratic risk dominates'}")
    else:
        print("  Insufficient data for factor analysis")

    # ============================================================
    # 4. Strategy Grading & Diagnostics (new in v2)
    # ============================================================

    print(f"\n{'=' * 60}")
    print("4. Strategy Grading & Diagnostics")
    print(f"{'=' * 60}")

    if metrics:
        grade_info = grade_strategy(metrics)
        print(f"  Overall grade:  {grade_info['overall']} ({grade_info['score']:.0f}/100)")
        print(f"  Strongest:      {grade_info['strongest']}")
        print(f"  Weakest:        {grade_info['weakest']}")
        print(f"  Summary:        {grade_info['summary_text']}")

        # Per-dimension breakdown
        for dim in grade_info["dimensions"]:
            bar = "█" * int(dim["score"] / 5) + "░" * (20 - int(dim["score"] / 5))
            print(f"    {dim['name']:<22s} {dim['score']:>5.1f}  [{bar}] {dim['grade']}")

        # Diagnostics
        diagnostics = diagnose_bottleneck(metrics, grade_info)
        if diagnostics:
            print(f"\n  Diagnostics ({len(diagnostics)} issue{'s' if len(diagnostics) > 1 else ''}):")
            for d in diagnostics:
                severity = "⚠" if d["severity"] == "warning" else "✗"
                print(f"    {severity} [{d['severity']}] {d['finding']}")
                print(f"      Root cause: {d['root_cause']}")
        else:
            print("\n  No diagnostics — all metrics meet targets.")
    else:
        print("  Skipping grading (no metrics available)")

    # ============================================================
    # 5. Generate Reports (PNG chart + Markdown)
    # ============================================================

    print(f"\n{'=' * 60}")
    print("5. Report Generation")
    print(f"{'=' * 60}")

    os.makedirs("reports", exist_ok=True)

    import datetime as dt
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    chart_path = f"reports/09_attribution_{timestamp}.png"
    md_path = f"reports/09_attribution_{timestamp}.md"

    generate_chart(result, chart_path)
    generate_report_md(result, md_path)

    print(f"  PNG chart:  {chart_path}")
    print(f"  MD report:  {md_path}")

    print(f"\n{'=' * 60}")
    print("Done. Full attribution pipeline complete.")
    print(f"{'=' * 60}")
