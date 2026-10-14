# 数据 API

> 获取历史行情、实时数据、财务信息、A 股特色数据等。

---

## get_price

获取历史价格数据。

```python
get_price(security, start_date=None, end_date=None, frequency='daily', fields=None, count=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` 或 `list` | 是 | 股票代码 |
| `start_date` | `str`/`date` | 否 | 开始日期 |
| `end_date` | `str`/`date` | 否 | 结束日期 |
| `frequency` | `str` | 否 | 支持 `'daily'` / `'1d'`；分钟请用 `get_price_minute` |
| `fields` | `list` | 否 | 指定返回字段 |
| `count` | `int` | 否 | 返回最近 N 根 bar |

返回 `DataFrame`（单只）或 `dict[str, DataFrame]`（多只）。

## history

获取从当前回测时间向前推 `count` 根 bar 的数据。仅在策略回调内可用。

```python
history(count, unit='1d', field='close', security=None, df=False)
```

## attribute_history

获取单只股票的历史属性数据。

```python
attribute_history(security, count, unit='1d', fields=('close',), df=True, skip_paused=True, fq='pre')
```

返回 `DataFrame`，列包括：`open`, `high`, `low`, `close`, `volume`, `money`, `pct_change`, `turnover`。

## get_current_data

获取全部 A 股实时快照。返回 `dict[str, dict]`，包含 `code`, `name`, `price`, `pct_change`, `volume`, `pe`, `pb`, `total_value` 等字段。

!!! warning "非时点（PIT）安全"
    返回**最新快照**（当前价格/PE/PB 等），无历史时点版本；回测会话内调用会发出 `FutureWarning`（`avoid_future_data=True` 时报错）。

## get_security_info

获取单只股票基本信息。返回 `SecurityInfo` 对象（`code`, `name`, `industry`, `total_shares`, `float_shares`, `total_value`, `list_date`）。

## get_valuation

获取估值数据。返回 `dict` 或 `None`。

## scan_market

扫描 A 股并筛选。

```python
scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
```

## get_financial_screen

按财务指标筛选。

```python
get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None,
                     min_roe=None, min_revenue=None, min_profit=None)
```

`min_pe` / `max_pe` / `min_pb` / `max_pb` 作用于实时现货快照；`min_roe`（单位：%，如 `10` 表示 ROE ≥ 10%）、`min_revenue`（单位：元）、`min_profit`（单位：元）作用于最近一期披露基本完整的季报（业绩报表），传入任一者后结果会附带 `roe` / `revenue` / `profit` 列。季报数据不可用时函数按失败关闭处理：返回空 `DataFrame` 并记录警告，不会假装过滤已生效。两类数据均为最新快照，回测中使用会触发 `FutureWarning`（见函数文档字符串）。

## get_all_securities

获取全部 A 股列表。返回 `DataFrame`（code, name）。

## get_trade_days

获取交易日历。返回 `list[date]`。

## 指数与行业

| API | 说明 | 返回 |
|-----|------|------|
| `get_index_stocks(index_code)` | 指数成分股 | `DataFrame` |
| `get_industry_list()` | 所有行业板块 | `list[str]` |
| `get_industry_stocks(industry_name)` | 某行业成分股 | `DataFrame` |
| `get_industry(code)` | 单只股票行业分类 | `dict` 或 `None` |
| `get_index_weights(index_code, date=None)` | 指数成分股权重 | `DataFrame` |

!!! warning "幸存者偏差"
    `get_index_stocks` 返回**当前**成分股名单，无历史时点版本。用它构建历史回测股票池会引入幸存者偏差（已退市/调出的股票被静默排除）。在回测会话内调用会发出告警；历史 universe 建议用显式股票列表并自行处理退市。

## 概念板块

| API | 说明 | 返回 |
|-----|------|------|
| `get_concept_list()` | 所有概念板块 | `list[str]` |
| `get_concept_stocks(concept_name)` | 概念股成分 | `DataFrame` |

## 分钟线数据

```python
fetch_minute_data(code, period='5m', start_date=None, end_date=None, adjust='qfq')
get_price_minute(security, count=None, period='5m', fields=None, adjust='qfq')
```

支持周期：`1m`, `5m`, `15m`, `30m`, `60m`。

## Tick 数据

```python
get_tick_data(code, trade_date=None)
```

## 资金流与龙虎榜

```python
get_money_flow(code, start_date=None, end_date=None, count=None)
get_billboard_list(stock_list=None, date=None, start_date=None, end_date=None)
```

## A 股特色数据

### get_north_money_flow

北向资金流向（沪股通 + 深股通汇总）。

```python
get_north_money_flow(start_date=None, end_date=None)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_date` | `str`/`date` | 开始日期，默认 30 天前 |
| `end_date` | `str`/`date` | 结束日期，默认今天（中国时区） |

返回 `DataFrame`，列包括：

| 列名 | 说明 |
|------|------|
| `date` | 交易日期 |
| `net_buy` | 净买入额（亿元） |
| `total_buy` | 总买入额（亿元） |
| `total_sell` | 总卖出额（亿元） |

```python
from eqlib import get_north_money_flow

# 获取近 3 个月北向资金
north = get_north_money_flow(start_date="2024-01-01", end_date="2024-03-31")

# 计算近 5 日净买入
recent_5d = north["net_buy"].tail(5).sum()
if recent_5d > 50:
    print("北向资金强势流入")
```

**注意**：使用中国时区 (UTC+8) 确定"今天"，缓存有效期 1 小时。

### get_margin_data

融资融券数据（全市场汇总）。

```python
get_margin_data(start_date=None, end_date=None)
```

返回 `DataFrame`，列包括：

| 列名 | 说明 |
|------|------|
| `date` | 交易日期 |
| `margin_balance` | 融资余额（亿元） |
| `margin_buy` | 融资买入额（亿元） |
| `margin_repay` | 融资偿还额（亿元）- 第一行为 NaN |
| `short_balance` | 融券余额（亿元） |

```python
from eqlib import get_margin_data

margin = get_margin_data(start_date="2024-01-01", end_date="2024-03-31")

# 融资余额变化率
margin["change_pct"] = margin["margin_balance"].diff(5) / margin["margin_balance"].shift(5) * 100
```

**注意**：`margin_repay` 第一行为 NaN（无前日余额可计算），用户可通过 `dropna()` 或 `fillna()` 处理。

### get_limit_up_down_stats

涨跌停统计（每日涨停/跌停数量）。

```python
get_limit_up_down_stats(start_date=None, end_date=None)
```

返回 `DataFrame`，列包括：

| 列名 | 说明 |
|------|------|
| `date` | 交易日期 |
| `limit_up_count` | 涨停股票数量 |
| `limit_down_count` | 跌停股票数量 |
| `api_error_count` | API 调用失败次数（数据质量监控） |

```python
from eqlib import get_limit_up_down_stats

stats = get_limit_up_down_stats()

# 系统性风险预警
latest_down = stats["limit_down_count"].iloc[-1]
if latest_down > 100:
    print("⚠️ 系统性风险预警")
```

**注意**：API 只支持最近 30 个交易日，超出范围会发出警告。

### get_restriction_release

限售股解禁（未来 N 天解禁列表）。

```python
get_restriction_release(days=30)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `days` | `int` | 未来天数范围，默认 30 |

返回 `DataFrame`，列包括：

| 列名 | 说明 |
|------|------|
| `code` | 股票代码 |
| `name` | 股票名称 |
| `release_date` | 解禁日期 |
| `release_amount` | 解禁数量（万股） |
| `release_value` | 解禁市值（亿元） |
| `release_pct` | 占解禁前流通市值比例 |

```python
from eqlib import get_restriction_release

# 获取未来 30 天解禁
releases = get_restriction_release(days=30)

# 大额解禁预警
large = releases[releases["release_value"] > 50]
print(f"大额解禁: {len(large)} 只")
```

## 财务数据

```python
get_financial_abstract(code)
```

## 链式选股 API

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

!!! warning "非时点（PIT）安全"
    `get_fundamentals` 返回数据源的**最新快照**，`date` 参数在 V1 中被忽略（底层数据源无披露日期历史）。在回测会话内调用会引入前视偏差：框架会发出 `FutureWarning`；设置 `set_option('avoid_future_data', True)` 后升级为 `ValueError`。回测中的基本面因子请使用自建的历史财务数据；研究模式与实盘不受限制。

## get_current_data_object

获取带属性访问的实时行情快照。返回 `dict[str, _StockDataObj]`。

!!! warning "非时点（PIT）安全"
    与 `get_current_data` 同源的**最新快照**（含由当前名称推导的 ST 状态）；回测会话内调用会发出 `FutureWarning`（`avoid_future_data=True` 时报错）。

## get_extras

获取额外数据字段（`'is_st'` 或 `'net_value'`）。

!!! warning "非时点（PIT）安全"
    返回**最新快照**（如当前 ST 状态），无历史时点版本；回测会话内调用会发出 `FutureWarning`（`avoid_future_data=True` 时报错）。回测中需要 PIT 安全的 ST 状态请使用 `set_option('st_status_map', ...)`。

## 股票池管理

```python
set_universe(security_list)   # 设置策略股票池
get_universe()                 # 获取当前股票池
```

## 本地文件

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

## 历史价格契约与复权

`count` 必须是正整数（不能是布尔值），结果取窗口内最后 N 行，数据不足时返回实际可用条数。字符串、date 和 datetime 日期均支持。存在活动回测上下文时，`get_price` 与 `attribute_history` 一样，只返回当前日期之前的日线；显式未来结束日期会被截断。没有回测上下文的研究查询按请求范围读取。`frequency="1m"` 会明确抛出 `NotImplementedError`，不会静默返回日线。

预载数据必须与 `fq` 的复权口径相符：默认 qfq 预载只支持 `fq="pre"`；请求 `fq=None`（不复权）会抛出 `ValueError`，除非预载数据本身明确标为不复权。请使用真实原始价格数据，不要将前复权数据冒充原始价格。缓存返回值可以由调用方处理，不会修改共享缓存。

`get_price_minute` 也限制模拟时间，只返回时间戳严格早于 `current_dt` 的分钟 bar；当前 bar 被保守排除。支持 1m、5m、15m、30m、60m，按时间排序后再取最后 `count` 行。

## 回测会话中的时点（PIT）截断

回测进行中，以下数据接口统一按模拟时钟截断，与 `get_price` 的语义一致：

| API | 会话内行为 |
|-----|-----------|
| `fetch_stock_data` | 决策期回调（`before_trading_start`、定时函数、`handle_data`）截断到 T-1；收盘后回调与回测结束后包含当日；纯未来请求直接返回空 |
| `fetch_minute_data` | 按精确模拟时钟截断（同 `get_price_minute`） |
| `get_money_flow` | 按同一截止日期过滤后再取 `count` |
| `get_billboard_list` / `get_north_money_flow` / `get_margin_data` / `get_limit_up_down_stats` | 查询区间钳制到截止日期 |
| `load_stock_local` | 按模拟时钟截断本地 CSV（同 `fetch_stock_data`）；引擎预载与回测结束后的基准读取经显式豁免不受限 |
| `fetch_cached`（`eqlib.data_cache`） | 磁盘缓存命中分支按同一截止日期截断；网络未命中分支已在 `fetch_stock_data` 内截断 |
| `check_golden_cross` | 历史序列按同一截止日期截断后再计算均线交叉 |
| `get_fundamentals` / `get_financial_abstract` | 快照接口无法截断 — 发出 `FutureWarning`（`avoid_future_data=True` 时报错） |
| `get_valuation` / `get_extras` / `scan_market` / `get_financial_screen` | 同上：最新行情快照（当前 PE/PB/ST 状态等），无历史时点版本 |
| `get_current_data` / `get_current_data_object` | 同上：全市场最新行情快照（当前价格/PE/PB/换手等），无历史时点版本 |
| `get_restriction_release` | 同上：按真实"今天"计算的当前已公告解禁日程，无公告日历史 |
| `get_index_stocks` / `get_index_weights` / `get_concept_stocks` / `get_industry_stocks` | 同上：仅当前成分快照，构建历史股票池有幸存者偏差 |
| `get_tick_data` | 同上：仅当日 tick 快照，`trade_date` 被忽略 |
| `get_industry` / `get_concept_list` / `get_industry_list` / `get_all_securities` / `get_security_info` | 名称/分类/基本资料类接口，不纳入防护（注意：`get_security_info` 的 `name` 为当前名称、可能含 ST 标记，`total_value` 为当前快照——时点敏感用途请改用 `st_status_map` 等 PIT 通道） |

研究模式（无活动回测上下文）与模拟盘不做截断，按请求范围读取。引擎内部的全量预载取数有显式豁免，不受影响。
