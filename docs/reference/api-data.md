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
| `frequency` | `str` | 否 | 仅支持 `'daily'` |
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
get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None, min_roe=None)
```

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

## get_current_data_object

获取带属性访问的实时行情快照。返回 `dict[str, _StockDataObj]`。

## get_extras

获取额外数据字段（`'is_st'` 或 `'net_value'`）。

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
