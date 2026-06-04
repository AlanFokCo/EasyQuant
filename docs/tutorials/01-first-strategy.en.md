# Tutorial 01: Writing Your First Strategy

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Build a dual moving average strategy by hand; understand `initialize` / `run_daily` / `order_*` and the `g` object |
    | **Estimated time** | ~45 minutes |
    | **Prerequisites** | [Tutorial 00: Environment & Quant Basics](00-getting-started.md) |

> Build and run your first quantitative trading strategy from scratch using EasyQuant.

---

## Table of Contents

1. [Preparation](#1-preparation)
2. [Strategy Design: Dual Moving Average](#2-strategy-design-dual-moving-average)
3. [Writing the Strategy Code](#3-writing-the-strategy-code)
4. [Running the Backtest](#4-running-the-backtest)
5. [Understanding the Strategy Framework Step by Step](#5-understanding-the-strategy-framework-step-by-step)
6. [Extensions: Adding More Conditions](#6-extensions-adding-more-conditions)
7. [Next Steps](#7-next-steps)

---

## 1. Preparation

### 1.1 Installing eqlib

**Requires Python 3.10 or later.**

```bash
# Option 1: Install from PyPI (recommended, no repo clone needed)
pip install easyquant-eqlib

# Option 2: Install from source (in the repo root)
# cd EasyQuant
# pip install .   # or: pip install -e .
```

If `eqlib` is not installed correctly, `import eqlib` will fail. For more detailed instructions and troubleshooting, see [Tutorial 00](00-getting-started.md) and the [FAQ](../project/faq.md).

### 1.2 Verifying the Installation

```python
from eqlib import *
print("eqlib OK")
```

If you see `eqlib OK`, the installation was successful.

### 1.3 Creating a Strategy File

Create a Python file, for example `my_first_strategy.py`:

```bash
touch my_first_strategy.py
```

---

## 2. Strategy Design: Dual Moving Average

Let's implement a classic **dual moving average strategy**:

### Strategy Rules

- **Buy signal**: The 5-day moving average crosses above the 20-day moving average (golden cross), and the current price is above the 5-day moving average
- **Sell signal**: The 5-day moving average crosses below the 20-day moving average (death cross)
- **Position management**: Use all available cash when buying; liquidate everything when selling
- **Target security**: 601390 (ICBC — Industrial and Commercial Bank of China)
- **Backtest period**: 2024-01-01 to 2024-12-31

### Why Dual Moving Average?

- Simple logic, easy to understand
- No complex data or calculations required
- Serves as the "Hello World" for learning the framework
- Easy to extend and modify

---

## 3. Writing the Strategy Code

Write the following code in `my_first_strategy.py`:

```python
from eqlib import *

# ========== Module-level constants (won't be cleared by the engine) ==========
SECURITY = '601390'       # Target security
FAST_PERIOD = 5           # Short-term moving average period
SLOW_PERIOD = 20          # Long-term moving average period


# ========== Initialization function ==========
def initialize(context):
    """Called once when the strategy starts."""
    # Set the benchmark for comparison
    set_benchmark('000300.XSHG')

    # Set trading costs (standard A-share fee schedule)
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,          # Stamp duty 0.05% (halved since Aug 2023)
        open_commission=0.00025,   # Buy commission 0.025%
        close_commission=0.00025,  # Sell commission 0.025%
        min_commission=5,          # Minimum commission 5 CNY
    ))

    # Run once per trading day
    run_daily(market_open, time='every_bar')

    log.info('Dual MA strategy initialized: %s, MA%d/MA%d' % (
        SECURITY, FAST_PERIOD, SLOW_PERIOD))


# ========== Daily trading logic ==========
def market_open(context):
    """Runs on every trading day."""
    security = SECURITY

    # 1. Get the last 25 days of closing prices (fetch a few extra to ensure MA20 can be computed)
    close_data = attribute_history(security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < SLOW_PERIOD:
        return  # Insufficient data, skip

    close_prices = close_data['close']

    # 2. Compute moving averages
    ma_fast = close_prices.tail(FAST_PERIOD).mean()
    ma_slow = close_prices.mean()
    current_price = close_prices.iloc[-1]

    # 3. Check buy condition: golden cross + price above fast MA
    if current_price > ma_fast > ma_slow:
        # Check that we don't already hold a position
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f, MA_fast=%.3f, MA_slow=%.3f' % (
                security, current_price, ma_fast, ma_slow))

    # 4. Check sell condition: death cross
    elif current_price < ma_fast < ma_slow:
        # Check that we currently hold a position
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount > 0:
            order_target(security, 0)  # Liquidate
            log.info('SELL %s @ %.3f, MA_fast=%.3f, MA_slow=%.3f' % (
                security, current_price, ma_fast, ma_slow))

    # 5. Record current state (will appear in the report)
    record(
        price=current_price,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        cash=context.portfolio.available_cash,
    )


# ========== Run the backtest ==========
if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2024-01-01',
        end_date='2024-12-31',
        starting_cash=100000,       # 100,000 CNY
        benchmark='000300.XSHG',
        securities=['601390'],      # Preload data to speed up backtest
        report_dir='reports',
    )
```

### Code Structure Overview

```
Import library
  |
  v
Module-level constants  <-- Configuration (not cleared by engine)
  |
  v
initialize()            <-- Called once: set benchmark, fees, scheduling
  |
  v
market_open()           <-- Called every trading day: fetch data -> compute signals -> place orders
  |
  v
run_strategy()          <-- Run the backtest and generate reports
```

---

## 4. Running the Backtest

```bash
python my_first_strategy.py
```

After running, you'll see output like:

```
[2024-01-02] Dual MA strategy initialized: 601390, MA5/MA20
[2024-01-15] BUY 601390 @ 4.850, MA_fast=4.820, MA_slow=4.780
[2024-03-20] SELL 601390 @ 5.120, MA_fast=5.080, MA_slow=5.110
...

==================================================
Final value: 108,234.56
P&L: +8,234.56 (+8.23%)
Trades: 12

Chart:  reports/backtest_20260503_143000.png
HTML:   reports/backtest_20260503_143000.html
Report: reports/backtest_20260503_143000.md
Data:   reports/backtest_20260503_143000.json
```

### Viewing the Reports

- **Chart** (PNG): Price curve with buy/sell point annotations
- **HTML report**: Interactive full results; see [Report Format Guide](../reference/reports-format.md) for **how to read each section**
- **Markdown report**: Text summary
- **JSON data**: Structured data for further analysis

---

## 5. Understanding the Strategy Framework Step by Step

### 5.1 The `g` Global Object

`g` is persistent storage that survives across trading days. **Important: The backtest engine clears all attributes of `g` before calling `initialize`**, so you must not assign configuration values to `g` at the module top level.

**Correct usage:**

```python
# Module-level constants -- configuration parameters (not cleared by the engine)
SECURITY = '601390'
MA_PERIOD = 20

# g -- runtime state (initialized in initialize(), persists across trading days)
def initialize(context):
    g.hold_days = 0       # Initialized inside initialize()
    g.max_loss_pct = 0.08

def market_open(context):
    g.hold_days += 1
    if g.hold_days > 30:
        order_target(SECURITY, 0)  # Use module-level constant
```

**Incorrect usage (top-level `g` assignments will be cleared by the engine):**

```python
# WRONG! These values will be cleared before initialize() runs
g.security = '601390'
g.ma_period = 20
```

### 5.2 The `context` Object

`context` contains the current runtime state of the backtest:

```python
def market_open(context):
    # Portfolio information
    context.portfolio.starting_cash     # Initial capital
    context.portfolio.available_cash    # Available cash
    context.portfolio.total_value       # Total assets (cash + position market value)
    context.portfolio.returns           # Total return

    # Positions
    context.portfolio.positions         # Dict {security: Position}
    # Position has these attributes:
    #   .security          Stock code
    #   .amount            Shares held
    #   .avg_cost          Average cost per share
    #   .closeable_amount  Shares available to sell (T+1 settlement restriction)

    # Backtest parameters
    context.current_dt               # Current date
    context.start_date               # Backtest start date
    context.end_date                 # Backtest end date
    context.benchmark                # Benchmark code
```

### 5.3 Scheduling Functions

```python
# Run daily (most common)
run_daily(market_open, time='every_bar')

# Run weekly (e.g., every Monday)
run_weekly(rebalance, day_of_week=1, time='every_bar')

# Run monthly (e.g., 1st of each month)
run_monthly(rebalance, day_of_month=1, time='every_bar')
```

### 5.4 Data Retrieval

```python
# Method 1: attribute_history (most commonly used in strategies)
# Get the last N bars of data
hist = attribute_history('601390', 20, '1d', ['close'])

# Method 2: history (concise syntax)
close = history(20, '1d', 'close', security='601390')

# Method 3: get_price (specify date range, suitable for use in initialize())
df = get_price('601390', start_date='2024-01-01', end_date='2024-06-30')
```

### 5.5 Trading API

```python
# Buy/sell by share count (positive = buy, negative = sell)
order('601390', 1000)        # Buy 1,000 shares

# Buy/sell by amount
order_value('601390', 50000)  # Buy 50,000 CNY worth

# Adjust to a target share count
order_target('601390', 5000)  # Adjust to 5,000 shares
order_target('601390', 0)     # Liquidate

# Adjust to a target market value
order_target_value('601390', 100000)  # Position market value = 100,000 CNY
```

### 5.6 Logging and Recording

```python
# Log output (appears in console and log files)
log.info('BUY %s @ %.2f' % (security, price))
log.warn('Insufficient data, skipping')

# Record values (will appear in the JSON report)
record(price=price, ma5=ma5, signal='BUY')
```

---

## 6. Extensions: Adding More Conditions

The dual moving average strategy is just a starting point. Below, we progressively add conditions to make the strategy more robust.

### 6.1 Adding a Stop-Loss

```python
def market_open(context):
    security = SECURITY

    # ... fetch data, compute moving averages ...

    # Stop-loss check
    if security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        loss_pct = (current_price - position.avg_cost) / position.avg_cost
        if loss_pct < -0.08:  # Loss exceeds 8%
            order_target(security, 0)
            log.info('Stop-loss SELL %s @ %.3f, loss %.2f%%' % (
                security, current_price, loss_pct * 100))
            return

    # ... original golden cross / death cross logic ...
```

### 6.2 Adding Volume Filtering

```python
# Fetch closing price and volume data
close_data = attribute_history(security, 25, '1d', ['close', 'volume'])

# Volume must be above the 20-day average (avoid illiquid stocks)
avg_volume = close_data['volume'].tail(20).mean()
current_volume = close_data['volume'].iloc[-1]

if current_volume < avg_volume * 0.5:
    return  # Insufficient volume, skip
```

### 6.3 Adding a Market Filter

```python
# If the CSI 300 index is below its 20-day moving average, don't go long
index_hist = attribute_history('000300.XSHG', 20, '1d', ['close'])
index_ma20 = index_hist['close'].mean()
index_price = index_hist['close'].iloc[-1]

if index_price < index_ma20:
    return  # Market is weak, don't go long
```

### 6.4 Extending to Multi-Stock Rotation

```python
SECURITIES = ['601390', '600519', '000858']

def market_open(context):
    for security in SECURITIES:
        # Apply the same logic to each stock
        hist = attribute_history(security, 25, '1d', ['close'])
        # ... signal detection ...
```

See the full multi-stock version at [examples/02_write_strategy.py](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/02_write_strategy.py).

---

## 7. Next Steps

You've learned how to write and run your first strategy. What's next:

- **[Tutorial 02: Backtest Validation](02-backtesting.md)** — Deep dive into backtest results, interpreting reports, and determining whether a strategy is effective
- **[Tutorial 03: Strategy Optimization & Improvement](03-optimization.md)** — Parameter tuning, portfolio optimization, attribution analysis
- **[Tutorial 04: Paper Trading to Live Trading](04-live-trading.md)** — Real-time market validation and PTrade/QMT live deployment
- **[Tutorial 05: RSI Mean Reversion Strategy](05-rsi-mean-reversion.md)** — Learn another classic strategy type: mean reversion

### Exercises

1. Change the moving average periods (e.g., MA10/MA30) and observe how the results change
2. Add a stop-loss to the strategy (e.g., force sell at -8%)
3. Backtest with a different stock
4. Try changing `order_value(..., available_cash)` to `order_value(..., available_cash * 0.5)` for half-position trading
