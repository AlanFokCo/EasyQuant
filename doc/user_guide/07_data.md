!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §6](06_trading_api.md) · [下一章 §8](08_utils.md)

---

## 7. 数据拉取

### 7.1 历史日线数据

```python
# 方式一：在 handle_data 中使用 history()
def market_open(context):
    close = history(20, '1d', 'close', security='601390')
    ma20 = close.mean()

# 方式二：attribute_history（更灵活）
    hist = attribute_history('601390', 30, '1d',
                             fields=['open', 'close', 'volume', 'high', 'low'])

# 方式三：get_price（支持指定日期范围）
    df = get_price('601390',
                   start_date='2024-01-01',
                   end_date='2024-06-30',
                   fields=['open', 'high', 'low', 'close', 'volume'])
```

返回的 DataFrame 包含：`open`, `high`, `low`, `close`, `volume`, `money`, `pct_change`, `turnover` 等列，索引为日期。

### 7.2 实时行情快照

```python
# 获取全部 A 股当前快照
data = get_current_data()
print(data['601390'])  # {'code': '601390', 'name': '工商银行', 'price': 5.2, ...}

# 获取单只股票信息
info = get_security_info('601390')
print(info.name, info.industry)

# 获取估值数据
val = get_valuation('601390')
print(val['pe'], val['pb'], val['total_value'])
```

### 7.3 选股与扫描

```python
# 扫描符合条件的股票
candidates = scan_market(
    min_price=10,
    min_pct_change=3,
    max_pct_change=5,
    max_pe=50,
)

# 按财务指标筛选
screened = get_financial_screen(
    min_pe=5, max_pe=30,
    min_pb=0.5, max_pb=3,
    min_roe=0.1,
)
```

### 7.4 指数与行业成分股

```python
# 指数成分股
constituents = get_index_stocks('000300.XSHG')  # 沪深300 成分股

# 行业列表及成分股
industries = get_industry_list()                # 所有行业板块
stocks = get_industry_stocks('白酒')            # 白酒行业成分股

# 概念板块
concepts = get_concept_list()                   # 所有概念板块
concept_stocks = get_concept_stocks('人工智能')  # 人工智能概念股

# 单只股票所属行业
info = get_industry('601390')
print(info['industry'])
```

### 7.5 分钟线数据

```python
# 获取 5 分钟线
df_5m = fetch_minute_data('601390', period='5m')

# 使用 get_price_minute
df_5m = get_price_minute('601390', count=100, period='5m',
                         fields=['open', 'close', 'volume'])
```

支持的周期：`1m`, `5m`, `15m`, `30m`, `60m`

### 7.6 Tick 数据

```python
df_tick = get_tick_data('601390')
```

### 7.7 资金流向与龙虎榜

```python
# 个股资金流向
flow = get_money_flow('601390', count=30)

# 龙虎榜
billboard = get_billboard_list(date='20241201')

# 指数成分股权重
weights = get_index_weights('000300.XSHG')
```

### 7.8 ST 标记与额外字段

```python
st_flags = get_extras('is_st')        # 哪些是 ST 股
net_vals = get_extras('net_value')     # 净资产估值
```

### 7.9 交易日历

```python
days = get_trade_days(
    start_date='2024-01-01',
    end_date='2024-12-31',
)

# 最近 10 个交易日
recent_days = get_trade_days(count=10)
```

### 7.10 财务摘要

```python
financial = get_financial_abstract('601390')
print(financial)
```

### 7.11 下载与加载本地 CSV

```python
# 下载数据到本地
path = download_stock_data('601390', '2020-01-01', '2024-12-31',
                           output_dir='data')

# 从本地 CSV 加载
df = load_csv('data/601390_daily.csv')
```

**建议的快速验证流程（本地优先）：**

```python
from eqlib import (
    set_local_data_dir, save_stock_local, has_local_data,
    run_backtest
)

set_local_data_dir('/home/user/eqlib_data')  # 建议使用绝对路径，便于多项目复用

# 先预下载策略股票 + 基准
for sec in ['601390', '600519', '000300.XSHG']:
    path = save_stock_local(sec, '2020-01-01', '2024-12-31')
    print(sec, '->', path, '; ready =', has_local_data(sec))

# 回测时开启 use_local，提高稳定性与速度
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390', '600519'],
    benchmark='000300.XSHG',
    use_local=True,
)
```

排错建议：

- 先确认 `has_local_data(code)` 为 `True`，再跑回测；
- 基准也建议本地化（如 `000300.XSHG`），避免只缓存股票未缓存基准；
- 大范围回测先用较短日期区间做冒烟测试，再扩展到完整区间。

### 7.12 数据源扩展与可靠性建议

当前 `eqlib` 默认使用 `akshare`。为了提升可靠性与覆盖范围，建议采用「主源 + 备源 + 本地落盘」的分层策略：

1. **主源（默认）**：`akshare`，覆盖 A 股日线、分钟线、财务等主要场景；
2. **备源（可选）**：对接聚宽/JQData、Tushare、Baostock 或券商端数据（按授权与接口可用性）；
3. **本地层**：统一落地为本地 CSV/Parquet，回测优先读取本地，网络仅做增量更新。

建议优先扩展的数据能力：

- 历史截面一致的估值/因子数据（降低实时快照替代历史值带来的偏差）；
- 多源交叉校验（成交量、复权因子、停牌状态）；
- 失败自动降级（主源失败时切换备源，保留可追踪日志）。

接入新数据源时，建议先保证以下一致性：

- 输出字段与现有 `get_price` / `fetch_stock_data` 兼容（`open/high/low/close/volume`）；
- 时间索引与交易日历对齐，避免未来函数和错位；
- 复权口径明确（qfq/hfq/none）并可复现。

实践上可先从「离线快验」做起：每次新增数据源后，固定 1-2 只股票 + 1 个基准做对照回测，确认收益曲线和关键指标（收益、回撤、交易次数）变化在可解释范围内，再放大到全量策略。

可先用一个简单阈值作为门槛：

这些阈值用于「首轮接入验收」：既能快速发现明显数据偏差，又不会因市场微小噪声导致误判。实盘前可按策略频率和风控要求再收紧。

- 总收益率偏差不超过 `1%`；
- 最大回撤偏差不超过 `1%`；
- 交易次数偏差不超过 `10%`。
