# EasyQuant API 参考

> 本文档描述 `eqlib` 核心库的全部公开 API。
> **注意：本工具仅支持中国 A 股市场。**

!!! tip "阅读提示"

    函数名可用浏览器页内查找（`Ctrl+F` / `⌘F`）。新手请先完成 [用户手册](user_guide.md) 再按需跳转本章。

## 如何使用本文档

**按使用场景查找：**

| 场景 | 跳转章节 |
|------|----------|
| 写第一个策略 | [策略生命周期结构体](#策略生命周期结构体) → [交易 API](#交易-api) |
| 拉取行情数据 | [数据 API](#数据-api) |
| 运行回测 | [回测与模拟盘引擎](#回测与模拟盘引擎) |
| 设置手续费/滑点 | [配置 API](#配置-api) |
| 模拟盘通知 | [通知 API](#通知-api) |
| 生成报告/计算指标 | [报告与分析 API](#报告与分析-api) |
| 选股/行业轮动 | [选股策略 API](#选股策略-api) |
| 优化仓位权重 | [组合优化 API](#组合优化-api) |
| 本地缓存 | [缓存 API](#缓存-api) |

**命名约定：**

- 股票代码格式为 6 位数字，如 `'601390'`；基准可带交易所后缀，如 `'000300.XSHG'`
- 日期格式统一为 `'YYYY-MM-DD'` 或 `date` 对象
- `context` 由框架自动传入，包含当前时间、投资组合、股票池等
- `g` 为策略级别全局对象，跨交易日持久化

**最小可运行策略：**

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist['close'].iloc[-1] > hist['close'].mean() * 1.02:
        order_value(g.security, context.portfolio.available_cash)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390'],
)
```

---

## 策略生命周期结构体

### Context

策略执行上下文，由框架在回调时自动传入。

| 属性 | 类型 | 说明 |
|------|------|------|
| `current_dt` | `datetime` | 当前模拟时间 |
| `start_date` | `date` | 回测开始日期 |
| `end_date` | `date` | 回测结束日期 |
| `frequency` | `str` | `'daily'` 或 `'minute'` |
| `portfolio` | `Portfolio` | 投资组合对象 |
| `universe` | `list[str]` | 当前策略股票池 |
| `run_params` | `dict` | 回测参数字典 |

### Portfolio

投资组合状态，通过 `context.portfolio` 访问。

| 属性 | 说明 | 用户输入 |
|------|------|----------|
| `starting_cash` | 初始资金 | 由 `starting_cash` 参数设定 |
| `available_cash` | 可用现金 | 框架自动维护 |
| `positions` | 持仓字典，key 为股票代码 | 框架自动维护 |
| `total_value` | 总资产 = 现金 + 持仓市值 | 框架自动计算 |
| `returns` | 总收益率 | 只读 |

### Position

单只股票持仓，通过 `context.portfolio.positions[code]` 访问。

| 属性 | 说明 | 用户输入 |
|------|------|----------|
| `security` | 股票代码 | 框架自动设定 |
| `amount` | 持仓数量（股） | 框架自动维护 |
| `closeable_amount` | 今日可卖数量（T+1 限制） | 框架自动维护 |
| `avg_cost` | 持仓均价 | 框架自动计算 |
| `total_value` | 持仓市值 | 框架自动计算 |
| `price` | 当前价 | 只读 |

### g — GlobalObject

策略级别的全局对象，用于跨交易日存储自定义变量。

```python
from eqlib import g

def initialize(context):
    g.security = '601390'
    g.ma_period = 20

def market_open(context):
    hist = attribute_history(g.security, g.ma_period, '1d', ['close'])
```

---

## 交易 API

> 回测执行语义：`order*` 系列 API 只负责在当前回调中提交请求，订单会在**下一交易日开盘价**统一撮合成交。

### order

按股数下单买卖。

```python
order(security, amount, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码，如 `'601390'` |
| `amount` | `int` | 是 | 股数，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型（保留参数） |

返回挂单 ID（`str`），失败返回 `None`。买入自动取整到 100 的整数倍。

```python
order('601390', 1000)    # 买入 1000 股
order('601390', -500)    # 卖出 500 股
```

### order_value

按金额下单买卖。

```python
order_value(security, value, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 金额，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型 |

```python
order_value('601390', 50000)    # 买入 5 万元
```

### order_target

调整持仓到目标股数。

```python
order_target(security, amount, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `amount` | `int` | 是 | 目标持仓股数，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

### order_target_value

调整持仓到目标市值。

```python
order_target_value(security, value, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 目标市值，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

### 手续费说明

通过 `set_order_cost()` 修改（见配置 API）。默认：买入印花税 0%、卖出印花税 0.1%、买卖佣金 0.03%、最低佣金 5 元。

---

## 数据 API

### get_price

获取历史价格数据。

```python
get_price(security, start_date=None, end_date=None, frequency='daily', fields=None, count=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` 或 `list` | 是 | 股票代码 |
| `start_date` | `str`/`date` | 否 | 开始日期 |
| `end_date` | `str`/`date` | 否 | 结束日期 |
| `frequency` | `str` | 否 | 仅支持 `'daily'` |
| `fields` | `list` | 否 | 指定返回字段 |
| `count` | `int` | 否 | 返回最近 N 根 bar |

返回 `DataFrame`（单只）或 `dict[str, DataFrame]`（多只）。

### history

获取从当前回测时间向前推 `count` 根 bar 的数据。仅在策略回调内可用。

```python
history(count, unit='1d', field='close', security=None, df=False)
```

### attribute_history

获取单只股票的历史属性数据。

```python
attribute_history(security, count, unit='1d', fields=('close',), df=True, skip_paused=True, fq='pre')
```

返回 `DataFrame`，列包括：`open`, `high`, `low`, `close`, `volume`, `money`, `pct_change`, `turnover`。

### get_current_data

获取全部 A 股实时快照。返回 `dict[str, dict]`，包含 `code`, `name`, `price`, `pct_change`, `volume`, `pe`, `pb`, `total_value` 等字段。

### get_security_info

获取单只股票基本信息。返回 `SecurityInfo` 对象（`code`, `name`, `industry`, `total_shares`, `float_shares`, `total_value`, `list_date`）。

### get_valuation

获取估值数据。返回 `dict` 或 `None`。

### scan_market

扫描 A 股并筛选。

```python
scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
```

### get_financial_screen

按财务指标筛选。

```python
get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None, min_roe=None)
```

### get_all_securities

获取全部 A 股列表。返回 `DataFrame`（code, name）。

### get_trade_days

获取交易日历。返回 `list[date]`。

### 指数与行业

| API | 说明 | 返回 |
|-----|------|------|
| `get_index_stocks(index_code)` | 指数成分股 | `DataFrame` |
| `get_industry_list()` | 所有行业板块 | `list[str]` |
| `get_industry_stocks(industry_name)` | 某行业成分股 | `DataFrame` |
| `get_industry(code)` | 单只股票行业分类 | `dict` 或 `None` |
| `get_index_weights(index_code, date=None)` | 指数成分股权重 | `DataFrame` |

### 概念板块

| API | 说明 | 返回 |
|-----|------|------|
| `get_concept_list()` | 所有概念板块 | `list[str]` |
| `get_concept_stocks(concept_name)` | 概念股成分 | `DataFrame` |

### 分钟线数据

```python
fetch_minute_data(code, period='5m', start_date=None, end_date=None, adjust='qfq')
get_price_minute(security, count=None, period='5m', fields=None, adjust='qfq')
```

支持周期：`1m`, `5m`, `15m`, `30m`, `60m`。

### Tick 数据

```python
get_tick_data(code, trade_date=None)
```

### 资金流与龙虎榜

```python
get_money_flow(code, start_date=None, end_date=None, count=None)
get_billboard_list(stock_list=None, date=None, start_date=None, end_date=None)
```

### 财务数据

```python
get_financial_abstract(code)
```

### 链式选股 API

```python
query(*fields)
get_fundamentals(query_or_code, date=None)
```

可用字段通过 `valuation` 命名空间访问：`code`, `market_cap`, `total_value`, `float_value`, `pe`, `pb`, `turnover`, `price`, `pct_change`。

链式方法：`.filter()`、`.order_by()`、`.limit()`。

```python
q = query(valuation.code, valuation.market_cap, valuation.pe) \
    .filter(valuation.market_cap.between(20, 30), valuation.pe > 0) \
    .order_by(valuation.market_cap.asc()) \
    .limit(5)
df = get_fundamentals(q)
```

### get_current_data_object

获取带属性访问的实时行情快照。返回 `dict[str, _StockDataObj]`。

### get_extras

获取额外数据字段（`'is_st'` 或 `'net_value'`）。

### 股票池管理

```python
set_universe(security_list)   # 设置策略股票池
get_universe()                 # 获取当前股票池
```

### 本地文件

| API | 说明 |
|-----|------|
| `download_stock_data(code, start_date, end_date, adjust='qfq', output_dir=None)` | 下载日线数据为 CSV |
| `load_csv(path, index_col='date', parse_dates=True)` | 从本地 CSV 加载数据 |
| `clear_cache()` | 清除内存缓存 |
| `save_stock_local(security, start_date, end_date)` | 下载并保存本地 |
| `load_stock_local(security, start_date, end_date)` | 从本地加载 |
| `has_local_data(security)` | 检查是否存在 |
| `list_local_stocks()` | 列出所有本地文件 |
| `remove_local_data(security)` | 删除单个文件 |
| `clear_all_local_data()` | 清空所有本地文件 |

---

## 回测与模拟盘引擎

### run_strategy

一站式回测 + 报告生成。

```python
run_strategy(initialize_func, start_date, end_date, starting_cash=100000,
             benchmark='000300.XSHG', handle_data=None, securities=None,
             report_dir='reports', use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

返回回测结果 `dict`。

### run_backtest

运行回测（不生成报告）。

```python
run_backtest(initialize_func, start_date, end_date, starting_cash=100000.0,
             frequency='daily', benchmark='000300.XSHG', securities=None,
             use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

返回 `{"context": Context, "trade_log": list, "recorded_values": dict, "benchmark": str}`。

### run_portfolio_backtest

面向多股票组合的高层回测接口。

```python
run_portfolio_backtest(config, strategy_func, report_dir='reports')
```

#### StrategyConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `securities` | `list[str]` | 必填 | 股票池 |
| `start_date` | `str`/`date` | 必填 | 开始日期 |
| `end_date` | `str`/`date` | 必填 | 结束日期 |
| `starting_cash` | `float` | `100000` | 初始资金 |
| `benchmark` | `str` | `"000300.XSHG"` | 基准指数 |
| `position_pct` | `float` | `0.33` | 每只股票最大仓位比例 |
| `position_amount` | `int` | `0` | 固定买入股数 |
| `report_suffix` | `str` | `""` | 报告文件名后缀 |
| `frequency` | `str` | `"daily"` | `"daily"` 或 `"minute"` |

### estimate_memory_mb

估算预加载数据的内存需求。返回 `dict`（`panel_mb`, `close_dict_mb`, `bar_cache_mb`, `total_mb`）。

### run_paper_trade

模拟盘交易，持续运行直到 `Ctrl+C` 终止。

```python
run_paper_trade(initialize_func, starting_cash=100000.0, benchmark='000300.XSHG', interval=60)
```

### record

在策略中记录自定义数据点。

```python
record(price=current_price, ma5=ma5, signal='BUY')
```

### 调度函数

| API | 说明 |
|-----|------|
| `run_daily(func, time='every_bar')` | 每日定时执行 |
| `run_weekly(func, day_of_week=1, time='09:30')` | 每周定时执行 |
| `run_monthly(func, day_of_month=1, time='09:30')` | 每月定时执行 |
| `run_selection(func, rebalance='monthly:1')` | 注册选股函数，按周期执行 |

`rebalance` 格式：`"monthly:N"`（每月第 N 天）、`"weekly:N"`（周几，0=周一）、`"daily"`（每个交易日）。

### 生命周期回调

| API | 说明 |
|-----|------|
| `before_trading_start(func)` | 注册盘前回调 |
| `after_trading_end(func)` | 注册盘后回调 |

---

## 配置 API

### set_benchmark

设置回测基准。

```python
set_benchmark('000300.XSHG')   # 沪深300
```

### set_order_cost

设置交易手续费。

```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                         open_commission=0.0003, close_commission=0.0003,
                         min_commission=5))
```

#### OrderCost

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `open_tax` | `0` | 买入印花税 |
| `close_tax` | `0.001` | 卖出印花税 |
| `open_commission` | `0.0003` | 买入佣金 |
| `close_commission` | `0.0003` | 卖出佣金 |
| `close_today_commission` | `0` | 今日卖出佣金 |
| `min_commission` | `5` | 最低佣金（元） |

### set_option

设置策略选项。

```python
set_option('use_real_price', True)
```

### set_slippage

设置滑点模型。

| 类 | 说明 |
|-----|------|
| `SlippageModel` | 基类，不调整价格 |
| `FixedSlippage(pct=0.001)` | 固定比例滑点 |
| `VolumeSlippage(impact=0.05)` | 与成交量成比例的冲击成本 |

### BacktestSession 与 get_session

`BacktestSession` 封装单次回测的可变状态。普通策略不必使用，多线程并行回测时可为每线程创建独立会话。

---

## 通知 API

!!! tip "模拟盘通知"

    在模拟盘运行时，通过钉钉或飞书 Webhook 接收交易信号通知，
    收到通知后可手动执行实盘操作。

### set_notification_webhook

配置 Webhook 用于发送交易信号通知。

```python
# 钉钉（支持签名验证）
set_notification_webhook("dingtalk", 
    "https://oapi.dingtalk.com/robot/send?access_token=xxx",
    secret="SECxxx")

# 飞书
set_notification_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/xxx")

# 关闭通知
set_notification_webhook(None, None)
```

| 参数 | 说明 |
|------|------|
| `platform` | `"dingtalk"` 或 `"feishu"` |
| `url` | Webhook URL |
| `secret` | 钉钉签名密钥（可选） |

!!! warning "获取 Webhook"

    - **钉钉**: 群设置 → 智能群助手 → 添加机器人 → 自定义
    - **飞书**: 群设置 → 群机器人 → 添加机器人 → 自定义机器人

### enable_notification

启用通知事件类型。

```python
# 启用信号通知（推荐）
enable_notification(["signal"])

# 启用所有通知
enable_notification(["signal", "filled"])

# 关闭通知
enable_notification([])
```

| 事件 | 说明 |
|------|------|
| `"signal"` | 策略触发交易信号时通知（推荐） |
| `"filled"` | 订单成交时通知 |
| `"queued"` | 订单生成时通知 |

### notify_signal

发送交易信号通知。在策略检测到交易信号时调用。

```python
def handle_data(context, data):
    price = data.current(g.security, 'close')
    ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
    ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()
    
    # 金叉信号 - 发送通知
    if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),  # ±2%区间
            strategy_name="双均线金叉策略",
            trigger_point=f"MA5={ma5:.2f} 上穿 MA20={ma20:.2f}"
        )
        order(g.security, 1000)
```

| 参数 | 说明 |
|------|------|
| `security` | 股票代码 |
| `side` | `"buy"` 或 `"sell"` |
| `amount` | 数量（股），须为100的整数倍 |
| `current_price` | 当前价格 |
| `price_range` | 建议价格区间 `(low, high)` |
| `strategy_name` | 策略名称 |
| `trigger_point` | 触发点详情 |

#### 通知消息格式

```
## 📈 EasyQuant 操作建议

**触发策略**: 双均线金叉策略
**股票**: 601390 (中国中铁)
**操作**: 买入
**数量**: 1,000 股 (10 手)
**当前价格**: ¥5.850
**建议价格区间**: ¥5.800 ~ ¥5.900
**区间幅度**: -0.85% ~ +0.85%
**预估金额**: ¥5,850.00
**时间**: 2024-01-15 09:30:00

**触发点**: MA5=5.25 上穿 MA20=4.80, 金叉形成

> 💡 **操作建议**:
> 建议在 ¥5.800 ~ ¥5.900 区间内买入 1,000 股
```

---

## 报告与分析 API

### generate_chart

生成回测图表（PNG）。

```python
generate_chart(result, out_path)
```

### generate_report_md

生成 Markdown 格式报告。

### generate_report_json

生成 JSON 格式报告。返回的 JSON 包含：`metadata`（生成信息）、`summary`（资金盈亏）、`risk_metrics`（风险指标）、`excess_return_metrics`（超额收益指标）、`brinson_attribution`（Brinson 归因）、`factor_analysis`（因子分析）、`trades`（成交列表）、`positions`（持仓）、`cumulative_returns`（净值序列），以及全部 **图表数据数组**：`candlestick_data`、`volume_data`、`ma5/20/60_data`、`rsi_data`、`macd_data`/`macd_signal_data`/`macd_hist_data`、`bb_upper/middle/lower_data`、`support_data`、`resistance_data`、`markers`、`cum_return_data`、`ret_hs300_data`、`ret_sse_data`、`drawdown_data`、`pnl_bar_data`、`daily_returns_data`。

### generate_html_report

生成交互式 HTML 报告。HTML 报告内含 K 线图（含 MA 均线、成交量、买卖信号）、RSI(14)、MACD(12,26,9)、Bollinger Bands(20,2)、累计收益、回撤、每日盈亏、成交记录。K 线图支持指标切换面板和十字光标联动图例。

### analyze_returns

计算综合风险指标。

```python
metrics = analyze_returns(result, risk_free_rate=0.03, trading_days=252)
```

返回 `dict`：`total_return`, `annual_return`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `alpha`, `beta`, `information_ratio`, `win_rate`, `trading_days`, `num_trades`。

### brinson_attribution

Brinson 归因分析。返回 `dict`（`allocation_effect`, `selection_effect`, `interaction_effect`, `total_active_return`）。

### fama_french_analysis

Fama-French 因子分析。返回 `dict`（`market_beta`, `market_exposure`, `alpha_annual`, `momentum_correlation`, `vol_of_vol`, `residual_volatility`, `explained_variance`）。

---

## 组合优化 API

### portfolio_optimizer

投资组合权重优化。

```python
portfolio_optimizer(securities, prices, target=None, constraints=None, bounds=None,
                    default_range=(0.0, 1.0), ftol=1e-9, return_none_if_fail=True)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 股票代码列表 |
| `prices` | `DataFrame` | 价格矩阵 |
| `target` | `MinVariance`/`MaxSharpe`/`RiskParity` | 优化目标 |
| `constraints` | `dict` | `{'max_weight': 0.3}` |
| `bounds` | `list[Bound]` | 每只股票权重上下限 |

返回优化后的权重 `Series` 或 `None`。

#### 优化目标

```python
MinVariance()
MaxSharpe(risk_free_rate=0.03)
RiskParity()
```

---

## 缓存 API

| API | 说明 |
|-----|------|
| `set_cache_dir(path)` | 设置磁盘缓存目录 |
| `fetch_cached(security, start_date, end_date, adjust='qfq')` | 获取数据，优先使用缓存 |

数据源接入建议：保持 API 入参/出参不变，先落盘统一格式再进入回测，采用主备数据源切换与交叉校验。

---

## 日志 API

### 基础日志

```python
log.info(msg)
log.debug(msg)
log.warn(msg)
log.error(msg)
```

### 结构化日志

| API | 说明 |
|-----|------|
| `log.section(title, **fields)` | 标记高层阶段 |
| `log.step(name, status='RUN', **fields)` | 记录步骤状态 |
| `log.progress(current, total, label='Progress')` | 显示进度 |
| `log.action(name, target=None, **fields)` | 记录操作动作 |
| `log.set_level(level)` | 控制详细程度 |
| `log.set_quiet(enabled=True)` | 仅输出 WARNING/ERROR |

---

## 辅助工具 API

| API | 说明 |
|-----|------|
| `engine.get_context()` | 获取当前回测上下文 |
| `engine.get_g()` | 获取全局对象 |
| `engine.get_trade_log()` | 获取交易记录 |
| `engine.get_recorded_values()` | 获取 record() 记录 |

---

## Web Studio API 端点

### `GET /api/v1/runs/{run_id}/report/data`

返回完整的回测报告 JSON 数据（包含所有图表数据数组），用于 Web 控制台中的原生 Lightweight Charts 渲染。

```bash
curl http://localhost:8081/api/v1/runs/<run_id>/report/data
```

返回结构与 `generate_report_json()` 输出的 JSON 一致，包含 `summary`、`risk_metrics`、`cumulative_returns`、`candlestick_data`、`volume_data`、`ma5/20/60_data`、`rsi_data`、`macd_data`、`bb_upper/middle/lower_data`、`drawdown_data`、`pnl_bar_data`、`daily_returns_data` 等全部字段。

---

## 选股策略 API

### 编写选股策略

**模式一：普通函数**

```python
def my_selection(context):
    candidates = filter_st_stocks(["601390", "600519"])
    df = fetch_factor_data(candidates, fields=["pe"])
    return df.sort_values("pe").head(5).index.tolist()
```

**模式二：StockSelector 子类**

```python
class MySelector(StockSelector):
    def filter(self, candidates, context):
        return filter_st_stocks(candidates)
    def rank(self, securities, context):
        return TopNSelector(factor="pe", top_n=5).rank(securities, context)
```

**模式三：内置选择器**

```python
TopNSelector(factor="pe", top_n=5, ascending=True)
MultiFactorSelector(factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4}, top_n=5)
```

### 注册与调用

```python
# 在 initialize 中调用
run_selection(my_selection, rebalance="monthly:1")

# 或通过 run_strategy 参数
result = run_strategy(initialize, selection_func=my_selection, selection_rebalance="weekly:0")
```

### 工具函数

| API | 说明 |
|-----|------|
| `StockSelector` | 选股基类 |
| `filter_st_stocks(securities)` | 剔除 ST 股票 |
| `filter_paused_stocks(securities, context)` | 剔除停牌股票 |
| `filter_low_price_stocks(securities, min_price=2.0)` | 剔除低价股 |
| `filter_high_pe_stocks(securities, max_pe=100.0)` | 剔除高 PE 股 |
| `fetch_factor_data(securities, fields=None)` | 获取多维度因子数据 |
| `TopNSelector(factor, top_n, ascending)` | 单因子 Top-N 选择器 |
| `MultiFactorSelector(factors, top_n)` | 多因子加权选择器 |

`fetch_factor_data` 可用字段：`price`, `pct_change`, `total_value`, `pe`, `pb`, `turnover`, `ma5`, `ma10`, `ma20`, `rsi14`。

---

## 参数化与优化约定

`eqlib` 的 API 可与任意 Python 流程配合（脚本、Notebook、定时任务）。典型调用链：`run_backtest()` → `analyze_returns()` → `brinson_attribution()` → 分析结果 → 修改参数 → 再回测。

策略文件定义 `PARAMS`（当前值）与 `PARAM_RANGES`（搜索空间），由优化脚本读取与更新。每次变更后建议核对：新参数落在范围内、满足交叉约束、未引入前视偏差。

---

## 附录：完整导入清单

```python
from eqlib import (
    # 生命周期
    run_backtest, run_strategy, run_portfolio_backtest,
    run_daily, run_weekly, run_monthly, run_selection,
    set_handle_data, record, run_paper_trade,
    # 配置
    set_benchmark, set_option, set_order_cost, set_slippage,
    OrderCost, SlippageModel, FixedSlippage, VolumeSlippage,
    # 交易
    order, order_target, order_value, order_target_value,
    # 数据
    get_price, history, attribute_history, get_all_securities,
    fetch_stock_data, download_stock_data, load_csv, clear_cache,
    scan_market, check_golden_cross, get_financial_screen,
    get_index_stocks, get_industry_list, get_industry_stocks,
    get_concept_list, get_concept_stocks, get_industry,
    fetch_minute_data, get_price_minute, get_tick_data,
    get_current_data, get_security_info, get_trade_days,
    get_fundamentals, get_financial_abstract, get_money_flow,
    get_billboard_list, get_valuation, get_index_weights, get_extras,
    query, valuation, get_current_data_object,
    set_universe, get_universe,
    before_trading_start, after_trading_end,
    # 日志
    log,
    # 对象
    g, GlobalObject, Context, Portfolio, Position,
    StrategyConfig,
    # 报告
    generate_chart, generate_report_md, generate_report_json, generate_html_report,
    # 组合优化
    portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity,
    # 分析
    analyze_returns, brinson_attribution, fama_french_analysis,
    # 选股
    StockSelector, TopNSelector, MultiFactorSelector,
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
    fetch_factor_data,
    # 缓存
    set_cache_dir, set_local_data_dir, fetch_cached, estimate_memory_mb,
    save_stock_local, load_stock_local, has_local_data,
    list_local_stocks, remove_local_data, clear_all_local_data,
    BacktestSession, get_session,
)
```
