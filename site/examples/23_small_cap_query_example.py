"""Example 23: Small-cap stock selection with query API.

Demonstrates the query() / valuation / get_fundamentals() API
for fluent, chainable stock screening.

Strategy:
- Screen stocks by ascending market cap (smallest first)
- Buy the 3 smallest
- Hold 5 trading days, then rebalance
"""

from eqlib import *

# Set in ``__main__`` to the same list passed as ``securities=`` so OHLCV preload matches picks.
_BT_CANDIDATES: list[str] = []


def initialize(context):
    # 持仓数量
    g.stocknum = 3
    # 交易日计时器
    g.days = 0
    # 调仓频率
    g.refresh_rate = 5

    # 策略配置
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("order_volume_ratio", 1)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ), type="stock")

    run_daily(trade, time="every_bar")

    context.universe = []


def check_stocks(context):
    """选股：若已设置 ``_BT_CANDIDATES``（与预加载列表一致）则用之；否则用 query + 行情快照。

    query 路径：按流通市值（亿元）升序取最小的若干只（市值来自当前快照）。
    """
    import sys

    mod = sys.modules[__name__]
    cand = getattr(mod, "_BT_CANDIDATES", None) or []
    if cand:
        buylist = list(cand)[: g.stocknum]
        filtered = filter_paused_stocks(buylist, context)
        return filtered if filtered else buylist

    q = (
        query(
            valuation.code,
            valuation.market_cap,
        )
        .filter(
            valuation.market_cap > 0,
        )
        .order_by(
            valuation.market_cap.asc(),
        )
        .limit(g.stocknum)
    )

    df = get_fundamentals(q)
    if df.empty:
        return []

    buylist = list(df["code"])
    # 过滤停牌（若全部被滤掉则仍返回原始列表，便于示例在无成交量字段时仍能跑通）
    filtered = filter_paused_stocks(buylist, context)
    return filtered if filtered else buylist[: g.stocknum]


def trade(context):
    """每 5 个交易日调仓。"""
    if g.days % g.refresh_rate == 0:
        # 卖出所有持仓
        sell_list = list(context.portfolio.positions.keys())
        if len(sell_list) > 0:
            for stock in sell_list:
                order_target_value(stock, 0)

        # 分配资金
        if len(context.portfolio.positions) < g.stocknum:
            num = g.stocknum - len(context.portfolio.positions)
            cash = context.portfolio.available_cash / num
        else:
            cash = 0

        # 选股 & 买入
        stock_list = check_stocks(context)
        log.info("Selected: %s" % stock_list)

        for stock in stock_list:
            if len(context.portfolio.positions.keys()) < g.stocknum:
                order_value(stock, cash)

        g.days = 1
    else:
        g.days += 1


if __name__ == "__main__":
    import os

    # `get_fundamentals` uses live snapshot; pick codes once then preload OHLCV
    # so fills and attribute_history work in backtest.
    _q = (
        query(valuation.code, valuation.market_cap)
        .filter(valuation.market_cap > 0)
        .order_by(valuation.market_cap.asc())
        .limit(12)
    )
    _df = get_fundamentals(_q)
    if _df is not None and not _df.empty and "code" in _df.columns:
        _preload = [str(c) for c in _df["code"].tolist()]
    else:
        _preload = [
            "601390", "000630", "518880", "600036", "601088",
            "601857", "002594", "000768", "600536", "601111",
        ]

    os.makedirs("reports", exist_ok=True)

    import sys

    sys.modules[__name__]._BT_CANDIDATES = list(_preload)

    result = run_backtest(
        initialize,
        start_date="2024-01-01",
        end_date="2024-04-01",
        starting_cash=100000,
        securities=_preload,
        use_local=True,
    )

    if result is None:
        print("Backtest failed (no trading days or no data).")
        raise SystemExit(1)

    ctx = result["context"]
    print(f"\nFinal value: {ctx.portfolio.total_value:,.2f}")
    print(f"P&L: {ctx.portfolio.total_value - ctx.portfolio.starting_cash:,.2f}")
    print(f"Trades: {len(result['trade_log'])}")
