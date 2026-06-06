# Money Management & Position Control

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Master position control methods and trading APIs |
    | **Prerequisite** | [Writing a Strategy](write-strategy.md) |

---
## 1. Money Management & Position Control

### 1.1 Setting Initial Capital

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=500000,   # 500,000 yuan initial capital
)
```

### 1.2 Reading Account State

```python
def market_open(context):
    cash = context.portfolio.available_cash
    total = context.portfolio.total_value
    positions = context.portfolio.positions
    returns = context.portfolio.returns
```

### 1.3 Position Control Methods

| Method | Function | Description |
|--------|----------|-------------|
| **All-in** | `order_value(sec, context.portfolio.available_cash)` | Buy with all available cash |
| **Proportional** | `order_value(sec, context.portfolio.available_cash * 0.5)` | Buy with 50% of cash |
| **Fixed amount** | `order_value(sec, 50000)` | Buy 50,000 yuan worth |
| **By lots** | `order_lots(sec, 5)` | Buy 5 lots (500 shares) |
| **By percentage** | `order_pct(sec, 0.5)` | Buy with 50% of available cash |
| **Fixed shares** | `order(sec, 1000)` | Buy 1,000 shares (auto-rounds down to multiples of 100) |
| **Target shares** | `order_target(sec, 5000)` | Adjust position to 5,000 shares |
| **Target value** | `order_target_value(sec, 100000)` | Adjust position market value to 100,000 yuan |
| **Liquidate** | `order_target(sec, 0)` | Sell everything |

The minimum trading unit on A-shares is **100 shares (1 lot)**. All buy orders are automatically rounded down to multiples of 100.

### 1.4 Equal-Weight Multi-Stock Allocation Example

```python
def market_open(context):
    stocks = ['601390', '600519', '000858']
    weight = context.portfolio.available_cash / len(stocks)
    for sec in stocks:
        order_value(sec, weight)
```

---

## 2. Trading API

> Important: `order` / `order_value` / `order_target` / `order_target_value` are **queued first** during backtesting and filled uniformly at the **next trading day's open price**.

### 2.1 `order(security, amount)`

Buy or sell by share count. Positive = buy, negative = sell.

```python
order('601390', 1000)     # Buy 1,000 shares
order('601390', -500)     # Sell 500 shares
```

### 2.2 `order_value(security, value)`

Buy or sell by amount.

```python
order_value('601390', 50000)   # Buy 50,000 yuan worth
```

### 2.3 `order_target(security, amount)`

Adjust position to a target share count.

```python
order_target('601390', 5000)   # Adjust position to 5,000 shares
order_target('601390', 0)      # Liquidate
```

### 2.4 `order_target_value(security, value)`

Adjust position to a target market value.

```python
order_target_value('601390', 100000)  # Adjust position value to 100,000 yuan
```

### 2.5 `order_lots(security, lots)`

Place an order by lot count (1 lot = 100 shares). Positive = buy, negative = sell.

```python
order_lots('601390', 5)     # Buy 5 lots (500 shares)
order_lots('601390', -2)    # Sell 2 lots (200 shares)
```

### 2.6 `order_pct(security, pct)`

Place an order using a percentage of available cash. Positive = buy, negative = sell.

```python
order_pct('601390', 0.5)     # Buy with 50% of available cash
order_pct('601390', -0.3)    # Sell 30% of current position
```

---

See the [Trading API Reference](../reference/api-trading.md) for full parameter documentation.
