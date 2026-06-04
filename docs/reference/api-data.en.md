# Data API

> Retrieve historical quotes, real-time data, financial information, A-share specific data, etc.

---

## get_price

Retrieve historical price data.

```python
get_price(security, start_date=None, end_date=None, frequency='daily', fields=None, count=None)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `security` | `str` or `list` | Yes | Stock code |
| `start_date` | `str`/`date` | No | Start date |
| `end_date` | `str`/`date` | No | End date |
| `frequency` | `str` | No | Only `'daily'` is supported |
| `fields` | `list` | No | Specify returned fields |
| `count` | `int` | No | Return the most recent N bars |

Returns a `DataFrame` (single stock) or `dict[str, DataFrame]` (multiple stocks).

## history

Retrieve `count` bars of data looking back from the current backtest time. Only available inside strategy callbacks.

```python
history(count, unit='1d', field='close', security=None, df=False)
```

## attribute_history

Retrieve historical attribute data for a single stock.

```python
attribute_history(security, count, unit='1d', fields=('close',), df=True, skip_paused=True, fq='pre')
```

Returns a `DataFrame` with columns: `open`, `high`, `low`, `close`, `volume`, `money`, `pct_change`, `turnover`.

## get_current_data

Retrieve real-time snapshots for all A-shares. Returns `dict[str, dict]` containing fields such as `code`, `name`, `price`, `pct_change`, `volume`, `pe`, `pb`, `total_value`, etc.

## get_security_info

Retrieve basic information for a single stock. Returns a `SecurityInfo` object (`code`, `name`, `industry`, `total_shares`, `float_shares`, `total_value`, `list_date`).

## get_valuation

Retrieve valuation data. Returns `dict` or `None`.

## scan_market

Scan A-shares with filters.

```python
scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
```

## get_financial_screen

Screen by financial metrics.

```python
get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None, min_roe=None)
```

## get_all_securities

Retrieve a list of all A-shares. Returns a `DataFrame` (code, name).

## get_trade_days

Retrieve the trading calendar. Returns `list[date]`.

## Indices & Industry

| API | Description | Returns |
|-----|-------------|---------|
| `get_index_stocks(index_code)` | Index constituent stocks | `DataFrame` |
| `get_industry_list()` | All industry sectors | `list[str]` |
| `get_industry_stocks(industry_name)` | Stocks in a given industry | `DataFrame` |
| `get_industry(code)` | Industry classification for a single stock | `dict` or `None` |
| `get_index_weights(index_code, date=None)` | Index constituent weights | `DataFrame` |

## Concept Sectors

| API | Description | Returns |
|-----|-------------|---------|
| `get_concept_list()` | All concept sectors | `list[str]` |
| `get_concept_stocks(concept_name)` | Constituent stocks of a concept | `DataFrame` |

## Minute-Level Data

```python
fetch_minute_data(code, period='5m', start_date=None, end_date=None, adjust='qfq')
get_price_minute(security, count=None, period='5m', fields=None, adjust='qfq')
```

Supported periods: `1m`, `5m`, `15m`, `30m`, `60m`.

## Tick Data

```python
get_tick_data(code, trade_date=None)
```

## Money Flow & Billboard

```python
get_money_flow(code, start_date=None, end_date=None, count=None)
get_billboard_list(stock_list=None, date=None, start_date=None, end_date=None)
```

## A-Share Specific Data

### get_north_money_flow

Northbound money flow (Shanghai-Hong Kong Stock Connect + Shenzhen-Hong Kong Stock Connect aggregate).

```python
get_north_money_flow(start_date=None, end_date=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | `str`/`date` | Start date; defaults to 30 days ago |
| `end_date` | `str`/`date` | End date; defaults to today (China timezone) |

Returns a `DataFrame` with the following columns:

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `net_buy` | Net buy amount (100 million yuan) |
| `total_buy` | Total buy amount (100 million yuan) |
| `total_sell` | Total sell amount (100 million yuan) |

```python
from eqlib import get_north_money_flow

# Get northbound flow for the last 3 months
north = get_north_money_flow(start_date="2024-01-01", end_date="2024-03-31")

# Calculate net buy over the last 5 days
recent_5d = north["net_buy"].tail(5).sum()
if recent_5d > 50:
    print("Strong northbound capital inflow")
```

**Note**: Uses China timezone (UTC+8) to determine "today"; cached for 1 hour.

### get_margin_data

Margin trading data (market-wide aggregate).

```python
get_margin_data(start_date=None, end_date=None)
```

Returns a `DataFrame` with the following columns:

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `margin_balance` | Margin balance (100 million yuan) |
| `margin_buy` | Margin buy amount (100 million yuan) |
| `margin_repay` | Margin repayment amount (100 million yuan) — NaN for the first row |
| `short_balance` | Short selling balance (100 million yuan) |

```python
from eqlib import get_margin_data

margin = get_margin_data(start_date="2024-01-01", end_date="2024-03-31")

# Margin balance rate of change
margin["change_pct"] = margin["margin_balance"].diff(5) / margin["margin_balance"].shift(5) * 100
```

**Note**: `margin_repay` is NaN for the first row (no prior balance to compute from). Users can handle this with `dropna()` or `fillna()`.

### get_limit_up_down_stats

Limit up/down statistics (daily count of stocks hitting price limit up / limit down).

```python
get_limit_up_down_stats(start_date=None, end_date=None)
```

Returns a `DataFrame` with the following columns:

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `limit_up_count` | Number of stocks hitting the upper price limit |
| `limit_down_count` | Number of stocks hitting the lower price limit |
| `api_error_count` | Number of failed API calls (for data quality monitoring) |

```python
from eqlib import get_limit_up_down_stats

stats = get_limit_up_down_stats()

# Systemic risk alert
latest_down = stats["limit_down_count"].iloc[-1]
if latest_down > 100:
    print("⚠️ Systemic risk alert")
```

**Note**: The API only supports the most recent 30 trading days; a warning is issued if the requested range exceeds this limit.

### get_restriction_release

Restricted share unlock schedule (list of upcoming unlocks within the next N days).

```python
get_restriction_release(days=30)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `days` | `int` | Number of days to look ahead; defaults to 30 |

Returns a `DataFrame` with the following columns:

| Column | Description |
|--------|-------------|
| `code` | Stock code |
| `name` | Stock name |
| `release_date` | Unlock date |
| `release_amount` | Unlock quantity (10,000 shares) |
| `release_value` | Unlock market value (100 million yuan) |
| `release_pct` | Percentage of pre-unlock float market cap |

```python
from eqlib import get_restriction_release

# Get unlocks for the next 30 days
releases = get_restriction_release(days=30)

# Alert on large unlocks
large = releases[releases["release_value"] > 50]
print(f"Large unlocks: {len(large)} stocks")
```

## Financial Data

```python
get_financial_abstract(code)
```

## Chained Stock Selection API

```python
query(*fields)
get_fundamentals(query_or_code, date=None)
```

Available fields are accessed via the `valuation` namespace: `code`, `market_cap`, `total_value`, `float_value`, `pe`, `pb`, `turnover`, `price`, `pct_change`.

Chained methods: `.filter()`, `.order_by()`, `.limit()`.

```python
q = query(valuation.code, valuation.market_cap, valuation.pe) \
    .filter(valuation.market_cap.between(20, 30), valuation.pe > 0) \
    .order_by(valuation.market_cap.asc()) \
    .limit(5)
df = get_fundamentals(q)
```

## get_current_data_object

Retrieve real-time market snapshots with attribute access. Returns `dict[str, _StockDataObj]`.

## get_extras

Retrieve additional data fields (`'is_st'` or `'net_value'`).

## Universe Management

```python
set_universe(security_list)   # Set the strategy universe
get_universe()                 # Get the current universe
```

## Local Files

| API | Description |
|-----|-------------|
| `download_stock_data(code, start_date, end_date, adjust='qfq', output_dir=None)` | Download daily data as CSV |
| `load_csv(path, index_col='date', parse_dates=True)` | Load data from a local CSV |
| `clear_cache()` | Clear in-memory cache |
| `save_stock_local(security, start_date, end_date)` | Download and save locally |
| `load_stock_local(security, start_date, end_date)` | Load from local storage |
| `has_local_data(security)` | Check if local data exists |
| `list_local_stocks()` | List all local files |
| `remove_local_data(security)` | Delete a single local file |
| `clear_all_local_data()` | Delete all local files |
