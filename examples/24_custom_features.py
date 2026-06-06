"""
Example 24: Custom features with MLSelector

Demonstrates how to add custom features to the feature pipeline.
Shows domain-specific features (e.g., A-share specific sentiment indicators).

Run with:
    python examples/24_custom_features.py
"""

import sys
sys.path.insert(0, '.')

from eqlib import (
    run_strategy, set_benchmark, set_order_cost, OrderCost,
    run_weekly, order_target, order_value,
    log, g,
)
from eqlib.ml import MLSelector, FeaturePipeline
from examples._defaults import DEFAULT_ORDER_COST


def price_to_ma_ratio(close, high, low, volume):
    """Custom feature: current price relative to 20-day MA."""
    if len(close) < 20:
        return float('nan')
    ma20 = close.iloc[-20:].mean()
    return float(close.iloc[-1] / ma20 - 1.0)


def volume_surge(close, high, low, volume):
    """Custom feature: is today's volume above 2x the 20-day average?"""
    if len(volume) < 20:
        return float('nan')
    today_vol = volume.iloc[-1]
    avg_vol = volume.iloc[-20:].mean()
    return float(today_vol / avg_vol)


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = ['601390', '600519', '000858', '002594', '601398']

    # Custom features mixed with built-in features
    custom_features = {
        'price_ma_ratio': price_to_ma_ratio,
        'volume_surge': volume_surge,
    }

    g.selector = MLSelector(
        model='random_forest',
        features=[
            'rsi', 'macd_hist', 'momentum', 'volatility',
            'price_ma_ratio', 'volume_surge',
        ],
        target='forward_return_5d',
        top_n=3,
    )
    # Inject custom features into the pipeline
    g.selector.pipeline = FeaturePipeline(
        features=['rsi', 'macd_hist', 'momentum', 'volatility',
                  'price_ma_ratio', 'volume_surge'],
        custom_features=custom_features,
    )

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def before_trading_start(context):
    try:
        g.selector.train(context.universe, context)
    except Exception as exc:
        log.warning("Failed to train: %s", exc)


def rebalance(context):
    selected = g.selector.rank(context.universe, context)
    log.info("ML selected (with custom features): %s", selected)

    for pos in list(context.portfolio.positions.keys()):
        if pos not in selected:
            order_target(pos, 0)

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
