"""
24 - Custom Features with MLSelector
====================================

Demonstrates how to extend FeaturePipeline with domain-specific custom
features. Two A-share-relevant custom features are defined:
    - ``price_ma_ratio``: current price vs 20-day moving average
    - ``volume_surge``: today's volume / 20-day average volume

These are mixed with built-in features (RSI, MACD, momentum, volatility)
and fed into MLSelector for ML-driven ranking.

Teaching Objectives:
    - Writing custom feature functions with the (close, high, low, volume) signature
    - Injecting custom features into FeaturePipeline via ``custom_features``
    - Combining built-in and custom features in MLSelector
    - Replacing the default pipeline on a selector instance

Expected Output:
    - Weekly training logs (model learns from 6 features)
    - Selection lists reflecting both technical and volume/MA signals
    - Final portfolio metrics via run_strategy report

Run:
    python examples/24_custom_features.py
"""

from eqlib import (
    run_strategy, set_benchmark, set_order_cost,
    run_weekly, before_trading_start, order_target, order_value,
    log, g,
)
from eqlib.ml import MLSelector
from examples._defaults import DEFAULT_ORDER_COST, START_DATE, END_DATE


UNIVERSE = ['601390', '600519', '000858', '002594', '601398']


def price_to_ma_ratio(close, high, low, volume):
    """Custom feature: current price relative to 20-day moving average."""
    if len(close) < 20:
        return float('nan')
    ma20 = close.iloc[-20:].mean()
    return float(close.iloc[-1] / ma20 - 1.0)


def volume_surge(close, high, low, volume):
    """Custom feature: today's volume divided by 20-day average volume."""
    if len(volume) < 20:
        return float('nan')
    today_vol = volume.iloc[-1]
    avg_vol = volume.iloc[-20:].mean()
    return float(today_vol / avg_vol)


CUSTOM_FEATURES = {
    'price_ma_ratio': price_to_ma_ratio,
    'volume_surge': volume_surge,
}

ALL_FEATURES = [
    'rsi', 'macd_hist', 'momentum', 'volatility',
    'price_ma_ratio', 'volume_surge',
]


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = UNIVERSE

    g.selector = MLSelector(
        model='random_forest',
        features=ALL_FEATURES,
        target='past_return_5d',
        top_n=3,
        custom_features=CUSTOM_FEATURES,
    )

    before_trading_start(train_model)
    run_weekly(rebalance, day_of_week=0, time='every_bar')


def train_model(context, data=None):
    """Pre-market training hook — refreshes the ML model each trading day."""
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
        start_date=START_DATE,
        end_date=END_DATE,
        securities=UNIVERSE,
        report_dir='reports',
    )
