!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §3](03_quickstart_strategy.md) · [下一章 §5](05_capital_position.md)

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
