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
screened = get_financial_screen(min_pe=5, max_pe=30, min_roe=0.1)
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

# 获取北向资金净流入数据（近 N 个交易日）
df = get_north_money_flow(count=30)
# 返回字段：date, buy_value, sell_value, net_inflow, total_inflow

# 在策略中使用北向资金信号
def market_open(context):
    north_flow = get_north_money_flow(count=5)
    if not north_flow.empty:
        recent_net = north_flow['net_inflow'].iloc[-1]
        if recent_net > 1e9:  # 净流入超 10 亿
            log.info("北向资金今日大幅净流入: %.2f 亿" % (recent_net / 1e8))
```

#### 1.10.2 融资融券

融资融券数据反映杠杆资金动向。

```python
from eqlib import get_margin_trading

# 获取个股融资融券数据
df = get_margin_trading('601390', count=30)
# 返回字段：date, margin_buy, margin_sell, margin_repay, margin_balance, etc.

# 查看融资余额变化
if not df.empty:
    balance_change = df['margin_balance'].diff()
    log.info("融资余额 5 日变化: %s" % balance_change.tail(5).tolist())
```

#### 1.10.3 涨跌停统计

统计市场涨跌停数量，用于判断市场情绪。

```python
from eqlib import get_limit_up_down_stats

# 获取涨跌停统计数据
df = get_limit_up_down_stats()
# 返回字段：date, limit_up_count, limit_down_count, limit_up_ratio, etc.

# 判断市场情绪
if not df.empty:
    latest = df.iloc[-1]
    if latest['limit_up_count'] > 100:
        log.info("市场情绪高涨，涨停数: %d" % latest['limit_up_count'])
```

#### 1.10.4 限售股解禁

解禁数据可提前规避潜在抛压。

```python
from eqlib import get_restriction_release

# 获取未来 30 天的解禁计划
df = get_restriction_release(start_date='2024-01-01', end_date='2024-01-31')
# 返回字段：code, name, release_date, release_value, release_amount, etc.

# 筛选大额解禁
big_releases = df[df['release_value'] > 1e9]  # 解禁市值超 10 亿
if not big_releases.empty:
    log.info("大额解禁股票: %s" % big_releases['code'].tolist())
```

---

完整 API 参数说明见 [数据 API 参考](../reference/api-data.md)。
