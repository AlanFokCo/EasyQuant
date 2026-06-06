# Trading API

> Backtest execution semantics: `order*` APIs only submit requests during the current callback; orders are filled uniformly at the **next trading day's opening price**.

---

## order

Place a buy or sell order by share count.

```python
order(security, amount, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code, e.g. `'601390'` |
| `amount` | `int` | Yes | Number of shares; positive = buy, negative = sell |
| `style` | — | No | Order type (reserved parameter) |

Returns the pending order ID (`str`), or `None` on failure. Buy orders are automatically rounded to the nearest multiple of 100.

```python
order('601390', 1000)    # Buy 1000 shares
order('601390', -500)    # Sell 500 shares
```

## order_value

Place a buy or sell order by monetary value.

```python
order_value(security, value, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code |
| `value` | `float` | Yes | Order value; positive = buy, negative = sell |
| `style` | — | No | Order type |

```python
order_value('601390', 50000)    # Buy 50,000 yuan worth
```

## order_target

Adjust position to a target share count.

```python
order_target(security, amount, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code |
| `amount` | `int` | Yes | Target position in shares; 0 = close position |
| `style` | — | No | Order type |

## order_target_value

Adjust position to a target market value.

```python
order_target_value(security, value, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code |
| `value` | `float` | Yes | Target market value; 0 = close position |
| `style` | — | No | Order type |

## order_lots

Place a buy or sell order by lot count (1 lot = 100 shares in A-share market).

```python
order_lots(security, lots, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code |
| `lots` | `int` | Yes | Number of lots; positive = buy, negative = sell |
| `style` | — | No | Order type |

```python
order_lots('601390', 5)     # Buy 5 lots (500 shares)
order_lots('601390', -2)    # Sell 2 lots (200 shares)
```

## order_pct

Place an order using a percentage of available cash.

```python
order_pct(security, pct, style=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` | Yes | Stock code |
| `pct` | `float` | Yes | Cash ratio, e.g. `0.5` = 50% of available cash; `-0.3` = sell 30% of current position |
| `style` | — | No | Order type |

```python
order_pct('601390', 0.5)     # Buy with 50% of available cash
order_pct('601390', -0.3)    # Sell 30% of current position
```

## Commission Fees

Configure via [`set_order_cost()`](api-config.md#set_order_cost) (see [Configuration API](api-config.md)). Defaults: buy stamp duty 0%, sell stamp duty 0.05% (halved since Aug 2023), buy/sell commission 0.025%, minimum commission 5 yuan.
