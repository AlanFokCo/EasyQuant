# Tutorial 06: 行业轮动策略

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 理解 A 股行业轮动现象，并用 `eqlib` 行业 API 实现动量轮动示例 |
    | **预计用时** | 约 90 分钟 |
    | **前置** | [Tutorial 01](01-first-strategy.md)；行业 API 见 [API 参考](../reference/index.md) |

> A 股市场有一个显著特点：资金不会同时追捧所有板块，而是在不同行业之间"轮流炒作"。理解和利用这一规律，可以构建超越大盘的行业轮动策略。

**行业 / 指数 API：** [API 参考](../reference/index.md)

---

## 目录

1. [什么是行业轮动](#1-什么是行业轮动)
2. [A 股行业轮动的特点](#2-a-股行业轮动的特点)
3. [数据基础：eqlib 的行业 API](#3-数据基础eqlib-的行业-api)
4. [策略设计：动量轮动](#4-策略设计动量轮动)
5. [编写行业轮动策略](#5-编写行业轮动策略)
6. [进阶：多维度行业评分](#6-进阶多维度行业评分)
7. [轮动策略的风险与陷阱](#7-轮动策略的风险与陷阱)
8. [指数成分股轮动](#8-指数成分股轮动)
9. [下一步](#9-下一步)

---

## 1. 什么是行业轮动

**行业轮动（Sector Rotation）** 是指在不同行业/板块之间动态切换持仓，当前最强势的行业进行加仓，即将走弱的行业进行减仓或清仓。

### 1.1 核心逻辑

```
识别当前强势板块
      ↓
买入该板块的代表股票
      ↓
持有到强势信号消失
      ↓
切换到下一个强势板块
```

### 1.2 为什么行业轮动有效

1. **资金流动是有迹可循的**：机构资金从一个估值过高的板块流出后，会进入下一个低估板块，这个过程通常要持续数周到数月
2. **动量效应**：短期内表现好的板块，往往还会继续表现好（趋势延续）
3. **相关性分散**：不同行业受不同宏观因素驱动，同时持有多行业可以降低相关性

### 1.3 与单股策略的对比

| | 单股策略 | 行业轮动策略 |
|--|---------|------------|
| **风险集中度** | 高（依赖单只股票） | 低（分散到多行业） |
| **Alpha 来源** | 个股选择 | 行业配置 |
| **换手频率** | 取决于策略 | 通常每周/每月 |
| **数据需求** | 单只股票历史 | 行业成分股数据 |

---

## 2. A 股行业轮动的特点

### 2.1 政策驱动

A 股的行业轮动很大程度上受**政策**驱动：
- 新能源政策 → 新能源、储能、锂电板块轮动
- 科技自主 → 半导体、软件、国产替代
- 消费刺激 → 白酒、消费电子、零售
- 金融政策 → 银行、保险、券商

### 2.2 主要 A 股行业板块

```python
# 常见大类行业（eqlib 返回的行业名称）
行业 = [
    '银行',        # 工商银行、招商银行
    '白酒',        # 茅台、五粮液
    '新能源',      # 宁德时代、比亚迪
    '半导体',      # 中芯国际、北方华创
    '医药',        # 恒瑞医药、迈瑞医疗
    '房地产',      # 万科、保利
    '保险',        # 中国平安、太保
    '证券',        # 中信证券、国泰君安
    '家电',        # 美的、格力
    '有色金属',    # 紫金矿业、中国铝业
]
```

### 2.3 轮动规律（参考）

```
经济复苏期：金融（银行/保险）→ 消费 → 科技
经济过热期：原材料 → 能源 → 工业
经济衰退期：医疗 → 公用事业 → 必需消费品
```

> ⚠️ 注意：这些规律来源于美股历史研究，在 A 股的适用性有限。A 股政策因素更强，不要机械套用。

---

## 3. 数据基础：eqlib 的行业 API

### 3.1 获取行业列表

```python
from eqlib import get_industry_list

# 获取所有行业板块名称
industries = get_industry_list()
print(industries[:10])
# 输出：['白酒', '银行', '新能源', '半导体', '医药', ...]
```

### 3.2 获取行业成分股及行情

```python
from eqlib import get_industry_stocks

# 获取白酒行业所有股票的行情数据
whitewine_df = get_industry_stocks('白酒')
print(whitewine_df.columns.tolist())
# 输出：['code', 'name', 'price', 'pct_change', 'pe', 'pb', 'total_value', ...]

# 查看涨幅排名
whitewine_df_sorted = whitewine_df.sort_values('pct_change', ascending=False)
print(whitewine_df_sorted[['name', 'price', 'pct_change']].head())
```

### 3.3 查询单股所属行业

```python
from eqlib import get_industry

# 查询工商银行的行业
info = get_industry('601390')
print(info)
# 输出：{'code': '601390', 'name': '工商银行', 'industry': '银行'}
```

### 3.4 查询行业历史价格

行业没有直接的"行业指数"价格，通常用行业内**前 N 大市值股票的等权平均收益**来代表行业表现：

```python
from eqlib import get_industry_stocks, attribute_history
import pandas as pd

def get_industry_return(industry_name, lookback=20):
    """计算行业近 N 日平均收益率。"""
    df = get_industry_stocks(industry_name)
    if df is None or df.empty:
        return 0.0

    # 取市值最大的前 5 只股票作为代表
    top_stocks = df.nlargest(5, 'total_value')['code'].tolist()

    returns = []
    for code in top_stocks:
        hist = attribute_history(code, lookback + 5, '1d', ['close'])
        if hist.empty or len(hist) < lookback:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-lookback]) - 1
        returns.append(ret)

    return sum(returns) / len(returns) if returns else 0.0


# 计算各行业近 20 日收益率
industries = ['银行', '白酒', '新能源', '医药', '家电']
for ind in industries:
    ret = get_industry_return(ind, 20)
    print('%-10s: %.2f%%' % (ind, ret * 100))
```

---

## 4. 策略设计：动量轮动

### 策略规则

最简单的行业轮动策略基于**动量因子**：近期涨得最多的行业，继续持有；涨得少或跌的行业，清仓换股。

| 步骤 | 操作 |
|------|------|
| 1. 定期评分 | 每周一，计算候选行业内代表股票的近 20 日收益率 |
| 2. 排名选择 | 选出收益率最高的 Top N 行业 |
| 3. 调仓 | 卖出不在 Top N 的持仓，等权买入 Top N 的代表股票 |
| 4. 循环 | 下周再次评分、调仓 |

### 参数说明

```python
INDUSTRY_POOL = [...]    # 候选行业列表
TOP_N         = 3        # 每次持有 Top N 个行业
LOOKBACK      = 20       # 动量计算回看期（交易日）
REBALANCE_DAY = 0        # 调仓日：0=周一
```

---

## 5. 编写行业轮动策略

```python
from eqlib import *

# ========== 策略参数（模块级常量，引擎不会清除） ==========
# 候选行业（每个行业选最大市值的代表股票）
INDUSTRY_POOL = ['银行', '白酒', '新能源', '医药', '家电', '保险']
TOP_N         = 2        # 持有排名前 2 的行业
LOOKBACK      = 20       # 近 20 个交易日的收益率


def get_industry_representative(industry_name):
    """获取行业市值最大的股票代码。"""
    df = get_industry_stocks(industry_name)
    if df is None or df.empty:
        return None
    top = df.nlargest(1, 'total_value')
    return top['code'].iloc[0] if not top.empty else None


def score_industries(context):
    """
    对所有候选行业打分，返回 list[(行业名称, 代表股票代码, 近期收益率)]，
    按收益率从高到低排序。
    """
    scored = []
    for ind in INDUSTRY_POOL:
        code = get_industry_representative(ind)
        if code is None:
            continue
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scored.append((ind, code, ret))
        log.info('行业评分: %-8s %s ret=%.2f%%' % (ind, code, ret * 100))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5,
    ))
    # 每周一调仓
    run_weekly(rebalance, day_of_week=0, time='every_bar')
    log.info('行业轮动策略初始化: 行业=%d, 持有Top%d' % (
        len(INDUSTRY_POOL), TOP_N))


def rebalance(context):
    """每周一重新评分并调仓。"""
    # 1. 对所有行业打分
    scored = score_industries(context)
    if not scored:
        log.warn('所有行业数据获取失败，跳过本次调仓')
        return

    # 2. 选出 Top N 行业的代表股票
    top_stocks = [code for _, code, _ in scored[:TOP_N]]
    log.info('本周持仓目标: %s' % str(top_stocks))

    # 3. 卖出不在 Top N 的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)
            log.info('清仓 %s（不在本周 Top%d）' % (sec, TOP_N))

    # 4. 等权买入 Top N 的代表股票
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        target_value = context.portfolio.total_value * weight
        order_target_value(sec, target_value)
        log.info('调仓 %s，目标市值=%.0f' % (sec, target_value))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=200000,
        benchmark='000300.XSHG',
        report_dir='reports',
    )
```

> **注意：** `get_industry_stocks()` 和 `get_industry_representative()` 需要实时网络访问。如果回测报错，请确保网络连通，或把行业代表股票改为手动固定列表（见下文）。

### 5.1 使用固定股票池（更稳定的回测方案）

当行业数据接口不稳定，或者希望使用确定的历史数据回测时，可以用固定股票池代替动态行业查询：

```python
# 每个行业选 1-2 只代表性股票（模块级常量，引擎不会清除）
INDUSTRY_STOCKS = {
    '银行':   '601390',   # 工商银行
    '白酒':   '600519',   # 贵州茅台
    '新能源': '300750',   # 宁德时代
    '医药':   '600276',   # 恒瑞医药
    '家电':   '000333',   # 美的集团
    '保险':   '601318',   # 中国平安
}


def score_industries_fixed(context):
    """使用固定股票池评分行业动量。"""
    scored = []
    for ind, code in INDUSTRY_STOCKS.items():
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scored.append((ind, code, ret))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

---

## 6. 进阶：多维度行业评分

仅用价格动量打分过于单一，结合多个维度可以提升策略稳健性。

### 6.1 综合评分因子

```python
def score_industries_multi(context, industry_stocks):
    """
    多维度行业评分：
    - 短期动量（近 10 日收益）权重 40%
    - 中期动量（近 20 日收益）权重 40%
    - 成交量增量（近 5 日均量 / 近 20 日均量）权重 20%
    """
    from eqlib import utils
    scored = []

    for ind, code in industry_stocks.items():
        hist = attribute_history(code, 30, '1d', ['close', 'volume'])
        if hist.empty or len(hist) < 25:
            continue

        close = hist['close']
        vol   = hist['volume']

        # 短期动量（10 日）
        ret_short = (close.iloc[-1] / close.iloc[-10]) - 1

        # 中期动量（20 日）
        ret_mid = (close.iloc[-1] / close.iloc[-20]) - 1

        # 成交量比值
        avg_vol_5  = vol.tail(5).mean()
        avg_vol_20 = vol.tail(20).mean()
        vol_ratio  = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # 综合打分
        score = ret_short * 0.4 + ret_mid * 0.4 + (vol_ratio - 1) * 0.2

        scored.append((ind, code, score))
        log.info('行业打分: %-8s %s score=%.4f (s=%.2f%%, m=%.2f%%, vol=%.2f)' % (
            ind, code, score, ret_short*100, ret_mid*100, vol_ratio))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

### 6.2 加入行业估值过滤

避免买入估值严重偏高的行业（泡沫风险）：

```python
def score_industries_with_valuation(context, industry_stocks):
    """估值过滤：PE 超过 50 的行业不纳入候选。"""
    from eqlib import get_valuation
    scored = []

    for ind, code in industry_stocks.items():
        # 检查估值
        val = get_valuation(code)
        if val and val.get('pe') and val['pe'] > 50:
            log.info('跳过 %s（%s）：PE=%.1f 过高' % (ind, code, val['pe']))
            continue

        hist = attribute_history(code, 25, '1d', ['close'])
        if hist.empty or len(hist) < 20:
            continue

        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-20]) - 1
        scored.append((ind, code, ret))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

---

## 7. 轮动策略的风险与陷阱

### 7.1 追高买入的风险

行业轮动策略本质上是**动量追高**。当行业已经涨了很多，买入时恰逢见顶，下一周就开始下跌：

```
行业收益排名:
  第 1 周：新能源 +15%，白酒 +8%  → 买新能源
  第 2 周：新能源 -12%，白酒 +5%  → 已经入套了
```

**应对方法：**
- 设置单股止损（如 -8%）
- 使用更长的动量周期（如 60 日而非 20 日）
- 控制单个行业仓位不超过 40%

### 7.2 换手率与手续费

每周调仓意味着每年有 50+ 次交易。手续费会显著侵蚀收益：

```python
# 估算年化手续费成本
trades_per_year = 52    # 每周换仓一次
avg_trade_value = 50000  # 平均每笔交易金额
commission_rate = 0.0006  # 往返佣金（买 0.03% + 卖 0.03% + 卖印花税 0.1%）

annual_cost = trades_per_year * avg_trade_value * commission_rate

# 100000 是假设的初始资金，用来计算年化成本占总资金的百分比
base_capital = 100000  # 假设初始资金 10 万元
print('预计年化手续费: %.0f 元 (%.2f%%)' % (
    annual_cost, annual_cost / base_capital * 100))
# 输出: 预计年化手续费: 1560 元 (1.56%)
```

**应对方法：** 每月而非每周调仓，减少换手率。

### 7.3 行业数据延迟

`get_industry_stocks()` 返回的是当前快照数据，在回测时并不代表历史上该日期的数据。严格意义上，这引入了一定的未来信息。

**应对方法：** 改用固定股票池（如上面的 `g.industry_stocks` 字典），用已知的代表股票替代动态行业查询，确保回测结果可靠。

---

## 8. 指数成分股轮动

除了按行业轮动，也可以基于**指数成分股**做动量轮动，在沪深 300 或中证 500 的成分股中选最强的 Top N。

```python
from eqlib import *

# 模块级常量（引擎不会清除）
INDEX_CODE = '000300'   # 沪深 300
TOP_N      = 5          # 持有 Top 5
LOOKBACK   = 20
MAX_STOCKS = 30         # 从成分股中取前 30 只作为候选（避免数据量过大）


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5,
    ))

    # 构建候选股票池：沪深 300 前 30 大成分股
    index_df = get_index_stocks(INDEX_CODE)
    if not index_df.empty:
        context.universe = index_df['code'].head(MAX_STOCKS).tolist()
        log.info('候选池: %d 只成分股' % len(context.universe))

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def rebalance(context):
    universe = getattr(context, 'universe', [])
    if not universe:
        return

    # 计算所有候选股的近期收益
    scores = {}
    for code in universe:
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scores[code] = ret

    if not scores:
        return

    # 选出 Top N
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_stocks = [code for code, _ in ranked[:TOP_N]]
    log.info('本周目标: %s' % str(top_stocks))

    # 卖出离场股票
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)

    # 等权买入 Top N
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        order_target_value(sec, context.portfolio.total_value * weight)


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=500000,
        benchmark='000300.XSHG',
        securities=None,   # 不预加载，因为股票池是动态确定的
        report_dir='reports',
    )
```

相关参考示例：[Example 10: 指数与概念策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py)

---

## 9. 下一步

掌握行业轮动后，下一步可以：

- **[Tutorial 07: 多因子选股](07-multi-factor.md)** — 在固定股票池内，用多个因子打分，选出最优标的
- **[Tutorial 03: 策略优化与改进](03-optimization.md)** — 参数调优（轮动周期、持仓数量）、组合优化
- **[Example 10: 指数与概念策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py)** — 指数成分股轮动的完整代码
- **[Example 16: 多因子选股策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/16_multi_factor_strategy.py)** — 多因子方法的完整代码

### 练习

1. 将调仓频率从每周改为每月（`run_monthly`），对比换手率和收益的变化
2. 修改 `TOP_N = 3`，观察持有更多行业时的分散效果
3. 加入估值过滤（PE < 50），观察是否能提升风险调整后的收益
4. 在固定股票池中，将行业代表股从市值最大改为你自己选择的股票，对比结果
