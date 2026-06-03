"""Example 26: Portfolio Risk Monitor.

Demonstrates the complete usage of PortfolioRiskMonitor for multi-strategy
risk monitoring including VaR, correlation analysis, concentration risk,
daily risk checks with kill switch, market sentiment context, and optional
correlation heatmap visualization.

Parts:
1. Run two different strategy backtests (trend following, mean reversion)
2. Create PortfolioRiskMonitor — portfolio_var(), correlation_matrix(),
   concentration_risk()
3. Daily risk check — daily_check() generates RiskReport,
   check_kill_switch() for kill switch logic
4. Output risk recommendations
5. Market sentiment context (north-bound flow, limit up/down stats)
6. Optional correlation heatmap visualization (requires matplotlib)

Usage:
    python examples/26_portfolio_risk_monitor.py
"""

import datetime
from eqlib import (
    run_backtest,
    analyze_returns,
    order_value,
    order_target,
    g,
    run_daily,
    set_benchmark,
    attribute_history,
    set_order_cost,
    OrderCost,
    log,
    record,
    PortfolioRiskMonitor,
    RiskThresholds,
    RiskReport,
    AlertLevel,
    check_kill_switch,
    get_north_money_flow,
    get_limit_up_down_stats,
)


# ============================================================
# Part 1: Strategy Definitions
# ============================================================

def initialize_trend_following(context):
    """趋势跟踪策略：基于均线金叉/死叉信号交易。

    Strategy A: Trend following with MA golden/death cross.
    """
    g.stock = "601390"  # 中国中铁
    g.fast_period = 5
    g.slow_period = 20
    g.position_pct = 0.95

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.stock]
    run_daily(handle_trend_following, time="every_bar")
    log.info("Trend Following Strategy initialized: %s" % g.stock)


def handle_trend_following(context):
    """趋势跟踪策略的交易逻辑。"""
    stock = g.stock
    hist = attribute_history(stock, g.slow_period + 1, "1d", ["close"])

    if hist.empty or len(hist) < g.slow_period:
        return

    close = hist["close"]
    fast_ma = close.tail(g.fast_period).mean()
    slow_ma = close.tail(g.slow_period).mean()

    # Previous MA values for cross detection
    prev_fast = close.tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close.tail(g.slow_period + 1).head(g.slow_period).mean()

    position = context.portfolio.positions.get(stock)
    current_price = close.iloc[-1]

    # Golden cross: buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if not position or position.amount == 0:
            cash_to_use = context.portfolio.available_cash * g.position_pct
            if cash_to_use > 1000:
                order_value(stock, cash_to_use)
                log.info("Trend BUY %s @ %.3f (Golden cross)" % (stock, current_price))

    # Death cross: sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if position and position.amount > 0:
            order_target(stock, 0)
            log.info("Trend SELL %s @ %.3f (Death cross)" % (stock, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma)


def initialize_mean_reversion(context):
    """均值回归策略：基于RSI超买/超卖信号交易。

    Strategy B: Mean reversion with RSI oversold/overbought.
    """
    g.stock = "600036"  # 招商银行
    g.rsi_period = 14
    g.oversold_threshold = 30
    g.overbought_threshold = 70
    g.position_pct = 0.95

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.stock]
    run_daily(handle_mean_reversion, time="every_bar")
    log.info("Mean Reversion Strategy initialized: %s" % g.stock)


def handle_mean_reversion(context):
    """均值回归策略的交易逻辑。"""
    stock = g.stock
    hist = attribute_history(stock, g.rsi_period + 1, "1d", ["close"])

    if hist.empty or len(hist) < g.rsi_period + 1:
        return

    close = hist["close"]

    # Calculate RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).tail(g.rsi_period)
    loss = (-delta.where(delta < 0, 0)).tail(g.rsi_period)

    avg_gain = gain.mean()
    avg_loss = loss.mean()

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    position = context.portfolio.positions.get(stock)
    current_price = close.iloc[-1]

    # Oversold: buy
    if rsi < g.oversold_threshold:
        if not position or position.amount == 0:
            cash_to_use = context.portfolio.available_cash * g.position_pct
            if cash_to_use > 1000:
                order_value(stock, cash_to_use)
                log.info("MR BUY %s @ %.3f (RSI=%.1f oversold)" % (stock, current_price, rsi))

    # Overbought: sell
    elif rsi > g.overbought_threshold:
        if position and position.amount > 0:
            order_target(stock, 0)
            log.info("MR SELL %s @ %.3f (RSI=%.1f overbought)" % (stock, current_price, rsi))

    record(price=current_price, rsi=rsi)


# ============================================================
# Part 2: PortfolioRiskMonitor Demo
# ============================================================

def run_strategies():
    """运行两个策略的回测，返回结果。"""
    log.info("=" * 60)
    log.info("Part 1: Running Strategy Backtests")
    log.info("=" * 60)

    # Strategy A: Trend following
    log.info("\nRunning Trend Following Strategy...")
    result_trend = run_backtest(
        initialize_trend_following,
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=["601390"],
        use_local=True,
    )

    if result_trend:
        metrics_trend = analyze_returns(result_trend, risk_free_rate=0.03)
        log.info(f"  Total return: {metrics_trend['total_return']:+.2%}")
        log.info(f"  Sharpe ratio: {metrics_trend['sharpe_ratio']:.2f}")
        log.info(f"  Max drawdown: {metrics_trend['max_drawdown']:+.2%}")
        log.info(f"  Trade count: {metrics_trend['num_trades']}")

    # Strategy B: Mean reversion
    log.info("\nRunning Mean Reversion Strategy...")
    result_mr = run_backtest(
        initialize_mean_reversion,
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        starting_cash=100000,
        benchmark="000300.XSHG",
        securities=["600036"],
        use_local=True,
    )

    if result_mr:
        metrics_mr = analyze_returns(result_mr, risk_free_rate=0.03)
        log.info(f"  Total return: {metrics_mr['total_return']:+.2%}")
        log.info(f"  Sharpe ratio: {metrics_mr['sharpe_ratio']:.2f}")
        log.info(f"  Max drawdown: {metrics_mr['max_drawdown']:+.2%}")
        log.info(f"  Trade count: {metrics_mr['num_trades']}")

    return result_trend, result_mr


def demo_portfolio_risk_monitor(result_trend, result_mr):
    """展示 PortfolioRiskMonitor 的完整用法。"""
    log.info("\n" + "=" * 60)
    log.info("Part 2: PortfolioRiskMonitor Demo")
    log.info("=" * 60)

    # 1) 创建风控监测器（可自定义阈值）
    custom_thresholds = RiskThresholds(
        max_drawdown_yellow=0.12,
        max_drawdown_red=0.18,
        max_drawdown_kill=0.25,
        correlation_yellow=0.50,
        correlation_red=0.70,
        correlation_kill=0.85,
        single_stock_max=0.15,
        single_sector_max=0.35,
        var_confidence=0.95,
    )
    monitor = PortfolioRiskMonitor(thresholds=custom_thresholds)

    # 2) 注册策略回测结果
    log.info("\nAdding strategies to monitor...")
    monitor.add_strategy("Trend Following", result_trend)
    monitor.add_strategy("Mean Reversion", result_mr)
    log.info(f"  Registered: {list(monitor._strategy_results.keys())}")

    # 3) 计算组合 VaR
    log.info("\n--- Portfolio VaR ---")
    var_amount, var_pct = monitor.portfolio_var()
    if var_amount > 0:
        log.info(f"  VaR (95% confidence): {var_amount:,.2f} 元")
        log.info(f"  VaR percentage: {var_pct:.2%}")
        log.info(f"  Interpretation: 在 95% 置信度下，组合单日最大预期损失约为 {var_amount:,.0f} 元")
    else:
        log.info("  VaR: 数据不足，无法计算")

    # 4) 计算策略相关性矩阵
    log.info("\n--- Strategy Correlation Matrix ---")
    corr_matrix = monitor.correlation_matrix()
    if not corr_matrix.empty:
        log.info(corr_matrix.to_string())

        # 分析相关性风险
        max_corr = 0.0
        pair = ("N/A", "N/A")
        found_valid = False
        for i in range(len(corr_matrix)):
            for j in range(i + 1, len(corr_matrix)):
                corr_val = abs(corr_matrix.iloc[i, j])
                if pd.isna(corr_val):
                    continue
                found_valid = True
                if corr_val > max_corr:
                    max_corr = corr_val
                    pair = (corr_matrix.index[i], corr_matrix.columns[j])

        if not found_valid:
            log.info("\n  ⚠️ 无有效相关性数据，无法评估策略分散度")
        else:
            log.info(f"\n  Maximum correlation: {max_corr:.2f} ({pair[0]} vs {pair[1]})")
            if max_corr >= custom_thresholds.correlation_kill:
                log.info("  ⚠️ 熔断级风险：策略相关性过高!")
            elif max_corr >= custom_thresholds.correlation_red:
                log.info("  ⚠️ 红色预警：策略相关性较高")
            elif max_corr >= custom_thresholds.correlation_yellow:
                log.info("  ⚡ 黄色预警：策略相关性值得关注")
            else:
                log.info("  ✅ 策略相关性正常，分散度良好")
    else:
        log.info("  Correlation matrix: 无数据（需至少2个策略）")

    # 5) 计算集中度风险
    log.info("\n--- Concentration Risk ---")
    concentration = monitor.concentration_risk()
    log.info(f"  Number of holdings: {concentration['num_holdings']}")
    log.info(f"  Max single stock: {concentration['max_single_stock']:.2%}")
    log.info(f"  Max single sector: {concentration['max_single_sector']:.2%}")
    log.info(f"  Top 3 concentration: {concentration['top3_concentration']:.2%}")

    # 集中度风险评估
    if concentration['max_single_stock'] > custom_thresholds.single_stock_max:
        log.info(f"  ⚠️ 单股票持仓占比超过阈值 ({custom_thresholds.single_stock_max:.2%})")
    else:
        log.info("  ✅ 单股票持仓占比正常")

    return monitor


# ============================================================
# Part 3: Daily Risk Check Demo
# ============================================================

def demo_daily_check(monitor):
    """展示每日风控检查和熔断逻辑。"""
    log.info("\n" + "=" * 60)
    log.info("Part 3: Daily Risk Check")
    log.info("=" * 60)

    # 1) 执行综合风控检查
    log.info("\nRunning daily_check()...")
    report = monitor.daily_check()

    # 2) 展示 RiskReport 内容
    log.info("\n--- Risk Report ---")
    log.info(f"  Timestamp: {report.timestamp}")
    log.info(f"  Alert Level: {report.alert_level.value}")
    log.info(f"  Triggers: {report.triggers}")
    log.info(f"  Regime: {report.regime}")

    if report.portfolio_var:
        log.info(f"  Portfolio VaR: {report.portfolio_var:,.2f} 元 ({report.portfolio_var_pct:.2%})")

    if report.concentration:
        log.info(f"  Holdings: {report.concentration['num_holdings']}")

    # 3) 展示风控建议
    log.info("\n--- Recommendations ---")
    if report.recommendations:
        for i, rec in enumerate(report.recommendations, 1):
            log.info(f"  {i}. {rec}")
    else:
        log.info("  No specific recommendations at this time.")

    # 4) 熔断检查
    log.info("\n--- Kill Switch Check ---")
    kill_actions = check_kill_switch(report)

    if kill_actions:
        log.info("  ⚠️ 熔断/红色预警触发! 需要执行以下操作:")
        for action in kill_actions:
            log.info(f"    {action}")
    else:
        log.info("  ✅ 无熔断触发，策略可正常运行")

    # 5) 根据预警级别输出总结
    log.info("\n--- Summary ---")
    if report.alert_level == AlertLevel.KILL_SWITCH:
        log.info("  🔴 熔断级别风险! 立即暂停策略并人工确认!")
    elif report.alert_level == AlertLevel.RED:
        log.info("  🟠 红色预警! 需要人工介入检查!")
    elif report.alert_level == AlertLevel.YELLOW:
        log.info("  🟡 黄色预警! 请关注相关指标变化.")
    else:
        log.info("  ✅ 风控状态正常.")

    return report, kill_actions


# ============================================================
# Part 4: Risk Recommendations Output
# ============================================================

def output_risk_recommendations(report, kill_actions):
    """输出综合风控建议。"""
    log.info("\n" + "=" * 60)
    log.info("Part 4: Risk Recommendations")
    log.info("=" * 60)

    # 综合建议
    log.info("\n根据风控检查结果，以下是具体建议:")

    recommendations = []

    # VaR 建议
    if report.portfolio_var_pct and report.portfolio_var_pct > 0.05:
        recommendations.append("VaR 建议: 组合单日潜在损失较高，建议降低整体仓位或增加对冲")

    # 相关性建议
    if report.correlation_matrix is not None and not report.correlation_matrix.empty:
        max_corr = 0.0
        for i in range(len(report.correlation_matrix)):
            for j in range(i + 1, len(report.correlation_matrix)):
                corr_val = abs(report.correlation_matrix.iloc[i, j])
                if corr_val > max_corr:
                    max_corr = corr_val

        if max_corr > 0.6:
            recommendations.append(f"相关性建议: 策略相关性({max_corr:.2f})较高，建议增加策略分散度")
        elif max_corr < 0.3:
            recommendations.append(f"相关性建议: 策略相关性({max_corr:.2f})较低，分散度良好")

    # 集中度建议
    if report.concentration:
        if report.concentration['max_single_stock'] > 0.1:
            recommendations.append(f"集中度建议: 单股票持仓({report.concentration['max_single_stock']:.2%})偏高，建议分散持仓")
        if report.concentration['num_holdings'] < 3:
            recommendations.append("集中度建议: 持仓数量较少，建议增加标的分散风险")

    # Regime 建议
    if report.regime == "bear":
        recommendations.append("市场环境建议: 当前为熊市 regime，建议降低仓位或增加防御性资产")
    elif report.regime == "oscillation":
        recommendations.append("市场环境建议: 当前为震荡市 regime，建议使用均值回归类策略")

    # 熔断建议
    if kill_actions:
        recommendations.append("紧急建议: 熔断触发，请立即执行上述熔断操作!")

    # 输出建议
    if recommendations:
        log.info("")
        for i, rec in enumerate(recommendations, 1):
            log.info(f"  {i}. {rec}")
    else:
        log.info("  当前无特殊风控建议，策略组合运行正常.")

    # 最佳实践建议
    log.info("\n--- Best Practices Reminder ---")
    log.info("  1. 每日开盘前运行 daily_check() 检查风控状态")
    log.info("  2. 设置合理的 RiskThresholds，避免过于宽松或严格")
    log.info("  3. 定期回顾 correlation_matrix，确保策略分散度")
    log.info("  4. 关注 concentration_risk，避免单一标的风险集中")
    log.info("  5. 熔断触发后必须人工确认，不可自动恢复")


# ============================================================
# Part 5: Market Sentiment Context
# ============================================================

def demo_market_context():
    """拉取北向资金和涨跌停数据，为风控报告补充市场情绪背景。"""
    log.info("\n" + "=" * 60)
    log.info("Part 5: Market Sentiment Context")
    log.info("=" * 60)

    # North-bound capital flow (北向资金)
    log.info("\n--- North-bound Capital Flow ---")
    try:
        north = get_north_money_flow()
        if not north.empty:
            recent_5d = north["net_buy"].tail(5).sum()
            recent_20d = north["net_buy"].tail(20).sum()
            log.info(f"  Net buy (5d) : {recent_5d:+.2f} 亿元")
            log.info(f"  Net buy (20d): {recent_20d:+.2f} 亿元")
            if recent_5d > 50:
                log.info("  Signal: 北向资金强势流入 (Strong inflow)")
            elif recent_5d < -50:
                log.info("  Signal: 北向资金强势流出 (Strong outflow)")
            else:
                log.info("  Signal: 北向资金流向平稳 (Stable)")
        else:
            log.info("  North-bound flow data unavailable.")
    except Exception as e:
        log.info(f"  Error fetching north-bound flow: {e}")

    # Limit up/down statistics (涨跌停统计)
    log.info("\n--- Limit Up/Down Statistics ---")
    try:
        limit_stats = get_limit_up_down_stats()
        if not limit_stats.empty:
            latest = limit_stats.iloc[-1]
            up_count = latest.get("limit_up_count", "N/A")
            down_count = latest.get("limit_down_count", "N/A")
            log.info(f"  Latest limit-up count  : {up_count}")
            log.info(f"  Latest limit-down count: {down_count}")

            # Systemic risk check
            if isinstance(down_count, (int, float)) and down_count > 100:
                log.info("  ⚠️ 系统性风险预警：跌停数 > 100")
            elif isinstance(down_count, (int, float)) and down_count > 50:
                log.info("  ⚠️ 市场情绪偏弱：跌停数 > 50")
            else:
                log.info("  ✅ 市场情绪正常")
        else:
            log.info("  Limit up/down data unavailable.")
    except Exception as e:
        log.info(f"  Error fetching limit stats: {e}")


# ============================================================
# Part 6: Risk Visualization (optional, requires matplotlib)
# ============================================================

def demo_visualization(monitor):
    """用 matplotlib 热力图可视化策略相关性矩阵。

    This is optional — call it manually if matplotlib is installed.
    Produces a PNG file in the current directory.
    """
    log.info("\n" + "=" * 60)
    log.info("Part 6: Correlation Heatmap (optional)")
    log.info("=" * 60)

    corr = monitor.correlation_matrix()
    if corr.empty:
        log.info("  No correlation data to visualize.")
        return

    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-1, vmax=1)

        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.index)))
        ax.set_xticklabels(corr.columns, rotation=30, ha="right")
        ax.set_yticklabels(corr.index)

        # Annotate each cell with the correlation value
        for i in range(len(corr)):
            for j in range(len(corr)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}",
                        ha="center", va="center", fontsize=10)

        fig.colorbar(im, ax=ax, label="Pearson correlation")
        ax.set_title("Strategy Correlation Matrix")
        fig.tight_layout()

        out_path = "portfolio_correlation.png"
        fig.savefig(out_path, dpi=120)
        log.info(f"  Heatmap saved to: {out_path}")
        plt.close(fig)

    except ImportError:
        log.info("  matplotlib not installed — skipping heatmap.")
        log.info("  Install it with:  pip install matplotlib")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("Example 26: Portfolio Risk Monitor Demo")
    log.info("=" * 60)

    # Part 1: Run strategy backtests
    result_trend, result_mr = run_strategies()

    if result_trend is None or result_mr is None:
        log.info("Backtest failed. Cannot proceed with risk monitor demo.")
        exit(1)

    # Part 2: Create PortfolioRiskMonitor and analyze
    monitor = demo_portfolio_risk_monitor(result_trend, result_mr)

    # Part 3: Daily risk check and kill switch
    report, kill_actions = demo_daily_check(monitor)

    # Part 4: Output risk recommendations
    output_risk_recommendations(report, kill_actions)

    # Part 5: Market sentiment context
    demo_market_context()

    # Part 6: Correlation heatmap (optional — uncomment to enable)
    # demo_visualization(monitor)

    log.info("\n" + "=" * 60)
    log.info("Demo Complete!")
    log.info("=" * 60)