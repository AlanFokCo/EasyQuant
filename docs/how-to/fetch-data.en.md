# Fetching Data

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Master all data fetching methods |
    | **Prerequisite** | [Writing a Strategy](write-strategy.md) |

---
## 1. Data Fetching

### 1.1 Historical Daily Data

```python
# Method 1: history()
close = history(20, '1d', 'close', security='601390')

# Method 2: attribute_history (more flexible)
hist = attribute_history('601390', 30, '1d',
                         fields=['open', 'close', 'volume', 'high', 'low'])

# Method 3: get_price (supports specifying a date range)
df = get_price('601390',
               start_date='2024-01-01',
               end_date='2024-06-30',
               fields=['open', 'high', 'low', 'close', 'volume'])
```

### 1.2 Real-Time Quote Snapshot

```python
data = get_current_data()
info = get_security_info('601390')
val = get_valuation('601390')
```

### 1.3 Stock Screening & Scanning

```python
candidates = scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
screened = get_financial_screen(min_pe=5, max_pe=30, min_roe=10)  # ROE ≥ 10% (latest quarterly report)
```

### 1.4 Index & Industry Constituents

```python
constituents = get_index_stocks('000300.XSHG')   # CSI 300 constituents
industries = get_industry_list()                  # all industry sectors
stocks = get_industry_stocks('白酒')              # Baijiu sector constituents
concepts = get_concept_list()                     # all concept sectors
concept_stocks = get_concept_stocks('人工智能')    # AI concept stocks
```

### 1.5 Minute-Level Data

```python
df_5m = fetch_minute_data('601390', period='5m')
# Supported periods: 1m, 5m, 15m, 30m, 60m
```

### 1.6 Tick Data

```python
df_tick = get_tick_data('601390')
```

### 1.7 Capital Flow & Billboard Rankings

```python
flow = get_money_flow('601390', count=30)
billboard = get_billboard_list(date='20241201')
weights = get_index_weights('000300.XSHG')
```

### 1.8 Trading Calendar

```python
days = get_trade_days(start_date='2024-01-01', end_date='2024-12-31')
recent_days = get_trade_days(count=10)
```

### 1.9 Local Data Cache

```python
from eqlib import set_local_data_dir, save_stock_local, has_local_data

set_local_data_dir('/path/to/eqlib_data')

for sec in ['601390', '600519', '000300.XSHG']:
    path = save_stock_local(sec, '2020-01-01', '2024-12-31')

result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390', '600519'],
    use_local=True,
)
```

Tip: confirm `has_local_data(code)` returns `True` before running the backtest; for large-scale backtests, do a smoke test with a shorter date range first.

### 1.10 A-Share Specific Data

eqlib provides several data APIs unique to the A-share market, covering North-bound capital, margin trading, limit up/down statistics, and restricted share unlock schedules.

#### 1.10.1 North-Bound Capital

North-bound capital (Shanghai-Hong Kong Stock Connect + Shenzhen-Hong Kong Stock Connect) is a key barometer of foreign capital inflows into A-shares.

```python
from eqlib import get_north_money_flow

# Get North-bound capital flows (defaults to the last 30 days)
df = get_north_money_flow(start_date='2024-01-01', end_date='2024-06-30')
# Returned fields: date, net_buy, total_buy, total_sell (unit: 100M CNY)

# Use North-bound capital signals in a strategy
def market_open(context):
    north_flow = get_north_money_flow()
    if not north_flow.empty:
        recent_net = north_flow['net_buy'].tail(3).sum()
        if recent_net > 100:  # 3-day net buy exceeds 10B CNY
            log.info("Strong north-bound net inflow: %.1f (100M CNY)" % recent_net)
```

#### 1.10.2 Margin Trading

Margin trading data reflects the movement of leveraged capital. This API returns **market-wide aggregates** (Shanghai + Shenzhen combined) — there is no per-stock granularity.

```python
from eqlib import get_margin_data

# Get market-wide margin data (defaults to the last 30 days)
df = get_margin_data(start_date='2024-01-01', end_date='2024-06-30')
# Returned fields: date, margin_balance, margin_buy, margin_repay, short_balance
# (unit: 100M CNY; margin_repay is derived from balances, first row is NaN)

# Check margin balance changes
if not df.empty:
    if len(df) >= 6:
        change_5d = df['margin_balance'].iloc[-1] - df['margin_balance'].iloc[-6]
    log.info("Margin balance 5-day change: %.1f (100M CNY)" % change_5d)
```

#### 1.10.3 Limit Up/Down Statistics

Counts the number of limit up/down stocks in the market, useful for gauging market sentiment.

```python
from eqlib import get_limit_up_down_stats

# Get limit up/down statistics
df = get_limit_up_down_stats()
# Returned fields: date, limit_up_count, limit_down_count, api_error_count
# The provider keeps only the most recent ~30 trading days

# Assess market sentiment
if not df.empty:
    latest = df.iloc[-1]
    if latest['limit_down_count'] > 100:
        log.warn("Limit-down count above 100 — systemic stress signal")
    elif latest['limit_up_count'] / max(latest['limit_down_count'], 1) > 3:
        log.info("Up/down ratio above 3 — strong sentiment")
```

#### 1.10.4 Restricted Share Unlock

Unlock data helps proactively avoid potential selling pressure.

```python
from eqlib import get_restriction_release

# Get the unlock schedule for the next 30 days (days is the only parameter;
# the window starts from the real today)
df = get_restriction_release(days=30)
# Returned fields: code, name, release_date, release_amount (10K shares),
#                  release_value (100M CNY), release_pct (of pre-unlock float cap)

# Filter large unlocks (release_value is in 100M CNY)
big_releases = df[df['release_value'] > 10]
if not big_releases.empty:
    log.info("Stocks with large unlocks: %s" % big_releases['code'].tolist())
```

The unlock window always starts from the **real today**, and the provider carries no announcement-date history — this is a snapshot API that triggers a `FutureWarning` inside backtests (see §2).

---

## 2. Data Visibility Inside Backtests (PIT)

Inside a backtest session, data APIs are gated by what the simulated clock can see. During decision-time callbacks (`before_trading_start`, scheduled functions, `handle_data`) the visibility boundary is **T-1**; the current day's data becomes visible in post-close callbacks.

| API | Behavior inside backtests |
|-----|---------------------------|
| `history` / `attribute_history` | Read preloaded data — no look-ahead by construction; the preferred choice |
| `get_price` | Only returns bars before the simulated day |
| `fetch_stock_data` / `load_stock_local` | Truncated at T-1; ranges starting past the cutoff return an empty DataFrame |
| `fetch_minute_data` | Only returns bars before the simulated clock |
| `get_money_flow` / `get_billboard_list` / `check_golden_cross` | Truncated at T-1 |
| `get_north_money_flow` / `get_margin_data` / `get_limit_up_down_stats` | Date range clamped at T-1; fully out-of-range requests return an empty DataFrame |
| `get_current_data` / `get_valuation` / `get_extras` | Snapshot APIs: emit `FutureWarning` |
| `get_index_stocks` / `get_industry_stocks` / `get_concept_stocks` / `get_index_weights` | Snapshot APIs (current constituents — survivorship bias): `FutureWarning` |
| `scan_market` / `get_financial_screen` / `get_financial_abstract` | Snapshot APIs: `FutureWarning` |
| `get_restriction_release` / `get_tick_data` | Snapshot APIs: `FutureWarning` |
| `get_fundamentals` | `date` parameter is ignored (no disclosure-date history at the provider): `FutureWarning` |

With `set_option('avoid_future_data', True)`, snapshot APIs escalate the warning to a `ValueError` and the backtest fails fast — enable it for rigorous backtests. Research and live trading are unaffected by these restrictions.

---

See the [Data API Reference](../reference/api-data.md) for full parameter documentation.
