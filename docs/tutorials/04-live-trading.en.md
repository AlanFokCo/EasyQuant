# Tutorial 04: Paper Trading to Live Trading

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Understand the differences and deployment steps from backtest → paper trading → QMT/PTrade live trading |
    | **Estimated time** | ~60 minutes |
    | **Prerequisites** | [Tutorial 00](00-getting-started.md); for export, see [PTrade/QMT Export Guide](../how-to/export-ptrade.md) |

> After passing the backtest, validate the strategy with real-time market data, then export to PTrade/QMT for live deployment.

**Export adaptation:** [PTrade/QMT Export Guide](../how-to/export-ptrade.md)

---

## Table of Contents

1. [Workflow from Backtest to Live](#1-workflow-from-backtest-to-live)
2. [Paper Trading](#2-paper-trading)
3. [Exporting to PTrade/QMT](#3-exporting-to-ptradeqmt)
4. [Live Trading Considerations](#4-live-trading-considerations)
   - [4.6 Portfolio Risk Monitoring Recommendations](#46-portfolio-risk-monitoring-recommendations)
5. [FAQ](#5-faq)
6. [Complete Example](#6-complete-example)

---

## 1. Workflow from Backtest to Live

```
Backtest validation (historical data)
    ↓  Pass
Paper trading (real-time data, virtual capital)
    ↓  Pass
PTrade/QMT simulated run (real trading interface, virtual environment)
    ↓  Pass
PTrade/QMT live trading (real capital)
```

Each step has a different objective:
- **Backtest**: Verify that the strategy logic is correct and assess historical performance
- **Paper trading**: Verify that the real-time data stream is stable and signals are timely
- **PTrade/QMT simulation**: Verify that the trading interface works properly and orders/fills match expectations
- **Live trading**: The ultimate validation — real money at stake

---

## 2. Paper Trading

### 2.1 Basic Usage

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return

    price = hist['close'].iloc[-1]
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f' % (g.security, price))
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
            log.info('SELL %s @ %.3f' % (g.security, price))

# Start paper trading, refresh every 60 seconds
run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,  # Polling interval (seconds)
)
```

### 2.2 Paper Trading Output

```
[09:30:00] total_value=100,000.00  PnL=+0.00 (+0.00%)
[09:31:00] total_value=100,000.00  PnL=+0.00 (+0.00%)
[09:32:00] BUY 601390 @ 5.230
[09:32:00] total_value=100,234.56  PnL=+234.56 (+0.23%)
...
```

### 2.3 Differences Between Paper Trading and Backtesting

| | Backtest | Paper Trading |
|--|---------|---------------|
| Data source | akshare historical data | akshare real-time quotes |
| Speed | Seconds to complete a year | Runs continuously, updates in real time |
| Trading | Orders queued, filled at next trading day's open | Simulated fills (using real-time prices) |
| Purpose | Validate strategy logic | Validate real-time data flow and signal timeliness |

### 2.4 Paper Trading Notes

- Run during trading hours to receive real-time quotes
- Use `Ctrl+C` to stop
- Paper trading does not generate real orders and does not actually buy or sell stocks
- Recommend running for at least 1-2 weeks to observe whether signals are reasonable

---

## 3. Exporting to PTrade/QMT

After paper trading validation, you can export the strategy to the PTrade/QMT platform for live trading.

### 3.1 Using the Export Tool

```bash
python examples/12_paper_trade.py
```

This generates `examples/ptrade_strategy_generated.py` (by default using `examples/03_run_backtest.py` as the sample strategy).

### 3.2 Custom Strategy Export

In `examples/12_paper_trade.py`'s `if __name__ == '__main__':` block, change the `strategy_file` parameter in `export_ptrade_script(strategy_file=...)` to your own strategy `.py` path (must contain `initialize(context)`). You can also call it directly:

```python
from eqlib.ptrade_adapter import export_ptrade_script

export_ptrade_script(
    strategy_file="/path/to/my_strategy.py",
    output_file="/path/to/ptrade_strategy_generated.py",
)
```

### 3.3 Manual Migration Steps

**Step 1**: Create a new strategy file in the QMT strategy editor.

**Step 2**: Write the following content:

```python
from eqlib.ptrade_adapter import *

# === Global variables ===
g.security = '601390'
g.fast_period = 5
g.slow_period = 20

# === Initialization function (identical to backtest) ===
def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')  # Your QMT account
    run_daily(market_open, time='every_bar')

# === Strategy logic (identical to backtest) ===
def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < g.slow_period:
        return

    price = hist['close'].iloc[-1]
    ma_fast = hist['close'].tail(g.fast_period).mean()
    ma_slow = hist['close'].mean()

    if price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f' % (g.security, price))
    elif price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s @ %.3f' % (g.security, price))

# === QMT entry functions (fixed pattern) ===
def init(ContextInfo):
    set_account('6000000248')  # Your QMT account
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**Step 3**: Set up your account in QMT → Run backtest or live trading.

### 3.4 Migration Differences Summary

From EasyQuant backtest to PTrade/QMT live trading, there are only 3 differences:

| # | Difference | Backtest | PTrade/QMT |
|---|-----------|----------|-----------|
| 1 | Import statement | `from eqlib import *` | `from eqlib.ptrade_adapter import *` |
| 2 | Account setup | `run_strategy(starting_cash=...)` | `set_account('your_QMT_account')` |
| 3 | Entry function | `run_strategy(initialize, ...)` | `def init(ContextInfo): start(ContextInfo)` |

The strategy logic itself remains **completely unchanged**.

### 3.5 Automatic Code Conversion

The adapter automatically handles the following, so you don't need to change them manually:

- **Stock codes**: `601390` → `601390.SH`
- **Index codes**: `000300.XSHG` → `000300.SH`
- **Trading functions**: `order_value()` → QMT native `order_value()`
- **Data functions**: `attribute_history()` → QMT native `get_market_data()`

---

## 4. Live Trading Considerations

### 4.1 Backtest Mode vs Live Mode

| | Backtest Mode | Live Mode |
|--|--------------|-----------|
| Data | QMT local historical data | Real-time quotes |
| Trading | Virtual account, generates buy/sell signals | Real orders, actual fills |
| Slippage | None | Yes (broker's actual execution price may differ) |
| Commissions | Simulated at configured rate | Broker's actual fee schedule |

### 4.2 Capital Management

- Start live trading with a **small position size** (e.g., 10%-20% of total capital)
- Observe for 1-2 weeks to confirm that strategy behavior matches the backtest
- Gradually increase position size — don't go all-in at once

### 4.3 Risk Control Recommendations

```python
# Recommended risk controls for live trading

# 1. Maximum position limit per stock
def market_open(context):
    max_position_pct = 0.30  # No single stock exceeds 30%
    max_value = context.portfolio.total_value * max_position_pct
    buy_value = min(context.portfolio.available_cash, max_value)
    order_value(g.security, buy_value)

# 2. Portfolio maximum drawdown limit
    if context.portfolio.returns < -0.15:  # Total loss exceeds 15%
        # Liquidate all positions
        for sec in list(context.portfolio.positions.keys()):
            order_target(sec, 0)
        log.warn('Max drawdown triggered, liquidating all positions')
        return

# 3. Daily maximum trade count limit
    g.daily_trades = getattr(g, 'daily_trades', 0)
    if g.daily_trades >= 5:  # Maximum 5 trades per day
        return
```

### 4.4 Logging

Logging is critical in live trading. It's recommended to record key operations:

```python
def market_open(context):
    log.info('Current total assets: %.2f, Available cash: %.2f, Return: %.2f%%' % (
        context.portfolio.total_value,
        context.portfolio.available_cash,
        context.portfolio.returns * 100,
    ))

    # Log every buy and sell
    if signal_buy:
        order_value(security, buy_value)
        log.info('BUY %s, amount=%d, price=%.3f' % (security, amount, price))
```

### 4.5 Monitoring

- Regularly check logs to confirm the strategy is running normally
- Monitor whether buy/sell points match expectations
- Compare actual returns with backtest expectations; if the deviation is too large, investigate the cause

### 4.6 Portfolio Risk Monitoring Recommendations

When running multi-strategy portfolios live, it is recommended to use `PortfolioRiskMonitor` for daily risk inspections. It automatically calculates portfolio VaR, strategy correlations, position concentration, and other metrics, and triggers YELLOW / RED / KILL_SWITCH three-tier alerts based on thresholds, helping you intervene before risk spirals out of control.

Adjust the key parameters in `RiskThresholds` according to your risk tolerance. Conservative investors can lower `max_drawdown_red` to 0.15 and `single_stock_max` to 0.05; aggressive investors can relax them somewhat, but it is not recommended to exceed 1.5x the default values.

```python
from eqlib import *

# Customize thresholds based on risk preference
thresholds = RiskThresholds(
    max_drawdown_yellow=0.12,
    max_drawdown_red=0.18,
    max_drawdown_kill=0.25,
    single_stock_max=0.10,
)
monitor = PortfolioRiskMonitor(thresholds=thresholds)

def market_open(context):
    # ... strategy signal logic ...

    # Daily risk inspection (recommended at the end of strategy logic)
    report = monitor.daily_check()
    if report.triggers:
        log.warn('Risk alert: %s' % '; '.join(report.triggers))
    for action in check_kill_switch(report):
        log.error(action)  # Circuit breaker actions require immediate attention
```

`check_kill_switch()` returns a circuit breaker action list (e.g., pause strategy, force position reduction) when the report level reaches KILL_SWITCH. In live trading, it is recommended to connect this list to a notification channel (e.g., DingTalk / Feishu webhook) to ensure circuit breaker signals are received immediately, avoiding larger losses due to delayed human response in extreme market conditions.

---

## 5. FAQ

### Q: Paper trading results don't match backtest results?

Possible causes:
- Backtest uses closing prices; paper trading uses real-time prices (may have slippage)
- Market environment differs between the backtest period and the paper trading period
- Paper trading hasn't run long enough, insufficient signals

### Q: QMT reports `ModuleNotFoundError: No module named 'eqlib'`?

Ensure `eqlib` is accessible in the QMT environment:
- Copy the `eqlib` directory into QMT's Python path
- Or add the following at the top of your QMT strategy code:
  ```python
  import sys
  sys.path.insert(0, '/path/to/your/EasyQuant')
  ```

### Q: Live trades are not being filled?

Possible causes:
- Price too far from market price (e.g., limit up/down)
- Insufficient liquidity, trading volume too low
- Account not set up or not authorized
- Outside trading hours (not within 9:30-11:30 or 13:00-15:00)

### Q: How to run multiple strategies simultaneously?

Each strategy needs its own independent strategy file in QMT, with separate account and stock universe configurations.

### Q: How to sync real positions from PTrade/QMT?

The adapter includes a built-in `Portfolio.update_from_qmt()` method that automatically syncs the real QMT account state at the start of each bar. See the [PTrade/QMT Export Guide](../how-to/export-ptrade.md) for details.

---

## 6. Complete Example

Below is the complete workflow from backtest to live trading:

### 6.1 Local Backtest

```python
# ma_strategy.py -- for local backtesting
from eqlib import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)

result = run_strategy(
    initialize, '2024-01-01', '2024-12-31',
    starting_cash=100000, securities=['601390'],
)
```

### 6.2 Paper Trading Validation

```python
# Same file, switch to paper trading
# python ma_strategy.py --paper-trade

import sys

if '--paper-trade' in sys.argv:
    run_paper_trade(
        initialize,
        starting_cash=100000,
        benchmark='000300.XSHG',
        interval=60,
    )
else:
    result = run_strategy(
        initialize, '2024-01-01', '2024-12-31',
        starting_cash=100000, securities=['601390'],
    )
```

### 6.3 QMT Live Trading

```python
# ma_strategy_ptrade.py -- runs in the QMT strategy editor
from eqlib.ptrade_adapter import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)

def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

---

## Congratulations

You have completed the full workflow from strategy concept to live deployment!

### Further Learning

- **[Tutorial 05: RSI Mean Reversion Strategy](../tutorials/05-rsi-mean-reversion.md)** — Learn a mean reversion strategy approach that is fundamentally different from trend following
- **[Tutorial 06: Sector Rotation Strategy](../tutorials/06-sector-rotation.md)** — Build an alpha strategy using A-share sector rotation dynamics
- **[Tutorial 07: Multi-Factor Stock Selection](../tutorials/07-multi-factor.md)** — Systematic quantitative stock selection methods
- [PTrade/QMT Export Guide](../how-to/export-ptrade.md) — Adapter API reference
- [API Reference](../reference/index.md) — Complete API listing
- [Utility Library Reference](../reference/utils.md) — Technical indicators, statistical tools, position sizing
- [Example Code](../examples/index.md) — 20 ready-to-run examples
- **[Example 20: Support/Resistance Portfolio Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** — A complete multi-stock portfolio strategy case study with pre-generated backtest reports
