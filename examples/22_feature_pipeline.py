"""
22 - Feature Pipeline Standalone Usage
======================================

Demonstrates how to use FeaturePipeline independently to compute technical
indicator features for a list of stocks, without involving MLSelector.
This is useful for factor research and custom signal construction.

Teaching Objectives:
    - FeaturePipeline as a standalone feature engineer
    - Computing RSI, MACD histogram, ATR, momentum, volatility per stock
    - Building a simple rule-based strategy from raw feature values
    - Combining features with conditional logic (RSI < 30 AND momentum > 0)

Expected Output:
    - Weekly feature computation logs
    - Buy/sell signals driven by feature thresholds
    - Final portfolio value summary

Run:
    python examples/22_feature_pipeline.py
"""

import pandas as pd

from eqlib import (
    run_backtest, set_benchmark, set_order_cost,
    run_weekly, attribute_history, order_target, order_value,
    log, g,
)
from eqlib.ml import FeaturePipeline
from examples._defaults import DEFAULT_ORDER_COST, START_DATE, END_DATE


UNIVERSE = ['601390', '600519', '000858', '002594', '601398']


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = UNIVERSE

    g.pipeline = FeaturePipeline(
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility']
    )

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def rebalance(context):
    features = g.pipeline.compute(context.universe, context, lookback=60)
    log.info("Features computed for %d stocks", len(features))

    if features.empty:
        log.warning("No features computed, skipping rebalance")
        return

    # Simple rule: buy stocks with RSI < 30 (oversold) and positive momentum
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
    result = run_backtest(
        initialize,
        start_date=START_DATE,
        end_date=END_DATE,
        securities=UNIVERSE,
    )
    print(f"Final value: {result['context'].portfolio.total_value:,.2f}")
