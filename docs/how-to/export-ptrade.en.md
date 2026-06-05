# PTrade/QMT Strategy Adapter

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Understand the differences between local backtesting and QMT live trading, and learn the import and API mapping |
    | **Prerequisite** | Able to run backtests with `eqlib`; see [Paper Trading](paper-trade.md) |

Converts strategies written with EasyQuant (`eqlib`) into a format runnable on **PTrade / QMT** platforms, replacing data sources and order APIs while preserving strategy logic as much as possible.

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [How It Works](#3-how-it-works)
4. [API Comparison](#4-api-comparison)
5. [Usage](#5-usage)
6. [Code Format Conversion](#6-code-format-conversion)
7. [Caveats](#7-caveats)

---

## 1. Overview

### 1.1 What Is the PTrade/QMT Adapter?

EasyQuant's PTrade adapter is a compatibility layer that lets you use the same strategy code for:

- **Local**: `from eqlib import *` + `run_backtest()` for backtesting (data source: akshare)
- **QMT platform**: `from eqlib.ptrade_adapter import *` + `start()` / `on_bar()` for live/paper trading (data source: QMT real-time quotes)

The strategy logic stays exactly the same — only the import statement and entry functions change.

### 1.2 Supported QMT Versions

The adapter is built on the QMT Python API documentation ([QMT_Python_API_Doc](https://qmt.ptradeapi.com/QMT_Python_API_Doc.html)) and is compatible with the Python runtime in the QMT strategy editor.

### 1.3 Core Capabilities

| Capability | Description |
|------------|-------------|
| Lifecycle bridging | EasyQuant `initialize` → QMT `init`, `handle_data` → QMT `handlebar` |
| Code conversion | `601390` → `601390.SH`, `000300.XSHG` → `000300.SH` |
| Data adaptation | `attribute_history` → `ContextInfo.get_market_data` |
| Trading adaptation | `order_value` → QMT `order_value()`, `order_target` → `order_shares` |
| Portfolio simulation | Built-in `Portfolio` / `Position` simulation; can sync with QMT real account state |

---

## 2. Quick Start

### 2.1 Easiest Way: Use the Export Tool

```bash
python examples/12_paper_trade.py
```

Generates `examples/ptrade_strategy_generated.py` (by default generated from `examples/03_run_backtest.py` as a sample). Copy it into the QMT strategy editor to run.

### 2.2 Manual Way: Three-Step Migration

**Step 1: Write an EasyQuant strategy**

```python
# my_strategy.py — for local backtesting
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma:
        order_value(g.security, context.portfolio.available_cash)
    else:
        order_target(g.security, 0)
```

**Step 2: Create a strategy in the QMT strategy editor**

```python
# QMT strategy editor — for live/paper trading
from eqlib.ptrade_adapter import *

# === Paste the strategy code above (without from eqlib import *) ===

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')  # your QMT account
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma:
        order_value(g.security, context.portfolio.available_cash)
    else:
        order_target(g.security, 0)

# === QMT entry functions — fixed pattern ===

def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**Step 3: Run in QMT**

Set up your account → backtest / live trade.

---

## 3. How It Works

### 3.1 Lifecycle Mapping

| EasyQuant | QMT | Description |
|-----------|-----|-------------|
| `initialize(context)` | `init(ContextInfo)` → `start()` | Strategy initialization; runs once |
| `handle_data(context, data)` | `handlebar(ContextInfo)` → `on_bar()` | Runs on every bar |
| `run_daily(func)` | `handlebar` → daily callback | Daily scheduled callback |
| `run_weekly(func)` | `handlebar` → weekly callback | Weekly scheduled callback |
| `run_monthly(func)` | `handlebar` → monthly callback | Monthly scheduled callback |
| `before_trading_start(context)` | New trading day detection | Pre-open callback |
| `after_trading_end(context)` | `is_last_bar()` detection | Post-close callback |

### 3.2 Data Flow

```
EasyQuant API              QMT Native API
─────────────              ──────────────
attribute_history()  ──►   ContextInfo.get_market_data()
get_price()          ──►   ContextInfo.get_market_data_ex()
get_current_data()   ──►   ContextInfo.get_full_tick()
get_universe()       ──►   ContextInfo.get_universe()
set_universe()       ──►   ContextInfo.set_universe()
```

### 3.4 Trading Flow

```
EasyQuant API              QMT Native API
─────────────              ──────────────
order()              ──►   order_shares()
order_value()        ──►   order_value()
order_target()       ──►   order_shares() (with position calc)
order_target_value() ──►   order_target_value()
```

---

## 4. API Comparison

### 4.1 Fully Compatible APIs

These APIs behave identically in QMT and local backtesting:

| API | Parameters | Description |
|-----|------------|-------------|
| `set_benchmark(security)` | `security`: stock code | Set benchmark |
| `set_option(name, value)` | `name`, `value` | Set option |
| `run_daily(func, time)` | `func`, `time` | Daily scheduling |
| `run_weekly(func, day, time)` | `func`, `day_of_week`, `time` | Weekly scheduling |
| `run_monthly(func, day, time)` | `func`, `day_of_month`, `time` | Monthly scheduling |
| `log(msg)` | `msg`: string | Log output |
| `record(**kwargs)` | key-value pairs | Record values |
| `g.*` | any attribute | Global variables |

### 4.2 Adapted APIs

These APIs are mapped to QMT native functions under the hood:

| EasyQuant API | QMT Native | Differences |
|---------------|------------|-------------|
| `attribute_history(sec, count, unit, fields)` | `ContextInfo.get_market_data()` | Returns a unified DataFrame format |
| `history(end_date, count, unit, fields)` | `ContextInfo.get_market_data()` | Same as above |
| `get_price(sec, start_date, end_date)` | `ContextInfo.get_market_data_ex()` | Supports date range queries |
| `order(sec, amount)` | `order_shares()` | Auto-converts code format |
| `order_value(sec, value)` | `order_value()` | Positive = buy, negative = sell; auto-converts code |
| `order_target(sec, target_amount)` | `order_shares()` | Calculates position delta then places order |
| `order_target_value(sec, target_value)` | `order_target_value()` | Direct mapping |
| `get_current_data()` | `ContextInfo.get_full_tick()` | Returns dict with EQ-format codes as keys |
| `get_index_stocks(index)` | `ContextInfo.get_sector()` | Returns list of EQ-format codes |
| `set_universe(securities)` | `ContextInfo.set_universe()` | Auto-converts code format |
| `get_universe()` | `ContextInfo.get_universe()` | Returns list of EQ-format codes |

### 4.3 New APIs (QMT Mode Only)

These APIs are only available in the QMT adapter:

| API | Description |
|-----|-------------|
| `set_account(account_id)` | Set the QMT trading account |
| `start(ContextInfo)` | Call inside QMT's `init()` to start the EasyQuant strategy |
| `on_bar(ContextInfo)` | Call inside QMT's `handlebar()` to drive strategy logic |
| `export_ptrade_script(file, output)` | Export tool: generates a QMT strategy file |
| `QMT_TEMPLATE` | QMT strategy template string |
| `@initialize` | Decorator: registers the initialization function |
| `@handle_data` | Decorator: registers the handle_data function |

### 4.4 Unsupported APIs

These EasyQuant APIs are **not supported** in QMT; use QMT native functions instead:

| EasyQuant API | Alternative |
|---------------|-------------|
| `fetch_stock_data()` | QMT built-in historical data |
| `download_stock_data()` | Not needed; QMT already has local data |
| `load_csv()` | Use pandas to read directly |
| `scan_market()` | Use QMT's `get_stock_list_in_sector()` |
| `run_backtest()` | Use the QMT UI to run backtests |
| `run_portfolio_backtest()` | Use the QMT UI to run backtests |
| `generate_chart()` | QMT built-in charts |
| `get_financial_abstract()` | QMT's `get_financial_data()` |
| `get_fundamentals()` | QMT's `get_factor_data()` |

---

## 5. Usage

### 5.1 Method 1: Paste Directly into the QMT Editor

Best for simple strategies. Paste the entire strategy code (including `init` / `handlebar`) into the QMT strategy editor.

```python
from eqlib.ptrade_adapter import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty:
        return
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif price < ma20 * 0.98:
        order_target(g.security, 0)

def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

### 5.2 Method 2: Decorator Style

```python
from eqlib.ptrade_adapter import *

g = {}

@initialize
def my_init(context):
    g['security'] = '601390'
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open)

@handle_data
def my_handler(context, data):
    sec = g['security']
    hist = attribute_history(sec, 20, '1d', ['close'])
    # ... strategy logic ...

# QMT entry functions
def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

### 5.3 Method 3: Use the Export Tool

Best for existing complete EasyQuant strategy files.

```bash
# You can modify strategy_file / output_file in 12_paper_trade.py
python examples/12_paper_trade.py
# Output: examples/ptrade_strategy_generated.py → copy to QMT
```

---

## 6. Code Format Conversion

### 6.1 Stock Code Conversion Rules

The adapter automatically handles the following conversions:

| EasyQuant Format | QMT Format | Rule |
|-----------------|------------|------|
| `601390` | `601390.SH` | Starts with 6 → Shanghai |
| `000001` | `000001.SZ` | Starts with 0 → Shenzhen |
| `300001` | `300001.SZ` | Starts with 3 → Shenzhen (ChiNext) |
| `688001` | `688001.SH` | Starts with 68 → Shanghai (STAR Market) |
| `000300.XSHG` | `000300.SH` | .XSHG → .SH |
| `000001.XSHE` | `000001.SZ` | .XSHE → .SZ |
| `601390.SH` | `601390.SH` | Already in QMT format → no change |

### 6.2 Account Setup

Trading in QMT requires setting an account:

```python
def initialize(context):
    set_account('6000000248')  # your QMT fund account
```

Or set it in the QMT entry function:

```python
def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)
```

### 6.3 Order Types

| EasyQuant | QMT Equivalent | Description |
|-----------|----------------|-------------|
| `order_value(sec, 10000)` | `order_value(sec.SH, 10000)` | Buy 10,000 yuan worth |
| `order_value(sec, -10000)` | `order_value(sec.SH, -10000)` | Sell 10,000 yuan worth |
| `order_target(sec, 0)` | `order_shares(sec.SH, -position_qty)` | Liquidate position |
| `order(sec, 100)` | `order_shares(sec.SH, 100)` | Buy 100 shares |

---

## 7. Caveats

### 7.1 Backtest Mode Differences

- **EasyQuant local backtest**: Uses akshare data with full report/chart generation
- **QMT backtest mode**: Uses QMT local data; trading functions execute via a virtual account and mark buy/sell points on the chart
- **QMT live mode**: Uses real-time quotes; trading functions generate actual orders

### 7.2 Data Type Differences

- EasyQuant's `attribute_history` returns a `pandas.DataFrame` with a date index
- QMT's `get_market_data` return format depends on parameters; the adapter converts everything to a unified DataFrame

### 7.3 Trading Function Limitations

- In QMT backtest mode, `cancel`, `can_cancel_order`, `do_order`, etc. have no effect
- In QMT paper trading mode, trading functions are inactive (requires live or backtest mode)
- EasyQuant local backtest uses "signal today, fill at next day's open"; QMT follows the platform's matching rules (typically immediate matching upon order placement)

### 7.4 Stock Universe

- EasyQuant uses `context.universe` or `set_universe()` to manage the stock universe
- QMT uses `ContextInfo.set_universe()` to set and `ContextInfo.get_universe()` to get
- The adapter automatically synchronizes both

### 7.5 Global Variables

- EasyQuant uses attribute access like `g.security`
- In the QMT adapter, `g` is a dictionary that also supports attribute access: `g.security` or `g['security']`

### 7.6 Slippage and Commission

- EasyQuant local backtest configures via `set_order_cost()`
- QMT backtest configures via `ContextInfo.set_commission()` / `ContextInfo.set_slippage()`
- QMT live trading uses the broker's actual fee schedule

### 7.7 Direct ContextInfo Access

The adapter exposes the underlying QMT ContextInfo object via `context._qmt`, allowing access to QMT-specific APIs when needed:

```python
def market_open(context):
    # EasyQuant API
    hist = attribute_history('601390', 20, '1d', ['close'])

    # QMT native API (when needed)
    ci = context._qmt
    barpos = ci.barpos  # current bar index
    period = ci.period  # current period, e.g. '1d'
```

---

## Appendix: Complete Migration Example

Below is a complete moving-average strategy migrated from EasyQuant to QMT.

### EasyQuant Original Code (Local Backtest)

```python
from eqlib import *

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    close_data = attribute_history(g.security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return

    ma_fast = close_data['close'].tail(g.fast_period).mean()
    ma_slow = close_data['close'].mean()
    current_price = close_data['close'].iloc[-1]

    if current_price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s' % g.security)
    elif current_price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s' % g.security)

# Run backtest
result = run_backtest(initialize, '2024-01-01', '2024-12-31',
                      starting_cash=100000, benchmark='000300.XSHG')
```

### QMT Version (Live / Paper Trading)

```python
from eqlib.ptrade_adapter import *

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')
    run_daily(market_open, time='every_bar')

def market_open(context):
    close_data = attribute_history(g.security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return

    ma_fast = close_data['close'].tail(g.fast_period).mean()
    ma_slow = close_data['close'].mean()
    current_price = close_data['close'].iloc[-1]

    if current_price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s' % g.security)
    elif current_price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s' % g.security)

# QMT entry functions
def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**Only three differences**:
1. `from eqlib import *` → `from eqlib.ptrade_adapter import *`
2. Added `set_account('YOUR_ACCOUNT_ID')`
3. Added `init()` / `handlebar()` entry functions

The strategy logic remains completely unchanged.
