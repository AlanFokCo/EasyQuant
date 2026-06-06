# 交易 API

> 回测执行语义：`order*` 系列 API 只负责在当前回调中提交请求，订单会在**下一交易日开盘价**统一撮合成交。

---

## order

按股数下单买卖。

```python
order(security, amount, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码，如 `'601390'` |
| `amount` | `int` | 是 | 股数，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型（保留参数） |

返回挂单 ID（`str`），失败返回 `None`。买入自动取整到 100 的整数倍。

```python
order('601390', 1000)    # 买入 1000 股
order('601390', -500)    # 卖出 500 股
```

## order_value

按金额下单买卖。

```python
order_value(security, value, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 金额，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型 |

```python
order_value('601390', 50000)    # 买入 5 万元
```

## order_target

调整持仓到目标股数。

```python
order_target(security, amount, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `amount` | `int` | 是 | 目标持仓股数，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

## order_target_value

调整持仓到目标市值。

```python
order_target_value(security, value, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `value` | `float` | 是 | 目标市值，0 = 清仓 |
| `style` | — | 否 | 订单类型 |

## order_lots

按手数下单买卖（A 股 1 手 = 100 股）。

```python
order_lots(security, lots, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `lots` | `int` | 是 | 手数，正数=买入，负数=卖出 |
| `style` | — | 否 | 订单类型 |

```python
order_lots('601390', 5)    # 买入 5 手（500 股）
order_lots('601390', -2)   # 卖出 2 手（200 股）
```

## order_pct

按可用资金的百分比下单。

```python
order_pct(security, pct, style=None)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | `str` | 是 | 股票代码 |
| `pct` | `float` | 是 | 资金比例，如 `0.5` = 50% 可用资金买入；`-0.3` = 卖出当前持仓 30% |
| `style` | — | 否 | 订单类型 |

```python
order_pct('601390', 0.5)    # 用 50% 可用资金买入
order_pct('601390', -0.3)  # 卖出当前持仓的 30%
```

## 手续费说明

通过 [`set_order_cost()`](api-config.md#set_order_cost) 修改（见[配置 API](api-config.md)）。默认：买入印花税 0%、印花税 0.05%（2023年8月起减半）、买卖佣金 0.025%、最低佣金 5 元。
