# Prerequisites: Technical Analysis Fundamentals

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Suitable for** | Readers who have not systematically studied candlesticks, moving averages, RSI, MACD, and other indicators |
    | **Estimated time** | 45–60 minutes |
    | **Already proficient?** | Continue from [Tutorial 00: Environment & Quantitative Foundations](../00-getting-started.md) or [Tutorial 01: Writing Your First Strategy](../01-first-strategy.md) |

> This article is for readers who have **never been exposed to technical analysis**. If you already understand moving averages, RSI, and MACD, feel free to skip ahead to [Tutorial 00: Environment & Quantitative Foundations](../00-getting-started.md).

---

## Table of Contents

1. [Price Data: OHLCV](#1-price-data-ohlcv)
2. [Moving Averages (MA)](#2-moving-averages-ma)
3. [RSI: Relative Strength Index](#3-rsi-relative-strength-index)
4. [MACD: Moving Average Convergence/Divergence](#4-macd-moving-average-convergencedivergence)
5. [Bollinger Bands](#5-bollinger-bands)
6. [ATR: Average True Range](#6-atr-average-true-range)
7. [KDJ / Stochastic Oscillator](#7-kdj--stochastic-oscillator)
8. [ADX: Trend Strength](#8-adx-trend-strength)
9. [Volume-Related Concepts](#9-volume-related-concepts)
10. [Support & Resistance](#10-support--resistance)
11. [Corresponding Functions in eqlib.utils](#11-corresponding-functions-in-eqlibutils)
12. [Next Steps](#12-next-steps)

---

## 1. Price Data: OHLCV

Each candlestick (bar) contains 5 fields, collectively known as **OHLCV**:

| Field | Meaning |
|-------|---------|
| `open` | Open price |
| `high` | Highest price of the day |
| `low` | Lowest price of the day |
| `close` | Close price |
| `volume` | Volume (number of shares traded) |

Sometimes there is also `money` (turnover, in CNY) = price × volume (approximate).

```python
# Fetching OHLCV data in eqlib
hist = attribute_history('601390', 20, '1d', ['open', 'high', 'low', 'close', 'volume'])
#           open   high    low  close      volume
# 2024-01-02  4.85   4.92   4.80   4.88  1234567890
# 2024-01-03  4.89   4.95   4.85   4.92  987654321
```

**Why is the close price so commonly used?**
Most strategies use `close` because it represents the final market price of the day and is the most widely quoted figure. Some strategies also use `high` / `low` / `volume` (e.g., ATR requires all three, while Bollinger Bands only need the close price).

---

## 2. Moving Averages (MA)

### 2.1 Simple Moving Average (SMA)

The **arithmetic mean** of the most recent N close prices:

```
MA(N) = (close[0] + close[1] + ... + close[N-1]) / N
```

**Typical parameters:** MA5 (weekly), MA10 (bi-weekly), MA20 (monthly), MA60 (quarterly), MA120 (semi-annual), MA250 (annual)

```python
from eqlib import *
from eqlib.utils import ma

hist = attribute_history('601390', 60, '1d', ['close'])
close = hist['close']

# Manual calculation
ma5  = close.tail(5).mean()
ma20 = close.tail(20).mean()

# Using eqlib.utils
ma5_series  = ma(close, 5)    # returns entire Series; use iloc[-1] for latest value
ma20_series = ma(close, 20)
```

### 2.2 Exponential Moving Average (EMA)

A moving average that assigns **higher weight to recent data**, reacting faster to price changes than SMA:

```python
from eqlib.utils import ema

ema12 = ema(close, 12)
ema26 = ema(close, 26)
```

### 2.3 Wilder's Smoothing Moving Average (SMMA)

The smoothing method used internally by RSI, ATR, and ADX (also known as RMA / Wilder's Smoothing):

```python
from eqlib.utils import smma

smma14 = smma(close, 14)
```

> **Note (project convention)**: `eqlib.utils.sma()` = simple rolling mean; `eqlib.utils.smma()` = Wilder's smoothing. Use `smma()` for RSI / ATR related indicators.

### 2.4 Common Uses of Moving Averages

| Scenario | Usage |
|----------|-------|
| Trend identification | Price above MA = bullish; price below MA = bearish |
| Golden cross / Death cross | Short MA crosses above long MA = buy signal (golden cross); crosses below = sell signal (death cross) |
| Support / Resistance | The moving average itself often acts as a support or resistance level |
| Trend strength | Multiple MAs in bullish alignment (short > medium > long) indicate a strong trend |

---

## 3. RSI: Relative Strength Index

**RSI (Relative Strength Index)** measures the ratio of upward price momentum to downward price momentum, mapping the result to the 0–100 range.

### 3.1 Calculation Logic (Simplified)

```
1. Calculate the average of up-moves (up) and down-moves (down) over the past N days
2. RS = average up / average down
3. RSI = 100 - 100 / (1 + RS)
```

**Typical parameter:** `period=14` (most commonly used)

### 3.2 Interpretation

| RSI Value | Meaning | Strategy Implication |
|-----------|---------|----------------------|
| > 70 | Overbought | Price may fall, consider selling |
| 50–70 | Moderately bullish | Bull market |
| 30–50 | Moderately bearish | Bear market |
| < 30 | Oversold | Price may rebound, consider buying |

```python
from eqlib.utils import rsi

hist = attribute_history('601390', 60, '1d', ['close'])
rsi14 = rsi(hist['close'], 14)   # returns Series
current_rsi = rsi14.iloc[-1]

if current_rsi < 30:
    print('Oversold, watch for buying opportunities')
```

---

## 4. MACD: Moving Average Convergence/Divergence

**MACD (Moving Average Convergence/Divergence)** derives three lines from the difference between two moving averages:

| Line | Calculation | Meaning |
|------|-------------|---------|
| **DIF (MACD Line)** | EMA(12) − EMA(26) | Difference between short-term and long-term MAs |
| **DEA (Signal Line)** | EMA(DIF, 9) | 9-day EMA of DIF (smoothed) |
| **Histogram** | (DIF − DEA) × 2 | Distance between the two lines; positive/negative = bullish/bearish |

### Interpretation

- **DIF crosses above DEA** (histogram turns from negative to positive) → Buy signal ("golden cross")
- **DIF crosses below DEA** (histogram turns from positive to negative) → Sell signal ("death cross")
- **Histogram transitions from shrinking to expanding** (increasing momentum) → Trend strengthening

```python
from eqlib.utils import macd

hist = attribute_history('601390', 60, '1d', ['close'])
dif, dea, histogram = macd(hist['close'], fast=12, slow=26, signal=9)

latest_dif = dif.iloc[-1]
latest_dea = dea.iloc[-1]

if latest_dif > latest_dea:
    print('MACD bullish alignment')
```

---

## 5. Bollinger Bands

**Bollinger Bands** consist of three lines based on the mean and standard deviation of the close price:

| Line | Calculation |
|------|-------------|
| **Upper Band** | MA(N) + k × Std(N) |
| **Middle Band** | MA(N) (typically N=20) |
| **Lower Band** | MA(N) − k × Std(N) |

**Typical parameters:** `N=20`, `k=2` (i.e., ±2 standard deviations)

### Interpretation

- Price touches the **upper band** → Overbought, may pull back
- Price touches the **lower band** → Oversold, may rebound
- **Band width narrows** → Volatility decreasing, potentially building up for a big move
- Price consistently rides the upper band → Strong trend, avoid shorting

```python
from eqlib.utils import boll

hist = attribute_history('601390', 60, '1d', ['close'])
upper, middle, lower = boll(hist['close'], period=20, std_dev=2)

price = hist['close'].iloc[-1]

if price < lower.iloc[-1]:
    print('Price below lower Bollinger Band, mean-reversion buy signal')
```

---

## 6. ATR: Average True Range

**ATR (Average True Range)** measures the daily **price volatility range**, used for setting stop-losses and position sizing.

### True Range (TR) Calculation

```
TR = max(High - Low, |High - PrevClose|, |Low - PrevClose|)
ATR(N) = Wilder's smoothed average(TR, N)
```

**Typical parameter:** `period=14`

### Usage

```python
from eqlib.utils import atr

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
atr14 = atr(hist['high'], hist['low'], hist['close'], 14)
current_atr = atr14.iloc[-1]

# ATR stop-loss: current price minus 2x ATR
stop_loss_price = current_price - 2 * current_atr

# ATR position sizing: risk at most 1% of total capital per trade
risk_per_trade = total_value * 0.01
shares = risk_per_trade / (2 * current_atr)
```

---

## 7. KDJ / Stochastic Oscillator

**KDJ (also known as the Stochastic Oscillator)** consists of three lines that gauge overbought/oversold conditions based on the price's relative position within a range:

| Line | Meaning |
|------|---------|
| **K** | Fast stochastic value (more sensitive than D) |
| **D** | Moving average of K (slower, acts as signal line) |
| **J** | 3K − 2D (leading indicator, more extreme overbought/oversold readings) |

- J < 0 → Extremely oversold
- J > 100 → Extremely overbought
- K crosses above D → Buy signal; K crosses below D → Sell signal

```python
from eqlib.utils import kdj

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
k, d, j = kdj(hist['high'], hist['low'], hist['close'])
```

---

## 8. ADX: Trend Strength

**ADX (Average Directional Index)** measures trend **strength** without indicating direction:

| ADX Value | Trend Strength |
|-----------|----------------|
| < 20 | No trend or weak trend (ranging market) |
| 20–40 | Moderate trend |
| > 40 | Strong trend |

ADX does not tell you whether the market is going up or down — only whether it is trending. It is commonly paired with moving averages: use trend-following strategies when ADX > 25, and switch to mean-reversion strategies when ADX < 20.

```python
from eqlib.utils import adx

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
adx_val, plus_di, minus_di = adx(hist['high'], hist['low'], hist['close'], period=14)
current_adx = adx_val.iloc[-1]
```

---

## 9. Volume-Related Concepts

| Concept | Meaning | In eqlib |
|---------|---------|----------|
| **Volume** | Number of shares traded today | `hist['volume']` |
| **Turnover (Amount/Money)** | Total value traded today | `hist['money']` |
| **Volume ratio** | Today's volume / average volume over past N days | Manual calculation |
| **OBV (On-Balance Volume)** | Cumulative: add volume on up-days, subtract on down-days | `eqlib.utils.obv()` |

**Why volume matters**:
- Price rises on high volume → Strong bullish force, signal is more reliable
- Price rises on low volume → Uptrend losing steam, exercise caution
- Price falls on high volume → Strong bearish force
- Price falls on low volume → Selling pressure may be fading, watch for rebound opportunities

```python
# Volume ratio (today's volume / 20-day average volume)
hist = attribute_history('601390', 25, '1d', ['close', 'volume'])
avg_vol = hist['volume'].tail(20).mean()
today_vol = hist['volume'].iloc[-1]
volume_ratio = today_vol / avg_vol

if volume_ratio > 1.5:
    print('Above-average volume, signal is more reliable')
```

---

## 10. Support & Resistance

**Support**: A price level where the price repeatedly stops falling and bounces back up.
**Resistance**: A price level where the price repeatedly stops rising and pulls back down.

Common sources of support/resistance:
- Historical highs and lows
- Round-number price levels (psychological levels, e.g., 5 CNY, 10 CNY, 100 CNY)
- Moving averages (MA20, MA60, etc.)
- Bollinger Band upper and lower bands
- Fibonacci retracement levels (38.2%, 61.8%)
- High-volume price zones (Volume Profile)

```python
from eqlib.utils import support_resistance_levels, donchian

# Fibonacci retracement
from eqlib.utils import fibonacci_retracement

hist = attribute_history('601390', 60, '1d', ['high', 'low', 'close'])
high = hist['high'].max()
low  = hist['low'].min()
fib_levels = fibonacci_retracement(high, low)
# Returns prices at [0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%]

# Donchian Channel (N-day high/low)
upper_ch, lower_ch = donchian(hist['high'], hist['low'], period=20)
```

---

## 11. Corresponding Functions in eqlib.utils

Below is a mapping of the technical indicators discussed in this article to their `eqlib.utils` functions:

| Indicator | Function | Returns |
|-----------|----------|---------|
| SMA (Simple Moving Average) | `utils.ma(series, period)` | Series |
| EMA (Exponential Moving Average) | `utils.ema(series, period)` | Series |
| Wilder's Smoothing | `utils.smma(series, period)` | Series |
| RSI | `utils.rsi(close, period=14)` | Series |
| MACD | `utils.macd(close, fast, slow, signal)` | (dif, dea, hist) |
| Bollinger Bands | `utils.boll(close, period=20, std_dev=2)` | (upper, mid, lower) |
| ATR | `utils.atr(high, low, close, period=14)` | Series |
| KDJ | `utils.kdj(high, low, close, ...)` | (k, d, j) |
| ADX | `utils.adx(high, low, close, period=14)` | (adx, +di, -di) |
| OBV | `utils.obv(close, volume)` | Series |
| Fibonacci Retracement | `utils.fibonacci_retracement(high, low)` | list of prices |
| Donchian Channel | `utils.donchian(high, low, period)` | (upper, lower) |

For a complete function list and parameter reference, see the [Utility Library Reference](../../reference/utils.md).

---

## 12. Next Steps

- **Continue prerequisites**: [A-Share Market Fundamentals](ashare-knowledge.md)
- **Start the main tutorials**: [Tutorial 00: Environment & Quantitative Foundations](../00-getting-started.md)
- **Tutorial 06: RSI Mean-Reversion Strategy** covers RSI mean-reversion strategy in depth: [05-rsi-mean-reversion.md](../05-rsi-mean-reversion.md)
