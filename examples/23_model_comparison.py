"""
Example 23: Model comparison — Random Forest vs Logistic Regression

Demonstrates how to compare different ML models within the same strategy.
Shows feature importance and prediction differences.

Run with:
    python examples/23_model_comparison.py
"""

import sys
sys.path.insert(0, '.')

from eqlib import (
    run_strategy, set_benchmark, set_order_cost, OrderCost,
    run_weekly, order_target, order_value,
    log, g,
)
from eqlib.ml import MLSelector
from examples._defaults import DEFAULT_ORDER_COST


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = ['601390', '600519', '000858', '002594', '601398']

    # Two different models for comparison
    g.rf_selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility'],
        target='forward_return_5d',
        top_n=3,
    )
    g.lr_selector = MLSelector(
        model='logistic_regression',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility'],
        target='forward_return_5d',
        top_n=3,
    )

    g.active_selector = 'rf'  # Use Random Forest as default

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def before_trading_start(context):
    try:
        g.rf_selector.train(context.universe, context)
        g.lr_selector.train(context.universe, context)
    except Exception as exc:
        log.warning("Failed to train models: %s", exc)


def rebalance(context):
    # Select the active model
    if g.active_selector == 'rf':
        selected = g.rf_selector.rank(context.universe, context)
        model_name = "Random Forest"
    else:
        selected = g.lr_selector.rank(context.universe, context)
        model_name = "Logistic Regression"

    log.info("[%s] Selected: %s", model_name, selected)

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
        securities=['601390', '600519', '000858', '002594', '601398'],
        report_dir='reports',
    )
