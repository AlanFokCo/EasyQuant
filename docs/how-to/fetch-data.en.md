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
screened = get_financial_screen(min_pe=5, max_pe=30, min_roe=0.1)
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

# Get North-bound capital net inflow data (last N trading days)
df = get_north_money_flow(count=30)
# Returned fields: date, buy_value, sell_value, net_inflow, total_inflow

# Use North-bound capital signals in a strategy
def market_open(context):
    north_flow = get_north_money_flow(count=5)
    if not north_flow.empty:
        recent_net = north_flow['net_inflow'].iloc[-1]
        if recent_net > 1e9:  # net inflow exceeds 1 billion
            log.info("North-bound capital large net inflow today: %.2f billion" % (recent_net / 1e8))
```

#### 1.10.2 Margin Trading

Margin trading data reflects the movement of leveraged capital.

```python
from eqlib import get_margin_trading

# Get margin trading data for a stock
df = get_margin_trading('601390', count=30)
# Returned fields: date, margin_buy, margin_sell, margin_repay, margin_balance, etc.

# Check margin balance changes
if not df.empty:
    balance_change = df['margin_balance'].diff()
    log.info("Margin balance 5-day change: %s" % balance_change.tail(5).tolist())
```

#### 1.10.3 Limit Up/Down Statistics

Counts the number of limit up/down stocks in the market, useful for gauging market sentiment.

```python
from eqlib import get_limit_up_down_stats

# Get limit up/down statistics
df = get_limit_up_down_stats()
# Returned fields: date, limit_up_count, limit_down_count, limit_up_ratio, etc.

# Assess market sentiment
if not df.empty:
    latest = df.iloc[-1]
    if latest['limit_up_count'] > 100:
        log.info("Market sentiment is strong, limit-up count: %d" % latest['limit_up_count'])
```

#### 1.10.4 Restricted Share Unlock

Unlock data helps proactively avoid potential selling pressure.

```python
from eqlib import get_restriction_release

# Get the unlock schedule for the next 30 days
df = get_restriction_release(start_date='2024-01-01', end_date='2024-01-31')
# Returned fields: code, name, release_date, release_value, release_amount, etc.

# Filter large unlocks
big_releases = df[df['release_value'] > 1e9]  # unlock market value exceeds 1 billion
if not big_releases.empty:
    log.info("Stocks with large unlocks: %s" % big_releases['code'].tolist())
```

---

See the [Data API Reference](../reference/api-data.md) for full parameter documentation.
