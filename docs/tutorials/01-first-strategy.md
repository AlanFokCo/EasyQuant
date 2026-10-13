# Tutorial 01: 写第一个策略

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 手写双均线策略，理解 `initialize` / `run_daily` / `order_*` 与 `g` 的用法 |
    | **预计用时** | 约 45 分钟 |
    | **前置** | [Tutorial 00: 环境与量化基础](00-getting-started.md) |

> 从零开始，用 EasyQuant 编写并运行你的第一个量化交易策略。

---

## 目录

1. [准备工作](#1-准备工作)
2. [策略设计：双均线](#2-策略设计双均线)
3. [编写策略代码](#3-编写策略代码)
4. [运行回测](#4-运行回测)
5. [逐步理解策略框架](#5-逐步理解策略框架)
6. [扩展：加入更多条件](#6-扩展加入更多条件)
7. [下一步](#7-下一步)

---

## 1. 准备工作

### 1.1 安装 eqlib

**要求：Python 3.10 及以上。**

```bash
# 方式一：PyPI 安装（推荐，无需克隆仓库）
pip install easyquant-eqlib

# 方式二：从源码安装（在仓库根目录）
# cd EasyQuant
# pip install .   # 或：pip install -e .
```

若未正确安装 `eqlib`，`import eqlib` 会失败。更详细的说明与排错见 [Tutorial 00](00-getting-started.md) 与 [FAQ](../project/faq.md)。

### 1.2 验证安装

```python
from eqlib import *
print("eqlib OK")
```

如果输出 `eqlib OK`，说明安装成功。

### 1.3 创建策略文件

创建一个 Python 文件，比如 `my_first_strategy.py`：

```bash
touch my_first_strategy.py
```

---

## 2. 策略设计：双均线

我们来实现一个经典的 **双均线策略**：

### 策略规则

- **买入信号**：5 日均线上穿 20 日均线（金叉），且当前价格高于 5 日均线
- **卖出信号**：5 日均线下穿 20 日均线（死叉）
- **仓位管理**：买入时使用 95% 可用现金（留出手续费缓冲），卖出时全部清仓
- **操作标的**：601398（工商银行）
- **回测区间**：2024-01-01 至 2024-12-31

### 为什么选择双均线？

- 逻辑简单，容易理解
- 不需要复杂的数据或计算
- 可以作为学习框架的"Hello World"
- 可以方便地扩展和改造

---

## 3. 编写策略代码

在 `my_first_strategy.py` 中写入以下代码：

```python
from eqlib import *

# ========== 模块级常量（配置参数） ==========
# 引擎会在调用 initialize 之前清空 g 的全部属性（见 §5.1），
# 所以配置参数用普通常量保存，不要挂在模块顶层的 g 上
SECURITY = '601398'       # 操作标的（工商银行）
FAST_PERIOD = 5           # 短期均线周期
SLOW_PERIOD = 20          # 长期均线周期


# ========== 初始化函数 ==========
def initialize(context):
    """策略启动时调用一次"""
    # 设置对比基准
    set_benchmark('000300.XSHG')

    # 设置交易成本（A 股标准费率）
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,          # 印花税 0.05%（2023年8月起减半）
        open_commission=0.00025,   # 买入佣金 0.025%
        close_commission=0.00025,  # 卖出佣金 0.025%
        min_commission=5,         # 最低佣金 5 元
    ))

    # 把参数挂到 g 上，供每个交易日的回调使用
    # g 在 initialize 之后不会被清除，可跨交易日保持
    g.security = SECURITY
    g.fast_period = FAST_PERIOD
    g.slow_period = SLOW_PERIOD

    # 每天运行一次
    run_daily(market_open, time='every_bar')

    log.info('双均线策略初始化完成: %s, MA%d/MA%d' % (
        g.security, g.fast_period, g.slow_period))


# ========== 每日交易逻辑 ==========
def market_open(context):
    """每个交易日运行"""
    security = g.security

    # 1. 获取最近 25 天的收盘价（多取几天，确保能计算 20 日均线）
    close_data = attribute_history(security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return  # 数据不足，跳过

    close_prices = close_data['close']

    # 2. 计算均线：对最近 N 根收盘价求均值
    ma_fast = close_prices.tail(g.fast_period).mean()
    ma_slow = close_prices.tail(g.slow_period).mean()
    current_price = close_prices.iloc[-1]

    # 3. 判断买入条件：多头排列（价格 > 快线 > 慢线）
    if current_price > ma_fast > ma_slow:
        # 检查当前是否没有持仓
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            # 只用 95% 现金：留出佣金缓冲，避免订单因差几元手续费而资金不足
            order_value(security, context.portfolio.available_cash * 0.95)
            log.info('买入 %s @ %.3f, MA快=%.3f, MA慢=%.3f' % (
                security, current_price, ma_fast, ma_slow))

    # 4. 判断卖出条件：空头排列
    elif current_price < ma_fast < ma_slow:
        # 检查当前是否有持仓
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount > 0:
            order_target(security, 0)  # 清仓
            log.info('卖出 %s @ %.3f, MA快=%.3f, MA慢=%.3f' % (
                security, current_price, ma_fast, ma_slow))

    # 5. 记录当前状态（会出现在报告中）
    record(
        price=current_price,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        cash=context.portfolio.available_cash,
    )


# ========== 运行回测 ==========
if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2024-01-01',
        end_date='2024-12-31',
        starting_cash=100000,       # 10 万元
        benchmark='000300.XSHG',
        securities=[SECURITY],      # 预加载数据，加速回测
        report_dir='reports',
    )
```

> **信号口径说明**：上面的 `价格 > MA5 > MA20` 是**状态判断**（多头/空头排列），不是严格意义的"当日穿越"检测。要对金叉/死叉当日精确下单，需要比较前后两天的均线关系，写法见 [examples/02_write_strategy.py](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/02_write_strategy.py) 中的 `golden_cross` / `death_cross` 判定。

### 代码结构说明

```
导入库
  |
  v
模块级常量     ← 配置参数（SECURITY / FAST_PERIOD / SLOW_PERIOD）
  |
  v
initialize()   ← 只调用一次：设置基准、费率、调度，并把参数挂到 g
  |
  v
market_open()  ← 每个交易日调用：获取数据 → 计算信号 → 下单
  |
  v
run_strategy() ← 运行回测并生成报告
```

---

## 4. 运行回测

```bash
python my_first_strategy.py
```

运行后终端会打印日志与 `reports/` 下的报告路径。下面是一段**示意输出**（数字与日期仅为格式示例，以你实际运行为准）：

```
09:30:01 | ℹ️ INFO     | 双均线策略初始化完成: 601398, MA5/MA20
09:30:05 | ℹ️ INFO     | 买入 601398 @ 4.850, MA快=4.820, MA慢=4.780
09:30:12 | ℹ️ INFO     | 卖出 601398 @ 5.120, MA快=5.080, MA慢=5.110
...

==================================================
Chart:  reports/backtest_20260503_143000.png
HTML:   reports/backtest_20260503_143000.html
Report: reports/backtest_20260503_143000.md
Data:   reports/backtest_20260503_143000.json
```

日志行的实际格式为 `HH:MM:SS | ℹ️ INFO | 消息`。报告文件名的共同部分是时间戳，每次运行都不同。

> **成交拦截**：引擎默认开启涨跌停检查（`check_price_limit=True`）——涨停开盘的买单、跌停开盘的卖单会被取消并记录 `cancel_reason`；停牌当日的订单同样会被取消。可用 `set_option('check_price_limit', False)` 关闭涨跌停拦截。另外，持仓标的一旦退市，超过 30 个交易日无行情后会被强制清算（交易记录中标为 `DELIST_LIQUIDATE`）。

### 查看报告

- **图表**（PNG）：价格曲线 + 买卖点标注
- **HTML 报告**：交互式完整结果；**如何阅读各区块**见 [报告格式详解](../reference/reports-format.md)
- **Markdown 报告**：文字摘要
- **JSON 数据**：结构化数据，可进一步分析

---

## 5. 逐步理解策略框架

### 5.1 `g` 全局对象

`g` 是跨交易日的持久化存储。**注意：回测引擎会在调用 `initialize` 之前清空 `g` 的所有属性**，所以不能在模块顶层给 `g` 赋值作为配置参数。

**正确用法：**

```python
# 模块级常量 — 配置参数（不会被引擎清除）
SECURITY = '601398'
MA_PERIOD = 20

# g — 运行时状态（在 initialize 中初始化，跨交易日保持）
def initialize(context):
    g.hold_days = 0       # 在 initialize 中初始化
    g.max_loss_pct = 0.08

def market_open(context):
    g.hold_days += 1
    if g.hold_days > 30:
        order_target(SECURITY, 0)  # 使用模块常量
```

**错误用法（模块顶层赋值会被引擎清除）：**

```python
# ❌ 错误！这些值会在 initialize 之前被清除
g.security = '601398'
g.ma_period = 20
```

### 5.2 `context` 上下文对象

`context` 包含当前回测的运行状态：

```python
def market_open(context):
    # 组合信息
    context.portfolio.starting_cash     # 初始资金
    context.portfolio.available_cash    # 可用现金
    context.portfolio.total_value       # 总资产（现金 + 持仓市值）
    context.portfolio.returns           # 总收益率

    # 持仓
    context.portfolio.positions         # 字典 {security: Position}
    # Position 有这些属性：
    #   .security   股票代码
    #   .amount     持仓股数
    #   .avg_cost   持仓成本价
    #   .closeable_amount  可卖股数（T+1 限制）

    # 回测参数
    context.current_dt               # 当前日期
    context.start_date               # 回测起始日期
    context.end_date                 # 回测结束日期
    context.benchmark                # 基准代码
```

### 5.3 调度函数

```python
# 每天运行（最常用）
run_daily(market_open, time='every_bar')

# 每周运行（如每周一）
run_weekly(rebalance, day_of_week=0, time='every_bar')  # day_of_week: 0=周一 … 4=周五

# 每月运行（如每月 1 号）
run_monthly(rebalance, day_of_month=1, time='every_bar')
```

### 5.4 数据获取

```python
# 方式一：attribute_history（策略中最常用）
# 获取最近 N 根 bar 的数据
hist = attribute_history('601398', 20, '1d', ['close'])

# 方式二：history（简洁写法）
close = history(20, '1d', 'close', security='601398')

# 方式三：get_price（指定日期范围，适合 initialize 中）
df = get_price('601398', start_date='2024-01-01', end_date='2024-06-30')
```

### 5.5 交易 API

```python
# 按股数买卖（正数=买入，负数=卖出）
order('601398', 1000)        # 买入 1000 股

# 按金额买卖
order_value('601398', 50000)  # 买入 5 万元

# 调到目标股数
order_target('601398', 5000)  # 调到 5000 股
order_target('601398', 0)     # 清仓

# 调到目标市值
order_target_value('601398', 100000)  # 持仓市值 10 万
```

### 5.6 日志与记录

```python
# 日志输出（出现在控制台和日志文件中）
log.info('买入 %s @ %.2f' % (security, price))
log.warn('数据不足，跳过')

# 记录数值：保存在 result['recorded_values'] 中
# 引擎每天还会自动记录 total_value 与 cash，用于报告的净值曲线
record(price=price, ma5=ma5, signal='BUY')
```

---

## 6. 扩展：加入更多条件

双均线策略只是一个起点。下面逐步添加条件，让策略更完善。

### 6.1 加入止损

```python
def market_open(context):
    security = g.security

    # ... 获取数据、计算均线 ...

    # 止损检查
    if security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        loss_pct = (current_price - position.avg_cost) / position.avg_cost
        if loss_pct < -0.08:  # 亏损超过 8%
            order_target(security, 0)
            log.info('止损卖出 %s @ %.3f，亏损 %.2f%%' % (
                security, current_price, loss_pct * 100))
            return

    # ... 原有金叉/死叉逻辑 ...
```

### 6.2 加入成交量过滤

```python
# 获取收盘数据
close_data = attribute_history(security, 25, '1d', ['close', 'volume'])

# 成交量需要高于 20 日均量（避免流动性不足的股票）
avg_volume = close_data['volume'].tail(20).mean()
current_volume = close_data['volume'].iloc[-1]

if current_volume < avg_volume * 0.5:
    return  # 成交量不足，不操作
```

### 6.3 加入大盘过滤

```python
# 如果沪深 300 在 20 日均线以下，不做多
index_hist = attribute_history('000300.XSHG', 20, '1d', ['close'])
index_ma20 = index_hist['close'].mean()
index_price = index_hist['close'].iloc[-1]

if index_price < index_ma20:
    return  # 大盘弱势，不做多
```

### 6.4 扩展为多股轮动

```python
# 模块级常量 — 不要在模块顶层给 g 赋值
SECURITIES = ['601398', '600519', '000858']

def initialize(context):
    g.securities = SECURITIES
    # ...

def market_open(context):
    for security in g.securities:
        # 对每只股票执行相同的逻辑
        hist = attribute_history(security, 25, '1d', ['close'])
        # ... 信号判断 ...
```

完整的多股版本见 [examples/02_write_strategy.py](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/02_write_strategy.py)。

---

## 7. 下一步

你已经学会了如何编写和运行第一个策略。接下来：

- **[Tutorial 02: 回测验证](02-backtesting.md)** — 深入理解回测结果，解读报告，判断策略是否有效
- **[Tutorial 03: 策略优化与改进](03-optimization.md)** — 参数调优、组合优化、归因分析
- **[Tutorial 04: 模拟盘到实盘](04-live-trading.md)** — 实时行情验证和 PTrade/QMT 实盘部署
- **[Tutorial 05: RSI 均值回归策略](05-rsi-mean-reversion.md)** — 学习另一类经典策略：均值回归

### 练习

1. 修改均线周期（如 MA10/MA30），观察结果变化
2. 给策略加上止损（如 -8% 强制卖出）
3. 换成另一只股票回测
4. 尝试把 `order_value(..., available_cash * 0.95)` 改为 `order_value(..., available_cash * 0.5)`，只半仓操作


## 支撑压力位的完整示例

需要带止损风险预算、成交跟踪和组合熔断的版本，可从[支撑压力风险预算策略](../explanation/sr-risk-budget.md)与 `examples/25_sr_risk_budget.py` 开始。其信号在收盘回调产生，最早次日开盘撮合；工程测试不构成盈利证据。

可用 `--allow-breakout` 比较直接突破，或用 `scripts/research_sr_risk_budget.py` 重放固定候选与分段。此次完整区间收益改善，但验证期和后段未通过；不应只凭累计收益选择策略。
