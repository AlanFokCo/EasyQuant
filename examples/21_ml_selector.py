"""
21 - ML-based Stock Selection
=============================

Demonstrates using MLSelector to replace hand-tuned factor weights with a
machine-learning model that learns from historical data. The selector trains
on past 5-day returns as labels and ranks the universe by predicted
performance each week.

Teaching Objectives:
    - MLSelector as a drop-in replacement for rule-based stock selection
    - Feature pipeline with technical indicators (RSI, MACD, ATR, etc.)
    - Weekly rebalance flow with ML-driven ranking
    - Honest target naming: ``past_return_5d`` (not ``forward_return_5d``)

Expected Output:
    - Weekly ML training logs
    - Selected top-N stocks for each rebalance
    - Final portfolio metrics via run_strategy report

Run:
    python examples/21_ml_selector.py
"""

from eqlib import (
    run_strategy, set_benchmark, set_order_cost,
    run_weekly, before_trading_start, order_target, order_value,
    MLSelector, log, g,
)
from examples._defaults import DEFAULT_ORDER_COST, START_DATE, END_DATE


UNIVERSE = [
    '601390', '600519', '000858', '002594', '601398',
    '000001', '600036', '600887', '601288', '600276',
]


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = UNIVERSE

    # ML Selector — learns from historical data to pick top stocks.
    # target='past_return_5d' uses historical 5-day returns as labels.
    # For true forward-return prediction, provide label_data (panel).
    g.selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility', 'volume_ratio'],
        target='past_return_5d',
        top_n=3,
    )

    before_trading_start(train_model)
    run_weekly(rebalance, day_of_week=0, time='every_bar')


def train_model(context, data=None):
    """Pre-market training hook — refreshes the ML model each trading day."""
    try:
        g.selector.train(context.universe, context)
    except Exception as exc:
        log.warning("Failed to train ML model: %s", exc)


def rebalance(context):
    selected = g.selector.rank(context.universe, context)
    log.info("ML selected: %s", selected)

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
