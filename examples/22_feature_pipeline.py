"""
Example 22: Feature Pipeline standalone usage

Demonstrates how to use FeaturePipeline independently to compute
technical indicator features for a list of stocks.

Run with:
    python examples/22_feature_pipeline.py
"""

import sys
sys.path.insert(0, '.')

from eqlib import (
    run_backtest, set_benchmark, set_order_cost, OrderCost,
    run_weekly, attribute_history, order_target, order_value,
    log, g,
)
from eqlib.ml import FeaturePipeline
from examples._defaults import DEFAULT_ORDER_COST


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = ['601390', '600519', '000858', '002594', '601398']

    # Create a feature pipeline with selected features
    g.pipeline = FeaturePipeline(
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility']
    )

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def rebalance(context):
    # Compute features for all stocks in universe
    features = g.pipeline.compute(context.universe, context, lookback=60)
    log.info("Features computed for %d stocks", len(features))

    if features.empty:
        log.warning("No features computed, skipping rebalance")
        return

    # Simple rule: buy stocks with RSI < 30 and positive momentum
    for stock in context.universe:
        if stock not in features.index:
            continue
        rsi = features.loc[stock, 'rsi']
        momentum = features.loc[stock, 'momentum']

        if pd.isna(rsi) or pd.isna(momentum):
            continue

        if rsi < 30 and momentum > 0:
            order_value(stock, context.portfolio.available_cash * 0.2)
        elif rsi > 70:
            order_target(stock, 0)


if __name__ == "__main__":
    import pandas as pd  # noqa: used in rebalance
    result = run_backtest(
        initialize,
        start_date='2022-01-01',
        end_date='2024-01-01',
        securities=['601390', '600519', '000858', '002594', '601398'],
    )
    print(f"Final value: {result['context'].portfolio.total_value:,.2f}")
