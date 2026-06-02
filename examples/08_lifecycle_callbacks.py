"""Example 8: Lifecycle callbacks and universe management.

Demonstrates:
- before_trading_start: pre-market preparation
- after_trading_end: post-market analysis
- set_universe / get_universe: dynamic universe management
- get_trade_days: trading calendar queries
- run_monthly: monthly scheduling
- Preloaded data for fast backtests

Usage:
    python examples/08_lifecycle_callbacks.py
"""

from eqlib import *
from datetime import date, timedelta


def before_market_open(context):
    """Called before each trading day (9:30)."""
    universe = get_universe()
    log.info(f"Before market open: {len(universe)} stocks in universe")

    # Check for ST stocks in universe
    st_map = get_extras("is_st", security_list=universe)
    st_stocks = [code for code, is_st in st_map.items() if is_st]
    if st_stocks:
        log.warning(f"ST stocks detected: {st_stocks}")

    # ============================================================
    # A-share market sentiment indicators (before market open)
    # ============================================================
    current_date = context.current_dt.date()

    # Get limit up/down stats for market sentiment
    limit_stats = get_limit_up_down_stats(date=current_date)
    if limit_stats:
        log.info(f"  Market Sentiment - Limit Up: {limit_stats.get('limit_up_count', 'N/A')}, "
                 f"Limit Down: {limit_stats.get('limit_down_count', 'N/A')}")

    # Get north money flow (foreign capital) - 3-day net buy as sentiment reference
    total_net_inflow = 0
    days_checked = 0
    for i in range(3):
        check_date = current_date - timedelta(days=i)
        north_flow = get_north_money_flow(date=check_date)
        if north_flow:
            net_inflow = north_flow.get('north_net_inflow', 0) or 0
            total_net_inflow += net_inflow
            days_checked += 1
    if days_checked > 0:
        direction = "inflow" if total_net_inflow > 0 else "outflow"
        log.info(f"  North Money (3-day): Net {direction} {abs(total_net_inflow)/1e8:.2f} 亿 CNY")


def after_market_close(context):
    """Called after each trading day (15:00)."""
    total = context.portfolio.total_value
    cash = context.portfolio.available_cash
    positions = len([p for p in context.portfolio.positions.values() if p.amount > 0])

    log.info(f"After market close: total_value={total:,.2f}, "
             f"cash={cash:,.2f}, positions={positions}")


def monthly_review(context):
    """Monthly portfolio review."""
    log.info(f"Monthly review - Date: {context.current_dt.date()}")

    # Print performance summary
    starting = context.portfolio.starting_cash
    current = context.portfolio.total_value
    pnl = current - starting
    pnl_pct = (pnl / starting) * 100

    log.info(f"  PnL: {pnl:+,.2f} ({pnl_pct:+.2f}%)")
    log.info(f"  Positions: {len([p for p in context.portfolio.positions.values() if p.amount > 0])}")


def initialize(context):
    """Initialize the strategy."""
    # Set initial universe
    g.securities = ["601390", "000001", "600519"]
    set_universe(g.securities)

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    # Register lifecycle callbacks
    before_trading_start(before_market_open)
    after_trading_end(after_market_close)

    # Monthly review
    run_monthly(monthly_review, day_of_month=1, time="15:00")

    # Daily trading logic
    run_daily(trade_logic, time="every_bar")

    log.info("Lifecycle strategy initialized")


def trade_logic(context):
    """Daily trading logic with dynamic universe."""
    universe = get_universe()

    # Simple momentum: buy if price above 20-day MA
    for sec in universe:
        close_data = attribute_history(sec, 25, "1d", ["close"])
        if close_data.empty or len(close_data) < 20:
            continue

        current_price = close_data["close"].iloc[-1]
        ma20 = close_data["close"].tail(20).mean()

        pos = context.portfolio.positions.get(sec)

        if current_price > ma20 * 1.02 and (not pos or pos.amount == 0):
            order_value(sec, context.portfolio.available_cash * 0.3)
            log.info(f"Momentum BUY {sec} @ {current_price:.3f}")
        elif current_price < ma20 * 0.98 and pos and pos.amount > 0:
            order_target(sec, 0)
            log.info(f"Momentum SELL {sec} @ {current_price:.3f}")

    # Record metrics
    record(total_value=context.portfolio.total_value)


if __name__ == "__main__":
    # Demo: trading calendar
    log.info("=== Trading Calendar ===")
    import datetime

    days = get_trade_days(
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 1, 31),
    )
    log.info(f"Trading days in Jan 2024: {len(days)}")
    log.info(f"First: {days[0]}, Last: {days[-1]}")
    print()

    # Run backtest with preloaded data for speed
    securities = ["601390", "000001", "600519"]

    result = run_strategy(
        initialize_func=initialize,
        start_date="2023-01-01",
        end_date="2024-12-31",
        starting_cash=100000,
        securities=securities,
        use_local=True,
    )

    if result is not None:
        ctx = result["context"]
        print(f"\n{'=' * 60}")
        print(f"Lifecycle backtest results")
        print(f"{'=' * 60}")
        print(f"  Final value: {ctx.portfolio.total_value:,.2f}")
        print(f"  Trades: {len(result['trade_log'])}")
