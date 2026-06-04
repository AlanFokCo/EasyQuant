# Tutorial 06: Sector Rotation Strategy

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Understand sector rotation in the A-share market and implement a momentum rotation strategy using the `eqlib` industry API |
    | **Estimated time** | ~90 minutes |
    | **Prerequisites** | [Tutorial 01](01-first-strategy.md); for the industry API see [API Reference](../reference/index.md) |

> The A-share market has a notable characteristic: capital does not chase all sectors simultaneously, but rather "rotates" across different industries. Understanding and leveraging this pattern allows you to build sector rotation strategies that outperform the broader market.

**Industry / Index API:** [API Reference](../reference/index.md)

---

## Table of Contents

1. [What Is Sector Rotation](#1-what-is-sector-rotation)
2. [Characteristics of A-Share Sector Rotation](#2-characteristics-of-a-share-sector-rotation)
3. [Data Foundation: eqlib Industry API](#3-data-foundation-eqlib-industry-api)
4. [Strategy Design: Momentum Rotation](#4-strategy-design-momentum-rotation)
5. [Writing a Sector Rotation Strategy](#5-writing-a-sector-rotation-strategy)
6. [Advanced: Multi-Dimensional Sector Scoring](#6-advanced-multi-dimensional-sector-scoring)
7. [Risks and Pitfalls of Rotation Strategies](#7-risks-and-pitfalls-of-rotation-strategies)
8. [Index Constituent Rotation](#8-index-constituent-rotation)
9. [Next Steps](#9-next-steps)

---

## 1. What Is Sector Rotation

**Sector Rotation** refers to dynamically switching positions across different industries/sectors — increasing exposure to the currently strongest sectors while reducing or exiting sectors that are about to weaken.

### 1.1 Core Logic

```
Identify currently strong sectors
      ↓
Buy representative stocks from those sectors
      ↓
Hold until the strength signal fades
      ↓
Switch to the next strong sector
```

### 1.2 Why Sector Rotation Works

1. **Capital flows follow traceable patterns**: After institutional capital exits an overvalued sector, it flows into the next undervalued sector — a process that typically lasts weeks to months
2. **Momentum effect**: Sectors that perform well in the short term tend to continue performing well (trend persistence)
3. **Correlation diversification**: Different industries are driven by different macro factors; holding multiple sectors simultaneously reduces overall correlation

### 1.3 Comparison with Single-Stock Strategies

| | Single-Stock Strategy | Sector Rotation Strategy |
|--|----------------------|--------------------------|
| **Risk concentration** | High (depends on one stock) | Low (diversified across sectors) |
| **Alpha source** | Stock selection | Sector allocation |
| **Turnover frequency** | Depends on strategy | Usually weekly/monthly |
| **Data requirements** | Single stock history | Industry constituent data |

---

## 2. Characteristics of A-Share Sector Rotation

### 2.1 Policy-Driven

A-share sector rotation is heavily **policy-driven**:
- New energy policies → New energy, energy storage, lithium battery sectors rotate
- Tech self-reliance → Semiconductors, software, domestic substitution
- Consumer stimulus → Baijiu (white liquor), consumer electronics, retail
- Financial policies → Banks, insurance, brokerages

### 2.2 Major A-Share Sectors

```python
# Common broad sectors (industry names returned by eqlib)
sectors = [
    'Banking',       # ICBC, China Merchants Bank
    'Baijiu',        # Moutai, Wuliangye
    'New Energy',    # CATL, BYD
    'Semiconductor', # SMIC, NAURA
    'Pharma',        # Hengrui, Mindray
    'Real Estate',   # Vanke, Poly
    'Insurance',     # Ping An, CPIC
    'Securities',    # CITIC Securities, Guotai Junan
    'Home Appliance',# Midea, Gree
    'Non-Ferrous',   # Zijin Mining, Chalco
]
```

### 2.3 Rotation Patterns (Reference)

```
Economic recovery:   Financials (Banks/Insurance) → Consumer → Tech
Economic overheating: Raw materials → Energy → Industrials
Economic recession:  Healthcare → Utilities → Consumer staples
```

> Warning: These patterns originate from US equity market research and have limited applicability in A-shares. Policy factors are much stronger in A-shares — do not apply them mechanically.

---

## 3. Data Foundation: eqlib Industry API

### 3.1 Get Industry List

```python
from eqlib import get_industry_list

# Get all sector names
industries = get_industry_list()
print(industries[:10])
# Output: ['Baijiu', 'Banking', 'New Energy', 'Semiconductor', 'Pharma', ...]
```

### 3.2 Get Industry Constituents and Quotes

```python
from eqlib import get_industry_stocks

# Get all stock quotes in the Baijiu sector
whitewine_df = get_industry_stocks('Baijiu')
print(whitewine_df.columns.tolist())
# Output: ['code', 'name', 'price', 'pct_change', 'pe', 'pb', 'total_value', ...]

# View top gainers
whitewine_df_sorted = whitewine_df.sort_values('pct_change', ascending=False)
print(whitewine_df_sorted[['name', 'price', 'pct_change']].head())
```

### 3.3 Query a Stock's Industry

```python
from eqlib import get_industry

# Query ICBC's industry
info = get_industry('601390')
print(info)
# Output: {'code': '601390', 'name': 'ICBC', 'industry': 'Banking'}
```

### 3.4 Query Industry Historical Prices

There is no direct "industry index" price. Typically, the **equal-weighted average return of the top N stocks by market cap** within the industry is used to represent industry performance:

```python
from eqlib import get_industry_stocks, attribute_history
import pandas as pd

def get_industry_return(industry_name, lookback=20):
    """Calculate the average return of an industry over the last N days."""
    df = get_industry_stocks(industry_name)
    if df is None or df.empty:
        return 0.0

    # Take the top 5 stocks by market cap as representatives
    top_stocks = df.nlargest(5, 'total_value')['code'].tolist()

    returns = []
    for code in top_stocks:
        hist = attribute_history(code, lookback + 5, '1d', ['close'])
        if hist.empty or len(hist) < lookback:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-lookback]) - 1
        returns.append(ret)

    return sum(returns) / len(returns) if returns else 0.0


# Calculate 20-day returns for each sector
industries = ['Banking', 'Baijiu', 'New Energy', 'Pharma', 'Home Appliance']
for ind in industries:
    ret = get_industry_return(ind, 20)
    print('%-15s: %.2f%%' % (ind, ret * 100))
```

---

## 4. Strategy Design: Momentum Rotation

### Strategy Rules

The simplest sector rotation strategy is based on the **momentum factor**: keep holding the sectors that have risen the most recently; sell and rotate out of sectors that have underperformed.

| Step | Action |
|------|--------|
| 1. Periodic scoring | Every Monday, calculate the recent 20-day return of representative stocks in each candidate sector |
| 2. Ranking & selection | Select the Top N sectors by return |
| 3. Rebalancing | Sell positions not in Top N; equal-weight buy Top N representative stocks |
| 4. Repeat | Score and rebalance again next week |

### Parameter Description

```python
INDUSTRY_POOL = [...]    # Candidate sector list
TOP_N         = 3        # Hold Top N sectors at a time
LOOKBACK      = 20       # Momentum lookback period (trading days)
REBALANCE_DAY = 0        # Rebalance day: 0=Monday
```

---

## 5. Writing a Sector Rotation Strategy

```python
from eqlib import *

# ========== Strategy parameters (module-level constants, not cleared by engine) ==========
# Candidate sectors (select the largest-cap representative stock per sector)
INDUSTRY_POOL = ['Banking', 'Baijiu', 'New Energy', 'Pharma', 'Home Appliance', 'Insurance']
TOP_N         = 2        # Hold the top 2 ranked sectors
LOOKBACK      = 20       # Return over the last 20 trading days


def get_industry_representative(industry_name):
    """Get the stock code with the largest market cap in the sector."""
    df = get_industry_stocks(industry_name)
    if df is None or df.empty:
        return None
    top = df.nlargest(1, 'total_value')
    return top['code'].iloc[0] if not top.empty else None


def score_industries(context):
    """
    Score all candidate sectors. Returns list[(sector_name, representative_stock_code, recent_return)],
    sorted by return descending.
    """
    scored = []
    for ind in INDUSTRY_POOL:
        code = get_industry_representative(ind)
        if code is None:
            continue
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scored.append((ind, code, ret))
        log.info('Sector score: %-12s %s ret=%.2f%%' % (ind, code, ret * 100))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    # Rebalance every Monday
    run_weekly(rebalance, day_of_week=0, time='every_bar')
    log.info('Sector rotation init: sectors=%d, hold Top%d' % (
        len(INDUSTRY_POOL), TOP_N))


def rebalance(context):
    """Re-score and rebalance every Monday."""
    # 1. Score all sectors
    scored = score_industries(context)
    if not scored:
        log.warn('All sector data fetch failed, skipping this rebalance')
        return

    # 2. Select representative stocks from Top N sectors
    top_stocks = [code for _, code, _ in scored[:TOP_N]]
    log.info('This week target: %s' % str(top_stocks))

    # 3. Sell positions not in Top N
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)
            log.info('Sell %s (not in this week Top%d)' % (sec, TOP_N))

    # 4. Equal-weight buy Top N representative stocks
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        target_value = context.portfolio.total_value * weight
        order_target_value(sec, target_value)
        log.info('Rebalance %s, target value=%.0f' % (sec, target_value))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=200000,
        benchmark='000300.XSHG',
        report_dir='reports',
    )
```

> **Note:** `get_industry_stocks()` and `get_industry_representative()` require real-time network access. If backtesting fails, ensure network connectivity or replace dynamic industry queries with a fixed stock list (see below).

### 5.1 Using a Fixed Stock Pool (More Stable Backtesting)

When the industry data interface is unstable, or you want to backtest with deterministic historical data, you can replace dynamic industry queries with a fixed stock pool:

```python
# Select 1-2 representative stocks per sector (module-level constants, not cleared by engine)
INDUSTRY_STOCKS = {
    'Banking':        '601390',   # ICBC
    'Baijiu':         '600519',   # Kweichow Moutai
    'New Energy':     '300750',   # CATL
    'Pharma':         '600276',   # Hengrui Medicine
    'Home Appliance': '000333',   # Midea Group
    'Insurance':      '601318',   # Ping An
}


def score_industries_fixed(context):
    """Score sector momentum using a fixed stock pool."""
    scored = []
    for ind, code in INDUSTRY_STOCKS.items():
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scored.append((ind, code, ret))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

---

## 6. Advanced: Multi-Dimensional Sector Scoring

Relying solely on price momentum for scoring is too simplistic. Combining multiple dimensions can improve strategy robustness.

### 6.1 Composite Scoring Factors

```python
def score_industries_multi(context, industry_stocks):
    """
    Multi-dimensional sector scoring:
    - Short-term momentum (10-day return) weight 40%
    - Medium-term momentum (20-day return) weight 40%
    - Volume surge (5-day avg volume / 20-day avg volume) weight 20%
    """
    from eqlib import utils
    scored = []

    for ind, code in industry_stocks.items():
        hist = attribute_history(code, 30, '1d', ['close', 'volume'])
        if hist.empty or len(hist) < 25:
            continue

        close = hist['close']
        vol   = hist['volume']

        # Short-term momentum (10 days)
        ret_short = (close.iloc[-1] / close.iloc[-10]) - 1

        # Medium-term momentum (20 days)
        ret_mid = (close.iloc[-1] / close.iloc[-20]) - 1

        # Volume ratio
        avg_vol_5  = vol.tail(5).mean()
        avg_vol_20 = vol.tail(20).mean()
        vol_ratio  = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Composite score
        score = ret_short * 0.4 + ret_mid * 0.4 + (vol_ratio - 1) * 0.2

        scored.append((ind, code, score))
        log.info('Sector score: %-12s %s score=%.4f (s=%.2f%%, m=%.2f%%, vol=%.2f)' % (
            ind, code, score, ret_short*100, ret_mid*100, vol_ratio))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

### 6.2 Adding Sector Valuation Filter

Avoid buying sectors with extremely high valuations (bubble risk):

```python
def score_industries_with_valuation(context, industry_stocks):
    """Valuation filter: exclude sectors with PE above 50."""
    from eqlib import get_valuation
    scored = []

    for ind, code in industry_stocks.items():
        # Check valuation
        val = get_valuation(code)
        if val and val.get('pe') and val['pe'] > 50:
            log.info('Skip %s (%s): PE=%.1f too high' % (ind, code, val['pe']))
            continue

        hist = attribute_history(code, 25, '1d', ['close'])
        if hist.empty or len(hist) < 20:
            continue

        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-20]) - 1
        scored.append((ind, code, ret))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored
```

---

## 7. Risks and Pitfalls of Rotation Strategies

### 7.1 Risk of Buying at the Top

Sector rotation strategies are essentially **momentum-chasing**. When a sector has already risen significantly, buying at the peak means it may start declining the very next week:

```
Sector return rankings:
  Week 1: New Energy +15%, Baijiu +8%  → Buy New Energy
  Week 2: New Energy -12%, Baijiu +5%  → Already trapped
```

**Mitigation:**
- Set per-stock stop-loss (e.g., -8%)
- Use a longer momentum period (e.g., 60 days instead of 20)
- Cap any single sector position at 40%

### 7.2 Turnover and Transaction Costs

Weekly rebalancing means 50+ trades per year. Transaction costs significantly erode returns:

```python
# Estimate annualized transaction cost
trades_per_year = 52    # Rebalance once per week
avg_trade_value = 50000  # Average trade amount
commission_rate = 0.001   # Round-trip cost (buy 0.025% + sell 0.025% + stamp duty 0.05%)

annual_cost = trades_per_year * avg_trade_value * commission_rate

# 100000 is the assumed starting capital, used to calculate cost as percentage
base_capital = 100000  # Assumed starting capital of 100,000
print('Estimated annual transaction cost: %.0f (%.2f%%)' % (
    annual_cost, annual_cost / base_capital * 100))
# Output: Estimated annual transaction cost: 1560 (1.56%)
```

**Mitigation:** Rebalance monthly instead of weekly to reduce turnover.

### 7.3 Industry Data Latency

`get_industry_stocks()` returns a current snapshot, which does not represent historical data on that date during backtesting. Strictly speaking, this introduces some look-ahead information.

**Mitigation:** Use a fixed stock pool (like the `INDUSTRY_STOCKS` dictionary above) with known representative stocks instead of dynamic industry queries to ensure reliable backtest results.

---

## 8. Index Constituent Rotation

In addition to sector-based rotation, you can also do momentum rotation based on **index constituents** — selecting the strongest Top N stocks from the CSI 300 or CSI 500 constituents.

```python
from eqlib import *

# Module-level constants (not cleared by engine)
INDEX_CODE = '000300'   # CSI 300
TOP_N      = 5          # Hold Top 5
LOOKBACK   = 20
MAX_STOCKS = 30         # Take top 30 constituents as candidates (to limit data size)


def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))

    # Build candidate stock pool: top 30 CSI 300 constituents by market cap
    index_df = get_index_stocks(INDEX_CODE)
    if not index_df.empty:
        context.universe = index_df['code'].head(MAX_STOCKS).tolist()
        log.info('Candidate pool: %d constituent stocks' % len(context.universe))

    run_weekly(rebalance, day_of_week=0, time='every_bar')


def rebalance(context):
    universe = getattr(context, 'universe', [])
    if not universe:
        return

    # Calculate recent returns for all candidates
    scores = {}
    for code in universe:
        hist = attribute_history(code, LOOKBACK + 5, '1d', ['close'])
        if hist.empty or len(hist) < LOOKBACK:
            continue
        ret = (hist['close'].iloc[-1] / hist['close'].iloc[-LOOKBACK]) - 1
        scores[code] = ret

    if not scores:
        return

    # Select Top N
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_stocks = [code for code, _ in ranked[:TOP_N]]
    log.info('This week target: %s' % str(top_stocks))

    # Sell exiting stocks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)

    # Equal-weight buy Top N
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        order_target_value(sec, context.portfolio.total_value * weight)


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=500000,
        benchmark='000300.XSHG',
        securities=None,   # Don't preload since the stock pool is dynamically determined
        report_dir='reports',
    )
```

Related reference example: [Example 10: Index & Concept Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py)

---

## 9. Next Steps

After mastering sector rotation, you can:

- **[Tutorial 07: Multi-Factor Stock Selection](07-multi-factor.md)** — Score stocks within a fixed pool using multiple factors to select the best candidates
- **[Tutorial 03: Strategy Optimization & Improvement](03-optimization.md)** — Parameter tuning (rotation period, number of holdings), portfolio optimization
- **[Example 10: Index & Concept Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py)** — Complete code for index constituent rotation
- **[Example 17: Multi-Factor Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py)** — Complete code for the multi-factor approach

### Exercises

1. Change the rebalance frequency from weekly to monthly (`run_monthly`) and compare changes in turnover and returns
2. Change `TOP_N = 3` and observe the diversification effect of holding more sectors
3. Add a valuation filter (PE < 50) and observe whether risk-adjusted returns improve
4. In the fixed stock pool, replace the largest-cap representative stocks with your own selections and compare results
