# EasyQuant 用户手册

> EasyQuant 是一个面向中国 A 股市场的量化策略与回测工具。核心库为 `eqlib` Python 包，通过 `from eqlib import *` 导入使用。

---

## 目录

1. [简介与适用范围](#1-简介与适用范围)
2. [安装](#2-安装)
3. [快速开始：5 分钟写一个策略](#3-快速开始5-分钟写一个策略)
4. [策略生命周期](#4-策略生命周期)
5. [资金管理：设置初始资金与仓位控制](#5-资金管理设置初始资金与仓位控制)
6. [交易 API：买入与卖出](#6-交易-api买入与卖出)
7. [数据拉取](#7-数据拉取)
8. [计算工具库](#8-计算工具库)
9. [运行回测](#9-运行回测)
10. [回测报告与图表解读](#10-回测报告与图表解读)
11. [风险与归因分析](#11-风险与归因分析)
12. [模拟盘交易](#12-模拟盘交易)
13. [常见问题](#13-常见问题)

---

## 1. 简介与适用范围

`eqlib` 是一个面向 **中国 A 股市场** 的量化策略回测框架。它的数据源来自 `akshare`，采用事件驱动的策略 API 设计，支持完整的回测与模拟盘工作流。

**适用场景：**
- A 股日线 / 分钟线回测
- 策略开发验证
- 模拟盘交易
- 选股 / 行业轮动 / 资金流分析
- 投资组合优化

**不支持：**
- 港股、美股、期货、期权、加密货币等非 A 股品种
- 高频 T+0 策略（A 股为 T+1 交易制度）

---

## 2. 安装

```bash
# 核心依赖
pip install akshare pandas numpy matplotlib scipy

# 可选：更好的缓存性能
pip install pyarrow
```

确认安装成功：

```python
from eqlib import *
print("eqlib OK")
```

---

## 3. 快速开始：5 分钟写一个策略

一个完整的策略由三个部分组成：`initialize`（初始化）、`handle_data`（每日逻辑）、以及调度函数（`run_daily` 等）。

```python
from eqlib import *

# ========== 初始化函数 ==========
def initialize(context):
    # 设置要操作的股票
    g.security = '601390'          # 工商银行
    set_benchmark('000300.XSHG')   # 沪深300 作为基准
    set_option('use_real_price', True)

    # 设置初始资金（在 run_backtest 中也指定，这里仅作策略内参考）
    # context.portfolio.starting_cash 可读取

    # 每天开盘时运行
    run_daily(market_open, time='every_bar')

# ========== 每日交易逻辑 ==========
def market_open(context):
    # 获取过去 20 天的收盘价
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()

    # 获取当前价格（最近一根 bar 的收盘价）
    current_price = hist['close'].iloc[-1]

    # 金叉买入，死叉卖出（简化示例）
    if current_price > ma20 * 1.02:
        # 用可用现金全仓买入
        order_value(g.security, context.portfolio.available_cash)
        log.info("买入 %s，价格 %.3f" % (g.security, current_price))

    elif current_price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        # 清仓卖出
        order_target(g.security, 0)
        log.info("卖出 %s，价格 %.3f" % (g.security, current_price))

# ========== 运行回测 ==========
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,          # 初始资金 10 万元
    benchmark='000300.XSHG',       # 对比基准
    securities=['601390'],         # 预加载数据
    report_dir='reports',
)
```

运行后会输出：
- `reports/backtest_YYYYMMDD_HHMMSS.png` — 价格与交易标记图
- `reports/backtest_YYYYMMDD_HHMMSS.md` — 回测摘要报告
- `reports/backtest_YYYYMMDD_HHMMSS.json` — 结构化数据

---

## 4. 策略生命周期

```
initialize(context)          ← 回测开始时调用一次
    |
    v
before_trading_start(ctx, data)   ← 每个交易日开盘前调用（可选注册）
    |
    v
run_daily / run_weekly / run_monthly 定时函数
    |
    v
handle_data(context, data)   ← 每个交易日调用一次
    |
    v
after_trading_end(ctx, data) ← 每个交易日收盘后调用（可选注册）
```

### 4.1 `initialize(context)`

策略入口，每个策略必须定义。

```python
def initialize(context):
    g.security = '601390'           # 存入全局对象
    set_benchmark('000300.XSHG')    # 设置对比基准
    set_order_cost(OrderCost(       # 设置手续费（可选）
        open_tax=0,
        close_tax=0.001,            # 卖出印花税 0.1%
        open_commission=0.0003,     # 买入佣金 0.03%
        close_commission=0.0003,    # 卖出佣金 0.03%
        min_commission=5,           # 最低佣金 5 元
    ))
    run_daily(market_open, time='every_bar')
```

### 4.2 `handle_data(context, data)`

每日交易逻辑。也可以用 `run_daily` 代替。

```python
def handle_data(context, data):
    # data[security] 返回当前日的 bar 对象（open/high/low/close/volume/money）
    bar = data.get(g.security)
    if bar:
        log.info("%s 今日收盘: %.2f" % (g.security, bar.close))
```

### 4.3 盘前/盘后回调

```python
from eqlib import before_trading_start, after_trading_end

def before_start(context, data):
    log.info("盘前检查...")

def after_end(context, data):
    log.info("盘后统计: 持仓 %d 只" % len(context.portfolio.positions))

before_trading_start(before_start)
after_trading_end(after_end)
```

### 4.4 `g` 全局对象

`g` 是策略级别的持久化存储，跨交易日有效。

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0
    g.ma_period = 20

def market_open(context):
    g.hold_days += 1
    log.info("持有天数: %d" % g.hold_days)
```

---

## 5. 资金管理：设置初始资金与仓位控制

### 5.1 设置初始资金

在 `run_strategy` 或 `run_backtest` 中指定：

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=500000,   # 50 万元初始资金
)
```

### 5.2 读取账户状态

```python
def market_open(context):
    cash = context.portfolio.available_cash      # 可用现金
    total = context.portfolio.total_value         # 总资产（现金 + 持仓市值）
    positions = context.portfolio.positions       # 持仓字典
    returns = context.portfolio.returns           # 总收益率

    log.info("现金: %.2f, 总资产: %.2f, 收益率: %.2f%%"
             % (cash, total, returns * 100))
```

### 5.3 仓位控制方式

| 方式 | 函数 | 说明 |
|------|------|------|
| **全仓买入** | `order_value(security, context.portfolio.available_cash)` | 用全部可用现金买入 |
| **按比例买入** | `order_value(security, context.portfolio.available_cash * 0.5)` | 用 50% 现金买入 |
| **按固定金额** | `order_value(security, 50000)` | 买入 5 万元 |
| **按固定股数** | `order(security, 1000)` | 买入 1000 股（自动取整到 100 的整数倍） |
| **调到目标股数** | `order_target(security, 5000)` | 调整持仓到 5000 股 |
| **调到目标市值** | `order_target_value(security, 100000)` | 调整持仓市值到 10 万 |
| **清仓** | `order_target(security, 0)` | 全部卖出 |

A 股最小交易单位为 **100 股（1 手）**，所有买入会自动向下取整到 100 的整数倍。

### 5.4 多股等权配置示例

```python
def market_open(context):
    stocks = ['601390', '600519', '000858']
    weight = context.portfolio.available_cash / len(stocks)

    for sec in stocks:
        order_value(sec, weight)   # 每只股票平分可用资金
```

---

## 6. 交易 API：买入与卖出

### 6.1 `order(security, amount)`

按股数买卖，正数买入，负数卖出。

```python
order('601390', 1000)     # 买入 1000 股
order('601390', -500)     # 卖出 500 股
```

### 6.2 `order_value(security, value)`

按金额买卖，正数买入，负数卖出。

```python
order_value('601390', 50000)   # 买入 5 万元
order_value('601390', -30000)  # 卖出 3 万元
```

### 6.3 `order_target(security, amount)`

调整持仓到目标股数。

```python
order_target('601390', 5000)   # 持仓调到 5000 股
order_target('601390', 0)      # 清仓
```

### 6.4 `order_target_value(security, value)`

调整持仓到目标市值。

```python
order_target_value('601390', 100000)  # 持仓市值调到 10 万
order_target_value('601390', 0)       # 清仓
```

---

## 7. 数据拉取

### 7.1 历史日线数据

```python
# 方式一：在 handle_data 中使用 history()
def market_open(context):
    close = history(20, '1d', 'close', security='601390')
    ma20 = close.mean()

# 方式二：attribute_history（更灵活）
    hist = attribute_history('601390', 30, '1d',
                             fields=['open', 'close', 'volume', 'high', 'low'])

# 方式三：get_price（支持指定日期范围）
    df = get_price('601390',
                   start_date='2024-01-01',
                   end_date='2024-06-30',
                   fields=['open', 'high', 'low', 'close', 'volume'])
```

返回的 DataFrame 包含：`open`, `high`, `low`, `close`, `volume`, `money`, `pct_change`, `turnover` 等列，索引为日期。

### 7.2 实时行情快照

```python
# 获取全部 A 股当前快照
data = get_current_data()
print(data['601390'])  # {'code': '601390', 'name': '工商银行', 'price': 5.2, ...}

# 获取单只股票信息
info = get_security_info('601390')
print(info.name, info.industry)

# 获取估值数据
val = get_valuation('601390')
print(val['pe'], val['pb'], val['total_value'])
```

### 7.3 选股与扫描

```python
# 扫描符合条件的股票
candidates = scan_market(
    min_price=10,
    min_pct_change=3,
    max_pct_change=5,
    max_pe=50,
)

# 按财务指标筛选
screened = get_financial_screen(
    min_pe=5, max_pe=30,
    min_pb=0.5, max_pb=3,
    min_roe=0.1,
)
```

### 7.4 指数与行业成分股

```python
# 指数成分股
constituents = get_index_stocks('000300.XSHG')  # 沪深300 成分股

# 行业列表及成分股
industries = get_industry_list()                # 所有行业板块
stocks = get_industry_stocks('白酒')            # 白酒行业成分股

# 概念板块
concepts = get_concept_list()                   # 所有概念板块
concept_stocks = get_concept_stocks('人工智能')  # 人工智能概念股

# 单只股票所属行业
info = get_industry('601390')
print(info['industry'])
```

### 7.5 分钟线数据

```python
# 获取 5 分钟线
df_5m = fetch_minute_data('601390', period='5m')

# 使用 get_price_minute
df_5m = get_price_minute('601390', count=100, period='5m',
                         fields=['open', 'close', 'volume'])
```

支持的周期：`1m`, `5m`, `15m`, `30m`, `60m`

### 7.6 Tick 数据

```python
df_tick = get_tick_data('601390')
```

### 7.7 资金流向与龙虎榜

```python
# 个股资金流向
flow = get_money_flow('601390', count=30)

# 龙虎榜
billboard = get_billboard_list(date='20241201')

# 指数成分股权重
weights = get_index_weights('000300.XSHG')
```

### 7.8 ST 标记与额外字段

```python
st_flags = get_extras('is_st')        # 哪些是 ST 股
net_vals = get_extras('net_value')     # 净资产估值
```

### 7.9 交易日历

```python
days = get_trade_days(
    start_date='2024-01-01',
    end_date='2024-12-31',
)

# 最近 10 个交易日
recent_days = get_trade_days(count=10)
```

### 7.10 财务摘要

```python
financial = get_financial_abstract('601390')
print(financial)
```

### 7.11 下载与加载本地 CSV

```python
# 下载数据到本地
path = download_stock_data('601390', '2020-01-01', '2024-12-31',
                           output_dir='data')

# 从本地 CSV 加载
df = load_csv('data/601390_daily.csv')
```

---

## 8. 计算工具库

`eqlib.utils` 提供了完整的技术指标、统计分析、资金管理和支撑阻力位计算工具。

### 8.1 技术指标

```python
from eqlib import utils

# 均线
ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)

# MACD
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)

# RSI
rsi14 = utils.rsi(close, 14)

# KDJ
k, d, j = utils.kdj(high, low, close, period=9)

# 布林带
upper, mid, lower = utils.boll(close, period=20)

# ATR（波动率）
atr14 = utils.atr(high, low, close, 14)

# ADX（趋势强度）
pdi, mdi, adx, adxr = utils.adx(high, low, close, 14)
```

更多指标：`cci`, `wr`（威廉指标）, `roc`（变化率）, `obv`（能量潮）, `golden_cross`, `death_cross`

### 8.2 统计分析

```python
# 滚动夏普比率
sharpe = utils.rolling_sharpe(daily_returns, window=20)

# 最大回撤
max_dd, dd_start, dd_end = utils.max_drawdown(equity_curve)

# 风险价值
var_5 = utils.value_at_risk(daily_returns, confidence=0.05)

# Z-Score
z = utils.zscore(close, window=20)

# 年化复合增长率
cagr_val = utils.cagr(start_value, end_value, years)
```

### 8.3 资金管理

```python
# Kelly 公式
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
# 返回 0.25，即建议投入 25% 资金

# ATR 仓位管理
shares = utils.atr_position_size(
    capital=100000, risk_pct=0.02,
    atr=0.30, n_atr=2.0,
)  # 根据波动率自动计算股数

# 固定比例风险
shares = utils.fixed_fraction_size(
    capital=100000, risk_pct=0.02,
    entry_price=10.0, stop_price=9.5,
)  # 最多亏 2% 资金的股数

# 风险平价权重
weights = utils.risk_parity_weights([0.15, 0.25, 0.20])
```

### 8.4 支撑阻力位

```python
# 枢轴点
pp, r1, s1, r2, s2 = utils.pivot_classic(high, low, close)

# 支撑/阻力位（摆动点聚类）
sr = utils.support_resistance_levels(high, low, close)
print(sr['nearest_support'])
print(sr['nearest_resistance'])

# 斐波那契回撤
fib = utils.fibonacci_retracement(high, low, close)
print(fib[0.382], fib[0.618])

# 唐奇安通道（海龟交易法）
upper, mid, lower = utils.donchian(high, low, close)

# 成交量分布
vp = utils.volume_profile_support_resistance(close, volume)
print(vp['poc'])  # 最大成交量价格

# ATR 追踪止损
stop = utils.trailing_stop(close, atr=atr_val, multiplier=2.0)

# 缺口检测
gap_up, gap_down = utils.gap_up_down(open_, high, low, close)
```

> **详细说明**：每个工具的具体算法和计算原理见 [**工具库参考**](utils_reference.md)。

---

## 9. 运行回测

### 9.1 方式一：`run_strategy`（推荐）

一站式运行回测并生成所有报告。

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390', '600519'],
    report_dir='reports',
)
```

### 9.2 方式二：`run_backtest`（精细控制）

只运行回测，不生成报告。适合自定义后续处理。

```python
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390'],
)

if result:
    print("最终总资产: %.2f" % result['context'].portfolio.total_value)
    print("交易次数: %d" % len(result['trade_log']))
```

### 9.3 基准对比说明

回测时通过 `benchmark` 参数设置基准（默认 `000300.XSHG` 沪深300）。回测结果会自动计算策略收益与基准收益的 **alpha**、**beta** 和 **information ratio**，并在图表上叠加显示。

---

## 10. 回测报告与图表解读

### 10.1 图表（PNG）

图表文件：`reports/backtest_YYYYMMDD_HHMMSS.png`

**图表包含以下元素：**

```
  |                                                     |  Portfolio Value
P |  ---MA5                                              |
r |  ---MA20                                             |
i |  ---Close                                            |
c |                                                      |
e |     [SELL]    [BUY]                                  |
  |    o          o     o[SELL]                          |
  |   / \  ===== / \___/   \                             |
  |  /   \      /           \                            |
  | /     \====/             \=====                      |
  +------------------------------------------------------|-> Date
```

- **灰色线 (Close)**：股票每日收盘价
- **蓝色线 (MA5)**：5 日均线（短期趋势）
- **橙色线 (MA20)**：20 日均线（中期趋势）
- **绿色圆圈 (BUY)**：买入点，标注在价格下方
- **红色圆圈 (SELL)**：卖出点，标注在价格上方
- **绿色阴影区域**：持仓期间
- **绿色线 (右侧轴)**：投资组合总资产价值变化
- **标题**：显示该股票的总盈亏金额和百分比

**如何看图表：**
1. **价格与均线关系**：收盘价持续在 MA5/MA20 之上，说明处于上升趋势
2. **买卖点合理性**：BUY 点应在价格低位附近，SELL 点应在价格高位附近
3. **持仓区域**：绿色阴影区域越短，说明交易越频繁；区域越长，说明持仓越久
4. **资产曲线**：右轴的组合价值曲线持续向上说明策略盈利，向下说明亏损

### 10.2 Markdown 报告

文件：`reports/backtest_YYYYMMDD_HHMMSS.md`

```markdown
# Backtest Report: 601390

## Summary
- **Period**: 2024-01-01 to 2024-12-31
- **Initial Capital**: 100,000.00
- **Final Value**: 115,342.00
- **P&L**: +15,342.00 (+15.34%)
- **Buy Orders**: 5
- **Sell Orders**: 4

## Trade Log
| # | Date | Action | Security | Price | Amount | Commission |
|---|------|--------|----------|-------|--------|------------|
| 1 | 2024-01-15 | BUY | 601390 | 4.850 | 20,000 | 29.10 |
| 2 | 2024-03-20 | SELL | 601390 | 5.120 | 20,000 | 30.72 |

## Positions
- **601390**: 5000 shares, avg_cost=5.020

## Portfolio Values
365 data points recorded.
- Start: 2024-01-01
- End: 2024-12-31
```

**如何看报告：**
1. **P&L**：策略的绝对收益和收益率
2. **Trade Log**：每笔交易的时间、价格、数量、手续费
3. **Positions**：回测结束时的持仓状态
4. **Buy/Sell 数量差**：如果 Buy 比 Sell 多 1 个，说明最后还持有仓位

### 10.3 JSON 报告

文件：`reports/backtest_YYYYMMDD_HHMMSS.json`

结构化的机器可读格式，包含所有交易记录、持仓、每日组合价值。适合用 Python 进一步分析：

```python
import json

with open('reports/backtest_20240101_120000.json') as f:
    report = json.load(f)

print("总收益: %.2f%%" % report['pnl_pct'])
print("交易次数:", report['num_trades'])
```

---

## 11. 风险与归因分析

### 11.1 `analyze_returns`：综合风险指标

```python
from eqlib import analyze_returns

metrics = analyze_returns(result, risk_free_rate=0.03)
```

返回指标：

| 指标 | 说明 | 好值 |
|------|------|------|
| `total_return` | 总收益率 | 正数越大越好 |
| `annual_return` | 年化收益率 | 正数越大越好 |
| `annual_volatility` | 年化波动率 | 低一些更好 |
| `sharpe_ratio` | 夏普比率 | > 1 为好，> 2 为优秀 |
| `sortino_ratio` | 索提诺比率 | 只考虑下行风险，> 1 为好 |
| `max_drawdown` | 最大回撤 | 接近 0 越好 |
| `calmar_ratio` | 卡玛比率 (年化收益/最大回撤) | > 1 为好 |
| `alpha` | 超额收益（年化） | 正数为跑赢基准 |
| `beta` | 市场敏感度 | 1 表示与大盘同步，> 1 波动更大 |
| `information_ratio` | 信息比率 | > 0.5 为好 |
| `win_rate` | 日胜率 | > 0.5 为好 |

### 11.2 `brinson_attribution`：归因分析

将收益分解为 **配置效应**、**选股效应** 和 **交互效应**。

```python
from eqlib import brinson_attribution

attr = brinson_attribution(result)
print("配置效应: %.4f" % attr['allocation_effect'])
print("选股效应: %.4f" % attr['selection_effect'])
```

### 11.3 `fama_french_analysis`：因子分析

```python
from eqlib import fama_french_analysis

ff = fama_french_analysis(result)
print("市场 Beta: %.3f" % ff['market_beta'])
print("年化 Alpha: %.4f" % ff['alpha_annual'])
```

---

## 12. 模拟盘交易

模拟盘使用实时行情数据持续运行策略，适合在实盘前验证。

```python
from eqlib import run_paper_trade

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    # ... 策略逻辑
    pass

# 启动模拟盘，每 60 秒刷新一次
result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,          # 轮询间隔（秒）
)
```

模拟盘会持续输出当前总资产和盈亏：

```
[14:30:00] total_value=102,345.67  PnL=+2,345.67 (+2.35%)
[14:31:00] total_value=102,456.78  PnL=+2,456.78 (+2.46%)
```

按 `Ctrl+C` 停止。

---

## 13. 常见问题

### Q: 如何设置手续费？

```python
set_order_cost(OrderCost(
    open_tax=0,               # 买入印花税（A 股为 0）
    close_tax=0.001,          # 卖出印花税 0.1%
    open_commission=0.0003,   # 买入佣金 0.03%
    close_commission=0.0003,  # 卖出佣金 0.03%
    min_commission=5,         # 最低佣金 5 元
))
```

### Q: 如何做多只股票？

```python
def initialize(context):
    g.stocks = ['601390', '600519', '000858']
    run_daily(rebalance, time='every_bar')

def rebalance(context):
    n = len(g.stocks)
    weight = context.portfolio.total_value / n
    for sec in g.stocks:
        order_target_value(sec, weight)
```

### Q: 如何设置股票池？

```python
def initialize(context):
    # 设置 universe
    set_universe(['601390', '600519', '000858'])

def market_open(context):
    universe = get_universe()  # 获取当前股票池
    for sec in universe:
        # ... 策略逻辑
```

### Q: 如何加速大回测？

```python
# 1. 预加载数据（传入 securities 参数）
result = run_backtest(initialize, '2020-01-01', '2024-12-31',
                      securities=['601390', '600519', ...])

# 2. 设置磁盘缓存
from eqlib import set_cache_dir
set_cache_dir('/path/to/cache')

# 3. 清除缓存重新开始
from eqlib import clear_cache
clear_cache()
```

### Q: 如何在策略内记录自定义数据？

```python
def market_open(context):
    price = history(1, '1d', 'close', '601390').iloc[-1]
    record(price=price, ma5=ma5, signal='BUY')
```

记录的数据会出现在 JSON 报告的 `recorded_values` 字段中。

### Q: A 股 T+1 限制如何处理？

`eqlib` 内部自动处理 T+1 限制：当天买入的股票当天不能卖出（通过 `closeable_amount` 控制）。

### Q: 策略报错 "no price data" 怎么办？

检查股票代码是否正确。A 股代码格式为 6 位数字（如 `'601390'`），不需要带交易所后缀。如果使用了 `set_benchmark`，基准可以使用后缀如 `'000300.XSHG'`。
