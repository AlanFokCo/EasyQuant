# Running Backtests

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Master the three backtest interfaces |
    | **Prerequisite** | [Writing Strategies](write-strategy.md) |

---
## 1. Running Backtests

### 1.1 `run_strategy` (Recommended)

One-stop backtest execution with automatic report generation.

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

### 1.2 `run_backtest` (Fine-grained Control)

Runs the backtest only, without generating reports.

```python
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
)
```

### 1.3 `run_portfolio_backtest` (Portfolio Backtest)

High-level interface for multi-stock portfolio backtesting.

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

### 1.4 Benchmark Comparison

Set the benchmark via the `benchmark` parameter (defaults to `000300.XSHG`, the CSI 300 Index). The results will automatically calculate alpha, beta, and information ratio.

---

For complete parameter documentation, see [Backtest Engine API Reference](../reference/api-backtest.md).
