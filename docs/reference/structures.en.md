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
