# 编写策略

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 理解策略骨架并编写第一个策略 |
    | **前置** | [安装与快速上手](install.md) |

---
## 1. 快速开始：编写并运行一个策略

一个可运行的策略至少包含：**`initialize(context)`**（初始化），以及用 **`run_daily`** 注册的交易函数。

```python
from eqlib import *

def initialize(context):
    g.security = '601390'          # 工商银行
    set_benchmark('000300.XSHG')   # 沪深300 作为基准
    set_option('use_real_price', True)
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    current_price = hist['close'].iloc[-1]

    if current_price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif current_price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        order_target(g.security, 0)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390'],
    report_dir='reports',
)
```

运行后会输出 PNG、HTML、Markdown、JSON 四类报告文件。优先在浏览器打开 `.html` 查看完整报告。

> 订单执行模型：`order*` 系列 API 在当前回调里只是下单，实际按**下一个交易日开盘价**成交。

---

## 2. 策略生命周期

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

### 2.1 `initialize(context)`

策略入口，每个策略必须定义。

```python
def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')
```

### 2.2 `handle_data(context, data)`

每日交易逻辑。也可以用 `run_daily` 代替。

```python
def handle_data(context, data):
    bar = data.get(g.security)
    if bar:
        log.info("%s 今日收盘: %.2f" % (g.security, bar.close))
```

### 2.3 盘前/盘后回调

```python
from eqlib import before_trading_start, after_trading_end

def before_start(context, data):
    log.info("盘前检查...")

def after_end(context, data):
    log.info("盘后统计: 持仓 %d 只" % len(context.portfolio.positions))

before_trading_start(before_start)
after_trading_end(after_end)
```

### 2.4 `g` 全局对象

`g` 是策略级别的持久化存储，跨交易日有效。

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0

def market_open(context):
    g.hold_days += 1
```

---

