"""Example 9: Returns attribution and performance analysis.

Demonstrates:
- analyze_returns: Sharpe, Sortino, max drawdown, alpha, beta
- brinson_attribution: allocation, selection, interaction effects
- simple_factor_analysis: factor decomposition
- Using the full reporting pipeline (chart + Markdown + JSON)

Usage:
    python examples/09_attribution_analysis.py
"""

import pandas as pd
from eqlib import *
from eqlib import get_north_money_flow, get_limit_up_down_stats


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
    import os

    # Run backtest with preloaded data
    securities = ["601390", "000001", "600519", "600036", "000858"]

    os.makedirs("reports", exist_ok=True)

    result = run_backtest(
        initialize_func=initialize,
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=securities,
        use_local=True,
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

    # 3. Simple factor analysis
    print(f"\n{'=' * 60}")
    print("Factor Analysis (simplified)")
    print(f"{'=' * 60}")

    ff = simple_factor_analysis(result)
    if ff:
        print(f"  Market beta:         {ff['market_beta']:.2f}")
        print(f"  Market exposure:     {ff['market_exposure']:+.2f}")
        print(f"  Alpha (annual):      {ff['alpha_annual']:+.2%}")
        print(f"  Momentum corr:       {ff['momentum_correlation']:.2f}")
        print(f"  Vol-of-vol:          {ff['vol_of_vol']:.4f}")
        print(f"  Explained variance:  {ff['explained_variance']:.2%}")
    else:
        print("  Insufficient data for factor analysis")

    # 4. Market background context (A-share specific data)
    print(f"\n{'=' * 60}")
    print("市场背景 (Market Context)")
    print(f"{'=' * 60}")

    try:
        # Recent north capital trend (last 5 trading days)
        north_df = get_north_money_flow()
        if not north_df.empty and "net_buy" in north_df.columns:
            recent = north_df.tail(5)
            net_3d = recent["net_buy"].tail(3).sum()
            net_5d = recent["net_buy"].sum()
            print(f"  北向资金近5日净买入: {net_5d:+.2f} 亿元")
            print(f"  北向资金近3日净买入: {net_3d:+.2f} 亿元")
            if net_3d > 0:
                north_trend = "外资持续流入，市场情绪偏多"
            elif net_3d < -10:
                north_trend = "外资大幅流出，市场承压"
            else:
                north_trend = "外资流入趋缓，方向不明"
            print(f"  北向资金趋势判断:   {north_trend}")
        else:
            print("  北向资金数据暂不可用")

        # Recent limit up/down stats
        limit_df = get_limit_up_down_stats()
        if not limit_df.empty:
            recent_limit = limit_df.tail(5)
            avg_up = recent_limit["limit_up_count"].mean()
            avg_down = recent_limit["limit_down_count"].mean()
            print(f"\n  近5日涨停均值: {avg_up:.1f} 只")
            print(f"  近5日跌停均值: {avg_down:.1f} 只")
            if avg_up > avg_down * 2:
                limit_trend = "涨停多跌停少，市场人气旺盛"
            elif avg_down > avg_up:
                limit_trend = "跌停多于涨停，市场恐慌情绪浓厚"
            else:
                limit_trend = "涨跌停均衡，市场处于震荡期"
            print(f"  涨跌停趋势判断: {limit_trend}")
        else:
            print("  涨跌停统计数据暂不可用")

        # Combined market context interpretation
        print(f"\n  [综合市场背景]")
        if not north_df.empty and not limit_df.empty:
            north_bull = net_3d > 0
            limit_bull = avg_up > avg_down * 1.5
            if north_bull and limit_bull:
                print("  市场情绪偏多：外资流入 + 涨停活跃，归因结果在强势市场中更可靠。")
            elif not north_bull and not limit_bull:
                print("  市场情绪偏弱：外资流出 + 跌停偏多，策略需警惕系统性风险。")
            else:
                print("  市场信号分歧：北向资金与涨跌停方向不一致，建议结合更多指标判断。")
        else:
            print("  部分市场数据不可用，跳过综合判断。")

    except Exception as exc:
        print(f"  市场背景数据获取失败: {exc}")

    # ============================================================
    # Generate Reports
    # ============================================================
    print(f"\n{'=' * 60}")
    print("Generating Reports")
    print(f"{'=' * 60}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    generate_chart(result, f"reports/analysis_{timestamp}.png")
    generate_report_md(result, f"reports/analysis_{timestamp}.md")
    generate_report_json(result, f"reports/analysis_{timestamp}.json")

    ctx = result["context"]
    print(f"\n  Final value: {ctx.portfolio.total_value:,.2f}")
    print(f"  Trades: {len(result['trade_log'])}")
