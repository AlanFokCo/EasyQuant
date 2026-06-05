# Tutorial 07: 多因子选股

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 掌握多因子打分、标准化与组合，理解机构常用选股流程 |
    | **预计用时** | 约 90～120 分钟 |
    | **前置** | [Tutorial 06](06-sector-rotation.md)；链式选股见 [选股 API 参考](../reference/api-selection.md) 第 3.14 节 |

> 多因子选股是机构量化基金最常用的方法之一。它不依赖单一指标，而是从价格、财务、情绪等多个维度综合评分，系统性地找出"性价比最高"的股票。

**选股 API：** [选股 API 参考](../reference/api-selection.md) 第 3.14 节（链式选股）、第 11 章（`MultiFactorSelector`）

---

## 目录

1. [什么是因子选股](#1-什么是因子选股)
2. [常见因子类型](#2-常见因子类型)
3. [A 股特色因子](#3-a-股特色因子)
4. [因子构建基础](#4-因子构建基础)
5. [三因子模型：动量 + 成交量 + 价格](#5-三因子模型动量--成交量--价格)
6. [加入财务因子](#6-加入财务因子)
7. [因子标准化与合成](#7-因子标准化与合成)
8. [完整的多因子策略](#8-完整的多因子策略)
9. [因子有效性检验](#9-因子有效性检验)
10. [多因子选股的局限性](#10-多因子选股的局限性)
11. [下一步](#11-下一步)

---

## 1. 什么是因子选股

**因子（Factor）** 是可以用来预测股票未来收益的数量化特征。

举例：
- "过去一个月涨得最多的股票，下个月大概率继续涨"——这是**动量因子**
- "PE 最低的股票，长期来看更容易上涨"——这是**价值因子**
- "ROE 最高的公司，盈利能力强，适合长期持有"——这是**质量因子**

**多因子选股**的核心是：不依赖单一因子，而是综合多个因子打分，选出综合得分最高的股票组合。

```
股票池（100只）
    ↓
动量因子打分 → Z-Score 标准化
成交量因子打分 → Z-Score 标准化
价值因子打分 → Z-Score 标准化
    ↓
合成总分 = 因子1×权重1 + 因子2×权重2 + 因子3×权重3
    ↓
按总分排名，选前 N 名买入
```

---

## 2. 常见因子类型

### 2.1 技术类因子

| 因子名称 | 定义 | 特点 |
|----------|------|------|
| **动量因子** | 过去 N 日收益率 | 短期趋势延续 |
| **反转因子** | 过去 5 日收益率的负值 | 短期超涨超跌修复 |
| **波动率因子** | 过去 N 日收益率的标准差 | 低波动溢价 |
| **成交量因子** | 近期成交量 / 历史均量 | 资金关注度 |
| **均线排列** | 价格 / MA 的比值 | 趋势强度 |

### 2.2 财务类因子

| 因子名称 | 定义 | 特点 |
|----------|------|------|
| **价值因子** | 1 / PE（市盈率倒数） | 低估股票更安全 |
| **市净率** | 1 / PB | 资产价值修复 |
| **质量因子** | ROE（净资产收益率） | 盈利能力 |
| **成长因子** | 营收增速 / 利润增速 | 未来潜力 |

### 2.3 因子的使用原则

1. **因子要有经济学逻辑**：不能只是因为历史数据好就用，要能解释为什么有效
2. **因子不能太相关**：用 PE 和 PB 同时打分，意义不大（高度相关）
3. **不同市场环境，因子有效性不同**：动量在牛市有效，价值在熊市有效

---

## 3. A 股特色因子

A 股市场有一些独特的市场特征，可以构建特有的因子来捕捉超额收益。本节介绍两个典型的 A 股特色因子：北向资金流因子（情绪因子）和限售解禁因子（风险因子）。

### 3.1 北向资金流因子（情绪因子）

北向资金指通过沪股通和深股通进入 A 股市场的外资。由于北向资金通常被视为"聪明钱"，其流向对市场情绪有较强的预测能力。

**经济含义：**

- 北向资金持续净流入 → 外资看好 A 股 → 市场情绪偏乐观
- 北向资金持续净流出 → 外资看淡 A 股 → 市场情绪偏悲观

**因子构建示例：**

```python
from eqlib import get_north_money_flow

def compute_north_money_factor(lookback_days=5):
    """
    北向资金流因子：近 N 日北向资金净流入占比。

    返回:
        float: 净流入占成交额比例，正值表示净流入
    """
    df = get_north_money_flow(days=lookback_days)
    if df is None or df.empty:
        return None

    # 计算累计净流入
    total_net_inflow = df['north_net'].sum()
    total_turnover = df['north_money'].sum()  # 总成交额

    if total_turnover == 0:
        return None

    # 净流入比例
    net_ratio = total_net_inflow / total_turnover
    return net_ratio


def compute_north_momentum_factor(lookback_days=10):
    """
    北向资金动量因子：近 N 日北向资金净流入趋势。

    通过线性回归计算净流入趋势斜率。
    """
    import numpy as np

    df = get_north_money_flow(days=lookback_days)
    if df is None or len(df) < lookback_days:
        return None

    # 净流入序列
    net_flows = df['north_net'].values

    # 简单线性回归计算趋势
    x = np.arange(len(net_flows))
    y = net_flows

    # 斜率 = Cov(x, y) / Var(x)
    cov_xy = np.cov(x, y, ddof=0)[0, 1]
    var_x = np.var(x, ddof=0)

    if var_x == 0:
        return None

    slope = cov_xy / var_x
    return slope
```

**使用场景：**

1. **作为大盘择时信号**：当北向资金连续 3 日净流出且金额较大时，降低仓位
2. **作为情绪因子**：与其他因子组合，给北向资金净流入股票加分

**因子权重建议：** 5%-10%（情绪因子波动较大，不宜过高）

### 3.2 限售解禁因子（风险因子）

限售股解禁是指原本不能在二级市场流通的股票变为可流通，通常会带来抛售压力。解禁因子主要用于风险规避。

**经济含义：**

- 大量限售股解禁 → 潜在抛售压力 → 股价可能下跌
- 解禁市值占总市值比例越高，影响越大

**因子构建示例：**

```python
from eqlib import get_restriction_release
import datetime

def compute_restriction_risk_factor(code, lookforward_days=30):
    """
    限售解禁风险因子：未来 N 日内的解禁压力评分。

    返回:
        float: 解禁风险评分，越高表示风险越大
              0 表示无解禁或解禁影响可忽略
    """
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=lookforward_days)

    df = get_restriction_release(
        code=code,
        start_date=today.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )

    if df is None or df.empty:
        return 0.0  # 无解禁计划

    # 计算解禁市值
    total_release_value = df['release_value'].sum()

    # 获取当前市值
    from eqlib import get_valuation
    val = get_valuation(code)
    if val is None:
        return 0.0

    market_cap = val.get('market_cap', 0)
    if market_cap <= 0:
        return 0.0

    # 解禁比例 = 解禁市值 / 当前市值
    release_ratio = total_release_value / market_cap

    # 转换为风险评分（0-1，解禁比例超过 10% 视为高风险）
    risk_score = min(release_ratio / 0.10, 1.0)
    return risk_score


def filter_stocks_by_restriction(stock_pool, lookforward_days=30, threshold=0.05):
    """
    过滤即将解禁的股票。

    参数:
        stock_pool: 股票代码列表
        lookforward_days: 前瞻天数
        threshold: 解禁比例阈值，超过则过滤

    返回:
        list: 过滤后的股票列表
    """
    filtered = []
    for code in stock_pool:
        risk = compute_restriction_risk_factor(code, lookforward_days)
        if risk < threshold:
            filtered.append(code)
        else:
            log.info(f'{code} 解禁风险过高 ({risk:.2%})，已过滤')
    return filtered
```

**使用场景：**

1. **股票池过滤**：在选股前排除即将有大比例解禁的股票
2. **风险因子**：作为负向因子，解禁风险高的股票得分低
3. **持仓监控**：对已持仓股票监控解禁计划，提前减仓

**注意事项：**

- 解禁因子应在选股前使用，而非与其他因子标准化后合成
- 解禁市值数据可能存在延迟，建议结合公告信息交叉验证

### 3.3 A 股特色因子组合示例

将北向资金因子与限售解禁因子结合，可以构建 A 股特有的"聪明钱+风险过滤"策略：

```python
def a_share_stock_selection(base_scores, stock_pool):
    """
    A 股特色选股：基础因子 + 北向资金加成 + 解禁风险过滤。

    参数:
        base_scores: 基础多因子得分字典 {code: score}
        stock_pool: 股票池

    返回:
        dict: 调整后的最终得分
    """
    # Step 1: 解禁风险过滤
    filtered_stocks = filter_stocks_by_restriction(
        stock_pool,
        lookforward_days=30,
        threshold=0.05
    )

    # Step 2: 北向资金情绪因子
    north_factor = compute_north_money_factor(lookback_days=5)

    # Step 3: 调整得分
    final_scores = {}
    for code in filtered_stocks:
        if code not in base_scores:
            continue

        # 基础得分
        score = base_scores[code]

        # 根据北向资金流向调整仓位权重（不做个股区分）
        # 北向资金净流入时，整体提高得分
        if north_factor and north_factor > 0:
            score *= (1 + north_factor * 0.5)  # 弱调整

        final_scores[code] = score

    return final_scores
```

---

## 4. 因子构建基础

在 EasyQuant 中，因子通常用 `attribute_history` 获取历史数据，然后计算得出：

```python
from eqlib import attribute_history, get_valuation
from eqlib import utils

def compute_momentum(code, period=20):
    """动量因子：过去 N 日收益率。"""
    hist = attribute_history(code, period + 5, '1d', ['close'])
    if hist.empty or len(hist) < period:
        return None
    return (hist['close'].iloc[-1] / hist['close'].iloc[-period]) - 1


def compute_volatility(code, period=20):
    """波动率因子：过去 N 日日收益率的标准差（低波动为好，取负值）。"""
    hist = attribute_history(code, period + 5, '1d', ['close'])
    if hist.empty or len(hist) < period:
        return None
    daily_returns = hist['close'].pct_change().dropna()
    return -daily_returns.tail(period).std()   # 取负，越小越好 → 负号后越大越好


def compute_volume_ratio(code, short=5, long=20):
    """成交量因子：近期均量 / 长期均量，反映资金关注度。"""
    hist = attribute_history(code, long + 5, '1d', ['volume'])
    if hist.empty or len(hist) < long:
        return None
    short_avg = hist['volume'].tail(short).mean()
    long_avg  = hist['volume'].tail(long).mean()
    return short_avg / long_avg if long_avg > 0 else None


def compute_value(code):
    """价值因子：1 / PE（PE 越低，因子值越高）。"""
    val = get_valuation(code)
    if val is None or val.get('pe') is None or val['pe'] <= 0:
        return None
    return 1.0 / val['pe']
```

---

## 5. 三因子模型：动量 + 成交量 + 价格

我们先用三个纯技术因子构建一个基础版本，避免依赖实时财务数据：

### 4.1 因子定义

| 因子 | 含义 | 权重 |
|------|------|------|
| 动量 | 近 20 日收益率 | 40% |
| 成交量放大 | 近 5 日均量 / 近 20 日均量 | 30% |
| 短期反转修正 | 近 5 日收益率的负值（避免短期追高） | 30% |

### 4.2 因子计算示例

```python
from eqlib import attribute_history

def score_stock_three_factor(code):
    """
    三因子打分：动量 + 成交量 + 短期反转修正。
    返回: dict 包含各因子值和总分，或 None（数据不足）
    """
    hist = attribute_history(code, 35, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < 25:
        return None

    close = hist['close']
    vol   = hist['volume']

    # 因子 1：近 20 日动量
    momentum = (close.iloc[-1] / close.iloc[-20]) - 1

    # 因子 2：成交量放大比
    vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()

    # 因子 3：短期反转（近 5 日收益率为正时得分低，避免追高）
    reversal = -((close.iloc[-1] / close.iloc[-5]) - 1)

    return {
        'momentum': momentum,
        'vol_ratio': vol_ratio,
        'reversal': reversal,
    }
```

---

## 6. 加入财务因子

财务因子通常在策略中通过 `get_valuation` 获取，适合**低频调仓**（如每月一次）：

```python
from eqlib import get_valuation, get_financial_abstract

def score_stock_with_financials(code):
    """
    加入财务因子：价值 + 质量。
    适合低频（每月）更新。
    """
    # 价值因子
    val = get_valuation(code)
    pe_factor = 0.0
    pb_factor = 0.0
    if val:
        pe = val.get('pe')
        pb = val.get('pb')
        if pe and 0 < pe < 100:     # 过滤负 PE（亏损企业）和极端高 PE（> 100 通常是泡沫）
            pe_factor = 1.0 / pe
        if pb and 0 < pb < 20:
            pb_factor = 1.0 / pb

    # 质量因子（ROE = 净利润 / 净资产，从财务摘要中获取）
    roe_factor = 0.0
    try:
        fin = get_financial_abstract(code)
        if fin is not None and not fin.empty:
            # 财务摘要的行索引包含各财务指标，尝试获取 ROE
            if 'ROE' in fin.index:
                roe = float(fin.loc['ROE'].iloc[-1])
                # ROE 以小数形式存储（如 0.15 表示 15%），合理范围为 0 ~ 1
                if 0 < roe < 1:
                    roe_factor = roe
    except Exception:
        pass

    return {
        'pe_factor':  pe_factor,
        'pb_factor':  pb_factor,
        'roe_factor': roe_factor,
    }
```

---

## 7. 因子标准化与合成

不同因子的量纲不同（动量是百分比，成交量比是倍数），直接加权会出现某个因子主导的问题。需要先标准化再合成。

### 6.1 Z-Score 标准化

```python
def zscore_normalize(values_dict):
    """
    对多只股票的因子值进行 Z-Score 标准化。

    输入: {'code1': value1, 'code2': value2, ...}
    输出: {'code1': z_score1, 'code2': z_score2, ...}
    """
    import statistics

    valid_items = [(k, v) for k, v in values_dict.items() if v is not None]
    if len(valid_items) < 2:
        return {k: 0.0 for k in values_dict}

    codes, vals = zip(*valid_items)
    mean_val = statistics.mean(vals)
    std_val  = statistics.stdev(vals)

    if std_val == 0:
        return {k: 0.0 for k in values_dict}

    return {
        code: (val - mean_val) / std_val
        for code, val in valid_items
    }


def merge_factor_scores(factor_dicts, weights):
    """
    合并多个标准化后的因子字典。

    factor_dicts: [{'code': z_score}, ...] 每个因子的 Z-Score 字典
    weights:      [w1, w2, ...]            对应权重，和为 1
    返回: {'code': combined_score}
    """
    combined = {}
    for fdict, weight in zip(factor_dicts, weights):
        for code, zscore in fdict.items():
            combined[code] = combined.get(code, 0.0) + zscore * weight
    return combined
```

### 6.2 使用示例

```python
stock_pool = ['601390', '600519', '000858', '600036', '601318',
              '000333', '600887', '000651', '600276', '000001']

# 计算每只股票的各因子原始值
raw_momentum  = {}
raw_vol_ratio = {}
raw_reversal  = {}

for code in stock_pool:
    result = score_stock_three_factor(code)
    if result is None:
        continue
    raw_momentum[code]  = result['momentum']
    raw_vol_ratio[code] = result['vol_ratio']
    raw_reversal[code]  = result['reversal']

# Z-Score 标准化
z_momentum  = zscore_normalize(raw_momentum)
z_vol_ratio = zscore_normalize(raw_vol_ratio)
z_reversal  = zscore_normalize(raw_reversal)

# 合成总分
combined = merge_factor_scores(
    [z_momentum, z_vol_ratio, z_reversal],
    weights=[0.4, 0.3, 0.3],
)

# 排名
ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
print("排名  代码    综合得分")
for i, (code, score) in enumerate(ranked[:5]):
    print('%2d.  %s  %.3f' % (i + 1, code, score))
```

---

## 8. 完整的多因子策略

```python
from eqlib import *
from eqlib import utils
import statistics

# ========== 策略参数（模块级常量，引擎不会清除） ==========
STOCK_POOL = [
    '601390', '600519', '000858', '600036', '000001',
    '601318', '000333', '600887', '000651', '600276',
]
TOP_N          = 3     # 每次持有排名前 3 的股票
LOOKBACK_LONG  = 20    # 中期动量回看期
LOOKBACK_SHORT = 5     # 短期反转回看期
POSITION_PCT   = 0.33  # 每只股票最多 33% 仓位


# ========== 因子函数 ==========

def compute_factors(code):
    """计算单只股票的三因子原始值，失败返回 None。"""
    hist = attribute_history(code, LOOKBACK_LONG + 10, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < LOOKBACK_LONG:
        return None

    close = hist['close']
    vol   = hist['volume']
    price = close.iloc[-1]

    # 价格范围过滤：排除低价股（< 3 元）和极高价股（> 500 元）
    if price < 3.0 or price > 500.0:
        return None

    momentum  = (close.iloc[-1] / close.iloc[-LOOKBACK_LONG]) - 1
    vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()
    reversal  = -((close.iloc[-1] / close.iloc[-LOOKBACK_SHORT]) - 1)

    return (momentum, vol_ratio, reversal)


def zscore_dict(values_dict):
    """Z-Score 标准化。"""
    vals = list(values_dict.values())
    if len(vals) < 2:
        return {k: 0.0 for k in values_dict}
    mean_v = statistics.mean(vals)
    std_v  = statistics.stdev(vals) or 1e-9
    return {k: (v - mean_v) / std_v for k, v in values_dict.items()}


def rank_stocks(context):
    """
    对股票池内所有股票打分排名，返回 [(code, score)] 从高到低排序。
    """
    raw = {code: compute_factors(code) for code in STOCK_POOL}
    raw = {k: v for k, v in raw.items() if v is not None}

    if not raw:
        return []

    momentum_raw  = {code: v[0] for code, v in raw.items()}
    vol_ratio_raw = {code: v[1] for code, v in raw.items()}
    reversal_raw  = {code: v[2] for code, v in raw.items()}

    z_m = zscore_dict(momentum_raw)
    z_v = zscore_dict(vol_ratio_raw)
    z_r = zscore_dict(reversal_raw)

    scores = {
        code: z_m.get(code, 0) * 0.4 +
              z_v.get(code, 0) * 0.3 +
              z_r.get(code, 0) * 0.3
        for code in raw
    }

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ========== 策略主体 ==========

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    context.universe = STOCK_POOL
    run_weekly(rebalance, day_of_week=0, time='every_bar')
    log.info('多因子策略初始化: 股票池=%d, 持仓Top%d' % (
        len(STOCK_POOL), TOP_N))


def rebalance(context):
    """每周一重新打分并调仓。"""
    ranked = rank_stocks(context)
    if not ranked:
        log.warn('无有效评分，跳过调仓')
        return

    top_stocks = [code for code, _ in ranked[:TOP_N]]

    # 打印当前评分
    log.info('本周评分排名:')
    for i, (code, score) in enumerate(ranked[:TOP_N]):
        log.info('  %d. %s  score=%.3f' % (i + 1, code, score))

    # 卖出不在 Top N 的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)
            log.info('卖出 %s（未入选本周 Top%d）' % (sec, TOP_N))

    # 等权买入 Top N
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        target_value = context.portfolio.total_value * weight
        order_target_value(sec, target_value)
        log.info('调仓 %s，目标持仓=%.0f 元' % (sec, target_value))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=300000,
        benchmark='000300.XSHG',
        securities=STOCK_POOL,
        report_dir='reports',
    )
```

---

## 9. 因子有效性检验

在投入使用前，需要检验因子是否真的有预测能力。

### 8.1 IC（信息系数）检验

IC 是因子值与下期收益率的相关系数。IC 绝对值越大，预测能力越强：

```python
def compute_ic(stock_pool, factor_func, forward_period=5):
    """
    计算因子 IC（因子值与未来 N 日收益率的相关系数）。
    factor_func: function(code) -> float | None
    """
    import statistics

    factor_values = []
    forward_returns = []

    for code in stock_pool:
        # 因子值（今天计算）
        f = factor_func(code)
        if f is None:
            continue

        # 未来 N 日收益率（用于验证）
        hist = attribute_history(code, forward_period + 5, '1d', ['close'])
        if hist.empty or len(hist) < forward_period + 1:
            continue
        fwd_ret = (hist['close'].iloc[-1] / hist['close'].iloc[-(forward_period + 1)]) - 1

        factor_values.append(f)
        forward_returns.append(fwd_ret)

    if len(factor_values) < 5:
        return None

    # 计算 Pearson 相关系数
    n = len(factor_values)
    mean_f = statistics.mean(factor_values)
    mean_r = statistics.mean(forward_returns)
    cov  = sum((f - mean_f) * (r - mean_r)
               for f, r in zip(factor_values, forward_returns)) / n
    std_f = statistics.stdev(factor_values) or 1e-9
    std_r = statistics.stdev(forward_returns) or 1e-9
    ic = cov / (std_f * std_r)
    return ic


# 示例：检验动量因子的 IC
ic_value = compute_ic(
    g.stock_pool,
    lambda code: compute_momentum(code, period=20),
    forward_period=5,
)
if ic_value is not None:
    print('动量因子 IC = %.4f' % ic_value)
    # IC > 0.03 通常被认为有统计意义
    # IC > 0.10 属于较强的预测信号
```

### 8.2 多空分组收益分析

将股票按因子值从高到低分成 5 组（Q1~Q5），如果因子有效，Q1 组（最高分）应明显跑赢 Q5 组（最低分）：

```python
def factor_quintile_analysis(stock_pool, factor_func, lookback=5):
    """因子分组收益分析：将股票按因子值分成 5 组，比较各组收益。"""
    data = []
    for code in stock_pool:
        f = factor_func(code)
        if f is None:
            continue
        hist = attribute_history(code, lookback + 3, '1d', ['close'])
        if hist.empty or len(hist) < lookback + 1:
            continue
        fwd = (hist['close'].iloc[-1] / hist['close'].iloc[-(lookback+1)]) - 1
        data.append((code, f, fwd))

    if len(data) < 5:
        return

    data.sort(key=lambda x: x[1], reverse=True)
    n = len(data)
    group_size = max(n // 5, 1)

    print('因子分组收益分析（共 %d 只股票）:' % n)
    for q in range(5):
        start = q * group_size
        end   = min((q + 1) * group_size, n) if q < 4 else n
        group = data[start:end]
        avg_ret = sum(r for _, _, r in group) / len(group)
        print('  Q%d (Top %d%%): 平均收益 %.2f%%' % (
            q + 1, (q + 1) * 20, avg_ret * 100))
```

---

## 10. 多因子选股的局限性

### 9.1 A 股散户市场的特殊性

| 因子 | 在美股 | 在 A 股 |
|------|--------|---------|
| 价值因子 | 长期有效 | 有效但周期较长，短期常被忽视 |
| 动量因子 | 中期（3-12 个月）有效 | 短期动量明显，但需警惕过热题材 |
| 质量因子（高 ROE） | 稳定有效 | 有效，但绩优股有时被冷落 |
| 成长因子 | 有效 | 在牛市中效果更强 |

### 9.2 因子衰减与轮换

没有一个因子永远有效，因子会"过时"：
- 当太多资金追逐同一因子时，预测能力下降
- 建议定期（每季度）检验 IC，判断因子是否仍有效

### 9.3 数据偏差

回测时使用的是当前的财务数据（`get_valuation`），而非历史上该时点公布的数据。这可能引入**财务数据前瞻偏差**（Look-ahead Bias）。严格的多因子策略应当使用历史财务数据快照。

**实用建议：** 在回测中主要使用**价格和成交量类因子**（无前瞻偏差），把财务因子留作辅助参考或实盘筛选条件。

---

## 11. 下一步

掌握了多因子选股的基础，可以进一步：

- **[Tutorial 03: 策略优化与改进](03-optimization.md)** — 参数调优、归因分析，检验多因子策略的稳健性
- **[Tutorial 06: 行业轮动](06-sector-rotation.md)** — 将多因子选股与行业轮动结合，先选行业再选股
- **[Example 16: 多因子选股策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py)** — 完整可运行的多因子示例代码
- **[Example 09: 绩效归因分析](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/09_attribution.py)** — 对策略收益进行深度归因，了解选股效应和配置效应
- **[工具库参考](../reference/utils.md)** — `utils.zscore`、`utils.rolling_sharpe`、`utils.max_drawdown` 等工具的详细说明

### 练习

1. 修改因子权重（如动量权重从 40% 改为 60%），观察策略变化
2. 加入第四个因子：近 60 日收益率（长期动量），权重 20%，其他因子各降 5%
3. 将调仓频率从每周改为每月，分析换手率和净收益的变化
4. 使用 `analyze_returns` 对比多因子策略与双均线策略的风险调整收益
5. 扩大股票池（加入你关注的股票），重新回测对比结果
