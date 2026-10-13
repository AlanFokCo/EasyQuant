# Tutorial 03: Strategy Optimization & Improvement

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Parameter scanning & stability testing, signal filtering, portfolio optimization & attribution, avoiding blind parameter tuning |
    | **Estimated time** | ~60 minutes |
    | **Prerequisites** | [Tutorial 02: Backtest Validation](02-backtesting.md) |

> Building on backtest validation, improve strategy parameters, enrich strategy logic, and build portfolio strategies.

**Documentation index:** [How-To Guide Overview](../how-to/index.md)

---

## Table of Contents

1. [Why Optimize?](#1-why-optimize)
2. [Parameter Tuning & Stability Testing](#2-parameter-tuning--stability-testing)
3. [Adding Strategy Conditions](#3-adding-strategy-conditions)
4. [Portfolio Optimization](#4-portfolio-optimization)
5. [Attribution Analysis](#5-attribution-analysis)
6. [Building More Robust Strategies](#6-building-more-robust-strategies)
7. [Next Steps](#7-next-steps)

---

## 1. Why Optimize?

After passing the backtest, there is usually room for improvement:

| Problem | Optimization Direction |
|---------|------------------------|
| Returns not high enough | Improve signal quality, add filtering conditions |
| Drawdown too large | Add stop-loss, market filter, position sizing |
| Trading frequency too high | Add signal confirmation conditions, reduce false signals |
| Underperforming the market | Switch strategy, change targets, add sector rotation |

**Key principle:** Optimization must have a direction. You cannot "try all parameters and pick the best" — that is overfitting.

---

## 2. Parameter Tuning & Stability Testing

### 2.1 Moving Average Period Parameter Tuning

```python
from eqlib import *
import datetime

SECURITIES = ['601398']   # Module-level constant: the engine clears g before initialize

def test_ma_combo(fast_period, slow_period):
    """Test a set of moving average parameters."""
    results_log = []

    def initialize(context):
        g.security = SECURITIES[0]
        g.fast = fast_period
        g.slow = slow_period
        set_benchmark('000300.XSHG')
        set_order_cost(OrderCost(
            open_tax=0, close_tax=0.0005,
            open_commission=0.00025, close_commission=0.00025,
            min_commission=5,
        ))
        run_daily(market_open, time='every_bar')

    def market_open(context):
        hist = attribute_history(g.security, g.slow + 10, '1d', ['close'])
        if hist.empty or len(hist) < g.slow:
            return
        ma_fast = hist['close'].tail(g.fast).mean()
        ma_slow = hist['close'].tail(g.slow).mean()
        price = hist['close'].iloc[-1]

        if price > ma_fast > ma_slow:
            if g.security not in context.portfolio.positions:
                order_value(g.security, context.portfolio.available_cash * 0.95)  # keep a 5% fee buffer
        elif price < ma_fast < ma_slow:
            if g.security in context.portfolio.positions:
                order_target(g.security, 0)

    result = run_backtest(
        initialize, '2024-01-01', '2024-12-31',
        starting_cash=100000, benchmark='000300.XSHG',
        securities=SECURITIES,
    )
    if result:
        ctx = result['context']
        metrics = analyze_returns(result, risk_free_rate=0.03)
        results_log.append({
            'fast': fast_period,
            'slow': slow_period,
            'pnl_pct': (ctx.portfolio.total_value - 100000) / 100000,
            'sharpe': metrics['sharpe_ratio'],
            'max_dd': abs(metrics['max_drawdown']),
            'trades': len(result['trade_log']),
        })
    return results_log

# Scan parameters
combos = [
    (3, 10), (3, 15), (3, 20),
    (5, 15), (5, 20), (5, 30),
    (7, 20), (7, 25), (7, 30),
    (10, 30), (10, 40), (10, 60),
]

print('%-8s %-8s %-10s %-10s %-10s %-8s' % (
    'Fast', 'Slow', 'Return%', 'Sharpe', 'MaxDD%', 'Trades'))
print('-' * 58)

for fast, slow in combos:
    logs = test_ma_combo(fast, slow)
    if logs:
        r = logs[0]
        print('%-8d %-8d %-10.2f %-10.2f %-10.2f %-8d' % (
            r['fast'], r['slow'],
            r['pnl_pct'] * 100, r['sharpe'],
            r['max_dd'] * 100, r['trades']))
```

> Scan results already include the engine's default behaviors: price-limit interception (`check_price_limit=True`), same-day cancellation on suspension days, and forced liquidation 30 trading days after a delisted stock stops trading (`DELIST_LIQUIDATE`). These bring the backtest closer to live trading — don't turn them off to make the curve look better.

### 2.2 Stability Testing

```python
# If MA5/MA20 Sharpe = 1.8, MA5/MA25 Sharpe = 0.2 -> unstable
# If MA5/MA20 Sharpe = 1.5, MA5/MA18 Sharpe = 1.4, MA5/MA22 Sharpe = 1.3 -> stable

# Good parameters should:
# 1. Produce similar results for neighboring parameters (locally flat)
# 2. Perform consistently on training and test sets (generalization ability)
```

**Evaluation criteria:**
- Good parameters: Sharpe ratio difference among 2-3 neighboring parameter sets < 0.3
- Suspicious parameters: Sharpe difference with neighbors > 1.0, indicating a "lucky point" was found
- Poor parameters: Sharpe < 0.5 or max drawdown > 25%

---

## 3. Adding Strategy Conditions

### 3.1 Adding a Stop-Loss

A stop-loss is the most direct form of risk control:

```python
def market_open(context):
    security = g.security
    hist = attribute_history(security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return

    price = hist['close'].iloc[-1]
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].tail(20).mean()

    # === Stop-loss takes priority ===
    if security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        loss_pct = (price - pos.avg_cost) / pos.avg_cost
        if loss_pct < -0.08:
            order_target(security, 0)
            log.info('Stop-loss SELL %s @ %.3f, loss %.1f%%' % (
                security, price, loss_pct * 100))
            return

    # === Original signal logic ===
    if price > ma5 > ma20:
        if security not in context.portfolio.positions:
            order_value(security, context.portfolio.available_cash * 0.95)
    elif price < ma5 < ma20:
        if security in context.portfolio.positions:
            order_target(security, 0)
```

### 3.2 Market Filter

```python
def market_open(context):
    # Check the broad market first
    index_hist = attribute_history('000300.XSHG', 20, '1d', ['close'])
    index_ma20 = index_hist['close'].mean()
    index_price = index_hist['close'].iloc[-1]

    # Market below 20-day MA -> go to cash, observe
    if index_price < index_ma20:
        # Liquidate any holdings
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
        return

    # Market is safe -> execute individual stock strategy
    # ...
```

### 3.3 Volume Confirmation

```python
# Golden cross signal + volume confirmation -> more reliable buy signal
hist = attribute_history(security, 25, '1d', ['close', 'volume'])
close_prices = hist['close']
volume = hist['volume']

ma5 = close_prices.tail(5).mean()
ma20 = close_prices.tail(20).mean()
price = close_prices.iloc[-1]

avg_vol_20 = volume.tail(20).mean()
current_vol = volume.iloc[-1]

# Volume confirmation: today's volume > 1.5x the 20-day average volume
if price > ma5 > ma20 and current_vol > avg_vol_20 * 1.5:
    if security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.95)
```

### 3.4 MACD Confirmation

```python
from eqlib import utils

hist = attribute_history(security, 40, '1d', ['close'])
close_prices = hist['close']

ma5 = close_prices.tail(5).mean()
ma20 = close_prices.tail(20).mean()
price = close_prices.iloc[-1]

# MACD golden cross
dif, dea, macd_hist = utils.macd(close_prices, fast=12, slow=26, signal=9)
macd_golden_cross = dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]

# Dual confirmation: MA golden cross + MACD golden cross
if price > ma5 > ma20 and macd_golden_cross:
    if security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.95)
```

### 3.5 ATR Trailing Stop-Loss

A fixed-percentage stop-loss has the drawback of being "one size fits all" — high-volatility stocks are easily stopped out prematurely. An ATR trailing stop dynamically adjusts based on volatility:

```python
from eqlib import utils

hist = attribute_history(security, 30, '1d', ['high', 'low', 'close'])
high = hist['high']
low = hist['low']
close = hist['close']

price = close.iloc[-1]

# Calculate 14-day ATR
atr14 = utils.atr(high, low, close, 14).iloc[-1]

if security in context.portfolio.positions:
    pos = context.portfolio.positions[security]
    # Dynamic stop price = cost - 2x ATR
    stop_price = pos.avg_cost - 2 * atr14
    if price < stop_price:
        order_target(security, 0)
        log.info('ATR stop-loss %s @ %.3f, ATR=%.3f' % (security, price, atr14))
```

---

## 4. Portfolio Optimization

With multiple stocks, use `portfolio_optimizer` to allocate weights. Function signature:

```python
portfolio_optimizer(securities, prices, target=None, constraints=None,
                    bounds=None, default_range=(0.0, 1.0), ftol=1e-9,
                    return_none_if_fail=True)
```

| Parameter | Description |
|-----------|-------------|
| `securities` | List of stock codes |
| `prices` | **Price** DataFrame (index=dates, columns=stock codes) — returns are computed internally via `pct_change`; do not pass a returns matrix |
| `target` | Objective: `MinVariance()` (default), `MaxSharpe(risk_free_rate=0.03)`, or `RiskParity()` |
| `bounds` | One `Bound(lower, upper)` per stock; defaults to `default_range` for all |
| `constraints` | dict supporting `max_weight`, `min_weight` |
| `return_none_if_fail` | Default True: return `None` on solver failure instead of raising |

The return value is a `pd.Series` (stock code → weight, summing to 1), or `None` on failure. Requirements: at least 2 securities and at least 20 valid daily returns, otherwise it returns `None`. The covariance matrix uses Ledoit-Wolf shrinkage, which is more stable than the sample covariance on small samples.

### 4.1 Minimum Variance Portfolio

```python
import pandas as pd
from eqlib import get_price, portfolio_optimizer, MinVariance, Bound

SECURITIES = ['601398', '600519', '000858']

# get_price with a list returns a {code: DataFrame} dict
frames = get_price(SECURITIES, start_date='2023-01-01', end_date='2024-12-31')
prices = pd.DataFrame({sec: df['close'] for sec, df in frames.items()}).dropna()

weights = portfolio_optimizer(
    SECURITIES, prices,
    target=MinVariance(),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),  # 5%–40% per stock
)

if weights is None:
    print("Optimization failed: insufficient data or no convergence")
else:
    print({k: round(v, 3) for k, v in weights.items()})
```

### 4.2 Maximum Sharpe Portfolio

```python
from eqlib import MaxSharpe

# Risk-free rate defaults to 0.03 (3%), matching the backtest metrics convention
weights = portfolio_optimizer(
    SECURITIES, prices,
    target=MaxSharpe(risk_free_rate=0.03),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),
)
```

### 4.3 Risk Parity Portfolio

```python
from eqlib import RiskParity

# Each holding contributes equally to total portfolio risk
weights = portfolio_optimizer(
    SECURITIES, prices,
    target=RiskParity(),
    bounds=[Bound(0.05, 0.40)] * len(SECURITIES),
)
```

### 4.4 Using Optimized Weights in a Strategy

```python
# Module-level constants: weights come from the portfolio_optimizer output above
# (values shown here are for demonstration)
SECURITIES = ['601398', '600519', '000858']
WEIGHTS = [0.34, 0.33, 0.33]

def monthly_rebalance(context):
    """Rebalance monthly."""
    total_value = context.portfolio.total_value

    for sec, weight in zip(SECURITIES, WEIGHTS):
        target_value = total_value * weight
        order_target_value(sec, target_value)

def initialize(context):
    set_benchmark('000300.XSHG')
    run_monthly(monthly_rebalance, day_of_month=1, time='every_bar')
```

---

## 5. Attribution Analysis

After the backtest is complete, gain deeper insight into the sources of returns:

```python
from eqlib import analyze_returns, brinson_attribution, simple_factor_analysis

# Comprehensive risk metrics
metrics = analyze_returns(result, risk_free_rate=0.03)
print("Sharpe ratio:   %.2f" % metrics['sharpe_ratio'])
print("Max drawdown:   %.2f%%" % (metrics['max_drawdown'] * 100))
print("Alpha:          %.4f" % metrics['alpha'])

# Brinson attribution
attr = brinson_attribution(result)
print("Allocation effect: %.4f" % attr['allocation_effect'])
print("Selection effect:  %.4f" % attr['selection_effect'])

# Simplified factor analysis
ff = simple_factor_analysis(result)
print("Market Beta:       %.3f" % ff['market_beta'])
print("Annualized Alpha:  %.4f" % ff['alpha_annual'])
```

**How to use attribution results to improve your strategy:**

| Situation | Meaning | Improvement Direction |
|-----------|---------|-----------------------|
| Selection effect > 0, Allocation effect < 0 | Stocks were right but sector/timing was wrong | Strengthen market/sector judgment |
| Selection effect < 0, Allocation effect > 0 | Sector was right but individual stocks were wrong | Improve stock screening criteria |
| Alpha > 0 | Generating excess returns | Strategy is effective |
| Beta > 1.5 | Much more volatile than the market | Consider reducing position size or diversifying |
| Beta < 0.5 | Weak correlation with the market | May be an independent strategy |

> When benchmark data is unavailable, `alpha`, `beta`, and `information_ratio` are `NaN` (shown as `N/A` in reports); the Alpha/Beta rows of the table above then don't apply.

---

## 6. Building More Robust Strategies

### 6.1 Strategy Checklist

Before moving a strategy to paper trading, check each item:

- [ ] Backtest >= 1 year, covering different market environments
- [ ] Sharpe ratio > 1
- [ ] Max drawdown < 20% (within acceptable range)
- [ ] Outperformed the CSI 300 over the same period
- [ ] Parameters are stable (neighboring parameters produce similar results)
- [ ] Out-of-sample data validation passed
- [ ] Stop-loss has been set
- [ ] Trading costs are reasonably configured
- [ ] Liquidity checked (sufficient trading volume)
- [ ] T+1 settlement restriction checked (shares bought today cannot be sold today)
- [ ] No look-ahead bias
- [ ] Code uses `log.info` to record key operations

### 6.2 Multi-Strategy Combination

```python
# Strategy A: Dual MA trend following
# Strategy B: RSI mean reversion
# Each strategy uses 50% of capital

def initialize(context):
    g.strategy_a_capital_pct = 0.5

    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(run_strategy_a, time='every_bar')
    run_daily(run_strategy_b, time='every_bar')

def run_strategy_a(context):
    # Use 50% of available capital
    # ... dual MA logic ...
    pass

def run_strategy_b(context):
    # Use 50% of available capital
    # ... RSI mean reversion logic ...
    pass
```

### 6.3 Parameter Externalization

Good strategies keep all parameters in one place for easy adjustment:

```python
# Centralized strategy parameter management
PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    'stop_loss_pct': 0.08,
    'position_pct': 1.0,
    'min_volume_ratio': 1.5,
    'atr_stop_multiplier': 2.0,
}

def market_open(context):
    p = PARAMS
    # ... use p['fast_period'], p['stop_loss_pct'], etc. ...
```

---

## 7. Next Steps

After completing strategy optimization, the next step is to validate with real-time market data:

- **[Tutorial 04: Paper Trading to Live Trading](04-live-trading.md)** — Validate strategy with paper trading, then export to PTrade/QMT for live deployment
- **[Tutorial 05: RSI Mean Reversion Strategy](05-rsi-mean-reversion.md)** — Learn a fundamentally different strategy approach from dual moving averages
- **[Tutorial 06: Sector Rotation Strategy](06-sector-rotation.md)** — Build an alpha strategy leveraging A-share sector rotation dynamics
- **[Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md)** — Systematic multi-factor quantitative stock selection methods
- **[Example 19: Support/Resistance Portfolio Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** — A complete multi-stock portfolio strategy case study with pre-generated backtest reports (HTML/PNG/Markdown/JSON) for direct review of strategy performance
