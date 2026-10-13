# Utility Library

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Use technical indicators, statistical analysis, and money management tools |
    | **Prerequisite** | [Writing a Strategy](write-strategy.md) |

---
## 1. Utility Library

`eqlib.utils` provides technical indicators, statistical analysis, money management, and support/resistance level calculation tools.

### 1.0 A Runnable End-to-End Example

Fetch data → compute indicators → print. Runs as-is (network required for data):

```python
from eqlib import fetch_stock_data, utils

df = fetch_stock_data('601398', '2024-01-01', '2024-06-30')
close = df['close']

daily_returns = close.pct_change().dropna()

print("Latest MA20 : %.2f" % utils.ma(close, 20).iloc[-1])
print("RSI(14)     : %.1f" % utils.rsi(close, 14).iloc[-1])
print("Ann. Sharpe : %.2f" % utils.rolling_sharpe(daily_returns, window=20).iloc[-1])
print("VaR(5%%)    : %.2f%%" % (utils.value_at_risk(daily_returns, confidence=0.05) * 100))
```

`value_at_risk` supports three methods: `historical` (empirical quantile, default), `parametric` (normal assumption), and `cornish_fisher` (skew/kurtosis-adjusted — better suited to the fat-tailed returns typical of A-shares).

### 1.1 Technical Indicators

```python
from eqlib import utils

ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
rsi14 = utils.rsi(close, 14)
k, d, j = utils.kdj(high, low, close, period=9)
upper, mid, lower = utils.boll(close, period=20)
atr14 = utils.atr(high, low, close, 14)
```

### 1.2 Statistical Analysis

```python
sharpe = utils.rolling_sharpe(daily_returns, window=20)
max_dd, dd_start, dd_end = utils.max_drawdown(equity_curve)
var_5 = utils.value_at_risk(daily_returns, confidence=0.05)
```

### 1.3 Money Management

```python
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
shares = utils.atr_position_size(capital=100000, risk_pct=0.02, atr=0.30, n_atr=2.0)
weights = utils.risk_parity_weights([0.15, 0.25, 0.20])
```

### 1.4 Support & Resistance Levels

```python
pp, r1, s1, r2, s2, r3, s3 = utils.pivot_classic(high, low, close)
sr = utils.support_resistance_levels(high, low, close)
fib = utils.fibonacci_retracement(high, low, close)
```

See the [Utility Library Reference](../reference/utils.md) for details.
