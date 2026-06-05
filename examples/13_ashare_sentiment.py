"""
13 - A-Share Market Sentiment
=============================

Demonstrates A-share specific market data APIs for building
a composite sentiment indicator:
- get_north_money_flow(): northbound capital flow (沪股通 + 深股通)
- get_margin_data(): margin trading balance and activity
- get_limit_up_down_stats(): daily limit-up/limit-down counts
- get_restriction_release(): upcoming restricted share unlocks

Builds a composite sentiment score and shows how to use it
as a gating signal for a simple strategy.

Teaching Objectives:
    - Four A-share specific data APIs and their interpretation
    - Building a composite sentiment score from multiple sources
    - Using sentiment as a position sizing modifier
    - Comparing strategy performance with vs without sentiment filter

Expected Output:
    - Sentiment indicator values and interpretation
    - Two backtest results: baseline vs sentiment-filtered
    - Side-by-side comparison

Run:
    python examples/13_ashare_sentiment.py
"""

from datetime import datetime, timedelta

import pandas as pd

from eqlib import (
    run_backtest,
    set_benchmark,
    set_order_cost,
    run_daily,
    attribute_history,
    order_value,
    order_target,
    record,
    log,
    g,
    get_north_money_flow,
    get_margin_data,
    get_limit_up_down_stats,
    get_restriction_release,
    analyze_returns,
    OrderCost,
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
# 1. Demo: call all 4 A-share sentiment APIs
# ============================================================

def demo_sentiment_apis():
    """Call the four A-share sentiment APIs and print interpreted results.

    Each API returns a pandas DataFrame (or empty DataFrame on failure).
    We print the most recent values and a plain-language interpretation
    so you can see what each indicator tells you about market conditions.
    """
    print("\n" + "=" * 60)
    print("  A-share sentiment API demo")
    print("=" * 60)

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    # --- (a) North-bound capital flow --------------------------------
    print("\n[a] get_north_money_flow() — northbound capital (沪股通+深股通)")
    print("-" * 60)
    try:
        north = get_north_money_flow(start_date=start_date,
                                     end_date=end_date)
        if north is not None and not north.empty:
            print(f"  Data range: {north['date'].iloc[0]} ~ "
                  f"{north['date'].iloc[-1]}  ({len(north)} rows)")
            net_5d = north["net_buy"].tail(5).sum()
            net_20d = north["net_buy"].tail(20).sum()
            print(f"  5-day net buy:  {net_5d:>+10.2f} 亿元")
            print(f"  20-day net buy: {net_20d:>+10.2f} 亿元")
            if net_5d > 50 and net_20d > 100:
                print("  → Strong inflow: foreign capital is accumulating.")
            elif net_5d < -50 and net_20d < -100:
                print("  → Strong outflow: foreign capital is retreating.")
            elif net_5d > 0:
                print("  → Moderate inflow.")
            elif net_5d < 0:
                print("  → Moderate outflow.")
            else:
                print("  → Balanced flow.")
        else:
            print("  No data available.")
    except Exception as exc:
        print(f"  [warn] get_north_money_flow failed: {exc}")

    # --- (b) Margin trading data -------------------------------------
    print("\n[b] get_margin_data() — margin balance & activity")
    print("-" * 60)
    try:
        margin = get_margin_data(start_date=start_date, end_date=end_date)
        if margin is not None and not margin.empty:
            print(f"  Data range: {margin['date'].iloc[0]} ~ "
                  f"{margin['date'].iloc[-1]}  ({len(margin)} rows)")
            bal_now = margin["margin_balance"].iloc[-1]
            bal_5d_ago = (margin["margin_balance"].iloc[-6]
                          if len(margin) >= 6 else bal_now)
            chg_pct = ((bal_now - bal_5d_ago) / max(bal_5d_ago, 1)) * 100
            print(f"  Latest balance:     {bal_now:>14,.0f} 亿元")
            print(f"  5-day change:       {chg_pct:>+10.2f} %%")
            if "margin_buy" in margin.columns and \
                    "margin_repay" in margin.columns:
                buy = margin["margin_buy"].iloc[-1]
                repay = abs(margin["margin_repay"].iloc[-1])
                total = buy + repay
                buy_ratio = (buy / total * 100) if total > 0 else 50.0
                print(f"  Buy / repay ratio:  {buy_ratio:>10.1f} %% buy")
            if chg_pct > 2:
                print("  → Leveraged money growing fast — bullish.")
            elif chg_pct < -2:
                print("  → Leveraged money retreating — bearish.")
            else:
                print("  → Stable leverage — neutral.")
        else:
            print("  No data available.")
    except Exception as exc:
        print(f"  [warn] get_margin_data failed: {exc}")

    # --- (c) Limit up / down stats -----------------------------------
    print("\n[c] get_limit_up_down_stats() — daily limit-up/limit-down")
    print("-" * 60)
    try:
        limit_df = get_limit_up_down_stats()
        if limit_df is not None and not limit_df.empty:
            latest = limit_df.iloc[-1]
            up_count = int(latest.get("limit_up_count", 0))
            down_count = int(latest.get("limit_down_count", 0))
            ratio = up_count / max(down_count, 1)
            print(f"  Date:           {latest.get('date', '?')}")
            print(f"  Limit-up count:   {up_count}")
            print(f"  Limit-down count: {down_count}")
            print(f"  Up/down ratio:    {ratio:.2f}")
            if down_count > 100:
                print("  ⚠  Systemic stress — many stocks locked down.")
            elif down_count > 50:
                print("  ⚠  Weak breadth — sellers dominating.")
            elif ratio > 3:
                print("  → Strong breadth — buyers dominating.")
            else:
                print("  → Normal breadth.")
        else:
            print("  No data available.")
    except Exception as exc:
        print(f"  [warn] get_limit_up_down_stats failed: {exc}")

    # --- (d) Restriction release -------------------------------------
    print("\n[d] get_restriction_release() — upcoming lock-up expiries")
    print("-" * 60)
    try:
        releases = get_restriction_release(days=30)
        if releases is not None and not releases.empty:
            print(f"  Upcoming releases (30d): {len(releases)} stocks")
            if "release_value" in releases.columns:
                total_value = releases["release_value"].sum()
                large = (releases["release_value"] > 50).sum()
                print(f"  Total release value:  {total_value:.2f} 亿元")
                print(f"  Large (>50亿):        {large} stocks")
                if total_value > 500:
                    print("  ⚠  Heavy unlock pressure this month.")
                else:
                    print("  → Manageable unlock pressure.")
        else:
            print("  No upcoming releases.")
    except Exception as exc:
        print(f"  [warn] get_restriction_release failed: {exc}")

    print()


# ============================================================
# 2. Composite sentiment score
# ============================================================

def calculate_sentiment_score():
    """Compute a composite sentiment score in [-1.0, +1.0].

    Weights:
        - North-bound capital flow (5d net buy):  40%
        - Limit-up / limit-down ratio:            30%
        - Margin balance 5-day trend:             30%

    Returns:
        float: sentiment score.  +1 = extremely bullish, -1 = extremely
        bearish, 0 = neutral.  Returns 0.0 if no data is available so
        that strategies degrade gracefully.
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=60)

    score = 0.0

    # --- North-bound flow component ----------------------------------
    try:
        north = get_north_money_flow(start_date=start_date,
                                     end_date=end_date)
        if north is not None and not north.empty:
            net_5d = north["net_buy"].tail(5).sum()
            # Normalise: ±200亿 maps to ±1.0
            north_score = max(-1.0, min(1.0, net_5d / 200.0))
            score += 0.4 * north_score
    except Exception:
        pass

    # --- Limit ratio component ---------------------------------------
    try:
        limit_df = get_limit_up_down_stats()
        if limit_df is not None and not limit_df.empty:
            # Use 5-day average ratio to smooth noise
            recent = limit_df.tail(5)
            avg_up = recent["limit_up_count"].mean()
            avg_down = recent["limit_down_count"].mean()
            ratio = avg_up / max(avg_down, 1)
            # ratio of 1 = neutral (0), ratio of 5+ = +1, ratio < 0.3 = -1
            if ratio >= 1:
                limit_score = min(1.0, (ratio - 1) / 4.0)
            else:
                limit_score = max(-1.0, (ratio - 1) / 0.7)
            score += 0.3 * limit_score
    except Exception:
        pass

    # --- Margin trend component --------------------------------------
    try:
        margin = get_margin_data(start_date=start_date, end_date=end_date)
        if margin is not None and not margin.empty and len(margin) >= 6:
            bal_now = margin["margin_balance"].iloc[-1]
            bal_5d_ago = margin["margin_balance"].iloc[-6]
            chg_pct = ((bal_now - bal_5d_ago) / max(bal_5d_ago, 1)) * 100
            # ±5% change maps to ±1.0
            margin_score = max(-1.0, min(1.0, chg_pct / 5.0))
            score += 0.3 * margin_score
    except Exception:
        pass

    return max(-1.0, min(1.0, score))


# ============================================================
# 3. Strategies: baseline vs sentiment-filtered
# ============================================================
#
# Both strategies trade the same MA crossover on the same stock.  The
# "filtered" variant reduces its position size when the composite
# sentiment score drops below -0.3.
#
# IMPORTANT: run_daily callbacks receive only ``context`` — data is
# fetched via attribute_history(), NOT via a ``bar`` argument.

SECURITY = STOCKS_TRADE["bank"]       # 601398.XSHG — ICBC
FAST_PERIOD = 5
SLOW_PERIOD = 20
SENTIMENT_THRESHOLD = -0.3            # Reduce position below this


def _init_common(context):
    """Shared initialisation for both strategies."""
    g.security = SECURITY
    g.fast_period = FAST_PERIOD
    g.slow_period = SLOW_PERIOD
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)
    context.universe = [SECURITY]


def initialize_simple(context):
    """Baseline MA crossover (no sentiment filter)."""
    _init_common(context)
    run_daily(market_open_simple, time="every_bar")


def market_open_simple(context):
    """Baseline trade logic: pure MA crossover."""
    security = g.security
    hist = attribute_history(security, g.slow_period + 5, "1d", ["close"])
    if hist.empty or len(hist) < g.slow_period:
        return

    close = hist["close"]
    fast_ma = close.tail(g.fast_period).mean()
    slow_ma = close.tail(g.slow_period).mean()
    prev_fast = close.tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close.tail(g.slow_period + 1).head(g.slow_period).mean()

    position = context.portfolio.positions.get(security)

    # Golden cross → full buy
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if not position or position.amount == 0:
            order_value(security, context.portfolio.available_cash * 0.95)

    # Death cross → sell all
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if position and position.amount > 0:
            order_target(security, 0)

    record(fast_ma=fast_ma, slow_ma=slow_ma,
           total_value=context.portfolio.total_value)


def initialize_filtered(context):
    """MA crossover gated by composite sentiment score."""
    _init_common(context)
    run_daily(market_open_filtered, time="every_bar")


def market_open_filtered(context):
    """Filtered trade logic: reduce position when sentiment < threshold.

    The sentiment score is expensive to compute (hits multiple network
    APIs), so in a real strategy you would cache it in
    ``before_trading_start`` and read from ``g.sentiment`` here.  For
    teaching clarity we compute it inline and accept the slower backtest.
    """
    security = g.security
    hist = attribute_history(security, g.slow_period + 5, "1d", ["close"])
    if hist.empty or len(hist) < g.slow_period:
        return

    close = hist["close"]
    fast_ma = close.tail(g.fast_period).mean()
    slow_ma = close.tail(g.slow_period).mean()
    prev_fast = close.tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close.tail(g.slow_period + 1).head(g.slow_period).mean()

    # Compute sentiment (cached on context so we do it at most once/day)
    today = getattr(context, "current_dt", None)
    cache_key = today.date() if hasattr(today, "date") else None
    if cache_key != getattr(g, "_sentiment_date", None):
        g._sentiment_score = calculate_sentiment_score()
        g._sentiment_date = cache_key
    sentiment = getattr(g, "_sentiment_score", 0.0)

    # Position sizing: full position when sentiment OK, reduced when bad
    if sentiment < SENTIMENT_THRESHOLD:
        position_pct = 0.30    # 30% of available cash — defensive
    else:
        position_pct = 0.95    # 95% of available cash — normal

    position = context.portfolio.positions.get(security)

    # Golden cross → buy (sized by sentiment)
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if not position or position.amount == 0:
            order_value(security,
                        context.portfolio.available_cash * position_pct)

    # Death cross → sell all
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if position and position.amount > 0:
            order_target(security, 0)

    # Extra defensive exit: sentiment collapse while holding
    elif sentiment < SENTIMENT_THRESHOLD and position \
            and position.amount > 0:
        # Trim to ~30% of current portfolio value
        target_value = context.portfolio.total_value * 0.30
        order_target(security, target_value / max(close.iloc[-1], 0.01))

    record(fast_ma=fast_ma, slow_ma=slow_ma, sentiment=sentiment,
           total_value=context.portfolio.total_value)


# ============================================================
# 4. Run both backtests and compare
# ============================================================

def run_comparison():
    """Run baseline vs filtered backtests and print side-by-side metrics."""
    print("\n" + "=" * 60)
    print("  Backtest comparison: baseline vs sentiment-filtered")
    print("=" * 60)

    # Preload data for the target security
    actual_start, actual_end = verify_data_available(
        SECURITY, START_DATE, END_DATE)

    securities = [SECURITY]

    print(f"\nRunning baseline MA crossover ({actual_start} → {actual_end})...")
    result_simple = run_backtest(
        initialize_simple,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        securities=securities,
    )

    print(f"Running sentiment-filtered MA crossover "
          f"({actual_start} → {actual_end})...")
    result_filtered = run_backtest(
        initialize_filtered,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        securities=securities,
    )

    # Print evaluations side by side
    print_evaluation(result_simple, strategy_name="Baseline MA")
    print_evaluation(result_filtered, strategy_name="MA + Sentiment filter")

    # Compact side-by-side summary
    m_simple = (analyze_returns(result_simple, risk_free_rate=0.03)
                if result_simple else None)
    m_filtered = (analyze_returns(result_filtered, risk_free_rate=0.03)
                  if result_filtered else None)

    if m_simple and m_filtered:
        print("\n" + "=" * 60)
        print("  Side-by-side comparison")
        print("=" * 60)
        rows = [
            ("Total return",   "total_return",      "{:>10.2%}"),
            ("Annual return",  "annual_return",     "{:>10.2%}"),
            ("Annual vol",     "annual_volatility", "{:>10.2%}"),
            ("Sharpe ratio",   "sharpe_ratio",      "{:>10.2f}"),
            ("Max drawdown",   "max_drawdown",      "{:>10.2%}"),
            ("Win rate",       "win_rate_trade",    "{:>10.1%}"),
            ("Trade count",    "trade_count",       "{:>10.0f}"),
        ]
        print(f"  {'Metric':<20} {'Baseline':>14} {'Filtered':>14}  "
              f"{'Δ (Filt − Base)':>16}")
        print("  " + "-" * 66)
        for label, key, fmt in rows:
            v_b = m_simple.get(key, 0) or 0
            v_f = m_filtered.get(key, 0) or 0
            delta = v_f - v_b
            delta_fmt = "{:>+10.2f}".format(delta) if "ratio" in key \
                else "{:>+10.2%}".format(delta) if "count" not in key \
                else "{:>+10.0f}".format(delta)
            print(f"  {label:<20} {fmt.format(v_b):>14} "
                  f"{fmt.format(v_f):>14}  {delta_fmt:>16}")
        print()
        print("  Note: The sentiment filter is most valuable when it")
        print("  *reduces max drawdown* — a slightly lower total return")
        print("  with much smaller drawdown is usually preferable.")
        print()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    # 1) Show each A-share sentiment API with interpretation
    demo_sentiment_apis()

    # 2) Compute and report the composite sentiment score
    print("\n" + "=" * 60)
    print("  Composite sentiment score")
    print("=" * 60)
    score = calculate_sentiment_score()
    print(f"  Score: {score:+.2f}  (range: -1.00 to +1.00)")
    if score >= 0.3:
        zone = "Bullish (乐观区)"
    elif score >= 0.0:
        zone = "Neutral-bullish (中性偏乐观)"
    elif score >= -0.3:
        zone = "Neutral-bearish (中性偏悲观)"
    else:
        zone = "Bearish (悲观区)"
    print(f"  Zone:  {zone}\n")

    # 3) Run both backtests and compare
    run_comparison()
