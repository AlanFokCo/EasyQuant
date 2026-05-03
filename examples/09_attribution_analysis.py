"""Example 9: Returns attribution and performance analysis.

Demonstrates:
- analyze_returns: Sharpe, Sortino, max drawdown, alpha, beta
- brinson_attribution: allocation, selection, interaction effects
- fama_french_analysis: factor decomposition
- Using the full reporting pipeline (chart + Markdown + JSON)

Usage:
    python examples/09_attribution_analysis.py
"""

import pandas as pd
from eqlib import *


def initialize(context):
    """Multi-stock strategy for attribution analysis."""
    g.stocks = ["601390", "000001", "600519", "600036", "000858"]
    g.lookback = 30

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = g.stocks
    run_weekly(weekly_rebalance, day_of_week=0, time="09:30")


def weekly_rebalance(context):
    """Equal-weight rebalance with momentum filter."""
    returns = {}
    for sec in g.stocks:
        df = attribute_history(sec, g.lookback, "1d", ["close"])
        if not df.empty and "close" in df.columns and len(df) >= 5:
            ret = (df["close"].iloc[-1] / df["close"].iloc[-5]) - 1
            returns[sec] = ret

    if not returns:
        return

    # Buy top performers
    sorted_stocks = sorted(returns.items(), key=lambda x: x[1], reverse=True)
    top_stocks = [s[0] for s in sorted_stocks[:3]]

    # Sell stocks not in top picks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)

    # Buy top picks
    per_stock = context.portfolio.available_cash / len(top_stocks)
    for sec in top_stocks:
        if per_stock > 1000:
            order_value(sec, per_stock)

    record(total_value=context.portfolio.total_value)


if __name__ == "__main__":
    import datetime

    # Run backtest with preloaded data
    securities = ["601390", "000001", "600519", "600036", "000858"]

    result = run_backtest(
        initialize_func=initialize,
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=securities,
    )

    if result is None:
        print("Backtest failed.")
        exit(1)

    # ============================================================
    # Attribution & Performance Analysis
    # ============================================================

    print(f"\n{'=' * 60}")
    print("Performance Metrics")
    print(f"{'=' * 60}")

    # 1. Comprehensive returns analysis
    metrics = analyze_returns(result)
    if metrics:
        print(f"  Total return:      {metrics['total_return']:+.2%}")
        print(f"  Annual return:     {metrics['annual_return']:+.2%}")
        print(f"  Annual volatility: {metrics['annual_volatility']:.2%}")
        print(f"  Sharpe ratio:      {metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino ratio:     {metrics['sortino_ratio']:.2f}")
        print(f"  Max drawdown:      {metrics['max_drawdown']:+.2%}")
        print(f"  Calmar ratio:      {metrics['calmar_ratio']:.2f}")
        print(f"  Alpha (annual):    {metrics['alpha']:+.2%}")
        print(f"  Beta:              {metrics['beta']:.2f}")
        print(f"  Info ratio:        {metrics['information_ratio']:.2f}")
        print(f"  Win rate (daily):  {metrics['win_rate']:.2%}")
        print(f"  Trading days:      {metrics['trading_days']}")
        print(f"  Total trades:      {metrics['num_trades']}")

    # 2. Brinson attribution
    print(f"\n{'=' * 60}")
    print("Brinson Attribution")
    print(f"{'=' * 60}")

    brinson = brinson_attribution(result)
    if brinson:
        print(f"  Allocation effect: {brinson['allocation_effect']:+.4f}")
        print(f"  Selection effect:  {brinson['selection_effect']:+.4f}")
        print(f"  Interaction effect:{brinson['interaction_effect']:+.4f}")
        print(f"  Total active:      {brinson['total_active_return']:+.4f}")
    else:
        print("  Insufficient data for Brinson attribution")

    # 3. Fama-French factor analysis
    print(f"\n{'=' * 60}")
    print("Factor Analysis (simplified)")
    print(f"{'=' * 60}")

    ff = fama_french_analysis(result)
    if ff:
        print(f"  Market beta:         {ff['market_beta']:.2f}")
        print(f"  Market exposure:     {ff['market_exposure']:+.2f}")
        print(f"  Alpha (annual):      {ff['alpha_annual']:+.2%}")
        print(f"  Momentum corr:       {ff['momentum_correlation']:.2f}")
        print(f"  Vol-of-vol:          {ff['vol_of_vol']:.4f}")
        print(f"  Explained variance:  {ff['explained_variance']:.2%}")
    else:
        print("  Insufficient data for factor analysis")

    # ============================================================
    # Generate Reports
    # ============================================================
    print(f"\n{'=' * 60}")
    print("Generating Reports")
    print(f"{'=' * 60}")

    import os
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    generate_chart(result, f"reports/analysis_{timestamp}.png")
    generate_report_md(result, f"reports/analysis_{timestamp}.md")
    generate_report_json(result, f"reports/analysis_{timestamp}.json")

    ctx = result["context"]
    print(f"\n  Final value: {ctx.portfolio.total_value:,.2f}")
    print(f"  Trades: {len(result['trade_log'])}")
