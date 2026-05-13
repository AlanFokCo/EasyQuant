!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §5](05_capital_position.md) · [下一章 §7](07_data.md)

---

## 6. 交易 API：买入与卖出

> 重要：`order` / `order_value` / `order_target` / `order_target_value` 在回测中是**先入队**，统一按**下一交易日开盘价**成交（不是当日立即成交）。

### 6.1 `order(security, amount)`

按股数买卖，正数买入，负数卖出。

```python
order('601390', 1000)     # 买入 1000 股
order('601390', -500)     # 卖出 500 股
```

### 6.2 `order_value(security, value)`

按金额买卖，正数买入，负数卖出。

```python
order_value('601390', 50000)   # 买入 5 万元
order_value('601390', -30000)  # 卖出 3 万元
```

### 6.3 `order_target(security, amount)`

调整持仓到目标股数。

```python
order_target('601390', 5000)   # 持仓调到 5000 股
order_target('601390', 0)      # 清仓
```

### 6.4 `order_target_value(security, value)`

调整持仓到目标市值。

```python
order_target_value('601390', 100000)  # 持仓市值调到 10 万
order_target_value('601390', 0)       # 清仓
```
