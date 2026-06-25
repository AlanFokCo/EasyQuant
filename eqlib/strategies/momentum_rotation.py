"""Multi-factor momentum rotation strategy.

Selects top-N stocks by composite factor score and rebalances daily.
Ideal for learning multi-stock portfolio management and factor investing.
"""
from eqlib import *


def initialize(context):
    """Strategy initialization."""
    g.stocks = [
        "601390",  # 中国中铁
        "600519",  # 贵州茅台
        "000858",  # 五粮液
        "002415",  # 海康威视
        "600036",  # 招商银行
        "000333",  # 美的集团
        "600276",  # 恒瑞医药
        "002594",  # 比亚迪
        "300750",  # 宁德时代
        "601012",  # 隆基绿能
    ]
    g.hold_count = 3
    g.lookback = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = g.stocks
    run_daily(rebalance, time="every_bar")
    log.info("Multi-factor momentum rotation initialized | pool=%d | hold=%d"
             % (len(g.stocks), g.hold_count))


def get_factor_score(stock, context):
    """Calculate composite factor score for a single stock."""
    try:
        hist = attribute_history(stock, g.lookback + 5, "1d", ["close", "volume"])
        if hist is None or len(hist) < g.lookback + 5:
            return -999

        closes = hist["close"]
        volumes = hist["volume"]

        momentum = (closes.iloc[-1] / closes.iloc[-g.lookback] - 1) * 100
        vol_recent = volumes.iloc[-5:].mean()
        vol_avg = volumes.mean()
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0
        volatility = closes.std() / closes.mean() * 100

        score = momentum * 0.6 + (vol_ratio - 1) * 20 * 0.2 + max(0, 10 - volatility) * 0.2
        return score
    except Exception as e:
        log.warn("Score calc failed for %s: %s" % (stock, str(e)))
        return -999


def rebalance(context):
    """Daily rebalancing: keep top-N stocks by factor score."""
    scores = {s: get_factor_score(s, context) for s in g.stocks}
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_stocks = [s[0] for s in sorted_stocks[:g.hold_count]]

    log.info("Top stocks: " + ", ".join(["%s=%.1f" % (s, scores[s]) for s in top_stocks]))

    current = set(context.portfolio.positions.keys())
    for s in current - set(top_stocks):
        order_target(s, 0)
        log.info("Sell %s (dropped from top %d)" % (s, g.hold_count))

    need_buy = [s for s in top_stocks if s not in current or context.portfolio.positions[s].amount == 0]
    if need_buy:
        cash_per = context.portfolio.available_cash / len(need_buy)
        for s in need_buy:
            order_value(s, cash_per)
            log.info("Buy %s | cash=%.0f" % (s, cash_per))


# Convenience: expose as a callable strategy object
momentum_rotation_strategy = {
    "name": "Multi-Factor Momentum Rotation",
    "initialize": initialize,
    "rebalance": rebalance,
}
