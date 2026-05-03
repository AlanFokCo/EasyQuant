"""Example 6: Advanced APIs — scheduling, portfolio optimization, attribution.

Demonstrates eqlib advanced features:
1. run_weekly / run_monthly — weekly/monthly rebalancing
2. portfolio_optimizer — portfolio optimization (MinVariance, MaxSharpe, RiskParity)
3. analyze_returns — risk/return analysis of backtest results
4. brinson_attribution — Brinson attribution analysis
5. fama_french_analysis — Fama-French factor analysis
"""

import datetime
import pandas as pd
from eqlib import *


# ============================================================
# Demo 1: Strategy scheduling
# ============================================================

def demo_scheduling():
    """Demonstrate run_weekly / run_monthly scheduling."""
    log.info("=== Demo: Scheduling ===\n")

    log.info("Scheduling function usage:")
    log.info("  run_daily(func, '09:30')        — execute daily at 09:30")
    log.info("  run_weekly(func, day_of_week=0) — execute every Monday")
    log.info("  run_monthly(func, day_of_month=1) — execute on the 1st of each month")

    # Actual usage in a strategy:
    # def initialize(context):
    #     context.universe = ["601390", "000001", "600036"]
    #     run_weekly(rebalance, day_of_week=0, time="09:30")
    #     run_monthly(monthly_check, day_of_month=1, time="14:30")

    log.info("Scheduling functions are active in the backtest engine.")


# ============================================================
# Demo 2: Portfolio optimizer
# ============================================================

def demo_portfolio_optimizer():
    """Demonstrate portfolio optimization."""
    log.info("=== Demo: Portfolio Optimizer ===\n")

    securities = ["601390", "000001", "600036", "000858"]
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)

    price_data = get_price(securities, start_date=start_date, end_date=end_date)

    prices = pd.DataFrame()
    for sec, df in price_data.items():
        if not df.empty and "close" in df.columns:
            prices[sec] = df["close"]

    if prices.empty or len(prices) < 60:
        log.info("Insufficient data for optimizer demo (need at least 60 trading days)")
        return

    log.info(f"Price matrix: {len(prices)} days x {len(prices.columns)} stocks")

    # 1) Minimum Variance
    weights_mv = portfolio_optimizer(
        securities=securities,
        prices=prices,
        target=MinVariance(),
        constraints={"max_weight": 0.5},
    )
    if weights_mv is not None:
        log.info("Minimum Variance portfolio:")
        for sec, w in weights_mv.items():
            log.info(f"  {sec}: {w:.1%}")
    print()

    # 2) Maximum Sharpe
    weights_ms = portfolio_optimizer(
        securities=securities,
        prices=prices,
        target=MaxSharpe(risk_free_rate=0.03),
        constraints={"max_weight": 0.5},
    )
    if weights_ms is not None:
        log.info("Maximum Sharpe portfolio:")
        for sec, w in weights_ms.items():
            log.info(f"  {sec}: {w:.1%}")
    print()

    # 3) Risk Parity
    weights_rp = portfolio_optimizer(
        securities=securities,
        prices=prices,
        target=RiskParity(),
    )
    if weights_rp is not None:
        log.info("Risk Parity portfolio:")
        for sec, w in weights_rp.items():
            log.info(f"  {sec}: {w:.1%}")


# ============================================================
# Demo 3: Attribution analysis
# ============================================================

def demo_attribution():
    """Demonstrate attribution analysis."""
    log.info("=== Demo: Attribution Analysis ===\n")

    log.info("Running MA crossover backtest...")
    result = run_backtest(
        ma_initialize,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        starting_cash=100000,
        benchmark="000300.XSHG",
    )

    if result is None:
        log.info("No backtest result, skipping attribution")
        return

    # 1) Risk/return analysis
    log.info("\nRisk/return metrics:")
    metrics = analyze_returns(result)
    if metrics:
        for key, val in metrics.items():
            if isinstance(val, float):
                if "return" in key or "drawdown" in key:
                    log.info(f"  {key}: {val:+.2%}")
                elif "ratio" in key:
                    log.info(f"  {key}: {val:.3f}")
                else:
                    log.info(f"  {key}: {val}")
            else:
                log.info(f"  {key}: {val}")

    # 2) Brinson attribution
    log.info("\nBrinson attribution:")
    brinson = brinson_attribution(result)
    if brinson:
        log.info(f"  Allocation effect: {brinson['allocation_effect']:+.4%}")
        log.info(f"  Selection effect:  {brinson['selection_effect']:+.4%}")
        log.info(f"  Interaction effect:{brinson['interaction_effect']:+.4%}")
        log.info(f"  Total active return: {brinson['total_active_return']:+.4%}")

    # 3) Fama-French factor analysis
    log.info("\nFactor analysis:")
    ff = fama_french_analysis(result)
    if ff:
        log.info(f"  Market beta:       {ff['market_beta']:.3f}")
        log.info(f"  Alpha (annual):    {ff['alpha_annual']:+.2%}")
        log.info(f"  Momentum corr:     {ff['momentum_correlation']:.3f}")
        log.info(f"  Residual vol:      {ff['residual_volatility']:.2%}")


# ============================================================
# Built-in strategy (for attribution demo)
# ============================================================

def ma_initialize(context):
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(ma_handle, time="every_bar")


def ma_handle(context):
    security = g.security
    close_data = attribute_history(security, 25, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = close_data["close"].tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close_data["close"].tail(g.slow_period + 1).head(g.slow_period).mean()

    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)

    record(total_value=context.portfolio.total_value)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    demo_scheduling()
    print()

    demo_portfolio_optimizer()
    print()

    demo_attribution()
