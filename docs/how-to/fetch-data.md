# 数据获取

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 掌握所有数据获取方式 |
    | **前置** | [编写策略](write-strategy.md) |

---
## 1. 数据拉取

### 1.1 历史日线数据

```python
# 方式一：history()
close = history(20, '1d', 'close', security='601390')

# 方式二：attribute_history（更灵活）
hist = attribute_history('601390', 30, '1d',
                         fields=['open', 'close', 'volume', 'high', 'low'])

# 方式三：get_price（支持指定日期范围）
df = get_price('601390',
               start_date='2024-01-01',
               end_date='2024-06-30',
               fields=['open', 'high', 'low', 'close', 'volume'])
```

### 1.2 实时行情快照

```python
data = get_current_data()
info = get_security_info('601390')
val = get_valuation('601390')
```

### 1.3 选股与扫描

```python
candidates = scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
screened = get_financial_screen(min_pe=5, max_pe=30, min_roe=10)  # ROE ≥ 10%（最近一期季报）
```

### 1.4 指数与行业成分股

```python
constituents = get_index_stocks('000300.XSHG')   # 沪深300 成分股
industries = get_industry_list()                  # 所有行业板块
stocks = get_industry_stocks('白酒')              # 白酒行业成分股
concepts = get_concept_list()                     # 所有概念板块
concept_stocks = get_concept_stocks('人工智能')    # 人工智能概念股
```

### 1.5 分钟线数据

```python
df_5m = fetch_minute_data('601390', period='5m')
# 支持的周期：1m, 5m, 15m, 30m, 60m
```

### 1.6 Tick 数据

```python
df_tick = get_tick_data('601390')
```

### 1.7 资金流向与龙虎榜

```python
flow = get_money_flow('601390', count=30)
billboard = get_billboard_list(date='20241201')
weights = get_index_weights('000300.XSHG')
```

### 1.8 交易日历

```python
days = get_trade_days(start_date='2024-01-01', end_date='2024-12-31')
recent_days = get_trade_days(count=10)
```

### 1.9 本地数据缓存

```python
from eqlib import set_local_data_dir, save_stock_local, has_local_data

set_local_data_dir('/path/to/eqlib_data')

for sec in ['601390', '600519', '000300.XSHG']:
    path = save_stock_local(sec, '2020-01-01', '2024-12-31')

result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390', '600519'],
    use_local=True,
)
```

建议：先确认 `has_local_data(code)` 为 `True` 再跑回测；大范围回测先用较短日期区间做冒烟测试。

### 1.10 A 股特色数据

eqlib 提供多个 A 股市场特有的数据接口，覆盖北向资金、融资融券、涨跌停统计和限售股解禁等维度。

#### 1.10.1 北向资金

北向资金（沪股通 + 深股通）是外资流入 A 股的重要风向标。

```python
from eqlib import get_north_money_flow

# 获取北向资金流向（不传日期默认近 30 天）
df = get_north_money_flow(start_date='2024-01-01', end_date='2024-06-30')
# 返回字段：date, net_buy, total_buy, total_sell（单位：亿元）

# 在策略中使用北向资金信号
def market_open(context):
    north_flow = get_north_money_flow()
    if not north_flow.empty:
        recent_net = north_flow['net_buy'].tail(3).sum()
        if recent_net > 100:  # 近 3 日净买入超 100 亿
            log.info("北向资金大幅净流入: %.1f 亿" % recent_net)
```

#### 1.10.2 融资融券

融资融券数据反映杠杆资金动向。该接口是**全市场汇总**口径（沪深两市合计），没有个股粒度。

```python
from eqlib import get_margin_data

# 获取全市场融资融券汇总（不传日期默认近 30 天）
df = get_margin_data(start_date='2024-01-01', end_date='2024-06-30')
# 返回字段：date, margin_balance, margin_buy, margin_repay, short_balance
# （单位：亿元；margin_repay 由余额推算，首行为 NaN）

# 查看融资余额变化
if not df.empty:
    if len(df) >= 6:
        change_5d = df['margin_balance'].iloc[-1] - df['margin_balance'].iloc[-6]
    log.info("融资余额 5 日变化: %.1f 亿" % change_5d)
```

#### 1.10.3 涨跌停统计

统计市场涨跌停数量，用于判断市场情绪。

```python
from eqlib import get_limit_up_down_stats

# 获取涨跌停统计数据
df = get_limit_up_down_stats()
# 返回字段：date, limit_up_count, limit_down_count, api_error_count
# 数据源只保留最近约 30 个交易日，更早的区间拿不到

# 判断市场情绪
if not df.empty:
    latest = df.iloc[-1]
    if latest['limit_down_count'] > 100:
        log.warn("跌停超 100 只，系统性风险信号")
    elif latest['limit_up_count'] / max(latest['limit_down_count'], 1) > 3:
        log.info("涨跌停比 > 3，情绪偏强")
```

#### 1.10.4 限售股解禁

解禁数据可提前规避潜在抛压。

```python
from eqlib import get_restriction_release

# 获取未来 30 天的解禁计划（days 是唯一参数，窗口从真实当天起算）
df = get_restriction_release(days=30)
# 返回字段：code, name, release_date, release_amount（万股）,
#           release_value（亿元）, release_pct（占解禁前流通市值比例）

# 筛选大额解禁（release_value 单位是亿元）
big_releases = df[df['release_value'] > 10]
if not big_releases.empty:
    log.info("大额解禁股票: %s" % big_releases['code'].tolist())
```

解禁窗口永远从**真实当天**起算，数据源不带公告日历史——这是快照型接口，回测中调用会触发 `FutureWarning`（见 §2）。

---

## 2. 回测中的数据可见性（PIT）

回测会话内，数据接口按"模拟时钟能看到什么"分两档处理。决策时回调（`before_trading_start`、定时函数、`handle_data`）的可见边界是 **T-1**；当天数据在收盘后的回调里才可见。

| 接口 | 回测内行为 |
|------|-----------|
| `history` / `attribute_history` | 读预加载数据，天然不含未来数据，回测内首选 |
| `get_price` | 只返回模拟当天之前的 bar |
| `fetch_stock_data` / `load_stock_local` | 截断到 T-1；起点晚于截断日返回空 DataFrame |
| `fetch_minute_data` | 只返回模拟时钟之前的 bar |
| `get_money_flow` / `get_billboard_list` / `check_golden_cross` | 截断到 T-1 |
| `get_north_money_flow` / `get_margin_data` / `get_limit_up_down_stats` | 日期区间截断到 T-1；完全越界返回空 DataFrame |
| `get_current_data` / `get_valuation` / `get_extras` | 快照型：触发 `FutureWarning` |
| `get_index_stocks` / `get_industry_stocks` / `get_concept_stocks` / `get_index_weights` | 快照型（成分取当前名单，有幸存者偏差）：`FutureWarning` |
| `scan_market` / `get_financial_screen` / `get_financial_abstract` | 快照型：`FutureWarning` |
| `get_restriction_release` / `get_tick_data` | 快照型：`FutureWarning` |
| `get_fundamentals` | `date` 参数被忽略（数据源无披露日历史）：`FutureWarning` |

快照型接口在 `set_option('avoid_future_data', True)` 下把警告升级为 `ValueError`，回测直接报错退出——写论文级严谨回测时打开它。研究和实盘场景不受这些限制。

---

完整 API 参数说明见 [数据 API 参考](../reference/api-data.md)。
