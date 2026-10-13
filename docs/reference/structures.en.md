# Strategy Lifecycle Structures

> Core data structures automatically passed by the framework during strategy execution.

---

## Context

Strategy execution context, automatically passed by the framework during callbacks.

| Attribute | Type | Description |
|-----------|------|-------------|
| `current_dt` | `datetime` | Current simulation time |
| `start_date` | `date` | Backtest start date |
| `end_date` | `date` | Backtest end date |
| `frequency` | `str` | `'daily'` or `'minute'` |
| `portfolio` | `Portfolio` | Portfolio object |
| `universe` | `list[str]` | Current strategy stock universe |
| `run_params` | `dict` | Backtest parameter dictionary |

## Portfolio

Portfolio state, accessed via `context.portfolio`.

| Attribute | Description | User Input |
|-----------|-------------|------------|
| `starting_cash` | Initial capital | Set by `starting_cash` parameter |
| `available_cash` | Available cash | Automatically maintained by framework |
| `positions` | Position dictionary, keyed by stock code | Automatically maintained by framework |
| `total_value` | Total assets = cash + position market value | Automatically calculated by framework |
| `returns` | Total return | Read-only |

## Position

Individual stock position, accessed via `context.portfolio.positions[code]`.

| Attribute | Description | User Input |
|-----------|-------------|------------|
| `security` | Stock code | Automatically set by framework |
| `amount` | Position amount (shares) | Automatically maintained by framework |
| `closeable_amount` | Amount available to sell today (T+1 restriction) | Automatically maintained by framework |
| `avg_cost` | Average cost | Automatically calculated by framework |
| `total_value` | Position market value | Automatically calculated by framework |
| `price` | Current price | Read-only |
| `price_stale` | `bool`: `True` when the latest quote is missing/invalid and valuation carries the last valid price; a fresh quote resets it to `False` | Automatically maintained by framework |

## Order

A single order, returned by `order()` and the other order functions.

| Attribute | Type | Description |
|-----------|------|-------------|
| `order_id` | `str` | Unique order ID (auto-generated) |
| `security` | `str` | Stock code |
| `amount` | `int` | Requested shares (always positive; direction is `side`) |
| `side` | `str` | `"buy"` / `"sell"` (may be `None` for target orders until first match) |
| `style` | — | `MarketOrder()` or `LimitOrder(price)` |
| `status` | `str` | Order status (see below) |
| `filled_amount` | `int` | Filled shares |
| `avg_cost` | `float` | Average fill price |
| `commission` | `float` | Commission paid |
| `datetime` | `datetime` | Creation time |
| `submit_time` | `datetime \| None` | Submission time |
| `fill_time` | `datetime \| None` | Fill time |
| `reject_reason` | `str \| None` | Rejection reason (set when status is `rejected`) |
| `cancel_reason` | `str \| None` | Cancellation/expiry reason (set when status is `cancelled` / `expired`; values in the table below) |

Methods: `is_complete()` (`True` only when `filled`); `remaining_amount()` (unfilled shares; returns `None` for value/target orders until matching first resolves the quantity).

### Order Status

`pending` → `submitted` → (optionally via `partial_fill`) → `filled`; other terminal states: `rejected`, `cancelled`, `expired`.

### cancel_reason Values

| Value | Meaning |
|-------|---------|
| `"limit-up"` / `"limit-down"` | Buy hit limit-up / sell hit limit-down, unfillable |
| `"suspended"` | Suspended (bar exists but zero volume) |
| `"zero volume"` | Zero volume that day; the slippage model cannot price the trade |
| `"no bar data"` | No bar data for that day |
| `"no open price"` | Value/target order missing the open price needed to size shares |
| `"no price data"` | Market data missing |
| `"sub-lot"` | Quantity rounds down below 100 shares |
| `"insufficient cash"` | Not enough available cash |
| `"no position"` | Sell order without a closeable position |
| `"no position change needed"` | Target holdings equal current holdings |
| `"unknown action"` | Unknown order action |
| `"delisted"` | Forced liquidation on delisting |
| `"timeout"` | Order expired (status `expired`) |

## g — GlobalObject

Strategy-level global object for storing custom variables across trading days.

```python
from eqlib import g

def initialize(context):
    g.security = '601390'
    g.ma_period = 20

def market_open(context):
    hist = attribute_history(g.security, g.ma_period, '1d', ['close'])
```

!!! warning "Important: run_backtest clears ``g`` on startup"
    `run_backtest` (and `run_strategy`) **clears the `g` object** on every call. Therefore:

    - **Do not** set `g.xxx` before calling `run_backtest` — those values are wiped when the backtest starts.
    - **Do** set `g.xxx` inside `initialize(context)`, so the values are written as the backtest begins.
    - For configuration shared outside the backtest (constants, parameters), use module-level Python variables instead of `g`.

    ```python
    # ❌ Wrong: run_backtest clears g.universe
    g.universe = ['601398', '600519']
    run_backtest(initialize, ...)

    # ✅ Correct: set inside initialize
    def initialize(context):
        g.universe = ['601398', '600519']
    ```
