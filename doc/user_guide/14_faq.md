!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §13](13_optimization.md)

---

## 14. 常见问题

更完整的排错与场景说明见 [**FAQ.md**](../FAQ.md)。

### Q: 如何设置手续费？

```python
set_order_cost(OrderCost(
    open_tax=0,               # 买入印花税（A 股为 0）
    close_tax=0.001,          # 卖出印花税 0.1%
    open_commission=0.0003,   # 买入佣金 0.03%
    close_commission=0.0003,  # 卖出佣金 0.03%
    min_commission=5,         # 最低佣金 5 元
))
```

### Q: 如何做多只股票？

```python
def initialize(context):
    g.stocks = ['601390', '600519', '000858']
    run_daily(rebalance, time='every_bar')

def rebalance(context):
    n = len(g.stocks)
    weight = context.portfolio.total_value / n
    for sec in g.stocks:
        order_target_value(sec, weight)
```

### Q: 如何设置股票池？

```python
def initialize(context):
    # 设置 universe
    set_universe(['601390', '600519', '000858'])

def market_open(context):
    universe = get_universe()  # 获取当前股票池
    for sec in universe:
        # ... 策略逻辑
```

### Q: 如何加速大回测？

```python
# 1. 预加载数据（传入 securities 参数）
result = run_backtest(initialize, '2020-01-01', '2024-12-31',
                      securities=['601390', '600519', ...])

# 2. 设置磁盘缓存
from eqlib import set_cache_dir
set_cache_dir('/path/to/cache')

# 3. 清除缓存重新开始
from eqlib import clear_cache
clear_cache()
```

### Q: 如何在策略内记录自定义数据？

```python
def market_open(context):
    price = history(1, '1d', 'close', '601390').iloc[-1]
    record(price=price, ma5=ma5, signal='BUY')
```

记录的数据会出现在 JSON 报告的 `recorded_values` 字段中。

### Q: A 股 T+1 限制如何处理？

`eqlib` 内部自动处理 T+1 限制：当天买入的股票当天不能卖出（通过 `closeable_amount` 控制）。

### Q: 策略报错 "no price data" 怎么办？

检查股票代码是否正确。A 股代码格式为 6 位数字（如 `'601390'`），不需要带交易所后缀。如果使用了 `set_benchmark`，基准可以使用后缀如 `'000300.XSHG'`。
