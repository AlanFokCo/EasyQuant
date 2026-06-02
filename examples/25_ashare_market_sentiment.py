"""Example 25: A-share Market Sentiment Indicators.

Demonstrates how to use A-share specific data APIs to build market sentiment
indicators and use them as strategy filters.

Demos:
1. North-bound capital flow trend analysis
2. Margin trading sentiment indicators
3. Limit up/down statistics and market breadth
4. Restricted share release warnings
5. Composite sentiment score + strategy filter
"""

import pandas as pd
from datetime import datetime, timedelta

from eqlib import (
    get_north_money_flow,
    get_margin_data,
    get_limit_up_down_stats,
    get_restriction_release,
    get_price,
    run_backtest,
    analyze_returns,
    order_value,
    order_target,
    g,
    run_daily,
    set_benchmark,
    attribute_history,
    log,
)


# ============================================================
# Demo 1: North-bound Capital Flow Trend Analysis
# ============================================================

def demo_north_flow():
    """北向资金趋势分析：5日/20日滚动净买入，判断资金流向趋势。"""
    log.info("=== Demo 1: North-bound Capital Flow ===\n")

    # 获取近 3 个月数据
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    north = get_north_money_flow(start_date=start_date, end_date=end_date)

    if north.empty:
        log.info("No data available")
        return

    log.info(f"Data range: {north['date'].iloc[0]} ~ {north['date'].iloc[-1]}")
    log.info(f"Total records: {len(north)}\n")

    # 计算 5 日和 20 日滚动净买入
    north["rolling_5d"] = north["net_buy"].rolling(5).sum()
    north["rolling_20d"] = north["net_buy"].rolling(20).sum()

    log.info("Recent trend (last 10 days):")
    cols = ["date", "net_buy", "rolling_5d", "rolling_20d"]
    log.info(north[cols].tail(10).to_string())
    print()

    # 判断资金流向趋势
    latest_5d = north["rolling_5d"].iloc[-1]
    latest_20d = north["rolling_20d"].iloc[-1]

    # Handle NaN from insufficient data
    if pd.isna(latest_5d) or pd.isna(latest_20d):
        log.info("Insufficient data for trend analysis")
        return "neutral"

    if latest_5d > 50 and latest_20d > 100:
        trend = "强势流入 (Strong inflow)"
        signal = "bullish"
    elif latest_5d < -50 and latest_20d < -100:
        trend = "强势流出 (Strong outflow)"
        signal = "bearish"
    elif latest_5d > 0:
        trend = "温和流入 (Moderate inflow)"
        signal = "neutral_bullish"
    elif latest_5d < 0:
        trend = "温和流出 (Moderate outflow)"
        signal = "neutral_bearish"
    else:
        trend = "平衡 (Balanced)"
        signal = "neutral"

    log.info(f"5-day net buy: {latest_5d:.2f} 亿元")
    log.info(f"20-day net buy: {latest_20d:.2f} 亿元")
    log.info(f"Trend: {trend}")
    log.info(f"Signal: {signal}")

    return signal


# ============================================================
# Demo 2: Margin Trading Sentiment Indicators
# ============================================================

def demo_margin_sentiment():
    """融资融券情绪指标：融资余额变化率、融资买入占比。"""
    log.info("\n=== Demo 2: Margin Trading Sentiment ===\n")

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    margin = get_margin_data(start_date=start_date, end_date=end_date)

    if margin.empty:
        log.info("No data available")
        return

    log.info(f"Data range: {margin['date'].iloc[0]} ~ {margin['date'].iloc[-1]}")
    log.info(f"Total records: {len(margin)}\n")

    # 计算融资余额变化率（5日）
    margin["balance_change_5d"] = margin["margin_balance"].diff(5)
    margin["balance_change_pct"] = margin["balance_change_5d"] / margin["margin_balance"].shift(5) * 100

    # 计算融资买入占比（融资买入 / (融资买入 + 融资偿还)）
    margin["buy_ratio"] = margin["margin_buy"] / (margin["margin_buy"] + margin["margin_repay"].abs()) * 100

    log.info("Recent margin data (last 10 days):")
    cols = ["date", "margin_balance", "balance_change_pct", "buy_ratio"]
    available_cols = [c for c in cols if c in margin.columns]
    log.info(margin[available_cols].tail(10).to_string())
    print()

    # 判断杠杆情绪
    latest_change_pct = margin["balance_change_pct"].iloc[-1]
    latest_buy_ratio = margin["buy_ratio"].iloc[-1]

    # Handle NaN from insufficient data
    if pd.isna(latest_change_pct):
        latest_change_pct = 0
    if pd.isna(latest_buy_ratio):
        latest_buy_ratio = 50

    if latest_change_pct > 2:
        leverage_trend = "融资快速增长 (Fast growth)"
        leverage_signal = "bullish"
    elif latest_change_pct < -2:
        leverage_trend = "融资快速下降 (Fast decline)"
        leverage_signal = "bearish"
    else:
        leverage_trend = "融资平稳 (Stable)"
        leverage_signal = "neutral"

    if latest_buy_ratio > 55:
        buy_sentiment = "融资买入活跃 (Active buying)"
    elif latest_buy_ratio < 45:
        buy_sentiment = "融资偿还主导 (Repayment dominant)"
    else:
        buy_sentiment = "融资买卖平衡 (Balanced)"

    log.info(f"5-day balance change: {latest_change_pct:.2f}%")
    log.info(f"Margin buy ratio: {latest_buy_ratio:.2f}%")
    log.info(f"Leverage trend: {leverage_trend}")
    log.info(f"Buy sentiment: {buy_sentiment}")

    return leverage_signal


# ============================================================
# Demo 3: Limit Up/Down Statistics and Market Breadth
# ============================================================

def demo_limit_stats():
    """涨跌停统计与市场宽度：涨跌停比值、系统性风险预警。"""
    log.info("\n=== Demo 3: Limit Up/Down Statistics ===\n")

    limit_stats = get_limit_up_down_stats()

    if limit_stats.empty:
        log.info("No data available")
        return

    log.info(f"Data range: {limit_stats['date'].iloc[0]} ~ {limit_stats['date'].iloc[-1]}")
    log.info(f"Total records: {len(limit_stats)}\n")

    # 计算涨跌停比值
    limit_stats["up_down_ratio"] = limit_stats["limit_up_count"] / limit_stats["limit_down_count"].clip(lower=1)

    # 计算 5 日平均
    limit_stats["avg_up_5d"] = limit_stats["limit_up_count"].rolling(5).mean()
    limit_stats["avg_down_5d"] = limit_stats["limit_down_count"].rolling(5).mean()

    log.info("Recent limit stats (last 10 days):")
    cols = ["date", "limit_up_count", "limit_down_count", "up_down_ratio"]
    log.info(limit_stats[cols].tail(10).to_string())
    print()

    # 系统性风险预警
    latest_up = limit_stats["limit_up_count"].iloc[-1]
    latest_down = limit_stats["limit_down_count"].iloc[-1]
    latest_ratio = limit_stats["up_down_ratio"].iloc[-1]

    # 跌停数 > 100 触发风险预警
    if latest_down > 100:
        risk_alert = "⚠️ 系统性风险预警：跌停数 > 100"
        market_signal = "risk_alert"
    elif latest_down > 50:
        risk_alert = "⚠️ 市场情绪偏弱：跌停数 > 50"
        market_signal = "weak"
    elif latest_ratio > 3:
        risk_alert = "市场情绪偏强：涨跌停比值 > 3"
        market_signal = "strong"
    else:
        risk_alert = "市场情绪正常"
        market_signal = "normal"

    log.info(f"Latest up count: {latest_up}")
    log.info(f"Latest down count: {latest_down}")
    log.info(f"Up/down ratio: {latest_ratio:.2f}")
    log.info(f"Risk alert: {risk_alert}")

    return market_signal


# ============================================================
# Demo 4: Restricted Share Release Warnings
# ============================================================

def demo_restriction_warning():
    """限售股解禁预警：未来 30 天大额解禁列表，按解禁市值排序。"""
    log.info("\n=== Demo 4: Restricted Share Release Warnings ===\n")

    releases = get_restriction_release(days=30)

    if releases.empty:
        log.info("No upcoming releases")
        return

    log.info(f"Total upcoming releases: {len(releases)}\n")

    # 统计解禁市值分布
    if "release_value" in releases.columns:
        total_value = releases["release_value"].sum()
        large_releases = releases[releases["release_value"] > 50]
        log.info(f"Total release value (30 days): {total_value:.2f} 亿元")
        log.info(f"Large releases (>50亿): {len(large_releases)} stocks")
        print()

        # 按解禁市值排序，显示前 10
        top_releases = releases.nlargest(10, "release_value")
        log.info("Top 10 by release value:")
        cols = ["code", "name", "release_date", "release_value", "release_pct"]
        log.info(top_releases[cols].to_string())
        print()

        # 按日期分组统计（按月份）
        if "release_date" in releases.columns:
            releases["month"] = pd.to_datetime(releases["release_date"]).dt.strftime("%Y-%m")
            monthly_sum = releases.groupby("month")["release_value"].sum().sort_index()
            log.info("Monthly release summary:")
            log.info(monthly_sum.to_string())
            print()

        # 预警判断
        max_single = releases["release_value"].max()
        if max_single > 200:
            warning = f"⚠️ 大额解禁预警：单股票解禁市值 {max_single:.0f} 亿元"
        elif total_value > 500:
            warning = f"⚠️ 解禁高峰预警：30 天解禁市值合计 {total_value:.0f} 亿元"
        else:
            warning = "解禁压力正常"

        log.info(warning)

    return releases


# ============================================================
# Demo 5: Composite Sentiment Score + Strategy Filter
# ============================================================

def calculate_sentiment_score():
    """构建 0-100 综合情绪分数。"""
    log.info("\n=== Demo 5: Composite Sentiment Score ===\n")

    # 获取各指标信号
    north_signal = demo_north_flow() or "neutral"
    margin_signal = demo_margin_sentiment() or "neutral"
    limit_signal = demo_limit_stats() or "normal"

    # 计算分数（简单加权）
    score = 50  # 基准分数

    # 北向资金权重 30%
    if north_signal == "bullish":
        score += 30
    elif north_signal == "bearish":
        score -= 30
    elif north_signal == "neutral_bullish":
        score += 15
    elif north_signal == "neutral_bearish":
        score -= 15

    # 融资融券权重 25%
    if margin_signal == "bullish":
        score += 25
    elif margin_signal == "bearish":
        score -= 25

    # 涨跌停权重 25%
    if limit_signal == "strong":
        score += 25
    elif limit_signal == "risk_alert":
        score -= 25
    elif limit_signal == "weak":
        score -= 15

    # 确保分数在 0-100 范围内
    score = max(0, min(100, score))

    log.info(f"\n=== Sentiment Summary ===")
    log.info(f"North flow signal: {north_signal}")
    log.info(f"Margin signal: {margin_signal}")
    log.info(f"Limit stats signal: {limit_signal}")
    log.info(f"Composite sentiment score: {score}")
    print()

    # 情绪区间划分
    if score >= 70:
        zone = "乐观区 (Optimistic)"
    elif score >= 50:
        zone = "中性偏乐观 (Neutral-Bullish)"
    elif score >= 30:
        zone = "中性偏悲观 (Neutral-Bearish)"
    else:
        zone = "悲观区 (Pessimistic)"

    log.info(f"Sentiment zone: {zone}")

    return score


# ============================================================
# Strategy with Sentiment Filter
# ============================================================

def initialize_with_filter(context):
    """带情绪过滤的均线策略初始化。"""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20
    set_benchmark("000300.XSHG")
    run_daily(handle_data_with_filter, time="every_bar")


def handle_data_with_filter(context, bar):
    """带情绪过滤的交易逻辑。"""
    # 获取历史数据
    hist = attribute_history(g.security, g.slow_period, "1d", ["close"])
    if hist.empty:
        return

    close = hist["close"]
    fast_ma = close.tail(g.fast_period).mean()
    slow_ma = close.tail(g.slow_period).mean()

    # 检查情绪分数（简化版：使用北向资金作为代理）
    north = get_north_money_flow()
    if not north.empty:
        recent_3d = north["net_buy"].tail(3).sum()
        sentiment_ok = recent_3d > -50  # 资金流出不超过 50 亿
    else:
        sentiment_ok = True  # 无数据时不过滤

    # 交易逻辑（仅在情绪良好时交易）
    position = context.portfolio.positions.get(g.security)

    if fast_ma > slow_ma and sentiment_ok:
        # 金叉 + 情绪良好 → 买入
        if not position or position.amount == 0:
            order_value(g.security, context.portfolio.available_cash * 0.8)
            log.info(f"BUY signal: fast_ma={fast_ma:.2f} > slow_ma={slow_ma:.2f}, sentiment_ok={sentiment_ok}")

    elif fast_ma < slow_ma or not sentiment_ok:
        # 死叉或情绪恶化 → 卖出
        if position and position.amount > 0:
            order_target(g.security, 0)
            log.info(f"SELL signal: fast_ma={fast_ma:.2f} < slow_ma={slow_ma:.2f} or sentiment_ok={sentiment_ok}")


def run_strategy_comparison():
    """对比有/无情绪过滤的回测表现。"""
    log.info("\n=== Strategy Comparison: With vs Without Sentiment Filter ===\n")

    # 简单均线策略（无过滤）
    def initialize_simple(context):
        g.security = "601390"
        g.fast_period = 5
        g.slow_period = 20
        set_benchmark("000300.XSHG")
        run_daily(handle_data_simple, time="every_bar")

    def handle_data_simple(context, bar):
        hist = attribute_history(g.security, g.slow_period, "1d", ["close"])
        if hist.empty:
            return
        close = hist["close"]
        fast_ma = close.tail(g.fast_period).mean()
        slow_ma = close.tail(g.slow_period).mean()

        position = context.portfolio.positions.get(g.security)

        if fast_ma > slow_ma:
            if not position or position.amount == 0:
                order_value(g.security, context.portfolio.available_cash * 0.8)
        elif fast_ma < slow_ma:
            if position and position.amount > 0:
                order_target(g.security, 0)

    # 运行回测
    log.info("Running simple MA strategy (no filter)...")
    result_simple = run_backtest(
        initialize_simple,
        start_date="2024-01-01",
        end_date="2024-06-30",
        starting_cash=100000,
        securities=["601390"],
    )

    log.info("Running MA strategy with sentiment filter...")
    result_filtered = run_backtest(
        initialize_with_filter,
        start_date="2024-01-01",
        end_date="2024-06-30",
        starting_cash=100000,
        securities=["601390"],
    )

    # 分析结果
    metrics_simple = analyze_returns(result_simple, risk_free_rate=0.03)
    metrics_filtered = analyze_returns(result_filtered, risk_free_rate=0.03)

    log.info("\n=== Performance Comparison ===")
    log.info(f"Simple MA Strategy:")
    log.info(f"  Total return: {metrics_simple['total_return']:.2%}")
    log.info(f"  Sharpe ratio: {metrics_simple['sharpe_ratio']:.2f}")
    log.info(f"  Max drawdown: {metrics_simple['max_drawdown']:.2%}")
    log.info(f"  Trade count: {metrics_simple['num_trades']}")

    log.info(f"\nMA + Sentiment Filter Strategy:")
    log.info(f"  Total return: {metrics_filtered['total_return']:.2%}")
    log.info(f"  Sharpe ratio: {metrics_filtered['sharpe_ratio']:.2f}")
    log.info(f"  Max drawdown: {metrics_filtered['max_drawdown']:.2%}")
    log.info(f"  Trade count: {metrics_filtered['num_trades']}")

    return metrics_simple, metrics_filtered


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    # Demo 1-4: 单独展示各情绪指标
    demo_north_flow()
    demo_margin_sentiment()
    demo_limit_stats()
    demo_restriction_warning()

    # Demo 5: 综合情绪分数
    score = calculate_sentiment_score()

    # 策略对比（可选，耗时较长）
    # run_strategy_comparison()