"""
11 - Portfolio Backtest
=======================

Demonstrates the high-level portfolio backtest API:
- StrategyConfig: declarative backtest configuration
- run_portfolio_backtest(): multi-stock backtest with auto-reports
- PortfolioRiskMonitor: basic concentration risk analysis

Teaching Objectives:
    - StrategyConfig for declarative multi-stock setup
    - run_portfolio_backtest vs run_backtest (auto-reports + rebalance)
    - Correct position sizing (N stocks x position_pct <= 1.0)
    - PortfolioRiskMonitor for concentration risk

Expected Output:
    - Multi-stock backtest with auto-generated reports
    - Concentration risk analysis (max single stock, sector)

Run:
    python examples/11_portfolio_backtest.py
"""

import os

from eqlib import (
    run_portfolio_backtest,
    StrategyConfig,
    PortfolioRiskMonitor,
    set_order_cost,
    attribute_history,
    order_value,
    order_target,
    record,
    log,
    g,
)
from examples._defaults import (
    STOCKS,
    STOCKS_TRADE,
    INDEX_HS300,
    DEFAULT_ORDER_COST,
    INITIAL_CASH,
    START_DATE,
    END_DATE,
    verify_data_available,
    print_evaluation,
)


# ============================================================
# Strategy parameters
# ============================================================

# Select 5 stocks from the shared STOCKS dict (bare codes for universe)
UNIVERSE_KEYS = ["bank", "insurance", "liquor", "ev", "tech"]
UNIVERSE_CODES = [STOCKS[k] for k in UNIVERSE_KEYS]

# Position sizing: 5 stocks x 18% = 90% max total allocation.
# This leaves a 10% cash buffer for commissions and slippage.
POSITION_PCT = 0.18

# Momentum parameters
MOMENTUM_LOOKBACK = 20   # 20-day return window
TOP_N = 3                # Buy top-3 stocks by momentum


# ============================================================
# Strategy: multi-stock momentum rotation
# ============================================================

def momentum_strategy(context):
    """Multi-stock momentum: buy top-3 by 20-day return.

    Called once per bar (or per rebalance period) by
    run_portfolio_backtest.  ``context.universe`` is set
    automatically from StrategyConfig.securities.
    """
    # Score each stock in the universe by 20-day momentum
    scores = {}
    for sec in context.universe:
        hist = attribute_history(sec, MOMENTUM_LOOKBACK + 5, "1d", ["close"])
        if hist is None or hist.empty or len(hist) < MOMENTUM_LOOKBACK:
            continue
        ret = (hist["close"].iloc[-1] / hist["close"].iloc[-MOMENTUM_LOOKBACK]) - 1
        scores[sec] = ret

    if not scores:
        return

    # Rank by momentum descending, pick top N
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    picks = [s[0] for s in sorted_stocks[:TOP_N]]

    # Sell positions not in the pick list
    for sec in list(context.portfolio.positions.keys()):
        if sec not in picks:
            order_target(sec, 0)
            log.info("SELL %s (dropped from top-%d)", sec, TOP_N)

    # Buy picks with equal share of available cash.
    # With POSITION_PCT=0.18 and 5 stocks, max allocation = 90%.
    # We use available_cash / n_picks for equal-weight distribution.
    n_picks = len(picks)
    if n_picks > 0:
        # Cap per-stock allocation at POSITION_PCT of total value
        max_per_stock = context.portfolio.total_value * POSITION_PCT
        per_stock = min(
            context.portfolio.available_cash / n_picks,
            max_per_stock,
        )
        for sec in picks:
            if per_stock > 1000:
                order_value(sec, per_stock)
                log.info("BUY  %s @ %.2f per stock", sec, per_stock)

    record(total_value=context.portfolio.total_value)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("11 - Portfolio Backtest (StrategyConfig)")
    print("=" * 55)

    # --- Verify data is available for all universe stocks ---
    for code in UNIVERSE_CODES:
        verify_data_available(code, START_DATE, END_DATE)

    # --- Build StrategyConfig ---
    # Declarative configuration: all backtest parameters in one object.
    # 5 stocks x position_pct=0.18 = 0.90 (90% max allocation)
    config = StrategyConfig(
        securities=UNIVERSE_CODES,
        start_date=START_DATE,
        end_date=END_DATE,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        position_pct=POSITION_PCT,
        report_suffix="momentum_top3",
        rebalance_frequency="weekly",
    )

    print(f"\n  Config: {config}")
    print(f"  Universe: {UNIVERSE_KEYS}")
    print(f"  Position sizing: {len(UNIVERSE_CODES)} stocks x "
          f"{POSITION_PCT:.0%} = "
          f"{len(UNIVERSE_CODES) * POSITION_PCT:.0%} max allocation")
    print(f"  Strategy: buy top-{TOP_N} by {MOMENTUM_LOOKBACK}-day momentum")

    # --- Run portfolio backtest ---
    # run_portfolio_backtest auto-generates chart, HTML, MD, and JSON reports.
    os.makedirs("reports", exist_ok=True)
    result = run_portfolio_backtest(
        config,
        momentum_strategy,
        report_dir="reports",
    )

    if result is None:
        print("\n  Backtest failed — no results.")
        raise SystemExit(1)

    # --- Standard evaluation ---
    print_evaluation(result, "Portfolio Momentum")

    # --- Portfolio Risk Analysis ---
    print(f"\n{'=' * 55}")
    print("Concentration Risk Analysis (PortfolioRiskMonitor)")
    print(f"{'=' * 55}")

    risk_monitor = PortfolioRiskMonitor()
    risk_monitor.add_strategy("momentum_top3", result)

    concentration = risk_monitor.concentration_risk()

    print(f"  Number of holdings:    {concentration['num_holdings']:>6}")
    print(f"  Max single stock:      {concentration['max_single_stock']:>6.1%}")
    print(f"  Max single sector:     {concentration['max_single_sector']:>6.1%}")
    print(f"  Top-3 concentration:   {concentration['top3_concentration']:>6.1%}")

    # Interpretation
    max_single = concentration["max_single_stock"]
    if max_single > 0.25:
        print("  Warning: High concentration (single stock > 25%)")
    elif max_single > 0.15:
        print("  Note: Moderate concentration (single stock > 15%)")
    else:
        print("  Well-diversified portfolio.")
