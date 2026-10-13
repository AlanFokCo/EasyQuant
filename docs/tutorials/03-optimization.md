# Tutorial 03: 策略优化与改进

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 参数扫描与稳定性、信号过滤、组合与归因、避免盲目调参 |
    | **预计用时** | 约 60 分钟 |
    | **前置** | [Tutorial 02: 回测验证](02-backtesting.md) |

> 在回测验证的基础上，改进策略参数、丰富策略逻辑、构建组合策略。

**文档索引：** [指南总览](../how-to/index.md)

---

## 目录

1. [为什么要优化](#1-为什么要优化)
2. [参数调优与稳定性检验](#2-参数调优与稳定性检验)
3. [增加策略条件](#3-增加策略条件)
4. [组合优化](#4-组合优化)
5. [归因分析](#5-归因分析)
6. [构建更健壮的策略](#6-构建更健壮的策略)
7. [下一步](#7-下一步)

---

## 1. 为什么要优化

回测通过后，策略通常还有改进空间：

| 问题 | 优化方向 |
|------|---------|
| 收益不够高 | 改进信号质量、增加筛选条件 |
| 回撤太大 | 增加止损、大盘过滤、仓位控制 |
| 交易频率太高 | 增加信号确认条件，减少假信号 |
| 跑输大盘 | 换策略、换标的、增加行业轮动 |

**重要原则**：优化要有方向，不能"试遍所有参数选最好的"——那是过拟合。

---

## 2. 参数调优与稳定性检验

### 2.1 均线周期参数调优

```python
from eqlib import *
import datetime

SECURITIES = ['601398']   # 模块级常量：引擎会在 initialize 前清空 g

def test_ma_combo(fast_period, slow_period):
    """测试一组均线参数"""
    results_log = []

    def initialize(context):
        g.security = SECURITIES[0]
        g.fast = fast_period
        g.slow = slow_period
        set_benchmark('000300.XSHG')
        set_order_cost(OrderCost(
            open_tax=0, close_tax=0.0005,
            open_commission=0.00025, close_commission=0.00025,
            min_commission=5,
        ))
        run_daily(market_open, time='every_bar')

    def market_open(context):
        hist = attribute_history(g.security, g.slow + 10, '1d', ['close'])
        if hist.empty or len(hist) < g.slow:
            return
        ma_fast = hist['close'].tail(g.fast).mean()
        ma_slow = hist['close'].tail(g.slow).mean()
        price = hist['close'].iloc[-1]

        if price > ma_fast > ma_slow:
            if g.security not in context.portfolio.positions:
                order_value(g.security, context.portfolio.available_cash * 0.95)  # 留 5% 费用缓冲
        elif price < ma_fast < ma_slow:
            if g.security in context.portfolio.positions:
                order_target(g.security, 0)

    result = run_backtest(
        initialize, '2024-01-01', '2024-12-31',
        starting_cash=100000, benchmark='000300.XSHG',
        securities=SECURITIES,
    )
    if result:
        ctx = result['context']
        metrics = analyze_returns(result, risk_free_rate=0.03)
        results_log.append({
            'fast': fast_period,
            'slow': slow_period,
            'pnl_pct': (ctx.portfolio.total_value - 100000) / 100000,
            'sharpe': metrics['sharpe_ratio'],
            'max_dd': abs(metrics['max_drawdown']),
            'trades': len(result['trade_log']),
        })
    return results_log

# 扫描参数
combos = [
    (3, 10), (3, 15), (3, 20),
    (5, 15), (5, 20), (5, 30),
    (7, 20), (7, 25), (7, 30),
    (10, 30), (10, 40), (10, 60),
]

print('%-8s %-8s %-10s %-10s %-10s %-8s' % (
    'Fast', 'Slow', 'Return%', 'Sharpe', 'MaxDD%', 'Trades'))
print('-' * 58)

for fast, slow in combos:
    logs = test_ma_combo(fast, slow)
    if logs:
        r = logs[0]
        print('%-8d %-8d %-10.2f %-10.2f %-10.2f %-8d' % (
            r['fast'], r['slow'],
            r['pnl_pct'] * 100, r['sharpe'],
            r['max_dd'] * 100, r['trades']))
```

> 扫描结果已经包含引擎的默认行为：涨跌停拦截（`check_price_limit=True`）、停牌当日订单取消、退市 30 个交易日无行情后强制清算（`DELIST_LIQUIDATE`）。这些与实盘更接近，不要为了让曲线好看而关掉它们。

### 2.2 稳定性检验

```python
# 如果 MA5/MA20 夏普 1.8，MA5/MA25 夏普 0.2 → 不稳定
# 如果 MA5/MA20 夏普 1.5，MA5/MA18 夏普 1.4，MA5/MA22 夏普 1.3 → 稳定

# 好参数应该：
# 1. 周围参数的结果接近（局部平坦）
# 2. 训练集和测试集表现一致（泛化能力）
```

**判断标准：**
- 好参数：相邻 2-3 组参数的夏普比率差异 < 0.3
- 可疑参数：相邻参数夏普差异 > 1.0，说明找到了"巧合点"
- 差参数：夏普 < 0.5 或最大回撤 > 25%

---

## 3. 增加策略条件

### 3.1 加入止损

止损是最直接的风控手段：

```python
def market_open(context):
    security = g.security
    hist = attribute_history(security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return

    price = hist['close'].iloc[-1]
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].tail(20).mean()

    # === 止损优先 ===
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        loss_pct = (price - pos.avg_cost) / pos.avg_cost
        if loss_pct < -0.08:
            order_target(security, 0)
            log.info('止损卖出 %s @ %.3f，亏损 %.1f%%' % (
                security, price, loss_pct * 100))
            return

    # === 原有信号 ===
    if price > ma5 > ma20:
        if security not in context.portfolio.positions:
            order_value(security, context.portfolio.available_cash * 0.95)
    elif price < ma5 < ma20:
        if security in context.portfolio.positions:
            order_target(security, 0)
```

### 3.2 大盘过滤

```python
def market_open(context):
    # 先看大盘
    index_hist = attribute_history('000300.XSHG', 20, '1d', ['close'])
    index_ma20 = index_hist['close'].mean()
    index_price = index_hist['close'].iloc[-1]

    # 大盘在 20 日均线以下 → 空仓观望
    if index_price < index_ma20:
        # 有持仓就清仓
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
        return

    # 大盘安全 → 执行个股策略
    # ...
```

### 3.3 成交量确认

```python
# 金叉信号 + 放量确认 → 更可靠的买入信号
hist = attribute_history(security, 25, '1d', ['close', 'volume'])
close_prices = hist['close']
volume = hist['volume']

ma5 = close_prices.tail(5).mean()
ma20 = close_prices.tail(20).mean()
price = close_prices.iloc[-1]

avg_vol_20 = volume.tail(20).mean()
current_vol = volume.iloc[-1]

# 放量确认：当日成交量 > 20 日均量的 1.5 倍
if price > ma5 > ma20 and current_vol > avg_vol_20 * 1.5:
    if security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.95)
```

### 3.4 MACD 辅助确认

```python
from eqlib import utils

hist = attribute_history(security, 40, '1d', ['close'])
close_prices = hist['close']

ma5 = close_prices.tail(5).mean()
ma20 = close_prices.tail(20).mean()
price = close_prices.iloc[-1]

# MACD 金叉
dif, dea, macd_hist = utils.macd(close_prices, fast=12, slow=26, signal=9)
macd_golden_cross = dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]

# 双条件确认：均线金叉 + MACD 金叉
if price > ma5 > ma20 and macd_golden_cross:
    if security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.95)
```

### 3.5 ATR 追踪止损

固定比例止损的缺点是"一刀切"，波动大的股票容易被洗出去。ATR 追踪止损根据波动率动态调整：

```python
from eqlib import utils

hist = attribute_history(security, 30, '1d', ['high', 'low', 'close'])
high = hist['high']
low = hist['low']
close = hist['close']

price = close.iloc[-1]

# 计算 14 日 ATR
atr14 = utils.atr(high, low, close, 14).iloc[-1]

if security in context.portfolio.positions:
    pos = context.portfolio.positions[security]
    # 动态止损线 = 最高价 - 2 倍 ATR
    stop_price = pos.avg_cost - 2 * atr14
    if price < stop_price:
        order_target(security, 0)
        log.info('ATR 止损 %s @ %.3f, ATR=%.3f' % (security, price, atr14))
```

---

## 4. 组合优化

多标的时用 `portfolio_optimizer` 分配权重。函数签名：

```python
portfolio_optimizer(securities, prices, target=None, constraints=None,
                    bounds=None, default_range=(0.0, 1.0), ftol=1e-9,
                    return_none_if_fail=True)
```

| 参数 | 说明 |
|------|------|
| `securities` | 股票代码列表 |
| `prices` | **价格** DataFrame（index=日期，columns=股票代码）——内部自行用 `pct_change` 换算收益率，不要传收益率矩阵 |
| `target` | 优化目标：`MinVariance()`（默认）、`MaxSharpe(risk_free_rate=0.03)`、`RiskParity()` |
| `bounds` | 每只股票一个 `Bound(lower, upper)`；不传则全用 `default_range` |
| `constraints` | dict，支持 `max_weight`、`min_weight` |
| `return_none_if_fail` | 默认 True：求解失败返回 `None` 而非抛异常 |

返回值是 `pd.Series`（股票代码 → 权重，权重和为 1），失败时为 `None`。数据要求：至少 2 只股票、至少 20 个有效日收益，否则返回 `None`。协方差矩阵用 Ledoit-Wolf 收缩估计，小样本下比样本协方差稳定。

### 4.1 最小方差组合

```python
import pandas as pd
from eqlib import get_price, portfolio_optimizer, MinVariance, Bound

SECURITIES = ['601398', '600519', '000858']

# get_price 传入列表时返回 {代码: DataFrame} 字典
frames = get_price(SECURITIES, start_date='2023-01-01', end_date='2024-12-31')
prices = pd.DataFrame({sec: df['close'] for sec, df in frames.items()}).dropna()

weights = portfolio_optimizer(
    SECURITIES, prices,
    target=MinVariance(),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),  # 每只 5%–40%
)

if weights is None:
    print("优化失败：数据不足或求解未收敛")
else:
    print({k: round(v, 3) for k, v in weights.items()})
```

### 4.2 最大夏普组合

```python
from eqlib import MaxSharpe

# 无风险利率默认 0.03（3%），与回测指标计算口径一致
weights = portfolio_optimizer(
    SECURITIES, prices,
    target=MaxSharpe(risk_free_rate=0.03),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),
)
```

### 4.3 风险平价组合

```python
from eqlib import RiskParity

# 各标的对组合总风险的贡献相等
weights = portfolio_optimizer(
    SECURITIES, prices,
    target=RiskParity(),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),
)
```

### 4.4 在策略中使用优化权重

```python
# 模块级常量：权重来自上面 portfolio_optimizer 的输出（此处数值为演示）
SECURITIES = ['601398', '600519', '000858']
WEIGHTS = [0.34, 0.33, 0.33]

def monthly_rebalance(context):
    """每月调仓"""
    total_value = context.portfolio.total_value

    for sec, weight in zip(SECURITIES, WEIGHTS):
        target_value = total_value * weight
        order_target_value(sec, target_value)

def initialize(context):
    set_benchmark('000300.XSHG')
    run_monthly(monthly_rebalance, day_of_month=1, time='every_bar')
```

---

## 5. 归因分析

回测完成后，深入了解收益来源：

```python
from eqlib import analyze_returns, brinson_attribution, simple_factor_analysis

# 综合风险指标
metrics = analyze_returns(result, risk_free_rate=0.03)
print("夏普比率:   %.2f" % metrics['sharpe_ratio'])
print("最大回撤:   %.2f%%" % (metrics['max_drawdown'] * 100))
print("Alpha:      %.4f" % metrics['alpha'])

# Brinson 归因
attr = brinson_attribution(result)
print("配置效应: %.4f" % attr['allocation_effect'])
print("选股效应:   %.4f" % attr['selection_effect'])

# 简化因子分析
ff = simple_factor_analysis(result)
print("市场 Beta:  %.3f" % ff['market_beta'])
print("年化 Alpha: %.4f" % ff['alpha_annual'])
```

**如何利用归因结果改进策略：**

| 情况 | 含义 | 改进方向 |
|------|------|---------|
| 选股效应 > 0，配置效应 < 0 | 股票选对了但行业/时机不对 | 加强大盘/行业判断 |
| 选股效应 < 0，配置效应 > 0 | 行业选对了但个股不对 | 改进个股筛选条件 |
| Alpha > 0 | 有超额收益 | 策略有效 |
| Beta > 1.5 | 比大盘波动大很多 | 考虑降仓或分散 |
| Beta < 0.5 | 与大盘相关性弱 | 可能是独立策略 |

> 基准数据缺失时 `alpha`、`beta`、`information_ratio` 为 `NaN`（报告中显示 `N/A`），上表前两条判断不适用。

---

## 6. 构建更健壮的策略

### 6.1 策略检查清单

策略上模拟盘之前，逐一检查：

- [ ] 回测 >= 1 年，涵盖不同市场环境
- [ ] 夏普比率 > 1
- [ ] 最大回撤 < 20%（可接受的范围）
- [ ] 跑赢同期沪深 300
- [ ] 参数稳定（相邻参数结果接近）
- [ ] 样本外数据验证通过
- [ ] 已设置止损
- [ ] 交易成本已合理设置
- [ ] 检查过流动性（成交量充足）
- [ ] 检查过 T+1 限制（当天买入不会当天卖出）
- [ ] 没有未来函数
- [ ] 代码中 `log.info` 记录了关键操作

### 6.2 多策略组合

```python
# 策略 A：双均线趋势
# 策略 B：RSI 均值回归
# 两个策略各用 50% 资金

def initialize(context):
    g.strategy_a_capital_pct = 0.5

    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(run_strategy_a, time='every_bar')
    run_daily(run_strategy_b, time='every_bar')

def run_strategy_a(context):
    # 用 50% 的可用资金
    # ... 双均线逻辑 ...
    pass

def run_strategy_b(context):
    # 用 50% 的可用资金
    # ... RSI 均值回归逻辑 ...
    pass
```

### 6.3 参数外部化

好的策略应该让参数集中在一个地方，方便调整：

```python
# 策略参数集中管理
PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    'stop_loss_pct': 0.08,
    'position_pct': 1.0,
    'min_volume_ratio': 1.5,
    'atr_stop_multiplier': 2.0,
}

def market_open(context):
    p = PARAMS
    # ... 使用 p['fast_period'], p['stop_loss_pct'] 等 ...
```

---

## 7. 下一步

策略优化完成后，下一步是用实时行情验证：

- **[Tutorial 04: 模拟盘到实盘](04-live-trading.md)** — 用模拟盘验证策略，然后导出到 PTrade/QMT 实盘部署
- **[Tutorial 05: RSI 均值回归策略](05-rsi-mean-reversion.md)** — 学习一个与双均线思路截然不同的策略
- **[Tutorial 06: 行业轮动策略](06-sector-rotation.md)** — 利用 A 股行业轮动特性构建超额收益策略
- **[Tutorial 07: 多因子选股](07-multi-factor.md)** — 系统性的多因子量化选股方法
- **[Example 19: 支撑阻力位组合策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** — 一个完整的多股票组合策略实战案例，包含预生成的回测报告（HTML/PNG/Markdown/JSON），可直接查看策略表现
