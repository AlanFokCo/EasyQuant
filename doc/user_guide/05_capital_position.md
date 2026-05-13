!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §4](04_lifecycle.md) · [下一章 §6](06_trading_api.md)

---

## 5. 资金管理：设置初始资金与仓位控制

### 5.1 设置初始资金

在 `run_strategy` 或 `run_backtest` 中指定：

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=500000,   # 50 万元初始资金
)
```

### 5.2 读取账户状态

```python
def market_open(context):
    cash = context.portfolio.available_cash      # 可用现金
    total = context.portfolio.total_value         # 总资产（现金 + 持仓市值）
    positions = context.portfolio.positions       # 持仓字典
    returns = context.portfolio.returns           # 总收益率

    log.info("现金: %.2f, 总资产: %.2f, 收益率: %.2f%%"
             % (cash, total, returns * 100))
```

### 5.3 仓位控制方式

| 方式 | 函数 | 说明 |
|------|------|------|
| **全仓买入** | `order_value(security, context.portfolio.available_cash)` | 用全部可用现金买入 |
| **按比例买入** | `order_value(security, context.portfolio.available_cash * 0.5)` | 用 50% 现金买入 |
| **按固定金额** | `order_value(security, 50000)` | 买入 5 万元 |
| **按固定股数** | `order(security, 1000)` | 买入 1000 股（自动取整到 100 的整数倍） |
| **调到目标股数** | `order_target(security, 5000)` | 调整持仓到 5000 股 |
| **调到目标市值** | `order_target_value(security, 100000)` | 调整持仓市值到 10 万 |
| **清仓** | `order_target(security, 0)` | 全部卖出 |

A 股最小交易单位为 **100 股（1 手）**，所有买入会自动向下取整到 100 的整数倍。

### 5.4 多股等权配置示例

```python
def market_open(context):
    stocks = ['601390', '600519', '000858']
    weight = context.portfolio.available_cash / len(stocks)

    for sec in stocks:
        order_value(sec, weight)   # 每只股票平分可用资金
```
