# Backtest Execution Model

EasyQuant uses an **event-driven** backtest model, consistent with JoinQuant / Zipline. Understanding the execution model helps avoid common pitfalls such as look-ahead bias and memory issues.

---

## Strategy Skeleton

Every strategy consists of **three functions + one global object**:

| Component | When Called | Responsibility |
|-----------|-------------|----------------|
| `initialize(context)` | Once at backtest start | Set benchmark, commissions, register scheduled functions, initialize variables |
| `handle_data(context, data)` | Once per trading day | Read market data, evaluate signals, place orders |
| `market_open(context)` | Registered via `run_daily` | Custom entry point replacing `handle_data` |
| `g` | Persists across trading days | Store strategy variables (e.g., holding days, thresholds) |

## Daily Execution Flow

```text
Each trading day:
  ┌─ before_trading_start(ctx, data)    ← Pre-market callback (optional)
  │
  ├─ run_daily / run_weekly / run_monthly  ← Scheduled functions
  │
  ├─ handle_data(context, data)           ← Daily trading logic
  │
  └─ after_trading_end(ctx, data)         ← Post-market callback (optional)
```

## Key Constraints

| Constraint | Description | Design Intent |
|------------|-------------|---------------|
| **T+1** | Shares bought today can only be sold starting the next trading day | Complies with A-share trading rules; handled automatically by the framework |
| **100-share multiples** | Buy quantities are automatically rounded down to the nearest multiple of 100 | Complies with A-share minimum lot size |
| **Look-ahead bias prevention** | Strategies can only access data up to and including `context.current_dt` | Ensures credible backtest results |
| **Next-day execution** | `order*` calls are enqueued during the current callback and filled at the next trading day's open | Avoids the bias of placing orders at the current day's close |
| **Memory limit** | Default 1024 MB limit, adjustable via `max_memory_mb` | Prevents OOM in large backtests |

## Order Execution Semantics

```python
def market_open(context):
    # 1. Current moment: only places the order, does not fill immediately
    order_value('601390', 50000)

    # 2. Next trading day open: engine matches at the opening price
    #    - Checks available cash
    #    - Rounds to 100-share lots
    #    - Calculates commissions
    #    - Updates positions and cash
```

This means:

- **You cannot read the fill price immediately after placing an order** — the fill price is only available in the next callback
- **Shares bought today cannot be sold today** — `closeable_amount` is only greater than 0 on the T+1 day
- **Strategy signals lead executions by one day** — this is intentional, ensuring conservative and credible backtest results

## The `g` Global Object

`g` is strategy-level persistent storage that survives across trading days. Suitable for storing:

- Strategy parameters (moving average periods, thresholds, etc.)
- State variables (holding days, last signal, etc.)
- Pre-computed stock universes

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0
    g.last_signal = None

def market_open(context):
    g.hold_days += 1  # Persists across days
```

!!! warning "Do not use Python global variables"

    Use `g` instead of Python `global` variables. `g` is managed by the framework, ensuring consistent behavior across backtests and paper trading.
