"""
12 - Paper Trading (Live Simulation)
=====================================

Demonstrates running a strategy in paper trading mode:
- run_paper_trade(): live simulation with real market data
- Pre-market monitoring: restriction releases, limit up/down stats
- DingTalk/Feishu webhook notification setup

Teaching Objectives:
    - Difference between backtest and paper trading
    - run_paper_trade() with --cash and --interval CLI args
    - Pre-market data checks before trading
    - Webhook notification configuration (commented out template)

Expected Output:
    - Pre-market monitoring report (restriction releases, limit stats)
    - Paper trading starts and runs until Ctrl+C
    - Webhook configuration template printed

Run:
    python examples/12_paper_trade.py --cash 100000 --interval 60
"""

import argparse

from eqlib import (
    run_paper_trade,
    set_benchmark,
    set_order_cost,
    run_daily,
    attribute_history,
    order_value,
    order_target,
    record,
    log,
    g,
    get_restriction_release,
    get_limit_up_down_stats,
    OrderCost,
    before_trading_start,
)

from examples._defaults import (
    STOCKS_TRADE,
    INDEX_HS300,
    DEFAULT_ORDER_COST,
    INITIAL_CASH,
)


# ============================================================
# 1. Pre-market monitoring
# ============================================================

def demo_pre_market_monitor():
    """Show pre-market data checks: restriction releases and limit stats.

    Run this BEFORE starting paper trading to understand today's risk
    landscape.  In a production workflow you would call this from a
    ``before_trading_start`` callback so it fires automatically at 09:30.
    """
    print("\n" + "=" * 60)
    print("  Pre-market monitoring report")
    print("=" * 60)

    # 1) Upcoming restriction releases (限售解禁)
    #    Large upcoming unlocks can pressure stock prices.  We look at
    #    the next 7 calendar days.
    print("\n[1] Restriction releases (next 7 days)")
    print("-" * 60)
    try:
        release_df = get_restriction_release(days=7)
        if release_df is not None and not release_df.empty:
            print(f"  Total upcoming releases: {len(release_df)}")
            cols = ["code", "name", "release_date",
                    "release_value", "release_pct"]
            available = [c for c in cols if c in release_df.columns]
            if "release_value" in release_df.columns:
                top5 = release_df.nlargest(5, "release_value")
                print("  Top 5 by release value:")
                print(top5[available].to_string(index=False))
                total_value = release_df["release_value"].sum()
                print(f"  Total release value (7d): {total_value:.2f} 亿元")
                if total_value > 200:
                    print("  ⚠  Heavy unlock pressure this week — "
                          "consider reducing position sizes.")
            else:
                print(release_df.head(5).to_string(index=False))
        else:
            print("  No upcoming restriction releases in the next 7 days.")
    except Exception as exc:
        print(f"  [warn] get_restriction_release failed: {exc}")

    # 2) Limit up / down stats (涨跌停统计)
    #    High limit-down counts signal market stress; high limit-up
    #    counts signal speculative exuberance.
    print("\n[2] Limit up / down stats (most recent trading day)")
    print("-" * 60)
    try:
        limit_df = get_limit_up_down_stats()
        if limit_df is not None and not limit_df.empty:
            latest = limit_df.iloc[-1]
            up_count = int(latest.get("limit_up_count", 0))
            down_count = int(latest.get("limit_down_count", 0))
            date = latest.get("date", "?")
            print(f"  Date:           {date}")
            print(f"  Limit-up count:   {up_count}")
            print(f"  Limit-down count: {down_count}")
            ratio = (up_count / max(down_count, 1))
            print(f"  Up / down ratio:  {ratio:.2f}")

            # Interpretation
            if down_count > 100:
                print("  ⚠  Systemic stress signal — limit-down > 100. "
                      "Consider staying in cash today.")
            elif down_count > 50:
                print("  ⚠  Weak sentiment — limit-down > 50. "
                      "Trade with reduced position sizes.")
            elif ratio > 3:
                print("  ✓  Strong sentiment — up/down ratio > 3.")
            else:
                print("  ✓  Normal market breadth.")
        else:
            print("  Limit up/down data not available.")
    except Exception as exc:
        print(f"  [warn] get_limit_up_down_stats failed: {exc}")

    print()


# ============================================================
# 2. Notification setup (template)
# ============================================================

def demo_notification_setup():
    """Print a commented-out template for DingTalk / Feishu webhooks.

    These are CONFIG-TIME settings — call them inside ``initialize()``
    BEFORE placing any orders.  Uncomment and fill in your own URLs to
    enable live trade notifications.
    """
    print("\n" + "=" * 60)
    print("  Webhook notification template")
    print("=" * 60)
    print("""
# --- DingTalk (钉钉) --------------------------------------------------
# 1. Create a DingTalk group, add a "custom robot"
# 2. Copy the webhook URL and (optional) signing secret
#
# from eqlib import set_notification_webhook, enable_notification
#
# set_notification_webhook(
#     "dingtalk",
#     "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
#     secret="SECxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # optional
# )
# enable_notification(["signal"])          # notify on strategy signals
# # enable_notification(["signal", "filled"])  # also notify on fills

# --- Feishu (飞书) ----------------------------------------------------
# 1. Create a Feishu group, add a "custom bot"
# 2. Copy the webhook URL
#
# set_notification_webhook(
#     "feishu",
#     "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
# )
# enable_notification(["signal"])

# --- Sending a manual signal -----------------------------------------
# from eqlib import notify_signal
#
# notify_signal(
#     security="601390.XSHG",
#     side="buy",
#     amount=1000,
#     current_price=5.25,
#     price_range=(5.15, 5.35),
#     strategy_name="MA crossover",
#     trigger_point="MA5 上穿 MA20, 金叉形成",
# )
""")


# ============================================================
# 3. Paper trading strategy: MA crossover
# ============================================================

def _before_trading(context):
    """Pre-market hook fired at 09:30 during paper trading.

    Logs restriction-release warnings for currently held positions and
    prints today's limit up / down stats as market context.
    """
    held = [c for c, p in context.portfolio.positions.items() if p.amount > 0]

    # Restriction-release warnings for held positions
    try:
        release_df = get_restriction_release(days=7)
        if release_df is not None and not release_df.empty \
                and "code" in release_df.columns:
            held_releases = release_df[release_df["code"].isin(held)]
            if not held_releases.empty:
                for _, row in held_releases.iterrows():
                    name = row.get("name", "")
                    date = row.get("release_date", "")
                    value = row.get("release_value", 0)
                    pct = row.get("release_pct", 0)
                    log.warning(
                        "限售解禁预警: %s(%s) 解禁日:%s 市值:%.2f亿 占比:%.2f%%"
                        % (row["code"], name, date, value, pct)
                    )
            else:
                log.info("限售解禁: 持仓股近7日无限售解禁")
    except Exception as exc:
        log.warning("限售解禁数据获取失败: %s" % exc)

    # Limit up / down stats as market context
    try:
        limit_df = get_limit_up_down_stats()
        if limit_df is not None and not limit_df.empty:
            latest = limit_df.iloc[-1]
            up_count = int(latest.get("limit_up_count", 0))
            down_count = int(latest.get("limit_down_count", 0))
            date = latest.get("date", "")
            log.info("市场情绪 [%s]: 涨停 %d 只 / 跌停 %d 只"
                     % (date, up_count, down_count))
    except Exception as exc:
        log.warning("涨跌停统计获取失败: %s" % exc)


def initialize(context):
    """MA crossover strategy for paper trading.

    Uses a fast/slow moving average pair on a single stock.  Buys on
    the golden cross (fast crosses above slow) and sells on the death
    cross (fast crosses below slow).
    """
    g.security = STOCKS_TRADE["bank"]        # 601398.XSHG — ICBC
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    context.universe = [g.security]

    # Register the pre-market hook so it fires at 09:30 every trading
    # day while paper trading is running.
    before_trading_start(_before_trading)

    run_daily(market_open, time="every_bar")

    log.info("Paper strategy: MA crossover %s MA%d/MA%d"
             % (g.security, g.fast_period, g.slow_period))


def market_open(context):
    """Execute MA crossover logic on each live bar."""
    security = g.security
    close_data = attribute_history(security, g.slow_period + 5, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = (close_data["close"]
                 .tail(g.fast_period + 1).head(g.fast_period).mean())
    prev_slow = (close_data["close"]
                 .tail(g.slow_period + 1).head(g.slow_period).mean())

    # Golden cross → buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
                or context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info("Paper BUY: %s @ %.3f" % (security, current_price))

    # Death cross → sell
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
                and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Paper SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma,
           total_value=context.portfolio.total_value)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Paper trading (live simulation) with pre-market "
                    "monitoring and webhook notification template.")
    parser.add_argument("--cash", type=float, default=INITIAL_CASH,
                        help="Initial capital (default %(default)s)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Quote polling interval in seconds "
                             "(default %(default)s)")
    parser.add_argument("--skip-monitor", action="store_true",
                        help="Skip the pre-market monitoring report")
    parser.add_argument("--skip-webhook", action="store_true",
                        help="Skip the webhook notification template")
    args = parser.parse_args()

    # 1) Pre-market monitoring report
    if not args.skip_monitor:
        demo_pre_market_monitor()

    # 2) Webhook notification template
    if not args.skip_webhook:
        demo_notification_setup()

    # 3) Start paper trading (runs until Ctrl+C)
    print("\n" + "=" * 60)
    print("  Starting paper trading")
    print(f"  Initial capital:     {args.cash:,.0f}")
    print(f"  Polling interval:    {args.interval}s")
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    run_paper_trade(
        initialize_func=initialize,
        starting_cash=args.cash,
        interval=args.interval,
    )
