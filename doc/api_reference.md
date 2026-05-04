# EasyQuant API 参考文档

> 本文档描述 `eqlib` 核心库的全部 API。`eqlib` 是 EasyQuant 项目的 Python 包，提供策略编写、数据拉取、回测执行、模拟盘和风险分析等能力。
>
> **注意：本工具仅支持中国 A 股市场。**

---

## 目录

1. [策略生命周期结构体](#1-策略生命周期结构体)
2. [交易 API](#2-交易-api)
3. [数据 API](#3-数据-api)
4. [回测与模拟盘引擎](#4-回测与模拟盘引擎)
5. [配置 API](#5-配置-api)
6. [报告与分析 API](#6-报告与分析-api)
7. [组合优化 API](#7-组合优化-api)
8. [缓存 API](#8-缓存-api)
9. [日志 API](#9-日志-api)
10. [辅助工具 API](#10-辅助工具-api)

---

## 1. 策略生命周期结构体

策略编写涉及以下核心结构体：`Context`、`Portfolio`、`Position`、`GlobalObject (g)`。

### 1.1 `Context`

策略执行上下文，由框架在回调时自动传入。

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `current_dt` | `datetime` | 当前模拟时间（回测中为交易日 9:30） |
| `start_date` | `date` | 回测开始日期 |
| `end_date` | `date` | 回测结束日期 |
| `frequency` | `str` | `'daily'` 或 `'minute'` |
| `portfolio` | `Portfolio` | 投资组合对象 |
| `universe` | `list[str]` | 当前策略股票池 |
| `run_params` | `dict` | 回测参数字典 |

**使用方式：**

```python
def initialize(context):
    print(context.start_date, context.portfolio.available_cash)

def market_open(context):
    print(context.current_dt, context.universe)
```

### 1.2 `Portfolio`

投资组合状态，通过 `context.portfolio` 访问。

**属性：**

| 属性 | 类型 | 说明 | 用户输入 |
|------|------|------|----------|
| `starting_cash` | `float` | 初始资金 | 由 `starting_cash` 参数设定 |
| `available_cash` | `float` | 可用现金 | 框架自动维护，不可直接修改 |
| `positions` | `dict[str, Position]` | 持仓字典，key 为股票代码 | 框架自动维护 |
| `total_value` | `float` | 总资产 = 现金 + 持仓市值 | 框架自动计算 |
| `returns` | `float` | 总收益率 = (total_value - starting_cash) / starting_cash | 只读 |

**使用方式：**

```python
cash = context.portfolio.available_cash
total = context.portfolio.total_value
pct = context.portfolio.returns * 100
pos = context.portfolio.positions.get('601390')
```

### 1.3 `Position`

单只股票持仓，通过 `context.portfolio.positions[code]` 访问。

**属性：**

| 属性 | 类型 | 说明 | 用户输入 |
|------|------|------|----------|
| `security` | `str` | 股票代码 | 框架自动设定 |
| `amount` | `int` | 持仓数量（股） | 框架自动维护 |
| `closeable_amount` | `float` | 今日可卖数量（T+1 限制） | 框架自动维护 |
| `avg_cost` | `float` | 持仓均价 | 框架自动计算 |
| `total_value` | `float` | 持仓市值 = amount * 当前价 | 框架自动计算 |
| `price` | `float` | 当前价（等同于 avg_cost） | 只读 |

**使用方式：**

```python
pos = context.portfolio.positions.get('601390')
if pos and pos.amount > 0:
    print("持仓 %d 股，成本 %.3f，市值 %.2f"
          % (pos.amount, pos.avg_cost, pos.total_value))
```

### 1.4 `g` — GlobalObject

策略级别的全局对象，用于跨交易日存储自定义变量。

**说明：**
- 全局唯一实例，通过 `from eqlib import g` 导入
- 可动态设定任意属性
- 在 `initialize` 中初始化，在回调函数中读写

**属性：** 用户自定义（无固定字段）

**使用方式：**

```python
from eqlib import g

def initialize(context):
    g.security = '601390'
    g.ma_period = 20
    g.max_positions = 10
    g.trade_count = 0

def market_open(context):
    g.trade_count += 1
    hist = attribute_history(g.security, g.ma_period, '1d', ['close'])
```

---

## 2. 交易 API

用于在策略中下单买卖。

### 2.1 `order(security, amount, style=None)`

按股数下单买卖。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码，如 `'601390'` |
| `amount` | `int` | 是 | 股数，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型（保留参数，暂不支持限价） |

**返回：** `str` 订单 ID，如 `'BUY_601390_1000'`，失败返回 `None`

**说明：** 买入自动取整到 100 的整数倍（A 股最小交易单位）。资金不足时自动按最大可买数量执行。

```python
order('601390', 1000)    # 买入 1000 股
order('601390', -500)    # 卖出 500 股
```

### 2.2 `order_value(security, value, style=None)`

按金额下单买卖。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 金额，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型 |

**返回：** `str` 订单 ID，失败返回 `None`

```python
order_value('601390', 50000)    # 买入 5 万元
order_value('601390', -30000)   # 卖出 3 万元
```

### 2.3 `order_target(security, amount, style=None)`

调整持仓到目标股数。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `amount` | `int` | 是 | 目标持仓股数，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

**返回：** `str` 订单 ID，失败返回 `None`

```python
order_target('601390', 5000)   # 调到 5000 股
order_target('601390', 0)      # 清仓
```

### 2.4 `order_target_value(security, value, style=None)`

调整持仓到目标市值。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 目标市值，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

**返回：** `str` 订单 ID，失败返回 `None`

```python
order_target_value('601390', 100000)   # 持仓市值调到 10 万
order_target_value('601390', 0)        # 清仓
```

### 2.5 手续费说明

所有交易自动计算手续费，默认配置：

| 费用类型 | 费率 | 说明 |
|----------|------|------|
| 买入印花税 | 0% | A 股买入无印花税 |
| 卖出印花税 | 0.1% | A 股卖出收取 |
| 买入/卖出佣金 | 0.03% | 券商佣金 |
| 最低佣金 | 5 元 | 不足 5 元按 5 元收取 |

通过 `set_order_cost()` 修改（见第 5 节）。

---

## 3. 数据 API

### 3.1 历史日线数据

#### `get_price(security, start_date=None, end_date=None, frequency='daily', fields=None, count=None)`

获取历史价格数据。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` 或 `list` | 是 | 股票代码，可传多只 |
| `start_date` | `str` / `date` | 否 | 开始日期，如 `'2024-01-01'` |
| `end_date` | `str` / `date` | 否 | 结束日期 |
| `frequency` | `str` | 否 | `'daily'` 或 `'1m'`（分钟线） |
| `fields` | `list` | 否 | 指定返回字段，如 `['close', 'volume']` |
| `count` | `int` | 否 | 返回最近 N 根 bar |

**返回：** `DataFrame`（单只股票）或 `dict[str, DataFrame]`（多只股票）

```python
# 单只股票
df = get_price('601390', start_date='2024-01-01', end_date='2024-06-30')

# 多只股票
dfs = get_price(['601390', '600519'], start_date='2024-01-01', end_date='2024-06-30')

# 最近 30 天
df = get_price('601390', count=30)
```

#### `history(count, unit='1d', field='close', security=None, df=False)`

获取从当前回测时间向前推 `count` 根 bar 的数据。仅在策略回调函数内可用。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `count` | `int` | 是 | bar 数量 |
| `unit` | `str` | 否 | `'1d'`（日线） |
| `field` | `str` | 否 | 字段名 |
| `security` | `str` | 否 | 股票代码，默认使用 `context.universe` |
| `df` | `bool` | 否 | `True` 返回 DataFrame，`False` 返回 dict |

**返回：** `dict[str, Series]` 或 `DataFrame`

```python
def market_open(context):
    close = history(20, '1d', 'close', '601390')
    ma20 = close.mean()
```

#### `attribute_history(security, count, unit='1d', fields=('close',), df=True, skip_paused=True, fq='pre')`

获取单只股票的历史属性数据。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `count` | `int` | 是 | bar 数量 |
| `unit` | `str` | 否 | `'1d'` |
| `fields` | `tuple` | 否 | 字段列表 |
| `df` | `bool` | 否 | 返回 DataFrame |
| `fq` | `str` | 否 | `'pre'`（前复权）/ `'post'`（后复权） |

**返回：** `DataFrame`

```python
hist = attribute_history('601390', 30, '1d',
                         fields=['open', 'close', 'volume', 'high', 'low'])
```

**DataFrame 列说明：**

| 列名 | 说明 |
|------|------|
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量（股） |
| `money` | 成交额（元） |
| `pct_change` | 涨跌幅 (%) |
| `turnover` | 换手率 (%) |

### 3.2 实时行情与快照

#### `get_current_data()`

获取全部 A 股实时快照。

**返回：** `dict[str, dict]`，key 为股票代码，value 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `str` | 股票代码 |
| `name` | `str` | 股票名称 |
| `price` | `float` | 最新价 |
| `pct_change` | `float` | 涨跌幅 |
| `volume` | `float` | 成交量 |
| `money` | `float` | 成交额 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `open` | `float` | 开盘价 |
| `prev_close` | `float` | 昨收价 |
| `turnover` | `float` | 换手率 |
| `pe` | `float` | 市盈率（动态） |
| `pb` | `float` | 市净率 |
| `total_value` | `float` | 总市值 |
| `float_value` | `float` | 流通市值 |

```python
data = get_current_data()
info = data['601390']
print(info['price'], info['pe'])
```

#### `get_security_info(code)`

获取单只股票基本信息。

**返回：** `SecurityInfo` 对象，属性：

| 属性 | 说明 |
|------|------|
| `code` | 股票代码 |
| `name` | 股票简称 |
| `industry` | 所属行业 |
| `total_shares` | 总股本 |
| `float_shares` | 流通股 |
| `total_value` | 总市值 |
| `float_value` | 流通市值 |
| `list_date` | 上市时间 |

#### `get_valuation(code)`

获取估值数据（使用缓存的行情快照）。

**返回：** `dict` 或 `None`，字段同 `get_current_data` 的估值子集。

### 3.3 选股与扫描

#### `scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)`

扫描 A 股并筛选。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `min_price` | `float` | 最低价格 |
| `min_pct_change` | `float` | 最小涨幅 |
| `max_pct_change` | `float` | 最大涨幅 |
| `max_pe` | `float` | 最大市盈率 |

**返回：** 筛选后的 `DataFrame`（code, name, price, pct_change, pe）

#### `get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None, min_roe=None, min_revenue=None, min_profit=None)`

按财务指标筛选。

**参数：** 所有参数均为可选阈值。

**返回：** 筛选后的 `DataFrame`。

#### `check_golden_cross(code, fast_period=5, slow_period=20, min_rows=30)`

检查是否存在金叉。

**返回：** `bool`

### 3.4 股票列表与交易日历

#### `get_all_securities(types=None, date=None)`

获取全部 A 股列表。

**返回：** `DataFrame`（code, name）

#### `get_trade_days(start_date=None, end_date=None, count=None)`

获取交易日历。

**返回：** `list[date]`

### 3.5 指数与行业

#### `get_index_stocks(index_code)`

获取指数成分股。

**参数：** `index_code` — 指数代码，如 `'000300.XSHG'`（沪深300）

**返回：** `DataFrame`（code, name, include_date）

#### `get_industry_list()`

获取所有行业板块名称。

**返回：** `list[str]`

#### `get_industry_stocks(industry_name)`

获取某行业的成分股。

**返回：** `DataFrame`（含价格、涨跌幅、PE、PB、市值等）

#### `get_industry(code)`

获取单只股票的行业分类。

**返回：** `dict`（code, name, industry）或 `None`

#### `get_index_weights(index_code, date=None)`

获取指数成分股权重。

**返回：** `DataFrame`（code, name, weight）

### 3.6 概念板块

#### `get_concept_list()`

获取所有概念板块名称。

**返回：** `list[str]`

#### `get_concept_stocks(concept_name)`

获取概念股成分。

**返回：** `DataFrame`

### 3.7 分钟线数据

#### `fetch_minute_data(code, period='5m', start_date=None, end_date=None, adjust='qfq')`

获取分钟级 K 线数据。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `code` | `str` | 股票代码 |
| `period` | `str` | `'1m'`, `'5m'`, `'15m'`, `'30m'`, `'60m'` |
| `adjust` | `str` | `'qfq'`（前复权），`'hfq'`（后复权） |

**返回：** `DataFrame`，索引为 `datetime`

#### `get_price_minute(security, count=None, period='5m', fields=None, adjust='qfq')`

获取分钟级价格数据（策略内使用）。

### 3.8 Tick 数据

#### `get_tick_data(code, trade_date=None)`

获取当日逐笔成交数据。

**返回：** `DataFrame`（time, price, volume, money, direction）

### 3.9 资金流与龙虎榜

#### `get_money_flow(code, start_date=None, end_date=None, count=None)`

获取资金流向数据。

**返回：** `DataFrame`（含主力/超大单/大单/中单/小单净流入）

#### `get_billboard_list(stock_list=None, date=None, start_date=None, end_date=None)`

获取龙虎榜数据。

**返回：** `DataFrame`

### 3.10 财务数据

#### `get_financial_abstract(code)`

获取财务摘要。

**返回：** `DataFrame`（指标为行名）

#### `get_fundamentals(code, date=None)`

获取基本面数据（`get_financial_abstract` 的别名）。

### 3.11 额外字段

#### `get_extras(field, security_list=None, start_date=None, end_date=None)`

获取额外数据字段。

**参数：**
- `field`：`'is_st'`（ST 标记）或 `'net_value'`（净资产估值）
- `security_list`：可选，限定股票范围

**返回：** `dict[str, bool/float]`

### 3.12 股票池管理

#### `set_universe(security_list)`

设置策略股票池。

**参数：** `security_list` — `list[str]` 股票代码列表

#### `get_universe()`

获取当前策略股票池。

**返回：** `list[str]`

### 3.13 本地文件

#### `download_stock_data(code, start_date, end_date, adjust='qfq', output_dir=None, filename=None)`

下载日线数据并保存为 CSV。

**返回：** 文件路径 `str` 或 `None`

#### `load_csv(path, index_col='date', parse_dates=True)`

从本地 CSV 加载数据。

**返回：** `DataFrame`

#### `clear_cache()`

清除内存与行情快照缓存。

---

## 4. 回测与模拟盘引擎

### 4.1 `run_strategy(initialize_func, start_date, end_date, starting_cash=100000, benchmark='000300.XSHG', handle_data=None, securities=None, report_dir='reports', use_local=False, max_memory_mb=1024)`

一站式回测 + 报告生成。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `initialize_func` | `callable` | 是 | 用户 `initialize(context)` 函数 |
| `start_date` | `str` / `date` | 是 | 回测开始日期 |
| `end_date` | `str` / `date` | 是 | 回测结束日期 |
| `starting_cash` | `float` | 否 | 初始资金，默认 100,000 |
| `benchmark` | `str` | 否 | 基准代码，默认 `'000300.XSHG'` |
| `handle_data` | `callable` | 否 | `handle_data(context, data)` 函数 |
| `securities` | `list` | 否 | 预加载股票代码列表 |
| `report_dir` | `str` | 否 | 报告输出目录 |
| `use_local` | `bool` | 否 | 使用本地 CSV 数据，默认 False |
| `max_memory_mb` | `int` | 否 | 内存限制（MB），默认 1024（1GB） |

**返回：** `dict` 回测结果，包含 `context`, `trade_log`, `recorded_values`

**`max_memory_mb` 说明：** 回测引擎会在内存允许的情况下构建快速查找字典缓存（O(1)）。如果估计内存超过此限制，会自动回退到紧凑的 DataFrame 切片模式（O(log n)），结果完全一致但略慢。你可以通过 `estimate_memory_mb(securities, rows_per_sec)` 提前估算内存需求。

### 4.2 `run_backtest(initialize_func, start_date, end_date, starting_cash=100000.0, frequency='daily', benchmark='000300.XSHG', securities=None, use_local=False, max_memory_mb=1024)`

运行回测（不生成报告）。

**参数：** 与 `run_strategy` 类似，额外支持 `frequency`（`'daily'` 或 `'minute'`）。

**返回：**

```python
{
    "context": Context,            # 策略上下文
    "trade_log": list[dict],       # 交易记录
    "recorded_values": dict,       # record() 记录 (date -> dict)
    "benchmark": str,              # 基准代码
}
```

### 4.3 `estimate_memory_mb(securities, rows_per_sec)`

估算预加载数据的内存需求。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 股票代码列表 |
| `rows_per_sec` | `int` | 每只股票的数据行数（交易日数） |

**返回：** `dict`，包含 `panel_mb`、`close_dict_mb`、`bar_cache_mb`、`total_mb`、`securities`、`rows_per_sec`

```python
from eqlib import estimate_memory_mb
est = estimate_memory_mb(['601390', '600519'], 1500)
print(f"预计内存: {est['total_mb']} MB")
```

### 4.3 `run_paper_trade(initialize_func, starting_cash=100000.0, benchmark='000300.XSHG', interval=60)`

模拟盘交易。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `initialize_func` | `callable` | 策略初始化函数 |
| `starting_cash` | `float` | 初始资金 |
| `benchmark` | `str` | 基准代码 |
| `interval` | `int` | 轮询间隔（秒），默认 60 |

**说明：** 模拟盘会持续运行直到 `Ctrl+C` 终止，使用实时行情数据。

### 4.4 `record(**kwargs)`

在策略中记录自定义数据点。

```python
record(price=current_price, ma5=ma5, signal='BUY')
```

记录的数据出现在报告 JSON 的 `recorded_values` 字段中。

### 4.5 调度函数

#### `run_daily(func, time='every_bar')`

每日定时执行函数。

#### `run_weekly(func, day_of_week=1, time='09:30')`

每周定时执行。`day_of_week`：0=周一，1=周二，...，4=周五。

#### `run_monthly(func, day_of_month=1, time='09:30')`

每月定时执行。`day_of_month`：1-31。

### 4.6 生命周期回调

#### `before_trading_start(func)`

注册盘前回调函数（9:30 前执行）。函数签名：`func(context, data)`。

#### `after_trading_end(func)`

注册盘后回调函数（15:00 后执行）。函数签名：`func(context, data)`。

---

## 5. 配置 API

### 5.1 `set_benchmark(security)`

设置回测基准用于对比收益。

**参数：** `security` — 基准代码，如 `'000300.XSHG'`（沪深300）

### 5.2 `set_order_cost(cost, type='stock', ref=None)`

设置交易手续费。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `cost` | `OrderCost` | 手续费对象 |
| `type` | `str` | `'stock'`（固定值） |

#### `OrderCost` 类

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `open_tax` | `float` | `0` | 买入印花税 |
| `close_tax` | `float` | `0.001` | 卖出印花税（0.1%） |
| `open_commission` | `float` | `0.0003` | 买入佣金（0.03%） |
| `close_commission` | `float` | `0.0003` | 卖出佣金 |
| `close_today_commission` | `float` | `0` | 今日卖出佣金 |
| `min_commission` | `float` | `5` | 最低佣金（元） |

```python
set_order_cost(OrderCost(
    open_tax=0,
    close_tax=0.001,
    open_commission=0.0003,
    close_commission=0.0003,
    min_commission=5,
))
```

### 5.3 `set_option(name, value)`

设置策略选项。

```python
set_option('use_real_price', True)
```

---

## 6. 报告与分析 API

### 6.1 `generate_chart(result, out_path)`

生成回测图表（PNG）。

**参数：**
- `result` — `run_backtest` 返回的字典
- `out_path` — 输出路径，如 `'reports/chart.png'`

### 6.2 `generate_report_md(result, out_path)`

生成 Markdown 格式回测报告。

### 6.3 `generate_report_json(result, out_path)`

生成 JSON 格式回测报告（结构化数据）。

### 6.4 `analyze_returns(result, risk_free_rate=0.03, trading_days=252)`

计算综合风险指标。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `result` | `dict` | 回测结果 |
| `risk_free_rate` | `float` | 无风险利率（年化），默认 3% |
| `trading_days` | `int` | 年交易天数，默认 252 |

**返回：** `dict` 包含以下指标：

| 指标 | 类型 | 说明 |
|------|------|------|
| `total_return` | `float` | 总收益率 |
| `annual_return` | `float` | 年化收益率 |
| `annual_volatility` | `float` | 年化波动率 |
| `sharpe_ratio` | `float` | 夏普比率 |
| `sortino_ratio` | `float` | 索提诺比率 |
| `max_drawdown` | `float` | 最大回撤 |
| `max_drawdown_start` | `date` | 最大回撤起始日 |
| `max_drawdown_end` | `date` | 最大回撤结束日 |
| `calmar_ratio` | `float` | 卡玛比率 |
| `alpha` | `float` | 年化超额收益 |
| `beta` | `float` | 市场敏感度 |
| `information_ratio` | `float` | 信息比率 |
| `win_rate` | `float` | 日胜率 |
| `trading_days` | `int` | 回测天数 |
| `num_trades` | `int` | 交易次数 |

### 6.5 `brinson_attribution(result, sector_data=None)`

Brinson 归因分析：配置效应 + 选股效应 + 交互效应。

**返回：** `dict`（allocation_effect, selection_effect, interaction_effect, total_active_return）

### 6.6 `fama_french_analysis(result, factors=None)`

Fama-French 风格因子分析。

**返回：** `dict`（market_beta, market_exposure, alpha_annual, momentum_correlation, vol_of_vol, residual_volatility, explained_variance）

---

## 7. 组合优化 API

### 7.1 `portfolio_optimizer(securities, prices, target=None, constraints=None, bounds=None, default_range=(0.0, 1.0), ftol=1e-9, return_none_if_fail=True)`

投资组合权重优化。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 股票代码列表 |
| `prices` | `DataFrame` | 价格矩阵，columns=股票代码 |
| `target` | `MinVariance` / `MaxSharpe` / `RiskParity` | 优化目标 |
| `constraints` | `dict` | `{'max_weight': 0.3, 'min_weight': 0.0}` |
| `bounds` | `list[Bound]` | 每只股票的权重上下限 |
| `default_range` | `tuple` | 默认权重范围 |
| `ftol` | `float` | 优化容差 |
| `return_none_if_fail` | `bool` | 失败时返回 None |

**返回：** `Series`（优化后的权重，key 为股票代码）或 `None`

#### 优化目标类

```python
MinVariance()                          # 最小方差
MaxSharpe(risk_free_rate=0.03)          # 最大夏普比
RiskParity()                           # 风险平价
```

#### `Bound` 类

```python
Bound(lower=0.0, upper=1.0)   # 单只股票的权重上下限
```

**示例：**

```python
from eqlib import portfolio_optimizer, MinVariance, Bound

weights = portfolio_optimizer(
    securities=['601390', '600519', '000858'],
    prices=price_df,
    target=MinVariance(),
    constraints={'max_weight': 0.4},
)
```

---

## 8. 缓存 API

### 8.1 `set_cache_dir(path)`

设置磁盘缓存目录。

### 8.2 `fetch_cached(security, start_date, end_date, adjust='qfq')`

获取数据，优先使用磁盘缓存。

**返回：** `DataFrame`

### 8.3 `estimate_memory_mb(securities, rows_per_sec)`

估算预加载数据的内存需求。详见 4.3 节。

### 8.4 本地 CSV 数据

- `save_stock_local(security, start_date, end_date, adjust)` — 下载并保存
- `load_stock_local(security, start_date, end_date, adjust)` — 从本地加载
- `has_local_data(security, adjust)` — 检查是否存在
- `list_local_stocks(adjust)` — 列出所有本地文件
- `remove_local_data(security, adjust)` — 删除单个文件
- `clear_all_local_data(adjust)` — 清空所有本地文件

---

## 9. 日志 API

### `log.info(msg)`, `log.debug(msg)`, `log.warn(msg)`, `log.error(msg)`

策略内日志输出。

```python
log.info("买入 %s" % security)
log.warn("价格异常: %s" % code)
log.error("数据获取失败")
```

---

## 10. 辅助工具 API

### `engine.get_context()`

获取当前回测上下文（引擎内部使用）。

### `engine.get_g()`

获取全局对象（引擎内部使用）。

### `engine.get_trade_log()`

获取交易记录列表。

### `engine.get_recorded_values()`

获取 `record()` 记录列表。

---

## 附录：完整导入清单

```python
from eqlib import (
    # === 生命周期 ===
    "run_backtest", "run_strategy", "run_daily", "run_weekly", "run_monthly",
    "set_handle_data", "record", "run_paper_trade",
    # === 配置 ===
    "set_benchmark", "set_option", "set_order_cost", "OrderCost",
    # === 交易 ===
    "order", "order_target", "order_value", "order_target_value",
    # === 数据 ===
    "get_price", "history", "attribute_history", "get_all_securities",
    "download_stock_data", "load_csv", "clear_cache",
    # === 扫描 ===
    "scan_market", "check_golden_cross", "get_financial_screen",
    # === 指数/行业/概念 ===
    "get_index_stocks", "get_industry_list", "get_industry_stocks",
    "get_concept_list", "get_concept_stocks", "get_industry",
    # === 分钟线 / Tick ===
    "fetch_minute_data", "get_price_minute", "get_tick_data",
    # === 行情快照 / 基本面 ===
    "get_current_data", "get_security_info", "get_trade_days",
    "get_fundamentals", "get_money_flow", "get_billboard_list",
    "get_valuation", "get_index_weights", "get_extras",
    # === 股票池 ===
    "set_universe", "get_universe",
    # === 生命周期回调 ===
    "before_trading_start", "after_trading_end",
    # === 日志 ===
    "log",
    # === 对象 ===
    "g", "GlobalObject", "Context", "Portfolio", "Position",
    # === 报告 ===
    "generate_chart", "generate_report_md", "generate_report_json",
    # === 组合优化 ===
    "portfolio_optimizer", "Bound", "MinVariance", "MaxSharpe", "RiskParity",
    # === 分析 ===
    "analyze_returns", "brinson_attribution", "fama_french_analysis",
    # === 缓存 ===
    "set_cache_dir", "fetch_cached", "estimate_memory_mb",
    "save_stock_local", "load_stock_local", "has_local_data",
    "list_local_stocks", "remove_local_data", "clear_all_local_data",
)
```
