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
| `style` | — | 否 | `MarketOrder` 或 `LimitOrder` |

返回 `Order` 对象（ID 位于 `order_id`），无效请求返回 `None`。买入自动取整到 100 的整数倍。

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

## 成交、状态和代码规则

限价约束作用于含滑点的最终成交价；不满足限价的订单继续等待。同一证券同一交易日的买卖共用成交量预算，拆单或多次撮合不会增加预算；当日无法成交的待单会保留。首次建仓保留传入的代码格式，兼容已有的持仓字典访问方式；后续使用裸代码或带后缀代码下单，均匹配同一已有持仓。

`cancel_order(order_obj)` 可取消部分成交订单的未成交部分，保留成交记录并进入 `cancelled`。`is_complete()` 仅在状态为 `filled` 时返回 True。金额和目标订单在首次撮合解析股数前，`remaining_amount()` 返回 None；之后返回最近一次解析的剩余股数，目标金额对应股数可能随报价改变。卖出比例按现有持仓股数计算，`order_pct(code, -1)` 表示全部清仓请求。

持仓缺少有效报价时沿用上一有效估值价，`Position.price_stale=True`；收到新报价后恢复为 False。缺行情本身不会使持仓退回成本价。
