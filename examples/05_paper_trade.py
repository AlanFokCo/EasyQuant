"""Example 5: Paper trading (live simulation).

Demonstrates how to run paper trading with eqlib.
The paper trader:
1. Connects to real-time market data
2. Automatically executes buy/sell on strategy signals
3. Tracks positions and P&L
4. Does NOT send real trades

Usage:
    # Use built-in strategy
    python examples/05_paper_trade.py

    # Specify a strategy file
    python examples/05_paper_trade.py --strategy examples/02_write_strategy

    # Custom parameters
    python examples/05_paper_trade.py --cash 200000 --interval 120

Note: The paper trader runs indefinitely until stopped with Ctrl+C.
"""

import argparse
import importlib.util
import os
import sys
from eqlib import *
from eqlib import get_restriction_release, get_limit_up_down_stats


def load_strategy(path):
    """Load a strategy module from a file."""
    if not path.endswith(".py"):
        path += ".py"
    if not os.path.exists(path):
        print(f"Strategy file not found: {path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("strategy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(strategy_path=None, cash=100000, interval=60):
    """Start paper trading."""

    if strategy_path:
        mod = load_strategy(strategy_path)
        if not hasattr(mod, "initialize"):
            print("Strategy file is missing initialize(context) function")
            sys.exit(1)
        init_func = mod.initialize
    else:
        init_func = ma_initialize

    log.info("=" * 60)
    log.info("Paper Trading Started")
    log.info(f"Initial capital: {cash:,.0f}")
    log.info(f"Polling interval: {interval}s")
    log.info("Press Ctrl+C to stop")
    log.info("=" * 60)

    run_paper_trade(
        initialize_func=init_func,
        starting_cash=cash,
        interval=interval,
    )


# ============================================================
# Built-in strategy: Moving Average Crossover
# ============================================================

def _paper_before_trading(context):
    """Pre-market monitoring: restriction release warnings and market context.

    Registered via before_trading_start. Logs:
    1. Upcoming restriction releases for held positions (risk warning)
    2. Today's limit up/down stats (market sentiment context)
    """
    held = [c for c, p in context.portfolio.positions.items() if p.amount > 0]

    # 1. Restriction release warnings for held positions
    try:
        release_df = get_restriction_release(days=7)
        if not release_df.empty and "code" in release_df.columns:
            held_releases = release_df[release_df["code"].isin(held)]
            if not held_releases.empty:
                for _, row in held_releases.iterrows():
                    name = row.get("name", "")
                    date = row.get("release_date", "")
                    value = row.get("release_value", 0)
                    pct = row.get("release_pct", 0)
                    log.warning(
                        "⚠ 限售解禁预警: %s(%s) 解禁日:%s 市值:%.2f亿 占比:%.2f%%"
                        % (row["code"], name, date, value, pct)
                    )
            else:
                log.info("限售解禁: 持仓股近7日无限售解禁")
        else:
            log.info("限售解禁: 数据暂不可用")
    except Exception as exc:
        log.warning("限售解禁数据获取失败: %s" % exc)

    # 2. Limit up/down stats as market context
    try:
        limit_df = get_limit_up_down_stats()
        if not limit_df.empty:
            latest = limit_df.iloc[-1]
            up_count = latest.get("limit_up_count", 0)
            down_count = latest.get("limit_down_count", 0)
            date = latest.get("date", "")
            log.info(
                "市场情绪 [%s]: 涨停 %d 只 / 跌停 %d 只"
                % (date, int(up_count), int(down_count))
            )
        else:
            log.info("涨跌停统计: 数据暂不可用")
    except Exception as exc:
        log.warning("涨跌停统计获取失败: %s" % exc)


def ma_initialize(context):
    """MA crossover strategy initialization."""
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

    # Pre-market monitoring: restriction releases + market sentiment
    before_trading_start(_paper_before_trading)

    run_daily(ma_on_bar, time="every_bar")

    log.info("Paper trading strategy: MA crossover %s MA%d/MA%d" % (
        g.security, g.fast_period, g.slow_period))


def ma_on_bar(context):
    """MA crossover strategy - execute every bar."""
    security = g.security
    close_data = attribute_history(security, 25, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = close_data["close"].tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close_data["close"].tail(g.slow_period + 1).head(g.slow_period).mean()

    # Golden cross: buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("Paper BUY: %s @ %.3f" % (security, current_price))

    # Death cross: sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Paper SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma,
           total_value=context.portfolio.total_value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper trading")
    parser.add_argument("--strategy", default=None,
                        help="Strategy file path (without .py)")
    parser.add_argument("--cash", type=float, default=100000,
                        help="Initial capital (default 100000)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Quote polling interval in seconds (default 60)")
    args = parser.parse_args()

    run(
        strategy_path=args.strategy,
        cash=args.cash,
        interval=args.interval,
    )
