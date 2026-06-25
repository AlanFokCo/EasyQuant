# Configuration API

> Set benchmark index, trading costs, slippage models, and other backtest parameters.

---

## set_benchmark

Set the backtest benchmark.

```python
set_benchmark('000300.XSHG')   # CSI 300
```

## set_order_cost

Set trading costs.

```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                         open_commission=0.00025, close_commission=0.00025,
                         min_commission=5))
```

### OrderCost

| Parameter | Default | Description |
|-----------|---------|-------------|
| `open_tax` | `0` | Buy-side stamp duty |
| `close_tax` | `0.0005` | Sell-side stamp duty |
| `open_commission` | `0.00025` | Buy-side commission |
| `close_commission` | `0.00025` | Sell-side commission |
| `close_today_commission` | `0` | Intraday sell commission |
| `min_commission` | `5` | Minimum commission (¥) |

## set_option

Set strategy options.

```python
set_option('use_real_price', True)
```

## set_slippage

Set the slippage model.

| Class | Description |
|-------|-------------|
| `SlippageModel` | Base class, no price adjustment |
| `FixedSlippage(pct=0.001)` | Fixed percentage slippage |
| `VolumeSlippage(impact=0.05)` | Volume-proportional market impact |

## BacktestSession and get_session

`BacktestSession` encapsulates the mutable state of a single backtest run. Regular strategies do not need to use it; for multi-threaded parallel backtesting, you can create an independent session per thread.
