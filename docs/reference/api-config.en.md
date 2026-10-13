# Configuration API

> Set benchmark index, trading costs, slippage models, and other backtest parameters.

---

## set_benchmark

Set the backtest benchmark.

```python
set_benchmark('000300.XSHG')   # CSI 300
```

## set_order_cost

Set trading costs.

```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                         open_commission=0.00025, close_commission=0.00025,
                         min_commission=5))
```

### OrderCost

| Parameter | Default | Description |
|-----------|---------|-------------|
| `open_tax` | `0` | Buy-side stamp duty |
| `close_tax` | `None` | Sell-side stamp duty; `None` applies the statutory rate (0.05% on/after 2023-08-28, 0.1% before); an explicit value takes precedence |
| `open_commission` | `0.00025` | Buy-side commission |
| `close_commission` | `0.00025` | Sell-side commission |
| `close_today_commission` | `0` | Intraday sell commission |
| `min_commission` | `5` | Minimum commission (¥) |

## set_option

Set strategy options.

```python
set_option('use_real_price', True)
```

### Available options

| Option | Default | Description |
|--------|---------|-------------|
| `check_price_limit` | `True` | Price-limit fill enforcement (see "Price-limit rules" below). **Flipped from `False` to `True` in 2026-10** |
| `avoid_future_data` | `False` | Strict PIT mode: calling a snapshot API that is not point-in-time safe (e.g. `get_fundamentals`) inside a backtest raises `ValueError` instead of emitting a `FutureWarning` |
| `st_status_map` | `None` | Point-in-time ST status mapping: `{code: bool \| (start, end) \| [(start, end), ...] \| callable(bare_code, date)}`. No network detection in backtests; without it stocks are treated as non-ST (main board ±10%) |
| `delist_gap_days` | `30` | A held position with no bar for more than N trading days is treated as delisted and force-liquidated at the last close (`<= 0` disables) |
| `delisted_position_handling` | `"liquidate"` | Delisting handling; `"keep"` keeps the position valued at its last price |
| `delisted_liquidation_haircut` | `0.0` | Haircut fraction (0–1) applied to delisting liquidation, e.g. `1.0` models a total loss |

### Price-limit rules

With `check_price_limit=True` (default), buy orders opening at the limit-up price and sell orders opening at the limit-down price are cancelled with `Order.cancel_reason` (`"limit-up"` / `"limit-down"`). Limits are board- and date-aware:

| Board | Limit |
|-------|-------|
| Main board (non-ST) | ±10% |
| Main board ST / *ST | ±5% (requires `st_status_map` for point-in-time status) |
| ChiNext (300xxx) | ±10% before 2020-08-24, ±20% after (registration reform) |
| STAR Market (688xxx) | ±20% (since inception) |
| BSE (codes 83/87/43/92) | ±30% |

Limits are computed off the security's **last genuinely traded close** (not updated during suspensions) and rounded to the fen. New-stock limit-free windows are not modelled. Orders on suspension days are cancelled the same day with a recorded reason (`"no price data"` for a missing bar, `"suspended"` for zero volume), never deferred. Positions in delisted stocks are force-liquidated after `delist_gap_days` without bars, recorded as `DELIST_LIQUIDATE` in the trade log.

> **Migration note (breaking)**: previous versions defaulted to no price-limit check (`check_price_limit=False`), so old momentum/limit-up-chasing backtest results were systematically optimistic. To reproduce the old behavior, set `set_option('check_price_limit', False)` explicitly.

## set_slippage

Set the slippage model.

| Class | Description |
|-------|-------------|
| `SlippageModel` | Base class, no price adjustment |
| `FixedSlippage(pct=0.001)` | Fixed percentage slippage |
| `VolumeSlippage(impact=0.05)` | Volume-proportional market impact |

## BacktestSession and get_session

`BacktestSession` encapsulates the mutable state of a single backtest run. Regular strategies do not need to use it; for multi-threaded parallel backtesting, you can create an independent session per thread.
