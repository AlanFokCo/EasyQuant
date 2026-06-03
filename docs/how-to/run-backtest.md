# 运行回测

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 掌握三种回测接口 |
    | **前置** | [编写策略](write-strategy.md) |

---
## 1. 运行回测

### 1.1 `run_strategy`（推荐）

一站式运行回测并生成所有报告。

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390', '600519'],
    report_dir='reports',
)
```

### 1.2 `run_backtest`（精细控制）

只运行回测，不生成报告。

```python
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
)
```

### 1.3 `run_portfolio_backtest`（组合回测）

面向多股票组合的高层接口。

```python
from eqlib import StrategyConfig, run_portfolio_backtest

config = StrategyConfig(
    starting_cash=200000,
    securities=["601390", "600519", "000858"],
    benchmark="000300.XSHG",
    position_pct=0.33,
    start_date="2024-01-01",
    end_date="2024-12-31",
    report_suffix="momentum_v1",
)

def my_strategy(context):
    for sec in context.universe:
        hist = attribute_history(sec, 25, "1d", ["close"])
        if hist.empty:
            continue
        ma20 = hist["close"].tail(20).mean()
        price = hist["close"].iloc[-1]
        if price > ma20 * 1.02:
            order_value(sec, context.portfolio.available_cash)
        elif price < ma20 * 0.98 and context.portfolio.positions.get(sec):
            order_target(sec, 0)

result = run_portfolio_backtest(config, my_strategy, report_dir="reports")
```

### 1.4 基准对比

通过 `benchmark` 参数设置基准（默认 `000300.XSHG` 沪深300）。结果会自动计算 alpha、beta 和 information ratio。

---

完整参数说明见 [回测引擎 API 参考](../reference/api-backtest.md)。
