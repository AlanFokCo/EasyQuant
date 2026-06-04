# Tutorial 05: RSI 均值回归策略

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 从 RSI 原理到完整策略代码、风控与改进思路 |
    | **预计用时** | 约 90 分钟 |
    | **前置** | [Tutorial 01](01-first-strategy.md)、[Tutorial 02](02-backtesting.md) |

> 均值回归是最经典的量化策略思想之一。本教程从 RSI 指标原理出发，系统讲解如何设计、回测和改进一个 RSI 均值回归策略。

**相关示例：** [`examples/15_bollinger_strategy.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) 等（见 [`Examples.md`](../examples/index.md)）

---

## 目录

1. [均值回归的核心思想](#1-均值回归的核心思想)
2. [RSI 指标详解](#2-rsi-指标详解)
3. [策略设计](#3-策略设计)
4. [编写策略代码](#4-编写策略代码)
5. [加入风控条件](#5-加入风控条件)
6. [扩展为多股票版本](#6-扩展为多股票版本)
7. [均值回归策略的局限性](#7-均值回归策略的局限性)
8. [与布林带策略的对比](#8-与布林带策略的对比)
9. [下一步](#9-下一步)

---

## 1. 均值回归的核心思想

**均值回归（Mean Reversion）** 的基本假设是：资产价格偏离历史均值后，有倾向回归到均值附近。

```
价格走势：
           超买 ─────────────── 卖出
            │
─────── 均值 ─────────────────────── 均值
            │
           超卖 ─────────────── 买入
```

### 与趋势策略的对比

| | 趋势跟踪 | 均值回归 |
|--|---------|---------|
| **核心假设** | 价格一旦形成趋势会继续延续 | 价格偏离均值后会回归 |
| **买入时机** | 突破、金叉 | 价格超卖/触底 |
| **卖出时机** | 反转、死叉 | 价格超买/触顶 |
| **适合市场** | 趋势明显的牛市/熊市 | 横盘震荡市 |
| **风险** | 震荡市反复被套 | 趋势市越跌越买，扛不住 |

**选哪个？** 这正是量化交易的核心挑战——没有一种策略在所有市场环境下都有效。实战中通常用**大盘判断**来切换模式，或两种策略**并行运行、互相对冲**。

### A 股市场适用性

A 股市场以散户为主，情绪化交易普遍，股价经常出现"短期超调"——比真实价值涨太多或跌太多。这种特性让均值回归策略在 A 股有较好的适用性，尤其是：
- **大盘蓝筹股**（银行、保险、消费）：波动相对稳定，适合均值回归
- **震荡行情**：大盘没有明确趋势时，均值回归表现优于趋势跟踪

---

## 2. RSI 指标详解

**RSI（Relative Strength Index，相对强弱指标）** 衡量一段时间内价格上涨力度与下跌力度的比值。

### 2.1 计算公式

```
每日变化量 Δ = 今日收盘价 - 昨日收盘价

上涨日均值 AvgGain = EMA(max(Δ, 0), N)
下跌日均值 AvgLoss = EMA(max(-Δ, 0), N)

RS = AvgGain / AvgLoss

RSI = 100 - 100 / (1 + RS)
```

### 2.2 数值解读

| RSI 区间 | 含义 | 策略含义 |
|----------|------|---------|
| 70 ~ 100 | 超买区 | 上涨力度过强，可能回调 → **考虑卖出** |
| 50 ~ 70 | 强势区 | 多头占优 |
| 30 ~ 50 | 弱势区 | 空头占优 |
| 0 ~ 30 | 超卖区 | 下跌力度过强，可能反弹 → **考虑买入** |

### 2.3 在 EasyQuant 中计算 RSI

```python
from eqlib import attribute_history
from eqlib import utils

# 获取历史收盘价（至少 N + 10 根 bar，确保计算稳定）
hist = attribute_history('601390', 30, '1d', ['close'])
close_prices = hist['close']

# 计算 14 日 RSI
rsi14 = utils.rsi(close_prices, period=14)

print("最新 RSI:", rsi14.iloc[-1])   # 例如: 28.3（超卖区域）
```

---

## 3. 策略设计

### 策略规则

| 条件 | 操作 |
|------|------|
| RSI < 30（超卖）+ 当前没有持仓 | **买入**，用全部可用现金 |
| RSI > 70（超买）+ 当前有持仓 | **卖出**，清仓 |
| RSI 在 30 ~ 70 之间 | 不操作 |

### 参数设计

```python
RSI_PERIOD     = 14    # RSI 计算周期（标准为 14 日）
RSI_OVERSOLD   = 30    # 超卖阈值（买入触发）
RSI_OVERBOUGHT = 70    # 超买阈值（卖出触发）
```

---

## 4. 编写策略代码

```python
from eqlib import *
from eqlib import utils

# ========== 策略参数（模块级常量，引擎不会清除） ==========
SECURITY       = '601390'   # 操作标的：工商银行
RSI_PERIOD     = 14         # RSI 计算周期
RSI_OVERSOLD   = 30         # 超卖阈值
RSI_OVERBOUGHT = 70         # 超买阈值
BARS_NEEDED    = 40         # 需要获取的历史 bar 数量（RSI 需要足够的预热数据）


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')
    log.info('RSI 均值回归策略初始化: %s, RSI%d, 超卖=%d, 超买=%d' % (
        SECURITY, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT))


def market_open(context):
    security = SECURITY

    # 1. 获取历史数据
    hist = attribute_history(security, BARS_NEEDED, '1d', ['close'])
    if hist.empty or len(hist) < RSI_PERIOD + 10:
        return

    close_prices = hist['close']
    current_price = close_prices.iloc[-1]

    # 2. 计算 RSI
    rsi_series = utils.rsi(close_prices, RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]

    # 3. 超卖区：RSI 低于阈值 → 买入
    if current_rsi < RSI_OVERSOLD:
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info('买入 %s @ %.3f，RSI=%.1f（超卖）' % (
                security, current_price, current_rsi))

    # 4. 超买区：RSI 高于阈值 → 卖出
    elif current_rsi > RSI_OVERBOUGHT:
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info('卖出 %s @ %.3f，RSI=%.1f（超买）' % (
                security, current_price, current_rsi))

    # 5. 记录状态（出现在 JSON 报告中）
    record(
        price=current_price,
        rsi=current_rsi,
        cash=context.portfolio.available_cash,
    )


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=100000,
        benchmark='000300.XSHG',
        securities=['601390'],
        report_dir='reports',
    )
```

---

## 5. 加入风控条件

基础策略只有超买/超卖两个信号，实战中需要加入风控条件。

### 5.1 固定止损

```python
def market_open(context):
    security = SECURITY

    # === 止损优先（在信号判断之前执行）===
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            hist_check = attribute_history(security, 2, '1d', ['close'])
            price_now = hist_check['close'].iloc[-1]
            loss_pct = (price_now - pos.avg_cost) / pos.avg_cost
            if loss_pct < -0.08:   # 亏损超过 8%，止损出局
                order_target(security, 0)
                log.info('止损 %s @ %.3f，亏损 %.1f%%' % (
                    security, price_now, loss_pct * 100))
                return

    # === 原有 RSI 信号 ===
    # ... （同上文代码）
```

### 5.2 大盘过滤（避免在趋势下行时逆势抄底）

```python
def market_open(context):
    # 大盘过滤：沪深 300 处于 20 日均线之下 → 不做多
    index_hist = attribute_history('000300.XSHG', 25, '1d', ['close'])
    if not index_hist.empty:
        index_ma20 = index_hist['close'].mean()
        index_price = index_hist['close'].iloc[-1]
        if index_price < index_ma20:
            # 大盘弱势：只允许卖出，不允许买入
            # （止损检查仍然执行）
            pass  # 在买入判断前 return

    # ... RSI 信号逻辑 ...
```

### 5.3 RSI 低点二次确认（避免"接飞刀"）

```python
# 不只要求 RSI < 30，还要求 RSI 从更低处有所回升（底部确认）
rsi_prev = rsi_series.iloc[-2]   # 前一天的 RSI

# RSI 曾经低于 30，且今天开始回升 → 更可靠的买入信号
if current_rsi < g.rsi_oversold and current_rsi > rsi_prev:
    # 底部确认：RSI 从超卖开始回升
    order_value(security, context.portfolio.available_cash)
```

### 5.4 成交量确认

```python
# 超卖 + 量能萎缩 → 可能是抛售结束的信号
hist = attribute_history(security, g.bars_needed, '1d', ['close', 'volume'])
close_prices = hist['close']
volumes = hist['volume']

avg_vol = volumes.tail(20).mean()
current_vol = volumes.iloc[-1]

# 买入条件：RSI 超卖 + 成交量低于均量（说明抛售力道已减弱）
if current_rsi < g.rsi_oversold and current_vol < avg_vol * 0.8:
    order_value(security, context.portfolio.available_cash)
```

### 5.5 完整的带风控版本

```python
from eqlib import *
from eqlib import utils

# 模块级常量（引擎不会清除）
SECURITY       = '601390'
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
STOP_LOSS_PCT  = 0.08    # 8% 止损
BARS_NEEDED    = 40


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')


def market_open(context):
    security = SECURITY
    hist = attribute_history(security, BARS_NEEDED, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < RSI_PERIOD + 10:
        return

    close_prices = hist['close']
    volumes = hist['volume']
    current_price = close_prices.iloc[-1]

    rsi_series = utils.rsi(close_prices, RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]
    prev_rsi    = rsi_series.iloc[-2]

    avg_vol     = volumes.tail(20).mean()
    current_vol = volumes.iloc[-1]

    # --- 大盘过滤 ---
    idx_hist = attribute_history('000300.XSHG', 25, '1d', ['close'])
    market_bullish = True
    if not idx_hist.empty:
        idx_ma20 = idx_hist['close'].mean()
        idx_price = idx_hist['close'].iloc[-1]
        market_bullish = idx_price > idx_ma20

    # --- 止损 ---
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            loss_pct = (current_price - pos.avg_cost) / pos.avg_cost
            if loss_pct < -STOP_LOSS_PCT:
                order_target(security, 0)
                log.info('止损 %s @ %.3f，亏损 %.1f%%' % (
                    security, current_price, loss_pct * 100))
                record(price=current_price, rsi=current_rsi, signal='STOP')
                return

    # --- 买入：超卖 + 底部回升 + 大盘不过弱 + 量缩 ---
    in_position = security in context.portfolio.positions and \
                  context.portfolio.positions[security].amount > 0

    if (current_rsi < RSI_OVERSOLD and
            current_rsi > prev_rsi and        # RSI 开始回升
            market_bullish and
            current_vol < avg_vol * 1.2 and   # 非放量下跌
            not in_position):
        order_value(security, context.portfolio.available_cash)
        log.info('买入 %s @ %.3f，RSI=%.1f→%.1f' % (
            security, current_price, prev_rsi, current_rsi))
        record(price=current_price, rsi=current_rsi, signal='BUY')

    # --- 卖出：超买 ---
    elif current_rsi > RSI_OVERBOUGHT and in_position:
        order_target(security, 0)
        log.info('卖出 %s @ %.3f，RSI=%.1f（超买）' % (
            security, current_price, current_rsi))
        record(price=current_price, rsi=current_rsi, signal='SELL')

    else:
        record(price=current_price, rsi=current_rsi, signal='HOLD')


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=100000,
        benchmark='000300.XSHG',
        securities=['601390'],
        report_dir='reports',
    )
```

---

## 6. 扩展为多股票版本

单股 RSI 策略受制于该股票的走势。将策略扩展到多股票，可以提高信号出现的频率并分散风险。

### 6.1 候选池设计原则

- **选流动性好的股票**：日均成交额 > 5000 万，避免大资金无法成交
- **避免同一行业重仓**：不要全部选银行股，否则相关性太高，失去分散效果
- **排除 ST 股**：ST 股价格异常，均值回归模型失效

### 6.2 多股票 RSI 轮动

```python
from eqlib import *
from eqlib import utils

g.securities = [
    '601390',  # 工商银行（银行）
    '600519',  # 贵州茅台（消费）
    '000858',  # 五粮液（消费）
    '600036',  # 招商银行（银行）
    '601318',  # 中国平安（保险）
    '000333',  # 美的集团（家电）
    '600887',  # 伊利股份（消费）
    '000651',  # 格力电器（家电）
]

g.rsi_period     = 14
g.rsi_oversold   = 30
g.rsi_overbought = 70
g.position_pct   = 0.25   # 每只股票最多用 25% 可用资金


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')


def market_open(context):
    for security in g.securities:
        hist = attribute_history(security, 40, '1d', ['close'])
        if hist.empty or len(hist) < g.rsi_period + 10:
            continue

        close_prices = hist['close']
        current_price = close_prices.iloc[-1]
        rsi_series = utils.rsi(close_prices, g.rsi_period)
        current_rsi = rsi_series.iloc[-1]

        in_position = security in context.portfolio.positions and \
                      context.portfolio.positions[security].amount > 0

        # 买入
        if current_rsi < g.rsi_oversold and not in_position:
            buy_value = context.portfolio.available_cash * g.position_pct
            if buy_value > 1000:  # 金额太小不操作
                order_value(security, buy_value)
                log.info('买入 %s @ %.3f，RSI=%.1f' % (
                    security, current_price, current_rsi))

        # 卖出
        elif current_rsi > g.rsi_overbought and in_position:
            order_target(security, 0)
            log.info('卖出 %s @ %.3f，RSI=%.1f' % (
                security, current_price, current_rsi))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=200000,
        benchmark='000300.XSHG',
        securities=g.securities,
        report_dir='reports',
    )
```

---

## 7. 均值回归策略的局限性

### 7.1 强趋势行情中会失效

```
            均值回归策略的"噩梦"：单边下跌
价格
  │       ← RSI < 30，买入
  │──────/\
  │     /  \            ← RSI < 30，再次买入（越跌越买）
  │          \──────/\
  │                  \        ← 还在买…
  │                   \──────
  └───────────────────────────→ 时间
```

**应对方法**：加入大盘过滤 + 固定止损，出现趋势行情时及时止损退出。

### 7.2 RSI 阈值不是绝对标准

- RSI = 28 时买入，价格可能继续跌到 RSI = 15 才反弹
- RSI = 72 时卖出，价格可能继续涨到 RSI = 85 才回落
- **解决方案**：配合布林带、支撑阻力位等其他指标做二次确认

### 7.3 不同股票适合不同参数

- 高波动股票（科技、新能源）：可以用更极端的阈值（超卖 20，超买 80）
- 低波动股票（银行、公用事业）：标准阈值（30/70）通常就够

---

## 8. 与布林带策略的对比

RSI 均值回归和布林带均值回归都是常见的均值回归策略，但各有侧重：

| | RSI 均值回归 | 布林带均值回归 |
|--|-------------|--------------|
| **信号来源** | 价格变化的相对强弱（动量） | 价格偏离均线的标准差 |
| **参数** | RSI 周期、超买/超卖阈值 | Bollinger 周期、标准差倍数 |
| **信号特点** | 更关注**短期涨跌力度** | 更关注**当前价格相对历史的位置** |
| **假信号** | 强趋势时频繁触发超卖/超买 | 趋势突破时会在带外停留很长时间 |
| **相关示例** | 本教程 | [Example 14](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) |

### 8.1 结合使用

两者结合往往比单独使用更可靠：

```python
from eqlib import utils

# 同时满足两个条件才买入
hist = attribute_history(security, 40, '1d', ['close'])
close_prices = hist['close']

rsi_val = utils.rsi(close_prices, 14).iloc[-1]
upper, mid, lower = utils.boll(close_prices, 20, 2.0)
current_price = close_prices.iloc[-1]

# RSI 超卖 + 价格触及布林带下轨 → 双重确认
if rsi_val < 30 and current_price <= lower.iloc[-1]:
    order_value(security, context.portfolio.available_cash)
```

---

## 9. 下一步

掌握了 RSI 均值回归策略后，你可以继续学习：

- **[Tutorial 06: 行业轮动策略](06-sector-rotation.md)** — 利用 A 股行业轮动特性，通过板块切换赚取超额收益
- **[Tutorial 07: 多因子选股](07-multi-factor.md)** — 结合动量、价值、质量多个因子，系统化选股
- **[Tutorial 03: 策略优化与改进](03-optimization.md)** — 参数调优、避免过拟合、归因分析
- **[Example 14: 布林带策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py)** — 另一种经典均值回归策略的完整代码
- **[Example 18: 多策略对比](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/18_strategy_comparison.py)** — 在同一股票上横向对比多种策略

### 练习

1. 修改 `g.rsi_oversold = 25`，观察交易频率和收益的变化
2. 将大盘过滤阈值从 MA20 改为 MA60（更长期趋势判断），观察效果
3. 对比有止损和无止损的回测结果，量化止损的效果
4. 尝试在 2022 年（熊市）和 2024 年（震荡市）分别回测，对比两个市场环境下的表现
