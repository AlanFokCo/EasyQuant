# Stock Selection Framework

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Periodically refresh the stock pool with selectors and drive portfolio rebalancing |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Stock Selection Framework

Stock selection has two parts:

- **Selectors**: `filter()` removes unqualified stocks; `rank()` sorts and picks the top N.
- **Scheduling**: `run_strategy(..., selection_func=..., selection_rebalance=...)` controls how often the selection function runs. The returned list is written to `context.universe`, and the strategy rebalances against it.

### 1.1 TopNSelector: Single-Factor Ranking

Ranks by one factor column and takes the top N. `factor` is a column name (string) returned by `fetch_factor_data`, not a function.

```python
from eqlib import TopNSelector

# 5 stocks with the lowest PE (ascending=True = lowest first)
sel = TopNSelector(factor="pe", top_n=5, ascending=True)
selected = sel.rank(context.universe, context)

# 3 stocks with the highest daily change (descending, highest first)
sel = TopNSelector(factor="pct_change", top_n=3, ascending=False)
selected = sel.rank(context.universe, context)
```

Signature: `TopNSelector(factor: str = "pe", top_n: int = 5, ascending: bool = True)`.

Available `factor` columns:

| Column | Meaning | Usable in backtests |
|--------|---------|---------------------|
| `pct_change` | Daily price change | Yes |
| `turnover` | Turnover rate | Yes |
| `ma5` / `ma10` / `ma20` | Moving averages | Yes |
| `rsi14` | RSI(14) | Yes |
| `price` / `open` / `high` / `low` / `close` / `volume` / `money` | Quote fields | Yes |
| `pe` / `pb` / `total_value` | Valuation fields | No — always NaN in backtests (see §1.6) |

### 1.2 MultiFactorSelector: Multi-Factor Weighting

Z-score normalizes each factor column, sums them with weights into a composite score, and takes the top N. A negative weight means "lower is better".

```python
from eqlib import MultiFactorSelector

selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},  # default when omitted
    top_n=5,
)
selected = selector.rank(context.universe, context)
```

Signature: `MultiFactorSelector(factors: Optional[dict] = None, top_n: int = 5)`.

`factors` only accepts a `{built-in factor column: weight}` mapping — custom factor functions are not supported. To compute your own factors, see §1.5.

### 1.3 Rebalance Scheduling

Two registration styles — pick one:

```python
# Style 1: run_strategy arguments
result = run_strategy(
    initialize,
    start_date="2024-01-01",
    end_date="2024-12-31",
    selection_func=my_selection,
    selection_rebalance="monthly:1",
)

# Style 2: declare inside initialize
def initialize(context):
    run_selection(my_selection, rebalance="weekly:0")
```

`selection_rebalance` formats:

| Format | Meaning |
|--------|---------|
| `"monthly:N"` | First trading day of the month with `day >= N` (N in 1-31) |
| `"weekly:N"` | Nth weekday of each week (0=Monday, 4=Friday) |
| `"daily"` | Every trading day |

The selection function signature is fixed: `def my_selection(context) -> list[str]`, returning a list of security codes. The engine calls it before the day's callbacks on rebalance days and replaces `context.universe` with the returned list, so later callbacks on the same day see the new list. If it returns an empty list, the universe stays unchanged silently; if it raises, the universe stays unchanged and the engine logs a warning.

### 1.4 Filters

```python
from eqlib import (
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
)

candidates = filter_st_stocks(context.universe)                # remove ST/*ST
candidates = filter_paused_stocks(candidates, context)         # remove suspended
candidates = filter_low_price_stocks(candidates, 2.0, context) # remove < 2 CNY
```

Each filter behaves differently in backtests — read this before use:

- `filter_paused_stocks` and `filter_low_price_stocks` filter with preloaded data at `context.current_dt` — no look-ahead bias.
- `filter_st_stocks` uses the ST list as of the **real today** (akshare snapshot), not the historical date. Calling it in a backtest emits a `UserWarning` and introduces survivorship bias: stocks that were ST then but have since recovered are wrongly kept, and vice versa.
- `filter_high_pe_stocks` has no historical PE in backtests — it returns all candidates unchanged and logs a warning, i.e. it does not filter at all.

### 1.5 Custom Factors: Subclass StockSelector

Built-in selectors only work with the columns `fetch_factor_data` provides. To compute your own factor (e.g. 20-day momentum), subclass `StockSelector` and implement `rank()`:

```python
from eqlib import StockSelector, attribute_history

class MomentumSelector(StockSelector):
    """20-day momentum: top N by interval return."""

    def __init__(self, top_n: int = 3, lookback: int = 20):
        self.top_n = top_n
        self.lookback = lookback

    def rank(self, securities, context):
        momentum = {}
        for sec in securities:
            hist = attribute_history(sec, self.lookback + 1, "1d", ["close"])
            if hist is None or len(hist) < self.lookback + 1:
                continue
            close = hist["close"]
            momentum[sec] = close.iloc[-1] / close.iloc[0] - 1
        ranked = sorted(momentum, key=momentum.get, reverse=True)
        return ranked[: self.top_n]
```

`filter()` returns candidates unchanged by default; `rank()` returns the input order by default. Override whichever you need.

### 1.6 Valuation Factors Are Unavailable in Backtests

In backtest mode `fetch_factor_data` returns `pe`, `pb`, and `total_value` as NaN — there is no point-in-time source for historical valuation snapshots, so NaN is the no-look-ahead choice. Consequences:

- `TopNSelector(factor="pe")` drops every row in a backtest, so `rank()` returns an empty list and `context.universe` stays unchanged.
- `get_valuation(code)` returns the key `pe` (plus `pb`, `total_value`, `float_value`, `turnover`, `pct_change`), but inside a backtest it serves the **real current** snapshot and triggers a `FutureWarning`; with `set_option('avoid_future_data', True)` it raises `ValueError`.

There is no clean data source for valuation-based selection in backtests. Pragmatic options: use price-derived factors (`pct_change`, `turnover`, moving averages, RSI), or write your own `rank()` per §1.5 that computes factors from historical prices.

### 1.7 Complete Example

On the first trading day of each month, pick the 3 stocks in the pool with the highest daily change and hold them equal-weight until next month:

```python
from eqlib import (
    run_strategy, set_benchmark, set_order_cost, set_slippage,
    run_daily, order_target, order_target_value,
    TopNSelector, filter_paused_stocks, g,
)
from examples._defaults import DEFAULT_ORDER_COST, DEFAULT_SLIPPAGE

STOCK_POOL = ["601398", "601318", "600519", "002594", "000725", "600276"]


def initialize(context):
    set_benchmark("000300.XSHG")
    set_order_cost(DEFAULT_ORDER_COST)
    set_slippage(DEFAULT_SLIPPAGE)
    context.universe = STOCK_POOL
    g.held_universe = None
    run_daily(rebalance, time="every_bar")


def my_selection(context):
    active = filter_paused_stocks(context.universe, context)
    sel = TopNSelector(factor="pct_change", top_n=3, ascending=False)
    return sel.rank(active, context)


def rebalance(context):
    # Do nothing if the list has not changed
    if context.universe == g.held_universe:
        return
    g.held_universe = list(context.universe)

    for sec in list(context.portfolio.positions):
        if sec.split(".")[0] not in {s.split(".")[0] for s in context.universe}:
            order_target(sec, 0)
    if not context.universe:
        return
    target = context.portfolio.total_value / len(context.universe)
    for sec in context.universe:
        order_target_value(sec, target)


result = run_strategy(
    initialize,
    start_date="2024-01-01",
    end_date="2024-12-31",
    securities=STOCK_POOL,
    selection_func=my_selection,
    selection_rebalance="monthly:1",
)
```

Orders fill at the next day's open (T→T+1), so the list seen on a selection day becomes positions the next day.

---

See the [Selection API Reference](../reference/api-selection.md) for full parameter documentation.
