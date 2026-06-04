# EasyQuant Utilities Reference: Calculation Principles & Usage

> This document describes the **usage** and **underlying calculation principles** of all computational tools in `eqlib.utils`.
> `eqlib.utils` is a Python package within the EasyQuant project, imported via `from eqlib import utils`.

!!! abstract "About This Document"

    This document provides **usage examples** and **mathematical definitions** for each utility function. If you only need to call them in a strategy, start with the [API Reference Overview](index.md) and jump back to the relevant section.

---

## Table of Contents

1. [Technical Indicators (indicators)](#1-technical-indicators-indicators)
2. [Statistical Analysis (stats)](#2-statistical-analysis-stats)
3. [Money Management (money)](#3-money-management-money)
4. [Support & Resistance Levels (levels)](#4-support--resistance-levels-levels)

---

## 1. Technical Indicators (indicators)

### 1.1 Moving Averages

#### `ma(series, period)` — Simple Moving Average (SMA)

**Usage:**
```python
from eqlib import utils
ma5 = utils.ma(close, 5)
```

**Calculation:**
```
MA(t) = (C(t) + C(t-1) + ... + C(t-n+1)) / n
```
Arithmetic mean of the closing prices over the most recent `n` bars.

#### `ema(series, period)` — Exponential Moving Average (EMA)

**Usage:**
```python
ema10 = utils.ema(close, 10)
```

**Calculation:**
```
EMA(t) = α * C(t) + (1 - α) * EMA(t-1)
α = 2 / (n + 1)
```
EMA gives more weight to recent prices, making it more responsive. The initial value is the SMA.

#### `sma(series, period)` — Simple Moving Average (alias for `ma`)

**Usage:**
```python
sma14 = utils.sma(close, 14)
```

**Calculation:**
```
SMA(t) = (C(t) + C(t-1) + ... + C(t-n+1)) / n
```
Identical to `ma` — a rolling arithmetic mean.

#### `smma(series, period, weight=1.0)` — Smoothed Moving Average (Wilder MA; `weight` controls smoothing strength)

**Usage:**
```python
smma14 = utils.smma(close, 14)
```
The default `weight=1.0` is sufficient for most cases; only modify it explicitly when custom smoothing strength is needed.
This default corresponds to Wilder's standard smoothing weight.

**Calculation:**
```
SMMA(t) = (SMMA(t-1) * (n - w) + C(t) * w) / n
```
Initialized with the first `n` bars, then updated via the recursive formula. Wilder-style indicators such as ADX/RSI are better suited to `smma`.

#### `wma(series, period)` — Weighted Moving Average

**Usage:**
```python
wma10 = utils.wma(close, 10)
```

**Calculation:**
```
WMA(t) = Σ [C(t-i) * (i+1)] / Σ (i+1),  i = 0..n-1
```
Linear weights: the most recent bar has the highest weight (n), the farthest has the lowest (1).

#### `vwap(high, low, close, volume, window=None)` — Volume Weighted Average Price

**Usage:**
```python
vwap = utils.vwap(high, low, close, volume)           # Cumulative VWAP
vwap20 = utils.vwap(high, low, close, volume, 20)     # 20-day rolling VWAP
```

**Calculation:**
```
TP = (H + L + C) / 3          # Typical price
window=None:  VWAP = Σ(TP * Volume) / Σ(Volume)   (cumulative)
window=N:     VWAP = rolling_sum(TP*Volume, N) / rolling_sum(Volume, N)
```
Cumulative VWAP (`window=None`) can be computed at any frequency and is best suited for intraday minute-level sequences within a single trading session. For daily or cross-session analysis, you should typically pass a `window` to use rolling VWAP, because session-agnostic cumulative results would otherwise keep accumulating across days.

---

### 1.2 MACD

#### `macd(close, fast=12, slow=26, signal=9)`

**Usage:**
```python
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
```

**Calculation:**
```
EMA_fast = EMA(close, fast)
EMA_slow = EMA(close, slow)
DIF = EMA_fast - EMA_slow           # Difference (fast line)
DEA = EMA(DIF, signal)              # Signal line (slow line)
MACD histogram = 2 * (DIF - DEA)    # Histogram
```

**Signal interpretation:**
- DIF crosses above DEA → Golden cross (buy signal)
- DIF crosses below DEA → Death cross (sell signal)
- Histogram turns from negative to positive → Bullish momentum strengthening

---

### 1.3 RSI

#### `rsi(close, period=14)`

**Usage:**
```python
rsi14 = utils.rsi(close, 14)
```

**Calculation:**
```
Δ = C(t) - C(t-1)
AvgGain  = EMA(max(Δ, 0), period)
AvgLoss  = EMA(max(-Δ, 0), period)
RS = AvgGain / AvgLoss
RSI = 100 - 100 / (1 + RS)
```

**Signal interpretation:**
- RSI > 70 → Overbought
- RSI < 30 → Oversold
- RSI above 50 → Bulls in control

---

### 1.4 KDJ

#### `kdj(high, low, close, period=9, smooth=3)`

**Usage:**
```python
k, d, j = utils.kdj(high, low, close, period=9, smooth=3)
```

**Calculation:**
```
LLV = min(Low, period)
HHV = max(High, period)
RSV = (C - LLV) / (HHV - LLV) * 100    # Raw stochastic value
K   = EMA(RSV, smooth)                  # Smoothed
D   = EMA(K, smooth)                    # Double-smoothed
J   = 3*K - 2*D                         # Sensitivity line
```

**Signal interpretation:**
- K crosses above D → Golden cross
- J > 100 or < 0 → Extreme zones

---

### 1.5 Bollinger Bands

#### `boll(close, period=20, num_std=2.0)`

**Usage:**
```python
upper, mid, lower = utils.boll(close, period=20, num_std=2.0)
```

**Calculation:**
```
Middle = MA(close, period)
σ     = STD(close, period)             # Standard deviation
Upper = Middle + num_std * σ
Lower = Middle - num_std * σ
```

**Signal interpretation:**
- Price touches upper band → Possibly overbought
- Price touches lower band → Possibly oversold
- Bands narrow (squeeze) → Impending breakout

---

### 1.6 ATR

#### `atr(high, low, close, period=14)`

**Usage:**
```python
atr14 = utils.atr(high, low, close, period=14)
```

**Calculation:**
```
TR(t) = max(H-L, |H-C(t-1)|, |L-C(t-1)|)    # True range
ATR = EMA(TR, period)                         # Smoothed
```

ATR measures price volatility, not direction. Commonly used for setting stop-loss distances.

---

### 1.7 CCI

#### `cci(high, low, close, period=14)`

**Usage:**
```python
cci_val = utils.cci(high, low, close, period=14)
```

**Calculation:**
```
TP = (H + L + C) / 3                     # Typical price
MA_TP = MA(TP, period)                   # MA of typical price
MAD  = mean(|TP - MA_TP|, period)        # Mean absolute deviation
CCI = (TP - MA_TP) / (0.015 * MAD)
```

0.015 is a constant scaling factor that places approximately 70%-80% of CCI values within the [-100, +100] range.

**Signal interpretation:**
- CCI > +100 → Overbought
- CCI < -100 → Oversold

---

### 1.8 Williams %R

#### `wr(high, low, close, period=14)`

**Usage:**
```python
wr_val = utils.wr(high, low, close, period=14)
```

**Calculation:**
```
HHV = max(High, period)
LLV = min(Low, period)
WR = (HHV - C) / (HHV - LLV) * (-100)
```

Range: [-100, 0]. Similar to the KDJ stochastic oscillator but inverted.

**Signal interpretation:**
- WR > -20 → Overbought
- WR < -80 → Oversold

---

### 1.9 ROC

#### `roc(close, period=12)`

**Usage:**
```python
roc_val = utils.roc(close, period=12)
```

**Calculation:**
```
ROC = (C(t) - C(t-n)) / C(t-n) * 100
```
Measures the percentage change in price relative to `n` periods ago.

---

### 1.10 OBV

#### `obv(close, volume)`

**Usage:**
```python
obv_val = utils.obv(close, volume)
```

**Calculation:**
```
if C(t) > C(t-1):  OBV(t) = OBV(t-1) + Volume(t)
if C(t) < C(t-1):  OBV(t) = OBV(t-1) - Volume(t)
if C(t) == C(t-1): OBV(t) = OBV(t-1)
```
Accumulates volume on up-days and subtracts volume on down-days. Divergence between OBV trend and price trend can serve as a reversal signal.

---

### 1.11 ADX

#### `adx(high, low, close, period=14)`

**Usage:**
```python
pdi, mdi, adx, adxr = utils.adx(high, low, close, period=14)
```

**Calculation:**
```
+DM(t) = max(H(t) - H(t-1), 0)   where +DM > -DM
-DM(t) = max(L(t-1) - L(t), 0)   where -DM > +DM

+DI = 100 * WilderSmooth(+DM) / ATR
-DI = 100 * WilderSmooth(-DM) / ATR

DX   = |+DI - -DI| / (+DI + -DI) * 100
ADX  = WilderSmooth(DX, period)
ADXR = (ADX(t) + ADX(t-period)) / 2
```

**Signal interpretation:**
- ADX > 25 → Strong trend
- ADX < 20 → No trend / ranging
- +DI crosses above -DI → Bullish signal

---

### 1.12 Golden Cross / Death Cross

#### `golden_cross(fast_ma, slow_ma)` / `death_cross(fast_ma, slow_ma)`

**Usage:**
```python
is_golden = utils.golden_cross(ma5, ma20)
is_death = utils.death_cross(ma5, ma20)
```

**Calculation:**
```
Golden cross: fast_ma(t-1) <= slow_ma(t-1) AND fast_ma(t) > slow_ma(t)
Death cross:  fast_ma(t-1) >= slow_ma(t-1) AND fast_ma(t) < slow_ma(t)
```
Detects whether two moving averages have crossed.

---

## 2. Statistical Analysis (stats)

### 2.1 Rolling Correlation

#### `rolling_corr(x, y, window)`

**Usage:**
```python
corr = utils.rolling_corr(stock_ret, market_ret, 20)
```

**Calculation:**
```
ρ(t) = Cov(x, y) / (σ_x * σ_y)    # computed within the window
```

### 2.2 Rolling Beta

#### `rolling_beta(series, benchmark, window, risk_free=0.0)`

**Calculation:**
```
β(t) = Cov(series, benchmark) / Var(benchmark)    # within the window
```

### 2.3 Rolling Sharpe Ratio

#### `rolling_sharpe(returns, window, risk_free=0.0, annualize=252)`

**Calculation:**
```
Sharpe = (μ * annualize - risk_free) / (σ * √annualize)
```
where μ and σ are computed within the rolling window.

### 2.4 Z-Score

#### `zscore(series, window=None)`

**Calculation:**
```
If window specified: Z(t) = (x(t) - μ_window) / σ_window
Otherwise:           Z(t) = (x(t) - μ_full) / σ_full
```

### 2.5 Percentile Rank

#### `percentile_rank(series, window=None)`

**Calculation:**
```
PR(t) = rank(x(t)) / count * 100
```
Returns a value between 0 and 100, indicating the percentile position of the current value within the window.

### 2.6 Linear Regression

#### `linear_regression(x, y)`

**Calculation:**
```
β = SS_xy / SS_xx
α = ȳ - β * x̄
R² = 1 - SS_res / SS_tot
t_stat = β / SE(β)
```
Returns alpha, beta, R², t-statistic, and the residual series.

### 2.7 Downside Deviation

#### `downside_deviation(returns, target=0.0, annualize=252)`

**Calculation:**
```
DD = √[ mean(r²) for r in returns where r < target ] * √annualize
```
Only considers returns below the target value; this is the denominator of the Sortino ratio.

### 2.8 Value at Risk (VaR)

#### `value_at_risk(returns, confidence=0.05, method='historical')`

**Calculation:**
```
Historical: VaR = -quantile(returns, confidence)
Parametric: VaR = -(μ + z_α * σ)    where z_α is the standard normal quantile
```
Represents the maximum expected single-day loss at the given confidence level.

### 2.9 Conditional VaR (CVaR / Expected Shortfall)

#### `conditional_var(returns, confidence=0.05)`

**Calculation:**
```
CVaR = -E[r | r ≤ -VaR]    # Tail average loss beyond VaR
```
More conservative than VaR — accounts for extreme tail losses.

### 2.10 Drawdown Analysis

#### `drawdown(equity)` / `max_drawdown(equity)`

**Calculation:**
```
Drawdown(t) = (Equity(t) - Peak(t)) / Peak(t)
Peak(t) = max(Equity(0), ..., Equity(t))
MaxDrawdown = min(Drawdown(t))
```

### 2.11 Consecutive Wins/Losses

#### `consecutive_wins(returns)` / `consecutive_losses(returns)`

**Calculation:**
Scans day by day: increments the win counter on positive returns (resets on negative), and vice versa.

### 2.12 Compound Return

#### `compound_return(returns)`

**Calculation:**
```
CR = Π(1 + r_i) - 1
```

### 2.13 Compound Annual Growth Rate

#### `cagr(start_value, end_value, years)`

**Calculation:**
```
CAGR = (end_value / start_value) ^ (1 / years) - 1
```

### 2.14 Log Return

#### `log_return(prices)`

**Calculation:**
```
log_return(t) = ln(P(t) / P(t-1))
```

### 2.15 Math Utilities

| Function | Calculation |
|----------|-------------|
| `fibonacci(n)` | First n Fibonacci numbers: 1, 1, 2, 3, 5, 8, ... |
| `comb(n, k)` | Combinations C(n,k) = n! / (k! * (n-k)!) |
| `perm(n, k)` | Permutations P(n,k) = n! / (n-k)! |

---

## 3. Money Management (money)

### 3.1 Kelly Criterion

#### `kelly_criterion(win_rate, avg_win, avg_loss)`

**Usage:**
```python
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
# Returns 0.25, i.e., allocate 25% of capital
```

**Calculation:**
```
b = avg_win / avg_loss     # Win/loss ratio
q = 1 - win_rate           # Loss probability
Kelly = (b * win_rate - q) / b
```

The Kelly formula maximizes the logarithmic growth rate of capital. In practice, Half-Kelly (half the position) is often used to reduce volatility.

#### `half_kelly(win_rate, avg_win, avg_loss)`

Returns 50% of the Kelly value.

#### `kelly_from_returns(returns)`

Automatically computes win_rate, avg_win, and avg_loss from a trade return series.

---

### 3.2 Fixed Fraction Position Sizing

#### `fixed_fraction_size(capital, risk_pct, entry_price, stop_price)`

**Usage:**
```python
shares = utils.fixed_fraction_size(
    capital=100000, risk_pct=0.02,
    entry_price=10.0, stop_price=9.5,
)  # At most 4000 shares
```

**Calculation:**
```
risk_amount = capital * risk_pct
loss_per_share = |entry_price - stop_price|
shares = floor(risk_amount / loss_per_share / 100) * 100
```

Ensures the maximum loss on a single trade does not exceed `risk_pct` of capital (typically 1-2%).

---

### 3.3 Fixed Ratio Allocation

#### `fixed_ratio_size(capital, equity_ratio, entry_price)`

**Calculation:**
```
allocation = capital * equity_ratio
shares = floor(allocation / entry_price / 100) * 100
```

Allocates a fixed percentage of capital (e.g., 10%) to a single stock.

---

### 3.4 ATR Position Sizing

#### `atr_position_size(capital, risk_pct, atr, n_atr=2.0)`

**Usage:**
```python
shares = utils.atr_position_size(
    capital=100000, risk_pct=0.02,
    atr=0.30, n_atr=2.0,
)
```

**Calculation:**
```
stop_distance = ATR * n_atr
shares = floor(capital * risk_pct / stop_distance / 100) * 100
```

Automatically reduces position size for high-volatility stocks and increases it for low-volatility stocks.

---

### 3.5 Volatility Target Sizing

#### `volatility_target_size(capital, target_vol, price, vol_per_share)`

**Calculation:**
```
target_value = capital * target_vol / vol_per_share
shares = floor(target_value / price / 100) * 100
```

Sizes the position so that the overall portfolio volatility equals `target_vol`.

---

### 3.6 Martingale / Anti-Martingale

#### `martingale_size(base_amount, loss_streak, multiplier=2.0)`

**Calculation:**
```
size = base_amount * multiplier ^ loss_streak
```
Doubles the bet after consecutive losses, betting on mean reversion. Extremely high risk.

#### `anti_martingale_size(base_amount, win_streak, multiplier=1.5)`

**Calculation:**
```
size = base_amount * multiplier ^ win_streak
```
Increases position after consecutive wins, amplifying gains with the trend.

---

### 3.7 Portfolio Weights

#### `equal_weight(n)`

Equal weight: `w_i = 1/n`.

#### `risk_parity_weights(volatilities)`

**Calculation:**
```
w_i = (1/σ_i) / Σ(1/σ_j)
```
Lower-volatility assets receive higher weights, equalizing each asset's contribution to portfolio risk.

#### `volatility_normalize(returns)`

**Calculation:**
```
normalized_return(t) = r(t) / σ_20(t)
```
Normalizes returns using a rolling 20-day standard deviation.

---

## 4. Support & Resistance Levels (levels)

### 4.1 Pivot Points

Pivot points calculate the next day's support/resistance levels based on the previous day's high, low, and close prices.

#### `pivot_classic(high, low, close)` — Classic Pivot Points

**Calculation:**
```
PP  = (H + L + C) / 3
R1  = 2*PP - L
S1  = 2*PP - H
R2  = PP + (H - L)
S2  = PP - (H - L)
R3  = H + 2*(PP - L)
S3  = L - 2*(H - PP)
```

#### `pivot_fibonacci(high, low, close)` — Fibonacci Pivot Points

**Calculation:**
```
PP = (H + L + C) / 3
R1 = PP + 0.382 * (H - L)    S1 = PP - 0.382 * (H - L)
R2 = PP + 0.618 * (H - L)    S2 = PP - 0.618 * (H - L)
R3 = PP + 1.000 * (H - L)    S3 = PP - 1.000 * (H - L)
```

#### `pivot_woodie(high, low, close)` — Woodie Pivot Points

**Calculation:**
```
PP = (H + L + 2*C) / 4       # Close price weight doubled
R1 = 2*PP - L
S1 = 2*PP - H
R2 = PP + (H - L)
S2 = PP - (H - L)
```

#### `pivot_camarilla(high, low, close)` — Camarilla Pivot Points

**Calculation:**
```
R4 = (H - L) * 1.1 / 2  + C     R1 = (H - L) * 1.1 / 12 + C
R3 = (H - L) * 1.1 / 4  + C     S1 = C - (H - L) * 1.1 / 12
R2 = (H - L) * 1.1 / 6  + C     S2 = C - (H - L) * 1.1 / 6
                                S3 = C - (H - L) * 1.1 / 4
                                S4 = C - (H - L) * 1.1 / 2
```
Tighter ranges, suited for intraday trading. R4/S4 are breakout levels.

#### `pivot_demark(high, low, close, open_=None)` — DeMark Pivot Points

**Calculation:**
```
If C < O:  X = H + 2*L + C
If C > O:  X = 2*H + L + C
If C = O:  X = H + L + 2*C

PP = X / 4
R1 = X/2 - L
S1 = X/2 - H
```

---

### 4.2 Swing Highs/Lows

#### `swing_highs_lows(high, low, left_bars=5, right_bars=5)`

**Calculation:**
```
Swing High: H(t) > max(H(t-n) ... H(t+n))   i.e., higher than N bars on each side
Swing Low:  L(t) < min(L(t-n) ... L(t+n))   i.e., lower than N bars on each side
```

#### `support_resistance_levels(high, low, close=None, lookback=50, tolerance=0.02)`

**Calculation:**
1. Find Swing Highs/Lows within the `lookback` range
2. Cluster price levels that are close together (difference < tolerance%)
3. Cluster centers become support/resistance levels
4. Identify the nearest support and resistance to the current price

---

### 4.3 Fibonacci Retracement

#### `fibonacci_retracement(high, low, close=None, lookback=100)`

**Usage:**
```python
fib = utils.fibonacci_retracement(high, low, close, lookback=100)
print(fib[0.382], fib[0.618])  # Key retracement levels
```

**Calculation:**
```
swing_high = max(High, lookback)
swing_low  = min(Low, lookback)
diff = swing_high - swing_low

Uptrend retracement = swing_high - ratio * diff
Downtrend retracement = swing_low + ratio * diff
```

Key retracement ratios: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

---

### 4.4 Donchian Channel

#### `donchian(high, low, close=None, period=20)`

**Calculation:**
```
Upper = max(High, period)
Lower = min(Low, period)
Middle = (Upper + Lower) / 2
```

The core signal of the Turtle Trading system: buy on upper band breakout, sell on lower band breakdown.

---

### 4.5 Psychological Round-Number Levels

#### `psychological_levels(price, step=1.0, count=10)`

**Calculation:**
Generates round-number price levels at `step` intervals near the current price. For example, price=5.23, step=1.0 produces 1.0, 2.0, 3.0, ..., 10.0. Round-number prices often form support/resistance due to trading psychology.

---

### 4.6 Volume Profile

#### `volume_profile_support_resistance(close, volume, n_bins=50, lookback=100)`

**Calculation:**
1. Divide the price range within `lookback` into `n_bins` price bins
2. Count total volume in each price bin
3. The price with the highest volume = POC (Point of Control)
4. Expand outward from POC, accumulating 70% of total volume = Value Area
   - VAH (Value Area High): upper boundary of the volume profile
   - VAL (Value Area Low): lower boundary of the volume profile
5. Price bins with above-median volume are marked as significant nodes

**Signal interpretation:**
- Near POC: a balanced zone of repeated price contention, forming support/resistance
- VAH/VAL: value area boundaries — breakouts may accelerate

---

### 4.7 Moving Average Dynamic Support/Resistance

#### `ma_support_resistance(close, periods=None)`

**Usage:**
```python
levels = utils.ma_support_resistance(close, periods=[20, 50, 200])
```

**Calculation:**
For the specified MA periods, when the price is above the moving average it acts as support; when below, it acts as resistance. Default periods [20, 50, 200] correspond to short/medium/long-term horizons.

---

### 4.8 Previous Day High/Low/Close

#### `prev_day_levels(high, low, close)`

**Calculation:**
```
prev_high = high.shift(1)
prev_low  = low.shift(1)
prev_close = close.shift(1)
```
The previous day's high, low, and close prices often serve as intraday support/resistance references.

---

### 4.9 ATR Trailing Stop

#### `trailing_stop(close, atr=None, high=None, low=None, multiplier=2.0, period=14)`

**Calculation:**
```
stop_level(t) = close(t) - multiplier * ATR(t)
trailing_stop(t) = max(stop_level(0), ..., stop_level(t))
```

The stop level only ratchets upward, never downward, locking in profits.

---

### 4.10 Gap Detection

#### `gap_up_down(open_, high, low, close)`

**Calculation:**
```
Gap up:   Low(t) > High(t-1)    Gap price = (High(t-1) + Low(t)) / 2
Gap down: High(t) < Low(t-1)    Gap price = (Low(t-1) + High(t)) / 2
```

Gap zones often form future support/resistance levels.

---

## Appendix: Complete Import Reference

```python
from eqlib import utils

# Technical indicators
utils.ma(close, 5)
utils.rsi(close, 14)
utils.macd(close, 12, 26, 9)
utils.kdj(high, low, close, 9)
utils.boll(close, 20)
utils.atr(high, low, close, 14)

# Support & resistance levels
utils.pivot_classic(high, low, close)
utils.support_resistance_levels(high, low, close)
utils.fibonacci_retracement(high, low, close)
utils.donchian(high, low, close)
utils.volume_profile_support_resistance(close, volume)
utils.trailing_stop(close, atr=atr_val)
utils.gap_up_down(open_, high, low, close)

# Statistics
utils.rolling_sharpe(returns, 20)
utils.value_at_risk(returns)
utils.max_drawdown(equity)
utils.cagr(100, 200, 2)

# Money management
utils.kelly_criterion(0.55, 1500, 1000)
utils.atr_position_size(100000, 0.02, 0.30)
utils.risk_parity_weights([0.15, 0.25, 0.20])
```
