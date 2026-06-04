# Backtest & Paper Trading Engine

> Backtest execution, paper trading, scheduling functions and lifecycle callbacks.

---

## run_strategy

All-in-one backtest + report generation.

```python
run_strategy(initialize_func, start_date, end_date, starting_cash=100000,
             benchmark='000300.XSHG', handle_data=None, securities=None,
             report_dir='reports', use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

Returns the backtest result as a `dict`.

## run_backtest

Run a backtest (without generating a report).

```python
run_backtest(initialize_func, start_date, end_date, starting_cash=100000.0,
             frequency='daily', benchmark='000300.XSHG', securities=None,
             use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

Returns `{"context": Context, "trade_log": list, "recorded_values": dict, "benchmark": str}`.

## run_portfolio_backtest

High-level backtest interface for multi-stock portfolios.

```python
run_portfolio_backtest(config, strategy_func, report_dir='reports')
```

### StrategyConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `securities` | `list[str]` | Required | Stock universe |
| `start_date` | `str`/`date` | Required | Start date |
| `end_date` | `str`/`date` | Required | End date |
| `starting_cash` | `float` | `100000` | Initial capital |
| `benchmark` | `str` | `"000300.XSHG"` | Benchmark index |
| `position_pct` | `float` | `0.33` | Maximum position size per stock |
| `position_amount` | `int` | `0` | Fixed share count per buy |
| `report_suffix` | `str` | `""` | Report filename suffix |
| `frequency` | `str` | `"daily"` | `"daily"` or `"minute"` |

## estimate_memory_mb

Estimate the memory footprint of preloaded data. Returns a `dict` (`panel_mb`, `close_dict_mb`, `bar_cache_mb`, `total_mb`).

## run_paper_trade

Paper trading session; runs continuously until terminated with `Ctrl+C`.

```python
run_paper_trade(initialize_func, starting_cash=100000.0, benchmark='000300.XSHG', interval=60)
```

## record

Record custom data points within a strategy.

```python
record(price=current_price, ma5=ma5, signal='BUY')
```

## Scheduling Functions

| API | Description |
|-----|-------------|
| `run_daily(func, time='every_bar')` | Execute daily at a fixed time |
| `run_weekly(func, day_of_week=1, time='09:30')` | Execute weekly on a given day |
| `run_monthly(func, day_of_month=1, time='09:30')` | Execute monthly on a given day |
| `run_selection(func, rebalance='monthly:1')` | Register a stock selection function and run it on a schedule |

`rebalance` format: `"monthly:N"` (Nth day of each month), `"weekly:N"` (day of week, 0=Monday), `"daily"` (every trading day).

## Lifecycle Callbacks

| API | Description |
|-----|-------------|
| `before_trading_start(func)` | Register a pre-market callback |
| `after_trading_end(func)` | Register a post-market callback |

---

## Cache API

| API | Description |
|-----|-------------|
| `set_cache_dir(path)` | Set the disk cache directory |
| `fetch_cached(security, start_date, end_date, adjust='qfq')` | Retrieve data with cache-first priority |

Data source integration recommendation: keep API input/output signatures unchanged, persist data in a unified format before entering the backtest, and use primary-standby data source switching with cross-validation.

---

## Logging API

### Basic Logging

```python
log.info(msg)
log.debug(msg)
log.warn(msg)
log.error(msg)
```

### Structured Logging

| API | Description |
|-----|-------------|
| `log.section(title, **fields)` | Mark a high-level stage |
| `log.step(name, status='RUN', **fields)` | Record a step status |
| `log.progress(current, total, label='Progress')` | Display progress |
| `log.action(name, target=None, **fields)` | Record an action |
| `log.set_level(level)` | Control verbosity |
| `log.set_quiet(enabled=True)` | Output only WARNING/ERROR |

---

## Utility API

| API | Description |
|-----|-------------|
| `engine.get_context()` | Get the current backtest context |
| `engine.get_g()` | Get the global object |
| `engine.get_trade_log()` | Get the trade log |
| `engine.get_recorded_values()` | Get values recorded by record() |

---

## Web Studio API Endpoints

### `GET /api/v1/runs/{run_id}/report/data`

Returns the complete backtest report as JSON (including all chart data arrays), used for native Lightweight Charts rendering in the Web Studio.

```bash
curl http://localhost:8081/api/v1/runs/<run_id>/report/data
```

The response structure matches the JSON output of `generate_report_json()` and includes all fields: `summary`, `risk_metrics`, `cumulative_returns`, `candlestick_data`, `volume_data`, `ma5/20/60_data`, `rsi_data`, `macd_data`, `bb_upper/middle/lower_data`, `drawdown_data`, `pnl_bar_data`, `daily_returns_data`, etc.

---

## Parameterization & Optimization Conventions

The `eqlib` API works with any Python workflow (scripts, notebooks, scheduled tasks). A typical call chain: `run_backtest()` → `analyze_returns()` → `brinson_attribution()` → analyze results → modify parameters → re-run backtest.

Strategy files define `PARAMS` (current values) and `PARAM_RANGES` (search space), which are read and updated by the optimization script. After each change, verify that: new parameters fall within range, cross-parameter constraints are satisfied, and no look-ahead bias is introduced.
