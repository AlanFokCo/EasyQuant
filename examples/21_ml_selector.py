"""
Example 21: ML-based stock selection strategy

Demonstrates how to use MLSelector to replace hand-tuned factor weights
with a machine-learning model that learns from historical data.

Run with:
    python examples/21_ml_selector.py
"""

import sys
sys.path.insert(0, '.')

from eqlib import (
    run_strategy, set_benchmark, set_order_cost, OrderCost,
    run_weekly, before_trading_start, order_target, order_value,
    MLSelector, log, g,
)
from examples._defaults import DEFAULT_ORDER_COST


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                              open_commission=0.0003, close_commission=0.0003))

    # Stock universe
    context.universe = ['601390', '600519', '000858', '002594', '601398',
                        '000001', '600036', '600887', '601288', '600276']

    # ML Selector - learns from historical data to pick top stocks
    # This replaces manual weight tuning with a learned model
    g.selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility', 'volume_ratio'],
        target='forward_return_5d',
        top_n=3,
    )

    # Weekly rebalance
    run_weekly(rebalance, day_of_week=0, time='every_bar')


def before_trading_start(context):
    # Train model on available historical data before each rebalance
    try:
        g.selector.train(context.universe, context)
    except Exception as exc:
        log.warning("Failed to train ML model: %s", exc)


def rebalance(context):
    # Get top stocks from ML model
    selected = g.selector.rank(context.universe, context)
    log.info("ML selected: %s", selected)

    # Sell positions not in selected list
    for pos in list(context.portfolio.positions.keys()):
        if pos not in selected:
            order_target(pos, 0)

    # Buy selected stocks with equal weight
    if selected:
        cash_per_stock = context.portfolio.available_cash / len(selected)
        for stock in selected:
            order_value(stock, cash_per_stock)


if __name__ == "__main__":
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-01-01',
        securities=['601390', '600519', '000858', '002594', '601398',
                    '000001', '600036', '600887', '601288', '600276'],
        report_dir='reports',
    )
