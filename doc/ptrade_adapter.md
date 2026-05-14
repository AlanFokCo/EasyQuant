# PTrade/QMT 策略适配器

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 理解本地回测与 QMT 实盘之间的差异，以及导入与 API 映射关系 |
    | **前置** | 已能使用 `eqlib` 跑通回测；参见 [用户手册 — §12 模拟盘](user_guide.md#12-模拟盘交易) |

将 EasyQuant (`eqlib`) 编写的策略转换为 **PTrade / QMT** 平台可运行格式，在尽量保持策略逻辑不变的前提下替换数据源与下单接口。

## 目录

1. [概述](#1-概述)
2. [快速开始](#2-快速开始)
3. [工作原理](#3-工作原理)
4. [API 对照](#4-api-对照)
5. [使用方式](#5-使用方式)
6. [代码格式转换](#6-代码格式转换)
7. [注意事项](#7-注意事项)

---

## 1. 概述

### 1.1 什么是 PTrade/QMT 适配器

EasyQuant 的 PTrade 适配器是一个兼容层（compatibility layer），让你用同一套策略代码：

- **本地**：使用 `from eqlib import *` + `run_backtest()` 进行回测（数据源：akshare）
- **QMT 平台**：使用 `from eqlib.ptrade_adapter import *` + `start()` / `on_bar()` 进行实盘/模拟（数据源：QMT 实时行情）

策略逻辑完全一致，只需修改导入语句和入口函数。

### 1.2 支持的 QMT 版本

适配器基于 QMT Python API 接口文档（[QMT_Python_API_Doc](https://qmt.ptradeapi.com/QMT_Python_API_Doc.html)）编写，兼容 QMT 策略编辑器中的 Python 运行环境。

### 1.3 核心能力

| 能力 | 说明 |
|------|------|
| 生命周期桥接 | EasyQuant 的 `initialize` → QMT 的 `init`，`handle_data` → QMT 的 `handlebar` |
| 代码转换 | `601390` → `601390.SH`，`000300.XSHG` → `000300.SH` |
| 数据适配 | `attribute_history` → `ContextInfo.get_market_data` |
| 交易适配 | `order_value` → QMT `order_value()`，`order_target` → `order_shares` |
| 组合模拟 | 内置 `Portfolio` / `Position` 模拟，可同步 QMT 真实账户状态 |

---

## 2. 快速开始

### 2.1 最简单的方式：使用导出工具

```bash
python examples/13_ptrade_export.py
```

生成 `examples/ptrade_strategy_generated.py`（默认由 `examples/03_run_backtest.py` 生成样例），复制到 QMT 策略编辑器即可运行。

### 2.2 手动方式：三步迁移

**Step 1: 编写 EasyQuant 策略**

```python
# my_strategy.py — 本地回测用
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma:
        order_value(g.security, context.portfolio.available_cash)
    else:
        order_target(g.security, 0)
```

**Step 2: 在 QMT 策略编辑器中创建策略**

```python
# QMT 策略编辑器 — 实盘/模拟用
from eqlib.ptrade_adapter import *

# === 粘贴上面的策略代码（去掉 from eqlib import *） ===

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')  # 你的 QMT 账号
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma:
        order_value(g.security, context.portfolio.available_cash)
    else:
        order_target(g.security, 0)

# === QMT 入口函数 — 固定写法 ===

def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**Step 3: 在 QMT 中运行**

设置账号 → 回测/实盘。

---

## 3. 工作原理

### 3.1 生命周期映射

| EasyQuant | QMT | 说明 |
|-----------|-----|------|
| `initialize(context)` | `init(ContextInfo)` → `start()` | 策略初始化，只执行一次 |
| `handle_data(context, data)` | `handlebar(ContextInfo)` → `on_bar()` | 每根 K 线执行 |
| `run_daily(func)` | `handlebar` → 每日回调 | 每日定时回调 |
| `run_weekly(func)` | `handlebar` → 每周回调 | 每周定时回调 |
| `run_monthly(func)` | `handlebar` → 每月回调 | 每月定时回调 |
| `before_trading_start(context)` | 新交易日检测 | 开盘前回调 |
| `after_trading_end(context)` | `is_last_bar()` 检测 | 收盘后回调 |

### 3.2 数据流

```
EasyQuant API              QMT Native API
─────────────              ──────────────
attribute_history()  ──►   ContextInfo.get_market_data()
get_price()          ──►   ContextInfo.get_market_data_ex()
get_current_data()   ──►   ContextInfo.get_full_tick()
get_universe()       ──►   ContextInfo.get_universe()
set_universe()       ──►   ContextInfo.set_universe()
```

### 3.4 交易流

```
EasyQuant API              QMT Native API
─────────────              ──────────────
order()              ──►   order_shares()
order_value()        ──►   order_value()
order_target()       ──►   order_shares() (with position calc)
order_target_value() ──►   order_target_value()
```

---

## 4. API 对照

### 4.1 完全兼容的 API

以下 API 在 QMT 中与本地回测行为一致：

| API | 参数 | 说明 |
|-----|------|------|
| `set_benchmark(security)` | `security`: 股票代码 | 设置基准 |
| `set_option(name, value)` | `name`, `value` | 设置选项 |
| `run_daily(func, time)` | `func`, `time` | 每日调度 |
| `run_weekly(func, day, time)` | `func`, `day_of_week`, `time` | 每周调度 |
| `run_monthly(func, day, time)` | `func`, `day_of_month`, `time` | 每月调度 |
| `log(msg)` | `msg`: 字符串 | 日志输出 |
| `record(**kwargs)` | 键值对 | 记录数值 |
| `g.*` | 任意属性 | 全局变量 |

### 4.2 适配后兼容的 API

以下 API 在底层映射到 QMT 原生函数：

| EasyQuant API | QMT 原生 | 差异说明 |
|---------------|----------|---------|
| `attribute_history(sec, count, unit, fields)` | `ContextInfo.get_market_data()` | 返回格式统一为 DataFrame |
| `history(end_date, count, unit, fields)` | `ContextInfo.get_market_data()` | 同上 |
| `get_price(sec, start_date, end_date)` | `ContextInfo.get_market_data_ex()` | 支持日期范围查询 |
| `order(sec, amount)` | `order_shares()` | 自动转换代码格式 |
| `order_value(sec, value)` | `order_value()` | 正买负卖，自动转换代码 |
| `order_target(sec, target_amount)` | `order_shares()` | 计算持仓差值后下单 |
| `order_target_value(sec, target_value)` | `order_target_value()` | 直接映射 |
| `get_current_data()` | `ContextInfo.get_full_tick()` | 返回字典，键为 EQ 格式代码 |
| `get_index_stocks(index)` | `ContextInfo.get_sector()` | 返回 EQ 格式代码列表 |
| `set_universe(securities)` | `ContextInfo.set_universe()` | 自动转换代码格式 |
| `get_universe()` | `ContextInfo.get_universe()` | 返回 EQ 格式代码列表 |

### 4.3 新增 API（仅 QMT 模式）

以下 API 仅在 QMT 适配器中提供：

| API | 说明 |
|-----|------|
| `set_account(account_id)` | 设置 QMT 交易账号 |
| `start(ContextInfo)` | 在 QMT 的 `init()` 中调用，启动 EasyQuant 策略 |
| `on_bar(ContextInfo)` | 在 QMT 的 `handlebar()` 中调用，驱动策略逻辑 |
| `export_ptrade_script(file, output)` | 导出工具：生成 QMT 策略文件 |
| `QMT_TEMPLATE` | QMT 策略模板字符串 |
| `@initialize` | 装饰器：注册初始化函数 |
| `@handle_data` | 装饰器：注册 handle_data 函数 |

### 4.4 不支持的 API

以下 EasyQuant API 在 QMT 中**不支持**，需要使用 QMT 原生函数替代：

| EasyQuant API | 替代方案 |
|---------------|---------|
| `fetch_stock_data()` | QMT 自带历史数据 |
| `download_stock_data()` | 不需要，QMT 已有本地数据 |
| `load_csv()` | 使用 pandas 直接读取 |
| `scan_market()` | 使用 QMT 的 `get_stock_list_in_sector()` |
| `run_backtest()` | 在 QMT 界面操作回测 |
| `run_portfolio_backtest()` | 在 QMT 界面操作回测 |
| `generate_chart()` | QMT 自带图表 |
| `get_financial_abstract()` | QMT 的 `get_financial_data()` |
| `get_fundamentals()` | QMT 的 `get_factor_data()` |

---

## 5. 使用方式

### 5.1 方式一：直接粘贴到 QMT 编辑器

适用于简单策略。将整个策略代码（含 `init` / `handlebar`）粘贴到 QMT 策略编辑器。

```python
from eqlib.ptrade_adapter import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif price < ma20 * 0.98:
        order_target(g.security, 0)

def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

### 5.2 方式二：使用装饰器风格

```python
from eqlib.ptrade_adapter import *

g = {}

@initialize
def my_init(context):
    g['security'] = '601390'
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open)

@handle_data
def my_handler(context, data):
    sec = g['security']
    hist = attribute_history(sec, 20, '1d', ['close'])
    # ... strategy logic ...

# QMT 入口
def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

### 5.3 方式三：使用导出工具

适用于已有完整的 EasyQuant 策略文件。

```bash
# 可在 13_ptrade_export.py 中修改 strategy_file / output_file
python examples/13_ptrade_export.py
# 输出 examples/ptrade_strategy_generated.py → 复制到 QMT
```

---

## 6. 代码格式转换

### 6.1 股票代码转换规则

适配器自动处理以下转换：

| EasyQuant 格式 | QMT 格式 | 规则 |
|---------------|---------|------|
| `601390` | `601390.SH` | 6 开头 → 上海 |
| `000001` | `000001.SZ` | 0 开头 → 深圳 |
| `300001` | `300001.SZ` | 3 开头 → 深圳（创业板） |
| `688001` | `688001.SH` | 68 开头 → 上海（科创板） |
| `000300.XSHG` | `000300.SH` | .XSHG → .SH |
| `000001.XSHE` | `000001.SZ` | .XSHE → .SZ |
| `601390.SH` | `601390.SH` | 已为 QMT 格式 → 不变 |

### 6.2 账户设置

在 QMT 中交易需要设置账号：

```python
def initialize(context):
    set_account('6000000248')  # 你的 QMT 资金账号
```

或者在 QMT 入口函数中设置：

```python
def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)
```

### 6.3 订单类型

| EasyQuant | QMT 等效 | 说明 |
|-----------|---------|------|
| `order_value(sec, 10000)` | `order_value(sec.SH, 10000)` | 买入 10000 元 |
| `order_value(sec, -10000)` | `order_value(sec.SH, -10000)` | 卖出 10000 元 |
| `order_target(sec, 0)` | `order_shares(sec.SH, -持仓量)` | 清仓 |
| `order(sec, 100)` | `order_shares(sec.SH, 100)` | 买入 100 股 |

---

## 7. 注意事项

### 7.1 回测模式差异

- **EasyQuant 本地回测**：使用 akshare 数据，完整的报告/图表生成
- **QMT 回测模式**：使用 QMT 本地数据，交易函数通过虚拟账号执行，在 K 线上记录买卖点
- **QMT 实盘模式**：使用实时行情，交易函数产生实际委托

### 7.2 数据类型差异

- EasyQuant 的 `attribute_history` 返回 `pandas.DataFrame`，索引为日期
- QMT 的 `get_market_data` 返回格式取决于参数，适配器会统一转换为 DataFrame

### 7.3 交易函数限制

- QMT 回测模式中，`cancel`、`can_cancel_order`、`do_order` 等函数无实际意义
- QMT 模拟运行模式下，交易函数无效（需实盘或回测模式）
- EasyQuant 本地回测为“当日信号、次日开盘成交”；QMT 以平台成交规则为准（通常为当下委托撮合）

### 7.4 股票池

- EasyQuant 使用 `context.universe` 或 `set_universe()` 管理股票池
- QMT 使用 `ContextInfo.set_universe()` 设定，`ContextInfo.get_universe()` 获取
- 适配器自动同步两者

### 7.5 全局变量

- EasyQuant 使用 `g.security` 等属性访问
- QMT 适配器中的 `g` 是一个字典，也支持属性访问：`g.security` 或 `g['security']`

### 7.6 滑点和手续费

- EasyQuant 本地回测通过 `set_order_cost()` 配置
- QMT 回测通过 `ContextInfo.set_commission()` / `ContextInfo.set_slippage()` 配置
- QMT 实盘由券商实际费率决定

### 7.7 ContextInfo 直接访问

适配器暴露了底层的 QMT ContextInfo 对象，可通过 `context._qmt` 访问，以便在需要时使用 QMT 独有 API：

```python
def market_open(context):
    # EasyQuant API
    hist = attribute_history('601390', 20, '1d', ['close'])

    # QMT native API (when needed)
    ci = context._qmt
    barpos = ci.barpos  # current bar index
    period = ci.period  # current period, e.g. '1d'
```

---

## 附录：完整迁移示例

以下是一个完整的均线策略从 EasyQuant 到 QMT 的迁移。

### EasyQuant 原始代码（本地回测）

```python
from eqlib import *

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    close_data = attribute_history(g.security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return

    ma_fast = close_data['close'].tail(g.fast_period).mean()
    ma_slow = close_data['close'].mean()
    current_price = close_data['close'].iloc[-1]

    if current_price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s' % g.security)
    elif current_price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s' % g.security)

# 运行回测
result = run_backtest(initialize, '2024-01-01', '2024-12-31',
                      starting_cash=100000, benchmark='000300.XSHG')
```

### QMT 版本（实盘/模拟）

```python
from eqlib.ptrade_adapter import *

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')
    run_daily(market_open, time='every_bar')

def market_open(context):
    close_data = attribute_history(g.security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return

    ma_fast = close_data['close'].tail(g.fast_period).mean()
    ma_slow = close_data['close'].mean()
    current_price = close_data['close'].iloc[-1]

    if current_price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s' % g.security)
    elif current_price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s' % g.security)

# QMT 入口
def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**仅三处差异**：
1. `from eqlib import *` → `from eqlib.ptrade_adapter import *`
2. 增加 `set_account('YOUR_ACCOUNT_ID')`
3. 增加 `init()` / `handlebar()` 入口函数

策略逻辑完全不变。
