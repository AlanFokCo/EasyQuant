# 资金管理与仓位控制

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 掌握仓位控制方式和交易 API |
    | **前置** | [编写策略](write-strategy.md) |

---
## 1. 资金管理与仓位控制

### 1.1 设置初始资金

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=500000,   # 50 万元初始资金
)
```

### 1.2 读取账户状态

```python
def market_open(context):
    cash = context.portfolio.available_cash
    total = context.portfolio.total_value
    positions = context.portfolio.positions
    returns = context.portfolio.returns
```

### 1.3 仓位控制方式

| 方式 | 函数 | 说明 |
|------|------|------|
| **全仓买入** | `order_value(sec, context.portfolio.available_cash)` | 用全部可用现金买入 |
| **按比例买入** | `order_value(sec, context.portfolio.available_cash * 0.5)` | 用 50% 现金买入 |
| **按固定金额** | `order_value(sec, 50000)` | 买入 5 万元 |
| **按手数** | `order_lots(sec, 5)` | 买入 5 手（500 股） |
| **按比例资金** | `order_pct(sec, 0.5)` | 用 50% 可用资金买入 |
| **按固定股数** | `order(sec, 1000)` | 买入 1000 股（自动取整到 100 的整数倍） |
| **调到目标股数** | `order_target(sec, 5000)` | 调整持仓到 5000 股 |
| **调到目标市值** | `order_target_value(sec, 100000)` | 调整持仓市值到 10 万 |
| **清仓** | `order_target(sec, 0)` | 全部卖出 |

A 股最小交易单位为 **100 股（1 手）**，所有买入会自动向下取整到 100 的整数倍。

### 1.4 多股等权配置示例

```python
def market_open(context):
    stocks = ['601390', '600519', '000858']
    weight = context.portfolio.available_cash / len(stocks)
    for sec in stocks:
        order_value(sec, weight)
```

---

## 2. 交易 API

> 重要：`order` / `order_value` / `order_target` / `order_target_value` 在回测中是**先入队**，统一按**下一交易日开盘价**成交。

### 2.1 `order(security, amount)`

按股数买卖，正数买入，负数卖出。

```python
order('601390', 1000)     # 买入 1000 股
order('601390', -500)     # 卖出 500 股
```

### 2.2 `order_value(security, value)`

按金额买卖。

```python
order_value('601390', 50000)   # 买入 5 万元
```

### 2.3 `order_target(security, amount)`

调整持仓到目标股数。

```python
order_target('601390', 5000)   # 持仓调到 5000 股
order_target('601390', 0)      # 清仓
```

### 2.4 `order_target_value(security, value)`

调整持仓到目标市值。

```python
order_target_value('601390', 100000)  # 持仓市值调到 10 万
```

### 2.5 `order_lots(security, lots)`

按手数下单（1 手 = 100 股），正数买入，负数卖出。

```python
order_lots('601390', 5)    # 买入 5 手（500 股）
order_lots('601390', -2)   # 卖出 2 手（200 股）
```

### 2.6 `order_pct(security, pct)`

按可用资金的百分比下单。正数买入，负数卖出。

```python
order_pct('601390', 0.5)    # 用 50% 可用资金买入
order_pct('601390', -0.3)   # 卖出当前持仓的 30%
```

---

完整参数说明见 [交易 API 参考](../reference/api-trading.md)。
