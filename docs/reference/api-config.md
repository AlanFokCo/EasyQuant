# 配置 API

> 设置基准指数、交易手续费、滑点模型等回测参数。

---

## set_benchmark

设置回测基准。

```python
set_benchmark('000300.XSHG')   # 沪深300
```

## set_order_cost

设置交易手续费。

```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                         open_commission=0.0003, close_commission=0.0003,
                         min_commission=5))
```

### OrderCost

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `open_tax` | `0` | 买入印花税 |
| `close_tax` | `0.001` | 卖出印花税 |
| `open_commission` | `0.0003` | 买入佣金 |
| `close_commission` | `0.0003` | 卖出佣金 |
| `close_today_commission` | `0` | 今日卖出佣金 |
| `min_commission` | `5` | 最低佣金（元） |

## set_option

设置策略选项。

```python
set_option('use_real_price', True)
```

## set_slippage

设置滑点模型。

| 类 | 说明 |
|-----|------|
| `SlippageModel` | 基类，不调整价格 |
| `FixedSlippage(pct=0.001)` | 固定比例滑点 |
| `VolumeSlippage(impact=0.05)` | 与成交量成比例的冲击成本 |

## BacktestSession 与 get_session

`BacktestSession` 封装单次回测的可变状态。普通策略不必使用，多线程并行回测时可为每线程创建独立会话。
