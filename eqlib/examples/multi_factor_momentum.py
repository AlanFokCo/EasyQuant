"""多因子动量轮动策略 — 在 Web Studio 中编辑并运行回测.

策略思路：
1. 选取 10 只 A 股热门股票作为股票池
2. 每日计算每只股票的动量得分（收益率 + 成交量放大 + 波动率）
3. 按得分排序，持有得分最高的前 3 只
4. 不在前 3 的卖出，新进入前 3 的买入（等权分配资金）

适合学习：多股票管理、因子打分、定期轮动、风险控制
"""
from eqlib import *


def initialize(context):
    """策略初始化：设置股票池、参数、交易规则."""
    # 股票池：10 只热门 A 股（覆盖不同行业）
    g.stocks = [
        "601390",  # 中国中铁（基建）
        "600519",  # 贵州茅台（白酒）
        "000858",  # 五粮液（白酒）
        "002415",  # 海康威视（安防）
        "600036",  # 招商银行（银行）
        "000333",  # 美的集团（家电）
        "600276",  # 恒瑞医药（医药）
        "002594",  # 比亚迪（汽车）
        "300750",  # 宁德时代（新能源）
        "601012",  # 隆基绿能（光伏）
    ]

    g.hold_count = 3  # 每天持有得分最高的前 3 只
    g.lookback = 20   # 动量计算回看天数

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = g.stocks
    run_daily(rebalance, time="every_bar")

    log.info("多因子动量轮动策略初始化完成 | 股票池=%d只 | 每日持仓=%d只" % (len(g.stocks), g.hold_count))


def get_factor_score(stock, context):
    """计算单只股票的多因子综合得分.

    因子组成：
    - 动量因子：20 日收益率（越高越好）
    - 成交量因子：近 5 日平均成交量 / 20 日平均成交量（放量越好）
    - 波动率因子：近 20 日收盘价标准差（越低越好， penalize 高波动）
    """
    try:
        hist = attribute_history(stock, g.lookback + 5, "1d", ["close", "volume"])
        if hist is None or len(hist) < g.lookback + 5:
            return -999  # 数据不足

        closes = hist["close"]
        volumes = hist["volume"]

        # 动量因子：20 日收益率 (%)
        momentum = (closes.iloc[-1] / closes.iloc[-g.lookback] - 1) * 100

        # 成交量因子：近期放量倍数
        vol_recent = volumes.iloc[-5:].mean()
        vol_avg = volumes.mean()
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0

        # 波动率因子：20 日标准差（越低越好）
        volatility = closes.std() / closes.mean() * 100  # 变异系数

        # 综合得分 = 动量 * 0.6 + 成交量因子 * 5 * 0.2 + (10 - 波动率) * 0.2
        score = momentum * 0.6 + (vol_ratio - 1) * 20 * 0.2 + max(0, 10 - volatility) * 0.2

        return score

    except Exception as e:
        log.warn("计算 %s 因子得分失败: %s" % (stock, str(e)))
        return -999


def rebalance(context):
    """每日轮动：计算所有股票因子得分，调仓到 Top N."""
    # 1. 计算所有股票得分
    scores = {}
    for stock in g.stocks:
        scores[stock] = get_factor_score(stock, context)

    # 2. 排序并选出 Top N
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_stocks = [s[0] for s in sorted_stocks[:g.hold_count]]

    log.info("=== 今日因子排名 ===")
    for i, (stock, score) in enumerate(sorted_stocks[:5], 1):
        log.info("  #%d %s | score=%.2f" % (i, stock, score))

    # 3. 卖出不在 Top N 的股票
    current_positions = set(context.portfolio.positions.keys())
    for stock in current_positions:
        if stock not in top_stocks:
            order_target(stock, 0)
            log.info("卖出 %s（排名下降）" % stock)

    # 4. 买入新进入 Top N 的股票（等权分配可用资金）
    if top_stocks:
        # 计算需要新买入的股票（当前未持仓或在 Top N 中但持仓为 0）
        need_buy = [s for s in top_stocks if s not in current_positions]
        if need_buy:
            # 等权分配可用资金
            cash_per_stock = context.portfolio.available_cash / len(need_buy)
            for stock in need_buy:
                order_value(stock, cash_per_stock)
                log.info("买入 %s | 分配资金=%.2f" % (stock, cash_per_stock))

    # 记录当前持仓信息
    total_value = context.portfolio.available_cash
    for stock in top_stocks:
        if stock in context.portfolio.positions:
            total_value += context.portfolio.positions[stock].total_value

    log.info("当前持仓: %s | 总资产=%.2f" % (str(list(top_stocks)), total_value))
