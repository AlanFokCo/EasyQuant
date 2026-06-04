# Writing Strategies

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Understand the strategy skeleton and write your first strategy |
    | **Prerequisite** | [Installation & Quick Start](install.md) |

---
## 1. Quick Start: Write and Run a Strategy

A runnable strategy must contain at least: **`initialize(context)`** (initialization) and a trading function registered with **`run_daily`**.

```python
from eqlib import *

def initialize(context):
    g.security = '601390'          # Industrial and Commercial Bank of China
    set_benchmark('000300.XSHG')   # CSI 300 as benchmark
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

After running, four report files will be generated: PNG, HTML, Markdown, and JSON. Open the `.html` file in a browser first to view the complete report.

> Order execution model: The `order*` API series only places orders in the current callback; actual execution occurs at the **next trading day's opening price**.

---

## 2. Strategy Lifecycle

```
initialize(context)          ← Called once at the start of the backtest
    |
    v
before_trading_start(ctx, data)   ← Called before market open on each trading day (optional)
    |
    v
run_daily / run_weekly / run_monthly scheduled functions
    |
    v
handle_data(context, data)   ← Called once per trading day
    |
    v
after_trading_end(ctx, data) ← Called after market close on each trading day (optional)
```

### 2.1 `initialize(context)`

The strategy entry point. Every strategy must define this function.

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

Daily trading logic. Can also be replaced with `run_daily`.

```python
def handle_data(context, data):
    bar = data.get(g.security)
    if bar:
        log.info("%s today's close: %.2f" % (g.security, bar.close))
```

### 2.3 Pre-market / Post-market Callbacks

```python
from eqlib import before_trading_start, after_trading_end

def before_start(context, data):
    log.info("Pre-market check...")

def after_end(context, data):
    log.info("Post-market summary: holding %d stocks" % len(context.portfolio.positions))

before_trading_start(before_start)
after_trading_end(after_end)
```

### 2.4 `g` Global Object

`g` is strategy-level persistent storage that remains valid across trading days.

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0

def market_open(context):
    g.hold_days += 1
```

---
