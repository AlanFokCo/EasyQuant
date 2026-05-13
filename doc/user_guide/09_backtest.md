!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §8](08_utils.md) · [下一章 §10](10_reports.md)

---

## 9. 运行回测

### 9.1 方式一：`run_strategy`（推荐）

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

### 9.2 方式二：`run_backtest`（精细控制）

只运行回测，不生成报告。适合自定义后续处理。

```python
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390'],
)

if result:
    print("最终总资产: %.2f" % result['context'].portfolio.total_value)
    print("交易次数: %d" % len(result['trade_log']))
```

### 9.3 方式三：组合回测模式（`run_portfolio_backtest`）

面向多股票组合的高层接口。通过 `StrategyConfig` 定义初始资金、股票池、仓位比例和报告后缀，策略函数从 `context.universe` 中选股并交易。

```python
from eqlib import StrategyConfig, run_portfolio_backtest

# 定义策略配置
config = StrategyConfig(
    starting_cash=200000,              # 20 万初始资金
    securities=[                       # 股票池
        "601390",  # 工商银行
        "600519",  # 贵州茅台
        "000858",  # 五粮液
    ],
    benchmark="000300.XSHG",           # 基准：沪深300
    position_pct=0.33,                 # 每只股票最多用 33% 可用资金
    # position_amount=1000,            # 或者指定固定股数（会覆盖 position_pct）
    start_date="2024-01-01",
    end_date="2024-12-31",
    report_suffix="momentum_v1",        # 报告文件后缀，区分版本
)

# 策略函数：从 context.universe 中选股
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

# 运行回测
result = run_portfolio_backtest(config, my_strategy, report_dir="reports")
```

**输出内容：**

```
==================================================
Portfolio Backtest: 2024-01-01 → 2024-12-31
Universe: ['601390', '600519', '000858']
==================================================
Starting Cash:         200,000.00
Final Value:           215,342.00
P&L:                 +15,342.00 (+7.67%)
Total Trades:              12

--- Per-Stock Summary ---
  600519: 3 buys, 3 sells, net shares 0, realized ¥5,200.00
  601390: 4 buys, 4 sells, net shares 0, realized ¥3,100.00
  000858: 5 buys, 5 sells, net shares 0, realized ¥7,042.00

Chart:  reports/backtest_20240503_120000_momentum_v1.png
Report: reports/backtest_20240503_120000_momentum_v1.html
Data:   reports/backtest_20240503_120000_momentum_v1.json
```

**报告文件后缀（`report_suffix`）**：用于区分不同版本或参数的回测结果。例如 `report_suffix="v1"` 生成 `backtest_20240503_120000_v1.html`。

**`StrategyConfig` 参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `securities` | `list[str]` | 必填 | 股票池代码列表 |
| `start_date` | `str`/`date` | 必填 | 回测开始日期 |
| `end_date` | `str`/`date` | 必填 | 回测结束日期 |
| `starting_cash` | `float` | `100000` | 初始资金 |
| `benchmark` | `str` | `"000300.XSHG"` | 基准指数 |
| `position_pct` | `float` | `0.33` | 每只股票最大仓位比例（可用资金的百分比） |
| `position_amount` | `int` | `0` | 固定买入股数（非零时覆盖 `position_pct`） |
| `report_suffix` | `str` | `""` | 报告文件名后缀 |
| `frequency` | `str` | `"daily"` | `"daily"` 或 `"minute"` |

### 9.4 基准对比说明

回测时通过 `benchmark` 参数设置基准（默认 `000300.XSHG` 沪深300）。回测结果会自动计算策略收益与基准收益的 **alpha**、**beta** 和 **information ratio**，并在图表上叠加显示。
