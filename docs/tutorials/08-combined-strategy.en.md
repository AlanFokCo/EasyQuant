# Tutorial 08: All-Weather Alpha Combined Strategy

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Integrate stock selection, rotation, and risk management modules into a runnable combined strategy, connected to backtesting and paper trading |
    | **Estimated time** | 2+ hours (can be read in sections) |
    | **Prerequisites** | Tutorials 03-07 should be read at least once; code at [`examples/20_all_weather_alpha/`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md) |

> This tutorial integrates all strategy techniques from previous tutorials and examples into a complete, production-ready combined strategy.
> We will walk through the design rationale, mathematical formulas, and code implementation of each component step by step,
> and provide complete backtesting and paper trading code that can be run directly.

**Note:** Scripts in the [`examples/20_all_weather_alpha/README.md`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md) directory add the subdirectory to `sys.path` to import `combined_strategy`, which is independent of how `eqlib` is installed.

---

## Table of Contents

1. [Strategy Overview](#1-strategy-overview)
2. [Layer 1: Multi-Factor Stock Selection (Z-Score Normalization)](#2-layer-1-multi-factor-stock-selection-z-score-normalization)
3. [Layer 2: Sector Rotation Score Boost](#3-layer-2-sector-rotation-score-boost)
4. [Layer 3: Technical Indicator Entry / Exit Signals](#4-layer-3-technical-indicator-entry--exit-signals)
5. [Layer 4: Risk Management and Position Control](#5-layer-4-risk-management-and-position-control)
6. [Lifecycle Callback Integration](#6-lifecycle-callback-integration)
7. [Portfolio Risk Monitoring (PortfolioRiskMonitor)](#7-portfolio-risk-monitoring-portfolioriskmonitor)
8. [Complete Strategy Code Description](#8-complete-strategy-code-description)
9. [Backtest Validation](#9-backtest-validation)
10. [Paper Trading Deployment](#10-paper-trading-deployment)
11. [Strategy Interpretation and Improvement](#11-strategy-interpretation-and-improvement)

---

## 1. Strategy Overview

### 1.1 Design Goals

The "All-Weather Alpha" strategy is designed to:

- **Robustness**: Operate effectively in bull markets, bear markets, and sideways markets without depending on a single market condition
- **Multi-dimensional**: Simultaneously leverage fundamentals (factor scores), technicals (RSI / MACD / Bollinger Bands), and structural factors (support/resistance levels)
- **Controlled risk**: Multi-layer stop-loss (hard stop + ATR trailing stop), strict position caps
- **Explainability**: Every buy/sell decision has a traceable quantitative rationale

### 1.2 Strategy Architecture

```
┌──────────────────────────────────────────────────────────┐
│         Every Monday — Multi-Factor + Sector Rotation    │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Momentum │  │ Volume   │  │ Reversal │  │ Volat. │  │
│  │  (35%)   │  │  (30%)   │  │  (15%)   │  │ (20%)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       └──────────────┴─────────────┴─────────────┘       │
│                    Z-score normalization                   │
│                 ↓ Combine into composite score            │
│           Sector momentum score boost (+10%)              │
│                 ↓ Rank and select Top 5                   │
└──────────────────────────────────────────────────────────┘
                          ↓ g.selected_stocks

┌──────────────────────────────────────────────────────────┐
│            Daily — Technical Indicator Entry / Exit      │
│                                                          │
│  Entry conditions (C + D + E must all be met):           │
│    C. Oversold signal: RSI < 35  OR  price < Boll lower │
│                OR  price touches Donchian lower          │
│    D. Confirmation: MACD golden cross OR near support   │
│    E. Volume confirmation: vol >= 1.2x 20-day avg vol   │
│                                                          │
│  Exit conditions (any one triggers a sell):              │
│    1. Hard stop: loss > 8%                              │
│    2. ATR trailing stop                                 │
│    3. Bollinger upper band + RSI overbought             │
│    4. MACD death cross                                  │
│    5. Donchian upper band breakout                      │
│    6. Near resistance + RSI overbought                  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    Lifecycle Callbacks                    │
│  before_trading_start → Check ST stocks, log pre-market │
│  after_trading_end    → Log post-close portfolio snapshot│
└──────────────────────────────────────────────────────────┘
```

### 1.3 Stock Pool (12 stocks, covering 8 sectors)

| Code | Name | Sector | Selection Rationale |
|------|------|--------|-------------------|
| 601398 | ICBC | Banking | Large-cap blue chip, low volatility, suitable for mean reversion |
| 600519 | Kweichow Moutai | Baijiu (White Liquor) | High-ROE consumer leader, strong long-term trend |
| 002594 | BYD | New Energy | New energy sector leader, high volatility but clear trend |
| 601857 | PetroChina | Oil & Gas | Energy sector, driven by commodity prices |
| 601088 | China Shenhua | Coal | High-dividend defensive, negatively correlated with oil |
| 601390 | China Railway | Infrastructure | Policy-driven, correlated with economic cycles |
| 600276 | Hengrui Medicine | Pharma | Innovative drug leader, strong counter-cyclical properties |
| 000333 | Midea Group | Home Appliances | Manufacturing leader, stable ROE |
| 600916 | China Gold | Gold | Safe-haven asset, negatively correlated with equities |
| 000858 | Wuliangye | Baijiu (White Liquor) | Correlated with Moutai but at a relative discount |
| 601318 | Ping An | Insurance | Financial sector, low valuation |
| 600887 | Yili Group | Consumer Staples | Essential consumer, strong downside protection |

> **Sector diversification principle**: Stocks from different sectors are selected so that under any market condition, some stocks are likely in a strong position.

---

## 2. Layer 1: Multi-Factor Stock Selection (Z-Score Normalization)

### 2.1 Why Multi-Factor Selection

A single factor (e.g., momentum only) is prone to failure when market style rotates. Multi-factor models integrate multiple dimensions to maintain stock selection capability across different market environments (see [Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md)).

### 2.2 Four Factor Definitions

#### Factor 1: Momentum Factor (Weight 35%)

```
momentum = (P_t / P_{t-20}) - 1
```

- **Economic rationale**: The price change over the last 20 trading days. Higher momentum means a stronger recent trend.
- **Highest weight** rationale: The A-share market exhibits clear "chase the rise, sell the fall" behavior; the momentum effect is valid in the short to medium term.

```python
momentum = (close.iloc[-1] / close.iloc[-20]) - 1.0
```

#### Factor 2: Volume Surge Factor (Weight 30%)

```
volume_ratio = mean(vol[-5:]) / mean(vol[-20:])
```

- **Economic rationale**: The ratio of recent trading volume to the historical average volume.
  A volume ratio > 1 indicates rising capital attention, making price increases more reliable.

```python
vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()
```

#### Factor 3: Short-Term Reversal Correction (Weight 15%)

```
reversal = -((P_t / P_{t-5}) - 1)
```

- **Economic rationale**: The negated 5-day return.
  Stocks that have risen too much in the short term (high chase risk) get a low factor value;
  stocks with a slight pullback get a high factor value (safer entry point).
- This is a **complement to the momentum factor**: it avoids selecting stocks that have already risen significantly and offer poor value.

```python
reversal = -((close.iloc[-1] / close.iloc[-5]) - 1.0)
```

#### Factor 4: Low Volatility Factor (Weight 20%)

```
neg_volatility = -std(daily_returns[-20:])
```

- **Economic rationale**: Low-volatility stocks carry less risk for the same return (low-volatility premium).
  The negative sign is used because lower volatility should yield a higher factor value.

```python
daily_rets = close.pct_change().dropna().tail(20)
neg_vol    = -daily_rets.std()
```

### 2.3 Z-Score Normalization

Different factors have different units (momentum is a percentage, volume ratio is a multiplier). Directly weighting them would allow one factor to dominate. Z-score normalization eliminates unit differences:

```
z_i = (x_i - mu) / sigma

Where:
  x_i   = raw factor value for stock i
  mu    = mean of that factor across all stocks
  sigma = standard deviation of that factor across all stocks (sample std, ddof=1)
```

```python
def _zscore_normalize(values_dict):
    vals = list(values_dict.values())
    mu   = statistics.mean(vals)
    sig  = statistics.stdev(vals) or 1e-9
    return {k: (v - mu) / sig for k, v in values_dict.items()}
```

### 2.4 Composite Score Combination

```
score = 0.35 * z_momentum
      + 0.30 * z_volume
      + 0.15 * z_reversal
      + 0.20 * z_neg_volatility
```

Rank by `score` from high to low and select the Top 5 stocks.

---

## 3. Layer 2: Sector Rotation Score Boost

Following [Tutorial 06: Sector Rotation](06-sector-rotation.md), we add a sector rotation dimension on top of multi-factor scores.

### 3.1 Sector Momentum Calculation

For each sector, take one representative stock and calculate its 10-day return:

```
sector_momentum = (P_{sector,t} / P_{sector,t-10}) - 1
```

Apply Z-score normalization to obtain relative strength across sectors.

### 3.2 Sector Boost

```
final_score = factor_score + 0.10 * sector_z_score
```

**Why only 10% boost weight:**
Sector signals are typically "lagging" compared to individual stock factors (a sector is only observable as strong after it has already risen significantly). Too high a weight leads to chasing. A 10% boost gives sector signals some influence without dominating the entire ranking.

---

## 4. Layer 3: Technical Indicator Entry / Exit Signals

The multi-factor model determines "which stocks to hold," but doesn't tell us "when is the best time to buy."
Technical indicators handle the "precise entry timing" job.

### 4.1 RSI Mean Reversion Entry (Tutorial 05: RSI Mean Reversion)

**Formula:**
```
Delta_P_t = P_t - P_{t-1}
AvgGain_t = EMA(max(Delta_P_t, 0), N=14)
AvgLoss_t = EMA(max(-Delta_P_t, 0), N=14)
RS        = AvgGain / AvgLoss
RSI       = 100 - 100 / (1 + RS)
```

**Entry condition:** `RSI < 35` (oversold zone)

**Logic:** RSI < 35 indicates that recent downward pressure has significantly exceeded upward pressure. The market may be overly pessimistic, presenting a rebound opportunity.

```python
rsi_series = utils.rsi(close, period=14)
oversold   = rsi_series.iloc[-1] < 35
```

### 4.2 Bollinger Bands Mean Reversion (Example 15)

**Formula:**
```
Middle = MA(close, N=20)
Upper  = Middle + 2 * std(close, N=20)
Lower  = Middle - 2 * std(close, N=20)
```

**Entry condition:** `price <= Lower` (price breaks below the lower band, statistically oversold)

**Exit condition:** `price >= Upper AND RSI >= 65` (statistically overbought)

```python
bb_upper, bb_mid, bb_lower = utils.boll(close, period=20, num_std=2.0)
buy_signal  = price <= bb_lower.iloc[-1]
sell_signal = price >= bb_upper.iloc[-1] and rsi >= 65
```

### 4.3 MACD Trend Confirmation (Example 16)

**Formula:**
```
EMA_fast = EMA(close, N=12)
EMA_slow = EMA(close, N=26)
DIF      = EMA_fast - EMA_slow
DEA      = EMA(DIF, N=9)           # Signal line
Histogram = 2 * (DIF - DEA)
```

**Golden cross (bullish signal):** DIF crosses above DEA from below
```python
macd_golden = dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]
```

**Death cross (bearish signal):** DIF crosses below DEA from above
```python
macd_death = dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]
```

### 4.4 ATR Trailing Stop (Examples 16 / 19)

**ATR Formula:**
```
TR_t = max(High_t - Low_t,
           |High_t - Close_{t-1}|,
           |Low_t  - Close_{t-1}|)
ATR  = EMA(TR, N=14)
```

**Trailing stop price:**
```
trailing_stop = max(close) since entry - 2.5 * ATR
```

Sell when `current_price < trailing_stop`.

**Advantage**: The trailing stop moves up as the price rises, protecting profits while allowing normal price fluctuations. Compared to a fixed-percentage stop, the ATR stop dynamically adjusts to actual market volatility.

```python
atr_values    = utils.atr(high, low, close, 14)
current_atr   = atr_values.iloc[-1]
trailing_stop = highest_since_buy - 2.5 * current_atr
```

### 4.5 Support/Resistance Confirmation (Example 19)

Support and resistance levels are identified by detecting swing high/low clustering in historical prices:

```python
sr = utils.support_resistance_levels(
    high, low, close,
    lookback=60,       # Look back 60 bars
    tolerance=0.025,   # 2.5% tolerance
)
nearest_support    = sr.get("nearest_support")
nearest_resistance = sr.get("nearest_resistance")
```

**Near-support entry condition:**
```
dist_to_support = (price - nearest_support) / price < 2.5%
```

That is, price is within 2.5% of a support level, considered "near support."

**Near-resistance exit condition:**
```
dist_to_resistance = (nearest_resistance - price) / price < 2.5%
```

### 4.6 Volume Confirmation (Example 16)

**Formula:**
```
vol_ratio = current_volume / mean(volume[-20:])
```

**Confirmation condition:** `vol_ratio >= 1.2`

**Logic:** Price declining to a support level accompanied by increasing volume suggests that capital is absorbing selling pressure, and the decline may be ending. Example 16 uses a 1.5x threshold; this strategy uses 1.2x (slightly looser, since multiple other conditions already serve as filters).

### 4.7 Donchian Channel (Example 19)

**Formula:**
```
DC_upper = max(high[-20:])    # 20-day highest price
DC_lower = min(low[-20:])     # 20-day lowest price
```

- **Entry signal**: `price <= DC_lower` (price makes a 20-day low, oversold)
- **Exit signal**: `price >= DC_upper` (price makes a 20-day high, take profits)

---

## 5. Layer 4: Risk Management and Position Control

### 5.1 Entry Condition Composite Logic

```
Entry = A AND B AND C AND D AND E

A. Stock is in this week's Top-5 selection list
B. Current position count < 5 (room in the portfolio)
C. Oversold signal (RSI < 35  OR  price <= Bollinger lower  OR  price <= Donchian lower)
D. Confirmation signal (MACD golden cross  OR  price near support)
E. Volume confirmation (today's volume >= 1.2x 20-day avg volume)
```

**Benefits of multiple AND conditions:**
Reduces false signals. Each individual technical signal has roughly a 50% false signal rate; three independent signals triggering simultaneously theoretically reduces the false signal rate to 12.5%.

### 5.2 Exit Condition Priority

```
Exit = Any of the following conditions met (by priority, high to low):

1. Hard stop: loss_pct < -8%         <- Unconditional execution; capital preservation first
2. ATR trailing stop                 <- Dynamic risk control
3. Bollinger upper + RSI >= 65       <- Technical profit-taking
4. MACD death cross                  <- Trend reversal signal
5. Donchian upper band               <- Price pullback after new high
6. Near resistance + RSI >= 65       <- Positional profit-taking
```

### 5.3 Position Control

**Equal-weight allocation:**
```
per_stock_value = min(
    total_value * 20%,          # Per-stock cap
    available_cash / num_buys,  # Even split across candidates
)
```

**Maximum position count**: `1 / 20% = 5` stocks.

**Advantage**: Equal-weight allocation avoids excessive concentration risk. Even if one stock triggers a stop-loss, the maximum loss is only 20% x 8% = 1.6% of total capital.

---

## 6. Lifecycle Callback Integration

Following [Example 07](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/07_lifecycle.py), the strategy registers two lifecycle callbacks.

### 6.1 Pre-Market (before_trading_start)

```python
def _before_market_open(context):
    # Log current position state
    log.info("PRE-MARKET | total=%.2f | cash=%.2f | positions=%d"
             % (...))

    # Check for ST (Special Treatment) stocks (suspension, cap changes, etc.)
    st_map    = get_extras("is_st", security_list=universe)
    st_stocks = [c for c, flag in st_map.items() if flag]
    if st_stocks:
        log.warning("ST stocks: %s" % st_stocks)
```

### 6.2 Post-Market (after_trading_end)

```python
def _after_market_close(context):
    pnl_pct = (portfolio.total_value - portfolio.starting_cash) / portfolio.starting_cash
    record(
        total_value=portfolio.total_value,
        cash=portfolio.available_cash,
        num_holdings=held,
        pnl_pct=pnl_pct,
    )
```

`record()` saves data into the backtest results for `generate_chart` to plot.

---

## 7. Portfolio Risk Monitoring (PortfolioRiskMonitor)

Beyond per-stock stop-losses and position control, a combined strategy also requires **portfolio-level** risk monitoring. `PortfolioRiskMonitor` provides a one-stop portfolio risk dashboard covering concentration, volatility, drawdown, and other key dimensions.

### 7.1 Initialization and Daily Checks

Create the monitor instance in `initialize` and run daily checks in the `before_trading_start` callback:

```python
from eqlib import PortfolioRiskMonitor

def initialize(context):
    # ... other init code ...
    context.risk_monitor = PortfolioRiskMonitor(
        max_single_weight=0.20,    # Max single stock weight 20%
        max_sector_weight=0.40,    # Max single sector weight 40%
        max_drawdown_threshold=0.15,  # Drawdown alert threshold 15%
    )


def _before_market_open(context):
    # Daily risk check (executed before market open)
    report = context.risk_monitor.daily_check(context.portfolio)

    if report['alerts']:
        for alert in report['alerts']:
            log.warning("RISK ALERT: %s" % alert)

    # If drawdown exceeds threshold, pause buying for the day
    if report.get('drawdown_breached'):
        context.pause_buying = True
        log.warning("Drawdown %.2f%% exceeded threshold, pausing buys"
                     % (report['current_drawdown'] * 100))
    else:
        context.pause_buying = False
```

### 7.2 North-Bound Capital Regime Signal

North-bound capital (north-capital) flow can serve as a portfolio-level **regime signal** in `before_trading_start`, dynamically adjusting position limits based on market sentiment:

```python
from eqlib import get_north_money_flow

def _check_north_regime(context):
    """
    North-bound capital regime signal: determines market sentiment regime
    based on net inflows over the last 5 days.

    Returns:
        str: 'risk_on' (bullish), 'neutral', 'risk_off' (bearish)
    """
    df = get_north_money_flow(days=5)
    if df is None or df.empty:
        return 'neutral'

    net_5d = df['north_net'].sum()        # 5-day cumulative net inflow (100M CNY)
    avg_daily = net_5d / len(df)

    if avg_daily > 20:                    # Daily avg net inflow > 2B CNY
        return 'risk_on'
    elif avg_daily < -20:                 # Daily avg net outflow > 2B CNY
        return 'risk_off'
    else:
        return 'neutral'


def _before_market_open(context):
    # ... other checks ...

    regime = _check_north_regime(context)
    log.info("North capital regime: %s" % regime)

    # Adjust overall position cap based on regime
    regime_caps = {
        'risk_on':  1.0,    # Bullish: full position
        'neutral':  0.8,    # Neutral: 80% position
        'risk_off': 0.5,    # Bearish: 50% position
    }
    context.max_position_pct = regime_caps.get(regime, 0.8)
```

Combining the north-bound capital regime signal with `PortfolioRiskMonitor` enables **top-down** risk control in a combined strategy: first assess the market environment (regime signal), then monitor portfolio health (risk dashboard), and finally execute individual stock buy/sell signals.

---

## 8. Complete Strategy Code Description

### 8.1 File Structure

```
examples/20_all_weather_alpha/
├── combined_strategy.py    # Complete strategy module (importable, modifiable)
├── run_backtest.py         # Backtest runner script (directly runnable)
├── run_paper_trade.py      # Paper trading runner script (directly runnable)
└── README.md               # Tutorial summary
```

### 8.2 Strategy Module Structure

```python
# combined_strategy.py structure

STOCK_POOL     = [...]   # 12 stocks
SECTOR_MAP     = {...}   # Stock -> sector mapping
SECTOR_REPRES. = {...}   # Sector representative stocks (for sector momentum calc)

# Parameter configuration (modify as needed, using module-level constants)
TOP_N          = 5
RSI_OVERSOLD   = 35
ATR_MULTIPLIER = 2.5
...

# Core functions
_zscore_normalize(values_dict)          # Z-score normalization utility
_compute_factors(code)                  # Compute four factors for a single stock
_score_sector_momentum()                # Sector momentum scoring
rank_stocks_weekly(context)             # Weekly stock ranking
_compute_indicators(code)              # Compute technical indicators
_check_sell(context, code, ind)        # Exit logic
_check_buy(context, code, ind)         # Entry logic
_before_market_open(context, data=None)    # Lifecycle: pre-market
_after_market_close(context, data=None)    # Lifecycle: post-market
weekly_rebalance(context)              # Monday rebalance
daily_trading(context)                 # Daily signal processing

initialize(context)                    # Strategy entry point (required)
```

### 8.3 Key Parameter Reference

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `TOP_N` | 5 | Number of stocks selected per week |
| `W_MOMENTUM` | 0.35 | Momentum factor weight |
| `W_VOLUME` | 0.30 | Volume factor weight |
| `W_REVERSAL` | 0.15 | Reversal correction weight |
| `W_VOLATILITY` | 0.20 | Low volatility weight |
| `RSI_OVERSOLD` | 35 | RSI oversold threshold |
| `RSI_OVERBOUGHT` | 65 | RSI overbought threshold |
| `BOLL_PERIOD` | 20 | Bollinger Band period |
| `ATR_MULTIPLIER` | 2.5 | ATR trailing stop multiplier |
| `SR_LOOKBACK` | 60 | Support/resistance lookback (days) |
| `SR_TOLERANCE` | 0.025 | Support/resistance tolerance (2.5%) |
| `MAX_SINGLE_PCT` | 0.20 | Max single stock position (20%) |
| `HARD_STOP_PCT` | 0.08 | Hard stop-loss threshold (8%) |
| `VOL_CONFIRM_RATIO` | 1.2 | Volume confirmation multiplier |

---

## 9. Backtest Validation

### 9.1 Run Backtest Directly

```bash
# Run from the project root directory
python examples/20_all_weather_alpha/run_backtest.py
```

**Backtest parameters:**
- Period: 2022-01-01 to 2024-12-31 (3 years)
- Starting capital: 500,000 CNY
- Benchmark: CSI 300 (000300.XSHG)
- Stock pool: 12 stocks (8 sectors)

**Output reports:**
- `reports/backtest_<timestamp>.png`  — Equity curve chart
- `reports/backtest_<timestamp>.html` — Interactive HTML report
- `reports/backtest_<timestamp>.md`   — Markdown summary
- `reports/backtest_<timestamp>.json` — Complete backtest data

### 9.2 Backtest Code Walkthrough

```python
# run_backtest.py core snippet

import sys, os
sys.path.insert(0, ".")                          # Project root
sys.path.insert(0, "examples/20_all_weather_alpha")  # Strategy directory

from combined_strategy import initialize, STOCK_POOL
from eqlib import run_strategy, analyze_returns

result = run_strategy(
    initialize_func=initialize,     # Strategy entry function
    start_date="2022-01-01",
    end_date="2024-12-31",
    starting_cash=500_000,
    benchmark="000300.XSHG",
    securities=STOCK_POOL,          # Preload data to speed up backtest
    report_dir="reports",
)

# Performance analysis
metrics = analyze_returns(result, risk_free_rate=0.03)
print("Sharpe ratio : %.4f" % metrics["sharpe_ratio"])
print("Max drawdown : %.2f%%" % (metrics["max_drawdown"] * 100))
print("Win rate     : %.2f%%" % (metrics["win_rate"] * 100))
```

### 9.3 Backtest Results Interpretation Guide

After the run completes, focus on these key metrics:

| Metric | Meaning | Reference Value |
|--------|---------|----------------|
| **Sharpe ratio** | Excess return per unit of volatility risk | > 1.0 is good, > 2.0 is excellent |
| **Max drawdown** | Peak-to-trough decline | < 20% is acceptable |
| **Calmar ratio** | Annualized return / max drawdown | > 1.0 is good |
| **Alpha** | Excess return relative to benchmark | > 0 means the strategy created value |
| **Beta** | Correlation with the broad market | < 1.0 means the strategy is less volatile than the market |
| **Win rate** | Profitable trades / total trades | > 50% is favorable |

### 9.4 Using Local Data to Accelerate (Recommended)

Download and save data on the first run; subsequent runs read from local storage:

```bash
# Step 1: Pre-download data (one-time only)
python examples/06_local_data.py --download-all

# Step 2: Run backtest using local data (faster)
# In run_backtest.py, modify:
# result = run_strategy(..., use_local=True)
```

---

## 10. Paper Trading Deployment

### 10.1 Run Paper Trading

```bash
# Default settings (capital 500,000 CNY, refresh quotes every 60 seconds)
python examples/20_all_weather_alpha/run_paper_trade.py

# Custom parameters
python examples/20_all_weather_alpha/run_paper_trade.py \
    --cash 200000 \
    --interval 120

# Press Ctrl+C to stop
```

### 10.2 Paper Trading Notes

1. **Trading hours**: Recommended to run during 9:30-15:00 trading hours for real-time quotes
2. **Signal frequency**: The strategy triggers once per bar each day, with additional stock selection on Mondays
3. **Network requirements**: Requires network access to the akshare data source
4. **Log output**: All buy/sell decisions have detailed log entries for easy monitoring

### 10.3 Deploying to PTrade/QMT

Following [Tutorial 04: Paper Trading to Live Trading](04-live-trading.md) and [Example 12](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/12_paper_trade.py),
you can export this strategy to PTrade/QMT format:

```python
from eqlib.ptrade_adapter import export_ptrade_script

# Generate a QMT-compatible strategy file
export_ptrade_script(
    initialize_func=initialize,
    output_path="combined_strategy_qmt.py",
)
```

---

## 11. Strategy Interpretation and Improvement

### 11.1 Suitable Market Environments

| Market Environment | Expected Performance | Reason |
|-------------------|---------------------|--------|
| **Sideways/range-bound** | Good | RSI + Bollinger Band mean reversion dominates |
| **Bull market** | Good | Momentum factor + MACD trend following is effective |
| **Bear market** | Weaker | Stocks decline broadly; buy signals struggle to profit; stops triggered frequently |
| **Unidirectional decline** | Manageable | Hard stop + ATR stop limits maximum loss |

### 11.2 Possible Improvements

**1. Add a Market Filter (highest recommended priority)**

Following [Tutorial 03: Strategy Optimization & Improvement](03-optimization.md), pause buying when the broad market trend is downward:

```python
def _market_is_bullish():
    """Check whether the broad market is in an uptrend (5-day MA > 20-day MA)."""
    hist = attribute_history("000300.XSHG", 30, "1d", ["close"])
    if hist.empty:
        return True
    ma5  = hist["close"].tail(5).mean()
    ma20 = hist["close"].mean()
    return ma5 > ma20
```

Add to `_check_buy()`:
```python
if not _market_is_bullish():
    return False, "Market filter: index below MA20"
```

**2. Expand the Stock Pool**

Expand the stock pool from 12 to 20-30 stocks, covering more sectors,
and increase `top_n = 8` to improve diversification.

**3. Dynamically Adjust Factor Weights**

Increase momentum factor weight (to 50%) in bull markets, and low-volatility factor weight (to 35%) in sideways markets:

```python
def _get_factor_weights():
    """Dynamically adjust factor weights based on market state."""
    if _market_is_bullish():
        return {"momentum": 0.50, "volume": 0.25, "reversal": 0.10, "volatility": 0.15}
    else:
        return {"momentum": 0.25, "volume": 0.25, "reversal": 0.20, "volatility": 0.30}
```

**4. Monthly Financial Factor Rebalancing**

Add monthly PE/PB financial factors (see [Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md) Section 5), but only as auxiliary references:

```python
def _compute_pe_factor(code):
    val = get_valuation(code)
    if val and val.get("pe") and 0 < val["pe"] < 80:
        return 1.0 / val["pe"]
    return None
```

**5. Kelly Criterion Position Sizing**

Dynamically adjust position size based on historical win rate (see Example 08):

```python
from eqlib.utils import kelly_criterion
win_rate = historical_win_rate   # Extract from backtest results
avg_win  = historical_avg_win
avg_loss = historical_avg_loss
kelly_f  = kelly_criterion(win_rate, avg_win, avg_loss)
# Use Half-Kelly to reduce risk
position_pct = min(kelly_f * 0.5, g.max_single_pct)
```

### 11.3 Overfitting Risk Warning

> Warning: **Important Notice**
>
> The parameters in this strategy (such as RSI thresholds 35/65, ATR multiplier 2.5x, factor weights, etc.) are reasonable defaults based on quantitative research literature
> and A-share market characteristics, and are **not optimal parameters obtained through extensive backtest optimization**.
>
> Best practices to avoid overfitting:
> 1. **Out-of-sample testing**: Only use 2020-2022 data for parameter tuning; validate with 2023-2024 data
> 2. **Parameter stability**: Slightly change parameters (e.g., RSI threshold from 35 to 33 or 37). If returns change dramatically, the parameters are not robust enough
> 3. **Look-ahead bias check**: Ensure no future data is used (`attribute_history` always looks at history only)

---

## Further Reading

| Tutorial | Related Content |
|----------|----------------|
| [Tutorial 05: RSI Mean Reversion](05-rsi-mean-reversion.md) | RSI principles, Bollinger Band comparison |
| [Tutorial 06: Sector Rotation](06-sector-rotation.md) | Momentum rotation, multi-dimensional sector scoring |
| [Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md) | Z-score normalization, IC testing |
| [Tutorial 03: Strategy Optimization & Improvement](03-optimization.md) | Market filter, stop-loss design |

| Example | Related Code |
|---------|-------------|
| [Example 15: Bollinger Band Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) | Bollinger mean reversion |
| [Example 16: MACD Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/16_macd_volume.py) | MACD + volume + ATR |
| [Example 17: Multi-Factor Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py) | Momentum + volume stock selection |
| [Example 19: Support/Resistance Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md) | S/R + MACD + ATR complete case |
| [Example 08: Utils Library](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/08_utils_library.py) | All technical indicator demonstrations |

---

## Appendix: One-Click Run Commands

```bash
# After cloning the project, run from the project root:

# Install dependencies (PyPI)
pip install easyquant-eqlib
# Or install from source
# pip install .

# Run backtest (~60 seconds)
python examples/20_all_weather_alpha/run_backtest.py

# View report (open the generated HTML file in a browser)
# Report path: reports/backtest_<timestamp>.html

# Paper trading (requires network; best during trading hours)
python examples/20_all_weather_alpha/run_paper_trade.py
```
