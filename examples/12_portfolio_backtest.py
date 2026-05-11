"""Example 12: Portfolio backtest with StrategyConfig.

Demonstrates the high-level portfolio backtest mode:
- Define a StrategyConfig with capital, stock universe, and position sizing
- Write a strategy function that picks stocks from the universe
- Run backtest and get a comprehensive report with per-stock breakdown
- Use report_suffix to distinguish versions
"""

import os
from eqlib import *


# ============================================================
# Strategy: momentum-based stock selection from universe
# ============================================================

def momentum_strategy(context):
    """
    A simple momentum strategy:
    1. For each stock in the universe, check if price > MA20 (uptrend)
    2. If in uptrend and no position → buy
    3. If in downtrend and holding → sell
    """
    for sec in context.universe:
        hist = attribute_history(sec, 25, "1d", ["close"])
        if hist.empty or len(hist) < 20:
            continue

        ma20 = hist["close"].tail(20).mean()
        current_price = hist["close"].iloc[-1]

        # Uptrend: buy if no position
        if current_price > ma20 * 1.005:
            if sec not in context.portfolio.positions or \
               context.portfolio.positions[sec].amount == 0:
                # Use config.position_pct or position_amount
                # Here we use order_value with a fraction of cash
                cash_per_stock = context.portfolio.available_cash
                if cash_per_stock > 1000:
                    order_value(sec, cash_per_stock)
                    log.info("BUY %s @ %.3f (price > MA20)" % (sec, current_price))

        # Downtrend: sell if holding
        elif current_price < ma20 * 0.995:
            if sec in context.portfolio.positions and \
               context.portfolio.positions[sec].amount > 0:
                order_target(sec, 0)
                log.info("SELL %s @ %.3f (price < MA20)" % (sec, current_price))


# ============================================================
# Run portfolio backtest
# ============================================================

if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)

    # Method 1: Using StrategyConfig (recommended)
    # This is the cleanest way to define a portfolio backtest

    config = StrategyConfig(
        starting_cash=200000,              # 20万初始资金
        securities=[
            "601390",  # 中国中铁
            "000630",  # 铜陵有色
            "518880",  # 黄金ETF
            "600036",  # 招商银行
            "000768",  # 中航光电
        ],
        benchmark="000300.XSHG",           # 沪深300 对比
        position_pct=0.33,                 # 每只股票最多用 33% 可用资金
        start_date="2024-01-01",
        end_date="2024-12-31",
        report_suffix="momentum_v2",        # 报告文件后缀，用于区分版本
    )

    result = run_portfolio_backtest(
        config,
        momentum_strategy,
        report_dir="reports",
    )

    # Method 2: Access the result for further analysis
    if result:
        from eqlib import analyze_returns

        metrics = analyze_returns(result)
        if metrics:
            print(f"\n{'='*50}")
            print("Risk Metrics:")
            print(f"  Sharpe:        {metrics['sharpe_ratio']:.3f}")
            print(f"  Max Drawdown:  {metrics['max_drawdown']*100:.2f}%")
            print(f"  Win Rate:      {metrics['win_rate']*100:.1f}%")
            print(f"  Alpha:         {metrics['alpha']*100:.2f}%")
            print(f"  Beta:          {metrics['beta']:.3f}")
