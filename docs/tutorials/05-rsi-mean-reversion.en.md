# Tutorial 05: RSI Mean Reversion Strategy

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | From RSI principles to complete strategy code, risk controls, and improvement ideas |
    | **Estimated time** | ~90 minutes |
    | **Prerequisites** | [Tutorial 01](01-first-strategy.md), [Tutorial 02](02-backtesting.md) |

> Mean reversion is one of the most classic quantitative strategy concepts. This tutorial systematically covers how to design, backtest, and improve an RSI mean reversion strategy, starting from the RSI indicator itself.

**Related example:** [`examples/15_bollinger_strategy.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py), etc. (see [`Examples.md`](../examples/index.md))

---

## Table of Contents

1. [The Core Idea of Mean Reversion](#1-the-core-idea-of-mean-reversion)
2. [RSI Indicator Deep Dive](#2-rsi-indicator-deep-dive)
3. [Strategy Design](#3-strategy-design)
4. [Writing the Strategy Code](#4-writing-the-strategy-code)
5. [Adding Risk Controls](#5-adding-risk-controls)
6. [Extending to Multi-Stock Version](#6-extending-to-multi-stock-version)
7. [Limitations of Mean Reversion Strategies](#7-limitations-of-mean-reversion-strategies)
8. [Comparison with Bollinger Bands Strategy](#8comparisonwithbollingerbandsstrategy)
9. [Next Steps](#9-next-steps)

---

## 1. The Core Idea of Mean Reversion

**Mean Reversion** is based on the assumption that: after an asset's price deviates from its historical average, it tends to revert back toward that average.

```
Price movement:
           Overbought ─────────────── Sell
              │
────── Mean ───────────────────────── Mean
              │
           Oversold ───────────────── Buy
```

### Comparison with Trend-Following Strategies

| | Trend Following | Mean Reversion |
|--|----------------|----------------|
| **Core assumption** | Once a trend forms, it will continue | Price deviations from the mean will revert |
| **Buy timing** | Breakouts, golden crosses | Price oversold / at a bottom |
| **Sell timing** | Reversals, death crosses | Price overbought / at a top |
| **Suitable market** | Clearly trending bull/bear markets | Range-bound, sideways markets |
| **Risk** | Repeatedly whipsawed in sideways markets | Keeps buying into declines during trends, unable to hold |

**Which to choose?** This is the core challenge of quantitative trading — no single strategy works in all market conditions. In practice, traders typically use **market regime detection** to switch modes, or **run both strategies in parallel as a hedge** against each other.

### Applicability to the A-Share Market

The A-share market is dominated by retail investors, with widespread emotional trading. Stock prices frequently exhibit "short-term overshooting" — rising or falling far beyond their true value. This characteristic makes mean reversion strategies particularly well-suited to the A-share market, especially:
- **Large-cap blue chips** (banks, insurance, consumer): Relatively stable volatility, suitable for mean reversion
- **Range-bound markets**: When the broad market has no clear trend, mean reversion outperforms trend following

---

## 2. RSI Indicator Deep Dive

**RSI (Relative Strength Index)** measures the ratio of upward price momentum to downward price momentum over a given period.

### 2.1 Calculation Formula

```
Daily change Δ = Today's close - Yesterday's close

Average gain on up days AvgGain = EMA(max(Δ, 0), N)
Average loss on down days AvgLoss = EMA(max(-Δ, 0), N)

RS = AvgGain / AvgLoss

RSI = 100 - 100 / (1 + RS)
```

### 2.2 Interpreting Values

| RSI Range | Meaning | Strategy Implication |
|-----------|---------|---------------------|
| 70 ~ 100 | Overbought zone | Upward momentum too strong, possible pullback → **Consider selling** |
| 50 ~ 70 | Strong zone | Bulls have the upper hand |
| 30 ~ 50 | Weak zone | Bears have the upper hand |
| 0 ~ 30 | Oversold zone | Downward momentum too strong, possible rebound → **Consider buying** |

### 2.3 Calculating RSI in EasyQuant

```python
from eqlib import attribute_history
from eqlib import utils

# Get historical closing prices (at least N + 10 bars for stable calculation)
hist = attribute_history('601390', 30, '1d', ['close'])
close_prices = hist['close']

# Calculate 14-day RSI
rsi14 = utils.rsi(close_prices, period=14)

print("Latest RSI:", rsi14.iloc[-1])   # e.g., 28.3 (oversold zone)
```

---

## 3. Strategy Design

### Strategy Rules

| Condition | Action |
|-----------|--------|
| RSI < 30 (oversold) + no current position | **Buy**, using all available cash |
| RSI > 70 (overbought) + currently holding a position | **Sell**, liquidate |
| RSI between 30 ~ 70 | No action |

### Parameter Design

```python
RSI_PERIOD     = 14    # RSI calculation period (standard is 14 days)
RSI_OVERSOLD   = 30    # Oversold threshold (triggers buy)
RSI_OVERBOUGHT = 70    # Overbought threshold (triggers sell)
```

---

## 4. Writing the Strategy Code

```python
from eqlib import *
from eqlib import utils

# ========== Strategy parameters (module-level constants, not cleared by engine) ==========
SECURITY       = '601390'   # Target: ICBC
RSI_PERIOD     = 14         # RSI calculation period
RSI_OVERSOLD   = 30         # Oversold threshold
RSI_OVERBOUGHT = 70         # Overbought threshold
BARS_NEEDED    = 40         # Number of historical bars needed (RSI requires sufficient warm-up data)


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')
    log.info('RSI mean reversion strategy initialized: %s, RSI%d, oversold=%d, overbought=%d' % (
        SECURITY, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT))


def market_open(context):
    security = SECURITY

    # 1. Fetch historical data
    hist = attribute_history(security, BARS_NEEDED, '1d', ['close'])
    if hist.empty or len(hist) < RSI_PERIOD + 10:
        return

    close_prices = hist['close']
    current_price = close_prices.iloc[-1]

    # 2. Calculate RSI
    rsi_series = utils.rsi(close_prices, RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]

    # 3. Oversold zone: RSI below threshold -> buy
    if current_rsi < RSI_OVERSOLD:
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f, RSI=%.1f (oversold)' % (
                security, current_price, current_rsi))

    # 4. Overbought zone: RSI above threshold -> sell
    elif current_rsi > RSI_OVERBOUGHT:
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info('SELL %s @ %.3f, RSI=%.1f (overbought)' % (
                security, current_price, current_rsi))

    # 5. Record state (appears in the JSON report)
    record(
        price=current_price,
        rsi=current_rsi,
        cash=context.portfolio.available_cash,
    )


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=100000,
        benchmark='000300.XSHG',
        securities=['601390'],
        report_dir='reports',
    )
```

---

## 5. Adding Risk Controls

The basic strategy only has overbought/oversold signals. In practice, risk controls are essential.

### 5.1 Fixed Stop-Loss

```python
def market_open(context):
    security = SECURITY

    # === Stop-loss first (executed before signal detection) ===
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            hist_check = attribute_history(security, 2, '1d', ['close'])
            price_now = hist_check['close'].iloc[-1]
            loss_pct = (price_now - pos.avg_cost) / pos.avg_cost
            if loss_pct < -0.08:   # Loss exceeds 8%, stop-loss exit
                order_target(security, 0)
                log.info('Stop-loss %s @ %.3f, loss %.1f%%' % (
                    security, price_now, loss_pct * 100))
                return

    # === Original RSI signal ===
    # ... (same as the code above)
```

### 5.2 Market Filter (Avoid Bottom-Fishing During Downtrends)

```python
def market_open(context):
    # Market filter: CSI 300 below 20-day MA -> don't go long
    index_hist = attribute_history('000300.XSHG', 25, '1d', ['close'])
    if not index_hist.empty:
        index_ma20 = index_hist['close'].mean()
        index_price = index_hist['close'].iloc[-1]
        if index_price < index_ma20:
            # Weak market: only allow selling, no buying
            # (stop-loss check still executes)
            pass  # return before the buy logic

    # ... RSI signal logic ...
```

### 5.3 RSI Bottom Confirmation (Avoid "Catching a Falling Knife")

```python
# Don't just require RSI < 30; also require RSI to have started recovering from a lower point (bottom confirmation)
rsi_prev = rsi_series.iloc[-2]   # Previous day's RSI

# RSI was below 30 and is now starting to recover -> more reliable buy signal
if current_rsi < g.rsi_oversold and current_rsi > rsi_prev:
    # Bottom confirmed: RSI recovering from oversold
    order_value(security, context.portfolio.available_cash)
```

### 5.4 Volume Confirmation

```python
# Oversold + shrinking volume -> may signal the end of selling pressure
hist = attribute_history(security, g.bars_needed, '1d', ['close', 'volume'])
close_prices = hist['close']
volumes = hist['volume']

avg_vol = volumes.tail(20).mean()
current_vol = volumes.iloc[-1]

# Buy condition: RSI oversold + volume below average (selling pressure has weakened)
if current_rsi < g.rsi_oversold and current_vol < avg_vol * 0.8:
    order_value(security, context.portfolio.available_cash)
```

### 5.5 Complete Version with Risk Controls

```python
from eqlib import *
from eqlib import utils

# Module-level constants (not cleared by engine)
SECURITY       = '601390'
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
STOP_LOSS_PCT  = 0.08    # 8% stop-loss
BARS_NEEDED    = 40


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')


def market_open(context):
    security = SECURITY
    hist = attribute_history(security, BARS_NEEDED, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < RSI_PERIOD + 10:
        return

    close_prices = hist['close']
    volumes = hist['volume']
    current_price = close_prices.iloc[-1]

    rsi_series = utils.rsi(close_prices, RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]
    prev_rsi    = rsi_series.iloc[-2]

    avg_vol     = volumes.tail(20).mean()
    current_vol = volumes.iloc[-1]

    # --- Market filter ---
    idx_hist = attribute_history('000300.XSHG', 25, '1d', ['close'])
    market_bullish = True
    if not idx_hist.empty:
        idx_ma20 = idx_hist['close'].mean()
        idx_price = idx_hist['close'].iloc[-1]
        market_bullish = idx_price > idx_ma20

    # --- Stop-loss ---
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        if pos.amount > 0:
            loss_pct = (current_price - pos.avg_cost) / pos.avg_cost
            if loss_pct < -STOP_LOSS_PCT:
                order_target(security, 0)
                log.info('Stop-loss %s @ %.3f, loss %.1f%%' % (
                    security, current_price, loss_pct * 100))
                record(price=current_price, rsi=current_rsi, signal='STOP')
                return

    # --- Buy: oversold + bottom recovery + market not too weak + volume shrinking ---
    in_position = security in context.portfolio.positions and \
                  context.portfolio.positions[security].amount > 0

    if (current_rsi < RSI_OVERSOLD and
            current_rsi > prev_rsi and        # RSI starting to recover
            market_bullish and
            current_vol < avg_vol * 1.2 and   # Not heavy-volume decline
            not in_position):
        order_value(security, context.portfolio.available_cash)
        log.info('BUY %s @ %.3f, RSI=%.1f->%.1f' % (
            security, current_price, prev_rsi, current_rsi))
        record(price=current_price, rsi=current_rsi, signal='BUY')

    # --- Sell: overbought ---
    elif current_rsi > RSI_OVERBOUGHT and in_position:
        order_target(security, 0)
        log.info('SELL %s @ %.3f, RSI=%.1f (overbought)' % (
            security, current_price, current_rsi))
        record(price=current_price, rsi=current_rsi, signal='SELL')

    else:
        record(price=current_price, rsi=current_rsi, signal='HOLD')


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=100000,
        benchmark='000300.XSHG',
        securities=['601390'],
        report_dir='reports',
    )
```

---

## 6. Extending to Multi-Stock Version

A single-stock RSI strategy is limited by that stock's price movement. Extending the strategy to multiple stocks can increase signal frequency and diversify risk.

### 6.1 Candidate Pool Design Principles

- **Choose stocks with good liquidity**: Average daily turnover > 50 million CNY, to avoid large orders failing to fill
- **Avoid heavy concentration in one sector**: Don't pick only bank stocks, otherwise correlation is too high and diversification is lost
- **Exclude ST (Special Treatment) stocks**: ST stock prices behave abnormally, causing the mean reversion model to fail

### 6.2 Multi-Stock RSI Rotation

```python
from eqlib import *
from eqlib import utils

g.securities = [
    '601390',  # ICBC (Banking)
    '600519',  # Kweichow Moutai (Consumer)
    '000858',  # Wuliangye (Consumer)
    '600036',  # China Merchants Bank (Banking)
    '601318',  # Ping An Insurance (Insurance)
    '000333',  # Midea Group (Home Appliances)
    '600887',  # Yili Group (Consumer)
    '000651',  # Gree Electric (Home Appliances)
]

g.rsi_period     = 14
g.rsi_oversold   = 30
g.rsi_overbought = 70
g.position_pct   = 0.25   # Each stock uses at most 25% of available cash


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')


def market_open(context):
    for security in g.securities:
        hist = attribute_history(security, 40, '1d', ['close'])
        if hist.empty or len(hist) < g.rsi_period + 10:
            continue

        close_prices = hist['close']
        current_price = close_prices.iloc[-1]
        rsi_series = utils.rsi(close_prices, g.rsi_period)
        current_rsi = rsi_series.iloc[-1]

        in_position = security in context.portfolio.positions and \
                      context.portfolio.positions[security].amount > 0

        # Buy
        if current_rsi < g.rsi_oversold and not in_position:
            buy_value = context.portfolio.available_cash * g.position_pct
            if buy_value > 1000:  # Skip if amount is too small
                order_value(security, buy_value)
                log.info('BUY %s @ %.3f, RSI=%.1f' % (
                    security, current_price, current_rsi))

        # Sell
        elif current_rsi > g.rsi_overbought and in_position:
            order_target(security, 0)
            log.info('SELL %s @ %.3f, RSI=%.1f' % (
                security, current_price, current_rsi))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2023-01-01',
        end_date='2024-12-31',
        starting_cash=200000,
        benchmark='000300.XSHG',
        securities=g.securities,
        report_dir='reports',
    )
```

---

## 7. Limitations of Mean Reversion Strategies

### 7.1 Fails in Strong Trending Markets

```
            Mean reversion strategy's "nightmare": one-sided decline
Price
  |       <- RSI < 30, buy
  |------/\
  |     /  \            <- RSI < 30, buy again (buying deeper and deeper)
  |          \------/\
  |                  \        <- Still buying...
  |                   \------
  +-----------------------------> Time
```

**Countermeasure**: Add a market filter + fixed stop-loss to exit promptly when a trend develops.

### 7.2 RSI Thresholds Are Not Absolute Standards

- Buying at RSI = 28, price may continue to fall until RSI = 15 before rebounding
- Selling at RSI = 72, price may continue to rise until RSI = 85 before pulling back
- **Solution**: Combine with Bollinger Bands, support/resistance levels, or other indicators for secondary confirmation

### 7.3 Different Stocks Suit Different Parameters

- High-volatility stocks (tech, new energy): Can use more extreme thresholds (oversold 20, overbought 80)
- Low-volatility stocks (banks, utilities): Standard thresholds (30/70) are usually sufficient

---

## 8. Comparison with Bollinger Bands Strategy { #8comparisonwithbollingerbandsstrategy }

RSI mean reversion and Bollinger Bands mean reversion are both common mean reversion strategies, but each has its focus:

| | RSI Mean Reversion | Bollinger Bands Mean Reversion |
|--|--------------------|-------------------------------|
| **Signal source** | Relative strength of price changes (momentum) | Standard deviation of price deviation from the moving average |
| **Parameters** | RSI period, overbought/oversold thresholds | Bollinger period, standard deviation multiplier |
| **Signal characteristics** | Focuses more on **short-term up/down momentum** | Focuses more on **current price position relative to history** |
| **False signals** | Oversold/overbought triggers frequently during strong trends | Price can stay outside the bands for a long time during trend breakouts |
| **Related example** | This tutorial | [Example 15](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) |

### 8.1 Combined Usage

Using both together is often more reliable than using either alone:

```python
from eqlib import utils

# Only buy when both conditions are met
hist = attribute_history(security, 40, '1d', ['close'])
close_prices = hist['close']

rsi_val = utils.rsi(close_prices, 14).iloc[-1]
upper, mid, lower = utils.boll(close_prices, 20, 2.0)
current_price = close_prices.iloc[-1]

# RSI oversold + price touching Bollinger lower band -> dual confirmation
if rsi_val < 30 and current_price <= lower.iloc[-1]:
    order_value(security, context.portfolio.available_cash)
```

---

## 9. Next Steps

After mastering the RSI mean reversion strategy, you can continue learning:

- **[Tutorial 06: Sector Rotation Strategy](06-sector-rotation.md)** — Leverage A-share sector rotation dynamics to earn alpha through sector switching
- **[Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md)** — Combine momentum, value, and quality factors for systematic stock selection
- **[Tutorial 03: Strategy Optimization & Improvement](03-optimization.md)** — Parameter tuning, avoiding overfitting, attribution analysis
- **[Example 15: Bollinger Bands Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py)** — Complete code for another classic mean reversion strategy

### Exercises

1. Change `g.rsi_oversold = 25` and observe the impact on trading frequency and returns
2. Change the market filter threshold from MA20 to MA60 (longer-term trend judgment) and observe the effect
3. Compare backtest results with and without a stop-loss to quantify the stop-loss impact
4. Try backtesting separately in 2022 (bear market) and 2024 (range-bound market) to compare performance across market environments
