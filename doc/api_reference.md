# EasyQuant API 参考文档

> 本文档描述 `eqlib` 核心库的全部 API。`eqlib` 是 EasyQuant 项目的 Python 包，提供策略编写、数据拉取、回测执行、模拟盘和风险分析等能力。
>
> **注意：本工具仅支持中国 A 股市场。**
>
> **速查入口：** [文档中心 README](README.md) · [API 速查索引](api_index.md) · [报告与指标解读](reports_and_metrics.md) · [常见问题 FAQ](FAQ.md)

---

## 目录

1. [策略生命周期结构体](#1-策略生命周期结构体)
2. [交易 API](#2-交易-api)
3. [数据 API](#3-数据-api)
4. [回测与模拟盘引擎](#4-回测与模拟盘引擎)
5. [配置 API](#5-配置-api)（含滑点、会话）
6. [报告与分析 API](#6-报告与分析-api)
7. [组合优化 API](#7-组合优化-api)
8. [缓存 API](#8-缓存-api)
9. [日志 API](#9-日志-api)
10. [辅助工具 API](#10-辅助工具-api)
11. [选股策略 API](#11-选股策略-api)
12. [AI Agent 自动化工作流](#12-ai-agent-自动化工作流)

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
| `price` | `float` | 当前价（`current_price` 的别名） | 只读 |

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

> 回测执行语义：`order*` 系列 API 只负责在当前回调中提交请求，订单会在**下一交易日开盘价**统一撮合成交，以避免前视偏差。

### 2.1 `order(security, amount, style=None)`

按股数下单买卖。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码，如 `'601390'` |
| `amount` | `int` | 是 | 股数，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型（保留参数，暂不支持限价） |

**返回：** `str` 挂单 ID，失败返回 `None`  
格式：`PENDING_<ACTION>_<SECURITY>`，其中 `<ACTION>` 为 `ORDER` / `ORDER_VALUE` / `ORDER_TARGET` / `ORDER_TARGET_VALUE`（如 `PENDING_ORDER_601390`、`PENDING_ORDER_TARGET_601390`）

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

**返回：** `str` 挂单 ID，失败返回 `None`

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

**返回：** `str` 挂单 ID，失败返回 `None`

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

**返回：** `str` 挂单 ID，失败返回 `None`

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
| `frequency` | `str` | 否 | 当前仅支持 `'daily'`（分钟线请使用 `fetch_minute_data` / `get_price_minute`） |
| `fields` | `list` | 否 | 指定返回字段，如 `['close', 'volume']` |
| `count` | `int` | 否 | 返回最近 N 根 bar |

**返回：** `DataFrame`（单只股票）或 `dict[str, DataFrame]`（多只股票）

> `frequency` 参数当前为兼容保留项，建议省略或显式传 `'daily'`；传入其他值不会切换到分钟线。分钟线请见下文“分钟线数据”小节（`fetch_minute_data` / `get_price_minute`）。

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

**返回：**

- 单标的 + `df=False`：`Series`
- 单标的 + `df=True`：`DataFrame`
- 多标的 + `df=False`：`dict[str, Series]`
- 多标的 + `df=True`：`DataFrame`

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

### 3.14 链式选股 API

#### `query(*fields)`

创建链式查询对象，支持 `.filter()`、`.order_by()`、`.limit()` 方法。

**可用字段（通过 `valuation` 命名空间）：**

| 字段 | 说明 | 单位 |
|------|------|------|
| `valuation.code` | 股票代码 | — |
| `valuation.market_cap` | 流通市值 | 亿元 |
| `valuation.total_value` | 总市值 | 亿元 |
| `valuation.float_value` | 流通市值 | 亿元 |
| `valuation.pe` | 市盈率（动态） | — |
| `valuation.pb` | 市净率 | — |
| `valuation.turnover` | 换手率 | % |
| `valuation.price` | 最新价 | 元 |
| `valuation.pct_change` | 涨跌幅 | % |

**链式方法：**

| 方法 | 说明 |
|------|------|
| `.filter(*conditions)` | 添加过滤条件（AND 连接） |
| `.order_by(*clauses)` | 添加排序（`.asc()` / `.desc()`） |
| `.limit(n)` | 限制返回行数 |

**字段比较运算符：** `==`, `!=`, `>`, `>=`, `<`, `<=`, `.between(low, high)`, `.in_(values)`

```python
q = (
    query(
        valuation.code,
        valuation.market_cap,
        valuation.pe,
    )
    .filter(
        valuation.market_cap.between(20, 30),
        valuation.pe > 0,
    )
    .order_by(
        valuation.market_cap.asc(),
    )
    .limit(5)
)
df = get_fundamentals(q)
```

#### `get_fundamentals(query_or_code, date=None)`

获取基本面数据。

**双签名：**
- 传入 `Query` 对象：执行链式查询，返回筛选后的 `DataFrame`
- 传入股票代码字符串：返回财务摘要 `DataFrame`（原有行为）

```python
# 链式查询用法
df = get_fundamentals(q)

# 单只股票用法（向后兼容）
df = get_fundamentals('601390')
```

#### `get_current_data_object()`

获取带属性访问的实时行情快照。

**返回：** `dict[str, _StockDataObj]`，每个对象具有 `.paused`、`.price`、`.pe` 等属性。

```python
data = get_current_data_object()
stock = data['601390']
print(stock.price, stock.paused, stock.pe)
```

**Limitation (V1)：** 市值/PE/PB 等估值数据来自 akshare 的实时快照，非历史数据。在回测中，这些数据反映当前时刻的值，而非回测日的历史值。

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

### 4.1 `run_strategy(initialize_func, start_date, end_date, starting_cash=100000, benchmark='000300.XSHG', handle_data=None, securities=None, report_dir='reports', use_local=False, max_memory_mb=1024, selection_func=None, selection_rebalance='monthly:1')`

一站式回测 + 报告生成。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `initialize_func` | `callable` | 是 | 用户 `initialize(context)` 函数 |
| `start_date` | `str` / `date` | 否 | 回测开始日期（默认：今天往前 365 天） |
| `end_date` | `str` / `date` | 否 | 回测结束日期（默认：今天） |
| `starting_cash` | `float` | 否 | 初始资金，默认 100,000 |
| `benchmark` | `str` | 否 | 基准代码，默认 `'000300.XSHG'` |
| `handle_data` | `callable` | 否 | `handle_data(context, data)` 函数 |
| `securities` | `list` | 否 | 预加载股票代码列表 |
| `report_dir` | `str` | 否 | 报告输出目录 |
| `use_local` | `bool` | 否 | 使用本地 CSV 数据，默认 False |
| `max_memory_mb` | `int` | 否 | 内存限制（MB），默认 1024（1GB） |
| `selection_func` | `callable` | 否 | 选股函数，返回股票代码列表 |
| `selection_rebalance` | `str` | 否 | 选股频率，`"monthly:N"` / `"weekly:N"` / `"daily"` |

**返回：** 回测结果 `dict`，包含 `context`, `trade_log`, `recorded_values`

**`max_memory_mb` 说明：** 回测引擎会在内存允许的情况下构建快速查找字典缓存（O(1)）。如果估计内存超过此限制，会自动回退到紧凑的 DataFrame 切片模式（O(log n)），结果完全一致但略慢。你可以通过 `estimate_memory_mb(securities, rows_per_sec)` 提前估算内存需求。

### 4.2 `run_backtest(initialize_func, start_date, end_date, starting_cash=100000.0, frequency='daily', benchmark='000300.XSHG', securities=None, use_local=False, max_memory_mb=1024, selection_func=None, selection_rebalance='monthly:1')`

运行回测（不生成报告）。

**参数：** 与 `run_strategy` 类似，额外支持 `frequency`（`'daily'` 或 `'minute'`）、`selection_func`（选股函数）、`selection_rebalance`（选股频率）。

**返回：**

```python
{
    "context": Context,            # 策略上下文
    "trade_log": list[dict],       # 交易记录
    "recorded_values": dict,       # record() 记录 (date -> dict)
    "benchmark": str,              # 基准代码
}
```

### 4.3 `run_portfolio_backtest(config, strategy_func, report_dir='reports')`

面向多股票组合的高层回测接口。使用 `StrategyConfig` 定义初始资金、股票池、仓位比例和报告后缀，策略函数从 `context.universe` 中选股并交易。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `StrategyConfig` | 策略配置对象 |
| `strategy_func` | `callable` | 策略函数，签名 `func(context)` |
| `report_dir` | `str` | 报告输出目录，默认 `'reports'` |

#### `StrategyConfig` 类

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `securities` | `list[str]` | 必填 | 股票池代码列表 |
| `start_date` | `str`/`date` | 必填 | 回测开始日期 |
| `end_date` | `str`/`date` | 必填 | 回测结束日期 |
| `starting_cash` | `float` | `100000` | 初始资金 |
| `benchmark` | `str` | `"000300.XSHG"` | 基准指数 |
| `position_pct` | `float` | `0.33` | 每只股票最大仓位比例（可用资金的百分比） |
| `position_amount` | `int` | `0` | 固定买入股数（非零时覆盖 `position_pct`） |
| `report_suffix` | `str` | `""` | 报告文件名后缀，用于区分不同版本 |
| `frequency` | `str` | `"daily"` | `"daily"` 或 `"minute"` |

```python
from eqlib import StrategyConfig, run_portfolio_backtest

config = StrategyConfig(
    starting_cash=200000,
    securities=['601390', '600519', '000858'],
    benchmark='000300.XSHG',
    position_pct=0.33,
    start_date='2024-01-01',
    end_date='2024-12-31',
    report_suffix='v1',
)

def my_strategy(context):
    for sec in context.universe:
        hist = attribute_history(sec, 20, '1d', ['close'])
        if hist.empty:
            continue
        price = hist['close'].iloc[-1]
        ma20 = hist['close'].mean()
        if price > ma20 * 1.02:
            order_value(sec, context.portfolio.available_cash * config.position_pct)
        elif price < ma20 * 0.98 and context.portfolio.positions.get(sec):
            order_target(sec, 0)

result = run_portfolio_backtest(config, my_strategy, report_dir='reports')
```

### 4.4 `estimate_memory_mb(securities, rows_per_sec)`

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

### 4.5 `run_paper_trade(initialize_func, starting_cash=100000.0, benchmark='000300.XSHG', interval=60)`

模拟盘交易。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `initialize_func` | `callable` | 策略初始化函数 |
| `starting_cash` | `float` | 初始资金 |
| `benchmark` | `str` | 基准代码 |
| `interval` | `int` | 轮询间隔（秒），默认 60 |

**说明：** 模拟盘会持续运行直到 `Ctrl+C` 终止，使用实时行情数据。

### 4.6 `record(**kwargs)`

在策略中记录自定义数据点。

```python
record(price=current_price, ma5=ma5, signal='BUY')
```

记录的数据出现在报告 JSON 的 `recorded_values` 字段中。

### 4.7 调度函数

#### `run_daily(func, time='every_bar')`

每日定时执行函数。

#### `run_weekly(func, day_of_week=1, time='09:30')`

每周定时执行。`day_of_week`：0=周一，1=周二，...，4=周五。

#### `run_monthly(func, day_of_month=1, time='09:30')`

每月定时执行。`day_of_month`：1-31。

#### `run_selection(func, rebalance='monthly:1')`

注册选股函数，按周期执行并自动更新 `context.universe`。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `func` | `callable` | 选股函数，签名 `func(context) -> list[str]` |
| `rebalance` | `str` | 调度频率，见下表 |

**Rebalance 格式：**

| 值 | 含义 | 示例 |
|---|---|---|
| `"monthly:N"` | 每月第 N 天（1-31） | `"monthly:1"`（1号）、`"monthly:15"`（15号） |
| `"weekly:N"` | 周几（0=周一, 4=周五） | `"weekly:0"`（周一）、`"weekly:4"`（周五） |
| `"daily"` | 每个交易日 | `"daily"` |

**使用方式：**

```python
def my_selection(context):
    candidates = filter_st_stocks(context.universe)
    return TopNSelector(factor='pe', top_n=5).rank(candidates, context)

def initialize(context):
    run_selection(my_selection, rebalance='monthly:1')
```

**选股策略编写模式：**

1. **普通函数**（最简单）：编写一个函数，返回股票代码列表
2. **StockSelector 子类**（适合复杂逻辑）：继承 `StockSelector`，实现 `filter()` 和 `rank()` 方法
3. **通过 `run_strategy` 参数**：`run_strategy(..., selection_func=my_selection, selection_rebalance='weekly:0')`

### 4.8 生命周期回调

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

### 5.4 `set_slippage(model)`

在回测成交时按模型调整执行价，使结果更接近真实冲击成本。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `SlippageModel` | 滑点模型实例 |

**内置模型：**

| 类 | 说明 |
|------|------|
| `SlippageModel` | 基类；不对价格做调整 |
| `FixedSlippage(pct=0.001)` | 固定比例：买入 `price * (1 + pct)`，卖出 `price * (1 - pct)` |
| `VolumeSlippage(impact=0.05)` | 与「委托股数 / 当日成交量」成比例；当日成交量未知时不调整 |

```python
from eqlib import set_slippage, FixedSlippage, VolumeSlippage

set_slippage(FixedSlippage(0.0005))
# 或：set_slippage(VolumeSlippage(impact=0.05))
```

### 5.5 `BacktestSession` 与 `get_session()`（进阶）

`BacktestSession` 封装单次回测的可变状态（上下文、`g`、成交记录、调度表等）。`run_backtest` 内部会创建并注册会话，**普通策略不必使用**。

若你在**多线程**中并行跑多组回测，可为每线程使用独立会话，避免共享全局状态冲突：

```python
from eqlib import BacktestSession, get_session

# 典型用法见 eqlib._state 与引擎实现；进阶用户再查阅源码。
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

### 6.4 `generate_html_report(result, out_path)`

生成交互式 HTML 回测报告（图表 + 汇总统计，可直接在浏览器打开）。

**参数：**
- `result` — `run_backtest` 返回的字典
- `out_path` — 输出路径，如 `'reports/chart.html'`

### 6.5 `analyze_returns(result, risk_free_rate=0.03, trading_days=252)`

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

### 6.6 `brinson_attribution(result, sector_data=None)`

Brinson 归因分析：配置效应 + 选股效应 + 交互效应。

**返回：** `dict`（allocation_effect, selection_effect, interaction_effect, total_active_return）

### 6.7 `fama_french_analysis(result, factors=None)`

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

估算预加载数据的内存需求。详见 4.4 节。

### 8.4 本地 CSV 数据

- `save_stock_local(security, start_date, end_date, adjust)` — 下载并保存
- `load_stock_local(security, start_date, end_date, adjust)` — 从本地加载
- `has_local_data(security, adjust)` — 检查是否存在
- `list_local_stocks(adjust)` — 列出所有本地文件
- `remove_local_data(security, adjust)` — 删除单个文件
- `clear_all_local_data(adjust)` — 清空所有本地文件

**推荐：目标股票本地化 + 快速验证**

```python
from eqlib import (
    set_local_data_dir, save_stock_local, list_local_stocks,
    run_strategy
)

set_local_data_dir("data")
targets = ["601390", "600519", "000858", "000300.XSHG"]  # 含基准

for sec in targets:
    save_stock_local(sec, "2020-01-01", "2024-12-31")

print(list_local_stocks())

result = run_strategy(
    initialize,
    start_date="2024-01-01",
    end_date="2024-12-31",
    securities=["601390", "600519"],
    benchmark="000300.XSHG",
    use_local=True,
)
```

### 8.5 数据源接入建议（扩展）

当前默认数据源为 `akshare`。若需要更高可靠性或更多维度数据，建议按以下顺序扩展：

1. 保持现有 API 入参/出参不变（避免策略层改动）；
2. 先落盘统一格式（CSV/Parquet）再进入回测；
3. 采用主备数据源切换与交叉校验（价格、成交量、复权、停牌）；
4. 新增数据源先用小样本回测做一致性验证，再逐步扩大范围。

### 8.6 相关文档

- [Tutorial 00：先下载目标股票到本地，再回测](../tutorials/00_environment_and_first_run.md)
- [用户手册 7.12：数据源扩展与可靠性建议](user_guide.md#712-数据源扩展与可靠性建议规划)
- [FAQ：首次回测慢或卡住](FAQ.md#q-首次回测很慢或卡住)

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

## 11. 选股策略 API

选股策略允许你定义周期性的股票筛选逻辑，框架会在指定的调度频率（每周/每月）自动执行选股并更新 `context.universe`。

### 11.1 编写选股策略

**模式一：普通函数（最简单）**

编写一个函数，接收 `context`，返回股票代码列表：

```python
def my_selection(context):
    """返回当期要交易的股票列表。"""
    # 1. 筛选：剔除 ST 股
    candidates = filter_st_stocks(["601390", "600519", "000858"])
    # 2. 打分：按 PE 排序，选最低的 5 只
    df = fetch_factor_data(candidates, fields=["pe"])
    df = df.dropna(subset=["pe"]).sort_values("pe", ascending=True)
    return df.head(5).index.tolist()
```

**模式二：StockSelector 子类（适合复杂逻辑）**

继承 `StockSelector` 基类，实现 `filter()` 和 `rank()` 两个方法：

```python
class MySelector(StockSelector):
    def __init__(self, top_n=5, max_pe=50):
        self.top_n = top_n
        self.max_pe = max_pe

    def filter(self, candidates, context):
        """初选：剔除不合格股票"""
        filtered = filter_st_stocks(candidates)       # 剔除 ST
        filtered = filter_paused_stocks(filtered, context)  # 剔除停牌
        return filter_high_pe_stocks(filtered, max_pe=self.max_pe)  # 剔除高 PE

    def rank(self, securities, context):
        """打分排序：选出最优组合"""
        return TopNSelector(factor="pe", top_n=self.top_n).rank(securities, context)
```

**模式三：内置选择器（最快捷）**

直接使用 `TopNSelector` 或 `MultiFactorSelector`：

```python
# 单因子：选 PE 最低的 5 只
sel = TopNSelector(factor="pe", top_n=5, ascending=True)

# 多因子：加权综合评分
sel = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
    top_n=5,
)
```

### 11.2 注册与调用

**方式一：在 `initialize` 中调用 `run_selection`**

```python
def initialize(context):
    run_selection(my_selection, rebalance="monthly:1")  # 每月1号执行
    run_daily(trade, time="every_bar")
```

**方式二：通过 `run_strategy` 参数传入**

```python
result = run_strategy(
    initialize_func=initialize,
    selection_func=my_selection,
    selection_rebalance="weekly:0",  # 每周一执行
)
```

### 11.3 `run_selection(func, rebalance='monthly:1')`

注册选股函数到回测引擎。

| 参数 | 类型 | 说明 |
|------|------|------|
| `func` | `callable` | 选股函数，签名 `func(context) -> list[str]` |
| `rebalance` | `str` | 调度频率（见下表） |

**Rebalance 格式：**

| 值 | 含义 | 示例 |
|---|---|---|
| `"monthly:N"` | 每月第 N 天（1-31） | `"monthly:1"`（1号） |
| `"weekly:N"` | 周几（0=周一, 4=周五） | `"weekly:0"`（周一） |
| `"daily"` | 每个交易日 | `"daily"` |

### 11.4 工具函数

#### `StockSelector`

选股基类，子类需实现 `filter()` 和 `rank()` 方法。

#### `filter_st_stocks(securities)`

剔除 ST / *ST 股票。

**返回：** 非 ST 股票列表

#### `filter_paused_stocks(securities, context)`

剔除停牌股票（成交量为 0）。

**参数：** `context` 可选，回测模式下用于获取当前交易日

**返回：** 活跃交易股票列表

#### `filter_low_price_stocks(securities, min_price=2.0)`

剔除低于最低价格的股票。

#### `filter_high_pe_stocks(securities, max_pe=100.0)`

剔除高于最高 PE 的股票。

#### `fetch_factor_data(securities, fields=None)`

获取多维度因子数据。

**可用字段：**

| 字段 | 说明 | 来源 |
|------|------|------|
| `price` | 最新价 | 行情快照 |
| `pct_change` | 涨跌幅 | 行情快照 |
| `total_value` | 总市值 | 行情快照 |
| `pe` | 市盈率（动态） | 行情快照 |
| `pb` | 市净率 | 行情快照 |
| `turnover` | 换手率 | 行情快照 |
| `ma5` | 5日均价 | 预加载日线 |
| `ma10` | 10日均价 | 预加载日线 |
| `ma20` | 20日均价 | 预加载日线 |
| `rsi14` | 14日 RSI | 预加载日线 |

**返回：** `DataFrame`，索引为股票代码

#### `TopNSelector(factor='pe', top_n=5, ascending=True)`

按单因子排序，选出 Top-N。

| 参数 | 说明 |
|------|------|
| `factor` | 因子名称（`fetch_factor_data` 中的字段名） |
| `top_n` | 选取数量 |
| `ascending` | `True` 表示从小到大（如低 PE） |

#### `MultiFactorSelector(factors, top_n=5)`

按多因子加权综合评分排序。

| 参数 | 说明 |
|------|------|
| `factors` | `dict`，因子名 -> 权重（正权重=越大越好，负权重=越小越好） |
| `top_n` | 选取数量 |

---

## 12. AI Agent 自动化工作流

`eqlib` 的 API 被设计为可与 Claude Code（AI 编码智能体）配合使用，实现从回测到优化到模拟盘的全自动工作流。以下是 Claude Code 如何调用 `eqlib` API 完成自动化策略优化。

### 12.1 AI Agent 如何调用 eqlib API

Claude Code 作为主驱，通过以下步骤完成自动化：

| 步骤 | Claude Code 执行的动作 | 使用的 eqlib API |
|------|----------------------|-----------------|
| 基线回测 | 编写并运行 Python 脚本 | `run_backtest()` / `run_strategy()` |
| 指标分析 | 调用分析函数 | `analyze_returns()` |
| 归因分析 | 深度分析收益来源 | `brinson_attribution()` |
| 因子分析 | 检查市场暴露 | `fama_french_analysis()` |
| 数据查询 | 获取股票数据辅助诊断 | `get_price()`, `attribute_history()` |
| 模拟盘 | 编写并启动模拟盘脚本 | `run_paper_trade()` |

### 12.2 策略参数化约定

Claude Code 通过策略文件中的 `PARAMS` 和 `PARAM_RANGES` 字典识别可调参数：

```python
PARAMS = {
    'fast_period':      5,
    'slow_period':      20,
    'stop_loss_pct':    0.08,
}

PARAM_RANGES = {
    'fast_period':      (2,   15,   1),    # (min, max, step)
    'slow_period':      (10,  60,   5),
    'stop_loss_pct':    (0.03, 0.15, 0.01),
}
```

Claude Code 使用 Edit 工具直接修改策略文件中的 `PARAMS` 块，然后重新运行回测验证。

### 12.3 用户如何触发 AI 优化

无需运行任何命令 —— 直接在 Claude Code 对话中提出需求：

```
帮我优化 agent/strategy_template.py：
- 夏普比率 > 1.0
- 最大回撤 < 20%
- 在 2021、2022、2023 三个年度分别验证
```

Claude Code 会自动完成：回测运行 → 结果分析 → 参数调整 → 代码审查 → 再回测 → 审计报告。

### 12.4 代码审查子 Agent

每次参数变更后，Claude Code 会调用专门的代码审查子 Agent 验证：

1. **值域检查**：新参数值是否在 `PARAM_RANGES` 范围内
2. **约束检查**：`fast_period < slow_period`、`rsi_oversold < rsi_overbought` 等
3. **参数使用检查**：修改的参数是否在策略代码中通过 `PARAMS[key]` 引用
4. **前视偏差检查**：修改是否引入了使用未来数据的逻辑

### 12.5 审计日志

所有决策记录在 `audit_log/` 目录下：

```
audit_log/
├── session_<时间戳>.jsonl   # 机器可读，支持 jq 查询
└── session_<时间戳>.md      # 人类可读 Markdown 报告
```

每次迭代记录：
- 使用的参数集
- 各时段回测指标
- 需求满足情况
- 调参诊断依据和数据证据
- 代码审查结果

### 12.6 AI Agent 模拟盘自动化

除了回测优化，Claude Code 也可以自动化模拟盘流程：

```python
from eqlib import run_paper_trade

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    # 策略逻辑从 PARAMS 读取参数
    hist = attribute_history(g.security, PARAMS['slow_period'], '1d', ['close'])
    # ...
```

Claude Code 可以：
- 编写模拟盘启动脚本
- 添加盘前股票池扫描
- 对比多个策略的模拟盘表现
- 生成模拟盘日报

---

## 附录：完整导入清单

```python
from eqlib import (
    # === 生命周期 ===
    run_backtest, run_strategy, run_portfolio_backtest,
    run_daily, run_weekly, run_monthly,
    set_handle_data, record, run_paper_trade,
    # === 配置 ===
    set_benchmark, set_option, set_order_cost, set_slippage,
    OrderCost, SlippageModel, FixedSlippage, VolumeSlippage,
    # === 交易 ===
    order, order_target, order_value, order_target_value,
    # === 数据 ===
    get_price, history, attribute_history, get_all_securities,
    fetch_stock_data, download_stock_data, load_csv, clear_cache,
    # === 扫描 ===
    scan_market, check_golden_cross, get_financial_screen,
    # === 指数/行业/概念 ===
    get_index_stocks, get_industry_list, get_industry_stocks,
    get_concept_list, get_concept_stocks, get_industry,
    # === 分钟线 / Tick ===
    fetch_minute_data, get_price_minute, get_tick_data,
    # === 行情快照 / 基本面 ===
    get_current_data, get_security_info, get_trade_days,
    get_fundamentals, get_financial_abstract, get_money_flow,
    get_billboard_list, get_valuation, get_index_weights, get_extras,
    # === 链式选股 ===
    query, valuation, get_current_data_object,
    # === 股票池 ===
    set_universe, get_universe,
    # === 生命周期回调 ===
    before_trading_start, after_trading_end,
    # === 日志 ===
    log,
    # === 对象 ===
    g, GlobalObject, Context, Portfolio, Position,
    StrategyConfig,
    # === 报告 ===
    generate_chart, generate_report_md, generate_report_json, generate_html_report,
    # === 组合优化 ===
    portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity,
    # === 分析 ===
    analyze_returns, brinson_attribution, fama_french_analysis,
    # === 选股策略 ===
    StockSelector, TopNSelector, MultiFactorSelector,
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
    fetch_factor_data, run_selection,
    # === 缓存 ===
    set_cache_dir, set_local_data_dir, fetch_cached, estimate_memory_mb,
    save_stock_local, load_stock_local, has_local_data,
    list_local_stocks, remove_local_data, clear_all_local_data,
    BacktestSession, get_session,
)
```
