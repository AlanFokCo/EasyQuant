"""Example 18: Strategy Comparison — run multiple strategies on the same stock.

Demonstrates how to compare different strategies side by side on
the same stock and period, so you can objectively evaluate which
approach works best.

Strategies compared:
  1. Buy & Hold (baseline)
  2. MA Crossover (trend following)
  3. RSI Mean Reversion (counter-trend)
  4. Bollinger Band (mean reversion with bands)

Usage:
    python examples/18_strategy_comparison.py
"""

from eqlib import *
from eqlib import utils


# ============================================================
# Common parameters
# ============================================================

SECURITY = "002594"
START_DATE = "2024-01-01"
END_DATE = "2025-01-01"
STARTING_CASH = 100000
BENCHMARK = "000300.XSHG"


# ============================================================
# Strategy 1: Buy & Hold (baseline)
# ============================================================

def bh_init(context):
    g.sec = SECURITY
    set_benchmark(BENCHMARK)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))
    context.universe = [SECURITY]
    g.done = False
    run_daily(bh_handle, time="every_bar")


def bh_handle(context):
    if not g.done:
        order_value(g.sec, context.portfolio.available_cash)
        log.info("Buy&Hold: BUY %s" % g.sec)
        g.done = True
    record(total_value=context.portfolio.total_value)


# ============================================================
# Strategy 2: MA Crossover
# ============================================================

def ma_init(context):
    g.sec = SECURITY
    g.fast = 5
    g.slow = 20
    set_benchmark(BENCHMARK)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))
    context.universe = [SECURITY]
    run_daily(ma_handle, time="every_bar")


def ma_handle(context):
    hist = attribute_history(g.sec, g.slow + 10, "1d", ["close"])
    if hist.empty or len(hist) < g.slow:
        return
    price = hist["close"].iloc[-1]
    fast_ma = hist["close"].tail(g.fast).mean()
    slow_ma = hist["close"].tail(g.slow).mean()
    prev_fast = hist["close"].tail(g.fast + 1).head(g.fast).mean()
    prev_slow = hist["close"].tail(g.slow + 1).head(g.slow).mean()

    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if g.sec not in context.portfolio.positions or \
           context.portfolio.positions[g.sec].amount == 0:
            order_value(g.sec, context.portfolio.available_cash)
            log.info("MACross: BUY %s @ %.3f" % (g.sec, price))
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if g.sec in context.portfolio.positions and \
           context.portfolio.positions[g.sec].amount > 0:
            order_target(g.sec, 0)
            log.info("MACross: SELL %s @ %.3f" % (g.sec, price))

    record(price=price, fast_ma=fast_ma, slow_ma=slow_ma)


# ============================================================
# Strategy 3: RSI Mean Reversion
# ============================================================

def rsi_init(context):
    g.sec = SECURITY
    g.period = 14
    g.oversold = 30
    g.overbought = 70
    set_benchmark(BENCHMARK)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))
    context.universe = [SECURITY]
    run_daily(rsi_handle, time="every_bar")


def rsi_handle(context):
    hist = attribute_history(g.sec, g.period + 10, "1d", ["close"])
    if hist.empty or len(hist) < g.period + 1:
        return
    price = hist["close"].iloc[-1]

    delta = hist["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.tail(g.period).mean()
    avg_loss = loss.tail(g.period).mean()
    rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    if rsi < g.oversold:
        if g.sec not in context.portfolio.positions or \
           context.portfolio.positions[g.sec].amount == 0:
            order_value(g.sec, context.portfolio.available_cash * 0.9)
            log.info("RSI: BUY %s @ %.3f, RSI=%.1f" % (g.sec, price, rsi))
    elif rsi > g.overbought:
        if g.sec in context.portfolio.positions and \
           context.portfolio.positions[g.sec].amount > 0:
            order_target(g.sec, 0)
            log.info("RSI: SELL %s @ %.3f, RSI=%.1f" % (g.sec, price, rsi))

    record(price=price, rsi=rsi)


# ============================================================
# Strategy 4: Bollinger Band
# ============================================================

def boll_init(context):
    g.sec = SECURITY
    g.period = 20
    g.std = 2.0
    set_benchmark(BENCHMARK)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))
    context.universe = [SECURITY]
    run_daily(boll_handle, time="every_bar")


def boll_handle(context):
    hist = attribute_history(g.sec, g.period + 10, "1d", ["close"])
    if hist.empty or len(hist) < g.period:
        return
    price = hist["close"].iloc[-1]
    upper, mid, lower = utils.boll(hist["close"], period=g.period, num_std=g.std)

    if price < lower.iloc[-1]:
        if g.sec not in context.portfolio.positions or \
           context.portfolio.positions[g.sec].amount == 0:
            order_value(g.sec, context.portfolio.available_cash)
            log.info("Boll: BUY %s @ %.3f" % (g.sec, price))
    elif price > upper.iloc[-1]:
        if g.sec in context.portfolio.positions and \
           context.portfolio.positions[g.sec].amount > 0:
            order_target(g.sec, 0)
            log.info("Boll: SELL %s @ %.3f" % (g.sec, price))

    record(price=price, upper=upper.iloc[-1], lower=lower.iloc[-1])


# ============================================================
# Runner and comparison
# ============================================================

def run_strategy_quiet(init_func, label):
    """Run a strategy and return its result metrics."""
    from eqlib.engine import run_backtest

    result = run_backtest(
        init_func,
        start_date=_parse_date(START_DATE),
        end_date=_parse_date(END_DATE),
        starting_cash=STARTING_CASH,
        benchmark=BENCHMARK,
        securities=[SECURITY],
        use_local=True,
    )

    if result is None:
        return None

    ctx = result["context"]
    metrics = analyze_returns(result, risk_free_rate=0.03)
    if not metrics:
        return {
            "label": label,
            "final_value": ctx.portfolio.total_value,
            "pnl_pct": (ctx.portfolio.total_value - STARTING_CASH) / STARTING_CASH * 100,
            "sharpe": 0.0,
            "max_dd": 0.0,
            "trades": len(result["trade_log"]),
            "win_rate": 0.0,
        }
    trades = len(result["trade_log"])
    pnl_pct = (ctx.portfolio.total_value - STARTING_CASH) / STARTING_CASH * 100

    return {
        "label": label,
        "final_value": ctx.portfolio.total_value,
        "pnl_pct": pnl_pct,
        "sharpe": metrics["sharpe_ratio"],
        "max_dd": abs(metrics["max_drawdown"]) * 100,
        "trades": trades,
        "win_rate": metrics["win_rate"] * 100,
    }


def _parse_date(d):
    import datetime
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    return d


if __name__ == "__main__":
    print("=" * 60)
    print("Strategy Comparison")
    print("Stock: %s  |  Period: %s to %s" % (SECURITY, START_DATE, END_DATE))
    print("=" * 60)
    print()

    strategies = [
        ("Buy & Hold",      bh_init),
        ("MA Crossover",    ma_init),
        ("RSI Mean Revert", rsi_init),
        ("Bollinger Band",  boll_init),
    ]

    results = []
    for label, init_fn in strategies:
        print("Running: %s ..." % label)
        r = run_strategy_quiet(init_fn, label)
        if r:
            results.append(r)
            print("  -> P&L: %+.2f%%, Sharpe: %.2f, MaxDD: %.1f%%" % (
                r["pnl_pct"], r["sharpe"], r["max_dd"]))

    # Print comparison table
    print()
    print("=" * 78)
    print("%-18s %12s %10s %10s %10s %8s %10s" % (
        "Strategy", "Final Value", "Return%", "Sharpe", "MaxDD%", "Trades", "WinRate%"))
    print("-" * 78)

    # Sort by Sharpe, highest first
    results.sort(key=lambda r: r["sharpe"], reverse=True)
    for r in results:
        print("%-18s %12.2f %+10.2f %10.2f %10.1f %8d %10.1f" % (
            r["label"], r["final_value"], r["pnl_pct"],
            r["sharpe"], r["max_dd"], r["trades"], r["win_rate"]))
    print("=" * 78)
