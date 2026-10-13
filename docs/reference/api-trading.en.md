# Trading API

> Backtest execution semantics: `order*` APIs only submit requests during the current callback; orders are filled uniformly at the **next trading day's opening price**.

---

## Fill rules (A-share market conventions)

The backtest engine enforces the following market rules by default (all configurable — see [Configuration API](api-config.md)):

- **Price limits**: `check_price_limit` defaults to `True`. Buys opening at limit-up and sells opening at limit-down cannot fill; the order is cancelled with `Order.cancel_reason` recording `"limit-up"` / `"limit-down"`. Limits are board- and date-aware (main board ±10%, ST ±5%, ChiNext ±20% since 2020-08-24, STAR ±20%, BSE ±30%).
- **Suspension**: on suspension days (no bar or zero volume) orders are **cancelled the same day** with `cancel_reason` recording `"no price data"` (missing bar) / `"suspended"` (zero volume) — never deferred to resumption.
- **Delisting**: a position with no bar for more than `delist_gap_days` (default 30 trading days) is force-liquidated at the last close, recorded as `DELIST_LIQUIDATE` in the trade log. Use `delisted_position_handling="keep"` to keep the position, and `delisted_liquidation_haircut` to model a liquidation discount.
- **Trading calendar**: driven by the exchange calendar (built-in 2020–2026 calendar, online calendars as fallback outside that range) rather than inferred from the union of available data — a missing stock's data no longer removes that day from the calendar.

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
| `style` | — | No | `MarketOrder` or `LimitOrder` |

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

Configure via [`set_order_cost()`](api-config.md#set_order_cost) (see [Configuration API](api-config.md)). Defaults: buy stamp duty 0%, sell stamp duty 0.05% (halved since 2023-08-28), buy/sell commission 0.025%, minimum commission 5 CNY. `OrderCost.close_tax` defaults to `None`, meaning the statutory rate applies date-aware: 0.05% on/after 2023-08-28 and 0.1% before — long-history backtests crossing that date need no manual handling; an explicit value always overrides.

## Execution, status and security keys

Limits apply to the final execution price including slippage; an order waits if that price violates its limit. Buys and sells share a per-security, per-day volume budget across split orders and repeated matching calls. Temporarily unfillable requests remain queued. The first fill preserves the submitted symbol format for compatibility with existing position dictionary access. Later orders using bare or suffixed symbols resolve to the same existing position.

`cancel_order(order_obj)` cancels the unfilled remainder of a partial fill while preserving executions and setting `cancelled`. `is_complete()` is True only for `filled`. Value and target orders return None from `remaining_amount()` until matching first resolves their quantity; afterwards it reports the latest resolved remaining shares. Target-value quantities may change with prices. Negative `order_pct` uses current position shares; `order_pct(code, -1)` requests a full exit.

Missing or invalid quotes retain the last valid mark and set `Position.price_stale=True`; a fresh quote clears it. Missing data alone never resets the position to cost.
