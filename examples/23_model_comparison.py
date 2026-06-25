"""
23 - Model Comparison: Random Forest vs Logistic Regression
===========================================================

Demonstrates how to compare different ML models within the same strategy.
Both models use the same feature set and target (past 5-day returns), so
differences in selection come entirely from the model architecture.

Teaching Objectives:
    - Running multiple MLSelectors in parallel
    - Comparing RandomForest vs LogisticRegression on identical features
    - Switching the active selector at runtime via ``g.active_selector``
    - Feature importance and prediction differences surface in logs

Expected Output:
    - Weekly training logs for both models
    - Selection lists from the active model
    - Final portfolio metrics via run_strategy report

Run:
    python examples/23_model_comparison.py
"""

from eqlib import (
    run_strategy, set_benchmark, set_order_cost,
    run_weekly, before_trading_start, order_target, order_value,
    log, g,
)
from eqlib.ml import MLSelector
from examples._defaults import DEFAULT_ORDER_COST, START_DATE, END_DATE


UNIVERSE = ['601390', '600519', '000858', '002594', '601398']

FEATURES = ['rsi', 'macd_hist', 'atr', 'momentum', 'volatility']


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = UNIVERSE

    g.rf_selector = MLSelector(
        model='random_forest',
        features=FEATURES,
        target='past_return_5d',
        top_n=3,
    )
    g.lr_selector = MLSelector(
        model='logistic_regression',
        features=FEATURES,
        target='past_return_5d',
        top_n=3,
    )

    g.active_selector = 'rf'  # Toggle to 'lr' to switch models

    before_trading_start(train_models)
    run_weekly(rebalance, day_of_week=0, time='every_bar')


def train_models(context, data=None):
    """Pre-market training hook — trains both models each trading day."""
    try:
        g.rf_selector.train(context.universe, context)
        g.lr_selector.train(context.universe, context)
    except Exception as exc:
        log.warning("Failed to train models: %s", exc)


def rebalance(context):
    if g.active_selector == 'rf':
        selected = g.rf_selector.rank(context.universe, context)
        model_name = "Random Forest"
    else:
        selected = g.lr_selector.rank(context.universe, context)
        model_name = "Logistic Regression"

    log.info("[%s] Selected: %s", model_name, selected)

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
