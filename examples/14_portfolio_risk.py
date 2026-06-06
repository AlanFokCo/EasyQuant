"""
14 - Portfolio Risk Monitoring
==============================

Demonstrates comprehensive portfolio risk monitoring:
- PortfolioRiskMonitor: VaR, correlation, concentration
- RiskThresholds: customizable alert thresholds
- AlertLevel: yellow/red/kill-switch classification
- check_kill_switch(): immediate action recommendations
- daily_check(): comprehensive risk report

Teaching Objectives:
    - Setting up PortfolioRiskMonitor with multiple strategies
    - Interpreting portfolio VaR (Value at Risk)
    - Reading correlation matrices for diversification
    - Concentration risk: single stock and sector limits
    - Kill switch logic for risk management

Expected Output:
    - Two strategy backtests for risk comparison
    - Portfolio VaR with confidence interval
    - Correlation matrix heatmap description
    - Concentration risk analysis
    - Daily check report with alert level
    - Kill switch recommendations (if triggered)

Run:
    python examples/14_portfolio_risk.py
"""

import pandas as pd

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_daily, run_weekly, attribute_history,
    order_value, order_target,
    record, log, g, utils,
    PortfolioRiskMonitor, RiskThresholds, AlertLevel,
    check_kill_switch, analyze_returns,
)
from examples._defaults import (
    STOCKS, STOCKS_TRADE, INDEX_HS300,
    DEFAULT_ORDER_COST, INITIAL_CASH,
    START_DATE, END_DATE, verify_data_available,
)


# ============================================================
# Strategy A: Trend Following — MA 10/30 crossover on bank stock
# ============================================================

TREND_SECURITY = STOCKS["bank"]              # 601398 ICBC
TREND_SECURITY_TRADE = STOCKS_TRADE["bank"]  # 601398.XSHG
TREND_FAST = 10
TREND_SLOW = 30


def initialize_trend(context):
    """MA 10/30 golden-cross / death-cross trend follower."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = TREND_SECURITY
    g.security_trade = TREND_SECURITY_TRADE
    g.fast = TREND_FAST
    g.slow = TREND_SLOW

    context.universe = [g.security]
    run_daily(handle_trend, time="every_bar")
    log.info("Trend strategy init: %s  MA %d/%d" % (
        g.security, g.fast, g.slow))


def handle_trend(context):
    """Buy on golden cross, sell on death cross."""
    security = g.security
    security_trade = g.security_trade

    hist = attribute_history(security, g.slow + 5, "1d", ["close"])
    if hist is None or hist.empty or len(hist) < g.slow:
        return

    close = hist["close"]
    current_price = close.iloc[-1]

    fast_ma = close.rolling(g.fast).mean()
    slow_ma = close.rolling(g.slow).mean()

    if len(fast_ma.dropna()) < 2 or len(slow_ma.dropna()) < 2:
        return

    prev_fast, curr_fast = fast_ma.iloc[-2], fast_ma.iloc[-1]
    prev_slow, curr_slow = slow_ma.iloc[-2], slow_ma.iloc[-1]

    golden_cross = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    death_cross = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    if golden_cross and not has_position:
        cash = context.portfolio.available_cash
        if cash > current_price * 100:
            order_value(security_trade, cash * 0.95)
            log.info("Trend BUY %s @ %.2f (golden cross)" % (
                security_trade, current_price))

    elif death_cross and has_position:
        order_target(security_trade, 0)
        log.info("Trend SELL %s @ %.2f (death cross)" % (
            security_trade, current_price))

    record(
        total_value=context.portfolio.total_value,
        price=current_price,
        fast_ma=curr_fast,
        slow_ma=curr_slow,
    )


# ============================================================
# Strategy B: Mean Reversion — Bollinger Band on liquor stock
# ============================================================

MR_SECURITY = STOCKS["liquor"]              # 600519 Kweichow Moutai
MR_SECURITY_TRADE = STOCKS_TRADE["liquor"]  # 600519.XSHG
BOLL_PERIOD = 20
BOLL_STD = 2.0


def initialize_mean_revert(context):
    """Bollinger Band mean reversion — weekly rebalance."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.security = MR_SECURITY
    g.security_trade = MR_SECURITY_TRADE
    g.boll_period = BOLL_PERIOD
    g.boll_std = BOLL_STD

    context.universe = [g.security]
    # Weekly rebalance reduces noise and transaction costs for
    # mean-reversion signals on a slow-moving, high-price stock.
    run_weekly(handle_mean_revert, day_of_week=2, time="09:35")
    log.info("Mean-revert strategy init: %s  Boll(%d, %.1f) weekly" % (
        g.security, g.boll_period, g.boll_std))


def handle_mean_revert(context):
    """Buy below lower band, sell above upper band."""
    security = g.security
    security_trade = g.security_trade

    bars_needed = g.boll_period + 10
    hist = attribute_history(security, bars_needed, "1d", ["close"])
    if hist is None or hist.empty or len(hist) < g.boll_period:
        return

    close = hist["close"]
    current_price = close.iloc[-1]

    upper, mid, lower = utils.boll(close, period=g.boll_period, num_std=g.boll_std)

    has_position = (security_trade in context.portfolio.positions
                    and context.portfolio.positions[security_trade].amount > 0)

    # Sell: price exceeds upper band (overbought)
    if current_price > upper.iloc[-1] and has_position:
        order_target(security_trade, 0)
        log.info("MR SELL %s @ %.2f  (upper=%.2f)" % (
            security_trade, current_price, upper.iloc[-1]))

    # Buy: price below lower band (oversold)
    elif current_price < lower.iloc[-1] and not has_position:
        cash = context.portfolio.available_cash
        if cash > current_price * 100:
            order_value(security_trade, cash * 0.95)
            log.info("MR BUY %s @ %.2f  (lower=%.2f)" % (
                security_trade, current_price, lower.iloc[-1]))

    record(
        total_value=context.portfolio.total_value,
        price=current_price,
        upper=upper.iloc[-1],
        mid=mid.iloc[-1],
        lower=lower.iloc[-1],
    )


# ============================================================
# Section 1: Run both backtests and set up PortfolioRiskMonitor
# ============================================================

def run_both_strategies():
    """Run trend and mean-revert backtests, return results."""
    print("\n" + "=" * 60)
    print("Section 1: Run Strategy Backtests")
    print("=" * 60)

    # --- Strategy A: Trend following ---
    print("\n--- Strategy A: Trend Following (MA %d/%d on %s) ---" % (
        TREND_FAST, TREND_SLOW, TREND_SECURITY))
    actual_start, actual_end = verify_data_available(
        TREND_SECURITY, START_DATE, END_DATE)

    result_trend = run_backtest(
        initialize_func=initialize_trend,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[TREND_SECURITY],
        use_local=True,
    )
    if result_trend:
        m = analyze_returns(result_trend, risk_free_rate=0.03)
        if m:
            print("  Total return:  %+.2f%%" % (m["total_return"] * 100))
            print("  Sharpe ratio:  %.2f" % m["sharpe_ratio"])
            print("  Max drawdown:  %+.2f%%" % (m["max_drawdown"] * 100))
            print("  Trade count:   %d" % m.get("trade_count", 0))

    # --- Strategy B: Mean reversion ---
    print("\n--- Strategy B: Mean Reversion (Bollinger on %s) ---" % MR_SECURITY)
    actual_start_mr, actual_end_mr = verify_data_available(
        MR_SECURITY, START_DATE, END_DATE)

    result_mr = run_backtest(
        initialize_func=initialize_mean_revert,
        start_date=actual_start_mr,
        end_date=actual_end_mr,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=[MR_SECURITY],
        use_local=True,
    )
    if result_mr:
        m = analyze_returns(result_mr, risk_free_rate=0.03)
        if m:
            print("  Total return:  %+.2f%%" % (m["total_return"] * 100))
            print("  Sharpe ratio:  %.2f" % m["sharpe_ratio"])
            print("  Max drawdown:  %+.2f%%" % (m["max_drawdown"] * 100))
            print("  Trade count:   %d" % m.get("trade_count", 0))

    return result_trend, result_mr


def setup_monitor(result_trend, result_mr):
    """Create PortfolioRiskMonitor and register both strategies."""
    print("\n" + "=" * 60)
    print("Section 1b: Setup PortfolioRiskMonitor")
    print("=" * 60)

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

    if result_trend:
        monitor.add_strategy("Trend_MA", result_trend)
        print("  Added: Trend_MA")
    if result_mr:
        monitor.add_strategy("MeanRevert_Boll", result_mr)
        print("  Added: MeanRevert_Boll")

    print("  Registered strategies: %s" % list(monitor._strategy_results.keys()))
    return monitor


# ============================================================
# Section 2: Portfolio VaR
# ============================================================

def demo_portfolio_var(monitor):
    """Compute and display portfolio Value at Risk."""
    print("\n" + "=" * 60)
    print("Section 2: Portfolio VaR (Value at Risk)")
    print("=" * 60)

    var_amount, var_pct = monitor.portfolio_var(confidence=0.95)

    if pd.isna(var_amount) or var_amount <= 0:
        print("  VaR: insufficient data to compute (< 30 trading days)")
        return

    print("  Confidence level:  95%%")
    print("  VaR amount:        %12.2f CNY" % var_amount)
    print("  VaR percentage:    %12.2f%%" % (var_pct * 100))
    print("")
    print("  Interpretation:")
    print("    At 95%% confidence, the portfolio's maximum expected")
    print("    single-day loss is approximately %.0f CNY (%.2f%% of total value)." % (
        var_amount, var_pct * 100))
    print("    On 1 out of every 20 trading days, losses may exceed this amount.")


# ============================================================
# Section 3: Correlation Matrix
# ============================================================

def demo_correlation(monitor):
    """Display and interpret the strategy correlation matrix."""
    print("\n" + "=" * 60)
    print("Section 3: Strategy Correlation Matrix")
    print("=" * 60)

    corr = monitor.correlation_matrix()

    if corr.empty:
        print("  Correlation matrix: no data (need >= 2 strategies with >= 30 days)")
        return

    print("\n  Correlation DataFrame:")
    print(corr.to_string(float_format=lambda x: "%.4f" % x))

    # Find the maximum off-diagonal correlation
    max_corr = 0.0
    pair = ("N/A", "N/A")
    for i in range(len(corr)):
        for j in range(i + 1, len(corr)):
            val = abs(corr.iloc[i, j])
            if pd.isna(val):
                continue
            if val > max_corr:
                max_corr = val
                pair = (corr.index[i], corr.columns[j])

    print("\n  Maximum pairwise correlation: %.4f  (%s vs %s)" % (
        max_corr, pair[0], pair[1]))

    if max_corr > 0.7:
        print("  WARNING: High correlation (> 0.7) detected!")
        print("    Strategies move together — diversification benefit is limited.")
        print("    Consider adding a strategy from a different asset class.")
    elif max_corr > 0.4:
        print("  Moderate correlation (%.2f). Some diversification benefit." % max_corr)
    else:
        print("  Low correlation (%.2f). Good diversification across strategies." % max_corr)


# ============================================================
# Section 4: Concentration Risk
# ============================================================

def demo_concentration(monitor):
    """Display concentration risk metrics."""
    print("\n" + "=" * 60)
    print("Section 4: Concentration Risk")
    print("=" * 60)

    conc = monitor.concentration_risk()

    print("  Number of holdings:     %d" % conc["num_holdings"])
    print("  Max single stock:       %.2f%%" % (conc["max_single_stock"] * 100))
    print("  Max single sector:      %.2f%%" % (conc["max_single_sector"] * 100))
    print("  Top-3 concentration:    %.2f%%" % (conc["top3_concentration"] * 100))

    # Risk assessment
    if conc["max_single_stock"] > 0.15:
        print("\n  WARNING: Single-stock concentration exceeds 15%%.")
        print("    A large adverse move in one stock could significantly")
        print("    impact the entire portfolio.")
    elif conc["max_single_stock"] > 0.10:
        print("\n  NOTE: Single-stock concentration exceeds 10%%.")
        print("    Consider diversifying across more positions.")
    else:
        print("\n  Concentration is within acceptable limits.")

    if conc["num_holdings"] < 3:
        print("  NOTE: Fewer than 3 holdings — limited diversification.")


# ============================================================
# Section 5: Daily Check — comprehensive risk report
# ============================================================

def demo_daily_check(monitor):
    """Run daily_check() and display the full RiskReport."""
    print("\n" + "=" * 60)
    print("Section 5: Daily Risk Check (daily_check())")
    print("=" * 60)

    report = monitor.daily_check()

    print("  Timestamp:     %s" % report.timestamp)
    print("  Alert level:   %s" % report.alert_level.value)
    print("  Market regime: %s" % report.regime)

    # Triggers
    if report.triggers:
        print("\n  Triggers:")
        for t in report.triggers:
            print("    - %s" % t)
    else:
        print("\n  Triggers: (none)")

    # VaR summary
    if report.portfolio_var is not None:
        print("\n  Portfolio VaR:  %.2f CNY (%.2f%%)" % (
            report.portfolio_var,
            (report.portfolio_var_pct or 0) * 100))

    # Concentration summary
    if report.concentration:
        c = report.concentration
        print("  Holdings:       %d  (max single: %.1f%%)" % (
            c["num_holdings"], c["max_single_stock"] * 100))

    # Recommendations
    print("\n  Recommendations:")
    if report.recommendations:
        for i, rec in enumerate(report.recommendations, 1):
            print("    %d. %s" % (i, rec))
    else:
        print("    No specific recommendations — portfolio is within risk limits.")

    return report


# ============================================================
# Section 6: Kill Switch
# ============================================================

def demo_kill_switch(report):
    """Check kill switch and print action items."""
    print("\n" + "=" * 60)
    print("Section 6: Kill Switch Check")
    print("=" * 60)

    kill_actions = check_kill_switch(report)

    if kill_actions:
        print("  ALERT: Kill switch or red-level alert triggered!")
        print("  Immediate action items:")
        for action in kill_actions:
            print("    >> %s" % action)
    else:
        print("  No kill switch triggered. Strategy may continue running.")

    # Summary by alert level
    print("")
    if report.alert_level == AlertLevel.KILL_SWITCH:
        print("  STATUS: KILL-SWITCH level — pause all strategies immediately")
        print("          and wait for manual review before resuming.")
    elif report.alert_level == AlertLevel.RED:
        print("  STATUS: RED alert — human review required before next trade.")
    elif report.alert_level == AlertLevel.YELLOW:
        print("  STATUS: YELLOW advisory — monitor closely, no action required.")
    else:
        print("  STATUS: All clear — risk metrics within normal bounds.")

    return kill_actions


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("14 - Portfolio Risk Monitoring")
    print("=" * 60)

    # Section 1: Run backtests
    result_trend, result_mr = run_both_strategies()

    if result_trend is None and result_mr is None:
        print("\nBoth backtests failed. Cannot proceed with risk monitor demo.")
        raise SystemExit(1)

    # Section 1b: Setup monitor
    monitor = setup_monitor(result_trend, result_mr)

    # Section 2: Portfolio VaR
    demo_portfolio_var(monitor)

    # Section 3: Correlation matrix
    demo_correlation(monitor)

    # Section 4: Concentration risk
    demo_concentration(monitor)

    # Section 5: Daily check
    report = demo_daily_check(monitor)

    # Section 6: Kill switch
    demo_kill_switch(report)

    print("\n" + "=" * 60)
    print("Portfolio Risk Monitoring Demo Complete")
    print("=" * 60)
