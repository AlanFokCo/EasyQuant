# Tutorial 07: Multi-Factor Stock Selection

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Master multi-factor scoring, normalization, and combination; understand the stock selection process used by institutional funds |
    | **Estimated time** | ~90-120 minutes |
    | **Prerequisites** | [Tutorial 06](06-sector-rotation.md); for chained stock selection see [Selection API Reference](../reference/api-selection.md) Section 3.14 |

> Multi-factor stock selection is one of the most widely used methods by institutional quantitative funds. Rather than relying on a single indicator, it scores stocks across multiple dimensions — price, financials, sentiment — to systematically identify the stocks with the best "value for money."

**Selection API:** [Selection API Reference](../reference/api-selection.md) Section 3.14 (Chained Selection), Chapter 11 (`MultiFactorSelector`)

---

## Table of Contents

1. [What Is Factor-Based Stock Selection](#1-what-is-factor-based-stock-selection)
2. [Common Factor Types](#2-common-factor-types)
3. [A-Share Specific Factors](#3-a-share-specific-factors)
4. [Factor Construction Basics](#4-factor-construction-basics)
5. [Three-Factor Model: Momentum + Volume + Price](#5-three-factor-model-momentum--volume--price)
6. [Adding Financial Factors](#6-adding-financial-factors)
7. [Factor Normalization and Combination](#7-factor-normalization-and-combination)
8. [Complete Multi-Factor Strategy](#8-complete-multi-factor-strategy)
9. [Factor Effectiveness Testing](#9-factor-effectiveness-testing)
10. [Limitations of Multi-Factor Selection](#10-limitations-of-multi-factor-selection)
11. [Next Steps](#11-next-steps)

---

## 1. What Is Factor-Based Stock Selection

A **Factor** is a quantifiable characteristic that can be used to predict a stock's future returns.

Examples:
- "Stocks that rose the most in the past month are likely to keep rising next month" — this is the **momentum factor**
- "Stocks with the lowest PE are more likely to rise over the long term" — this is the **value factor**
- "Companies with the highest ROE have strong profitability and are suitable for long-term holding" — this is the **quality factor**

The core idea of **multi-factor stock selection** is: rather than relying on a single factor, score stocks across multiple factors and select the portfolio with the highest composite score.

```
Stock pool (100 stocks)
    ↓
Momentum factor scoring → Z-score normalization
Volume factor scoring   → Z-score normalization
Value factor scoring     → Z-score normalization
    ↓
Composite score = Factor1 × Weight1 + Factor2 × Weight2 + Factor3 × Weight3
    ↓
Rank by composite score, buy the top N
```

---

## 2. Common Factor Types

### 2.1 Technical Factors

| Factor Name | Definition | Characteristics |
|-------------|-----------|-----------------|
| **Momentum factor** | N-day return | Short-term trend persistence |
| **Reversal factor** | Negative of 5-day return | Short-term overbought/oversold correction |
| **Volatility factor** | Standard deviation of N-day returns | Low-volatility premium |
| **Volume factor** | Recent volume / historical average volume | Capital attention |
| **Moving average alignment** | Price / MA ratio | Trend strength |

### 2.2 Financial Factors

| Factor Name | Definition | Characteristics |
|-------------|-----------|-----------------|
| **Value factor** | 1 / PE (earnings yield) | Undervalued stocks are safer |
| **Price-to-book** | 1 / PB | Asset value reversion |
| **Quality factor** | ROE (return on equity) | Profitability |
| **Growth factor** | Revenue growth / profit growth | Future potential |

### 2.3 Factor Usage Principles

1. **Factors must have economic logic**: You can't use a factor just because it worked historically; you must be able to explain why it works
2. **Factors should not be too correlated**: Scoring with both PE and PB simultaneously adds little value (highly correlated)
3. **Factor effectiveness varies across market environments**: Momentum works in bull markets; value works in bear markets

---

## 3. A-Share Specific Factors

The A-share market has unique characteristics that allow construction of proprietary factors to capture excess returns. This section introduces two typical A-share specific factors: the north-bound capital flow factor (sentiment factor) and the restricted share unlock factor (risk factor).

### 3.1 North-Bound Capital Flow Factor (Sentiment Factor)

North-bound capital refers to foreign capital entering the A-share market via Shanghai-Hong Kong Stock Connect and Shenzhen-Hong Kong Stock Connect. Since north-bound capital is generally regarded as "smart money," its flow direction has strong predictive power for market sentiment.

**Economic rationale:**

- Sustained north-bound net inflows → Foreign investors are bullish on A-shares → Market sentiment is optimistic
- Sustained north-bound net outflows → Foreign investors are bearish on A-shares → Market sentiment is pessimistic

**Factor construction example:**

```python
from eqlib import get_north_money_flow

def compute_north_money_factor(lookback_days=5):
    """
    North-bound capital flow factor: net inflow ratio over the last N days.

    Returns:
        float: Net inflow as a proportion of turnover; positive means net inflow
    """
    df = get_north_money_flow(days=lookback_days)
    if df is None or df.empty:
        return None

    # Calculate cumulative net inflow
    total_net_inflow = df['north_net'].sum()
    total_turnover = df['north_money'].sum()  # Total turnover

    if total_turnover == 0:
        return None

    # Net inflow ratio
    net_ratio = total_net_inflow / total_turnover
    return net_ratio


def compute_north_momentum_factor(lookback_days=10):
    """
    North-bound capital momentum factor: net inflow trend over the last N days.

    Calculates the net inflow trend slope via linear regression.
    """
    import numpy as np

    df = get_north_money_flow(days=lookback_days)
    if df is None or len(df) < lookback_days:
        return None

    # Net inflow series
    net_flows = df['north_net'].values

    # Simple linear regression for trend
    x = np.arange(len(net_flows))
    y = net_flows

    # Slope = Cov(x, y) / Var(x)
    cov_xy = np.cov(x, y, ddof=0)[0, 1]
    var_x = np.var(x, ddof=0)

    if var_x == 0:
        return None

    slope = cov_xy / var_x
    return slope
```

**Use cases:**

1. **As a market timing signal**: When north-bound capital has net outflows for 3 consecutive days with significant amounts, reduce positions
2. **As a sentiment factor**: Combine with other factors to give bonus scores to stocks with north-bound net inflows

**Recommended factor weight:** 5%-10% (sentiment factors are volatile and should not be weighted too heavily)

### 3.2 Restricted Share Unlock Factor (Risk Factor)

Restricted share unlock (限售股解禁) refers to shares that were previously prohibited from trading on the secondary market becoming tradeable, typically creating selling pressure. The unlock factor is primarily used for risk avoidance.

**Economic rationale:**

- Large-scale restricted share unlocks → Potential selling pressure → Stock price may decline
- The higher the unlock market value as a proportion of total market cap, the greater the impact

**Factor construction example:**

```python
from eqlib import get_restriction_release
import datetime

def compute_restriction_risk_factor(code, lookforward_days=30):
    """
    Restricted share unlock risk factor: unlock pressure score over the next N days.

    Returns:
        float: Unlock risk score; higher means greater risk.
              0 means no unlock or negligible impact.
    """
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=lookforward_days)

    df = get_restriction_release(
        code=code,
        start_date=today.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )

    if df is None or df.empty:
        return 0.0  # No unlock scheduled

    # Calculate unlock market value
    total_release_value = df['release_value'].sum()

    # Get current market cap
    from eqlib import get_valuation
    val = get_valuation(code)
    if val is None:
        return 0.0

    market_cap = val.get('market_cap', 0)
    if market_cap <= 0:
        return 0.0

    # Unlock ratio = unlock market value / current market cap
    release_ratio = total_release_value / market_cap

    # Convert to risk score (0-1; unlock ratio above 10% is considered high risk)
    risk_score = min(release_ratio / 0.10, 1.0)
    return risk_score


def filter_stocks_by_restriction(stock_pool, lookforward_days=30, threshold=0.05):
    """
    Filter out stocks with upcoming restricted share unlocks.

    Args:
        stock_pool: List of stock codes
        lookforward_days: Look-forward window in days
        threshold: Unlock ratio threshold; stocks above this are filtered out

    Returns:
        list: Filtered stock list
    """
    filtered = []
    for code in stock_pool:
        risk = compute_restriction_risk_factor(code, lookforward_days)
        if risk < threshold:
            filtered.append(code)
        else:
            log.info(f'{code} unlock risk too high ({risk:.2%}), filtered out')
    return filtered
```

**Use cases:**

1. **Stock pool filtering**: Exclude stocks with upcoming large-scale unlocks before selection
2. **Risk factor**: As a negative factor, stocks with high unlock risk receive lower scores
3. **Position monitoring**: Monitor unlock schedules for held positions and reduce positions in advance

**Important notes:**

- The unlock factor should be used before stock selection, not combined with other factors after normalization
- Unlock market value data may have delays; cross-verify with public announcements

### 3.3 A-Share Specific Factor Combination Example

Combining the north-bound capital factor with the restricted share unlock factor creates an A-share specific "smart money + risk filtering" strategy:

```python
def a_share_stock_selection(base_scores, stock_pool):
    """
    A-share specific selection: base factors + north-bound capital bonus + unlock risk filter.

    Args:
        base_scores: Base multi-factor score dictionary {code: score}
        stock_pool: Stock pool

    Returns:
        dict: Adjusted final scores
    """
    # Step 1: Unlock risk filtering
    filtered_stocks = filter_stocks_by_restriction(
        stock_pool,
        lookforward_days=30,
        threshold=0.05
    )

    # Step 2: North-bound capital sentiment factor
    north_factor = compute_north_money_factor(lookback_days=5)

    # Step 3: Adjust scores
    final_scores = {}
    for code in filtered_stocks:
        if code not in base_scores:
            continue

        # Base score
        score = base_scores[code]

        # Adjust position weight based on north-bound capital flow (no per-stock differentiation)
        # When north-bound capital has net inflow, boost overall scores
        if north_factor and north_factor > 0:
            score *= (1 + north_factor * 0.5)  # Mild adjustment

        final_scores[code] = score

    return final_scores
```

---

## 4. Factor Construction Basics

In EasyQuant, factors are typically computed using `attribute_history` to fetch historical data:

```python
from eqlib import attribute_history, get_valuation
from eqlib import utils

def compute_momentum(code, period=20):
    """Momentum factor: N-day return."""
    hist = attribute_history(code, period + 5, '1d', ['close'])
    if hist.empty or len(hist) < period:
        return None
    return (hist['close'].iloc[-1] / hist['close'].iloc[-period]) - 1


def compute_volatility(code, period=20):
    """Volatility factor: standard deviation of daily returns over N days (lower is better, negated)."""
    hist = attribute_history(code, period + 5, '1d', ['close'])
    if hist.empty or len(hist) < period:
        return None
    daily_returns = hist['close'].pct_change().dropna()
    return -daily_returns.tail(period).std()   # Negate: lower vol → higher factor value


def compute_volume_ratio(code, short=5, long=20):
    """Volume factor: recent avg volume / long-term avg volume, reflecting capital attention."""
    hist = attribute_history(code, long + 5, '1d', ['volume'])
    if hist.empty or len(hist) < long:
        return None
    short_avg = hist['volume'].tail(short).mean()
    long_avg  = hist['volume'].tail(long).mean()
    return short_avg / long_avg if long_avg > 0 else None


def compute_value(code):
    """Value factor: 1 / PE (lower PE → higher factor value)."""
    val = get_valuation(code)
    if val is None or val.get('pe') is None or val['pe'] <= 0:
        return None
    return 1.0 / val['pe']
```

---

## 5. Three-Factor Model: Momentum + Volume + Price

Let's first build a basic version using three purely technical factors, avoiding dependence on real-time financial data:

### 5.1 Factor Definitions

| Factor | Meaning | Weight |
|--------|---------|--------|
| Momentum | Recent 20-day return | 40% |
| Volume surge | Recent 5-day avg volume / recent 20-day avg volume | 30% |
| Short-term reversal correction | Negative of recent 5-day return (avoids chasing short-term spikes) | 30% |

### 5.2 Factor Calculation Example

```python
from eqlib import attribute_history

def score_stock_three_factor(code):
    """
    Three-factor scoring: momentum + volume + short-term reversal correction.
    Returns: dict with factor values and total score, or None (insufficient data)
    """
    hist = attribute_history(code, 35, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < 25:
        return None

    close = hist['close']
    vol   = hist['volume']

    # Factor 1: 20-day momentum
    momentum = (close.iloc[-1] / close.iloc[-20]) - 1

    # Factor 2: Volume surge ratio
    vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()

    # Factor 3: Short-term reversal (positive 5-day return gets low score, avoiding chasing)
    reversal = -((close.iloc[-1] / close.iloc[-5]) - 1)

    return {
        'momentum': momentum,
        'vol_ratio': vol_ratio,
        'reversal': reversal,
    }
```

---

## 6. Adding Financial Factors

Financial factors are typically obtained via `get_valuation` in strategies and are suitable for **low-frequency rebalancing** (e.g., monthly):

```python
from eqlib import get_valuation, get_financial_abstract

def score_stock_with_financials(code):
    """
    Add financial factors: value + quality.
    Suitable for low-frequency (monthly) updates.
    """
    # Value factor
    val = get_valuation(code)
    pe_factor = 0.0
    pb_factor = 0.0
    if val:
        pe = val.get('pe')
        pb = val.get('pb')
        if pe and 0 < pe < 100:     # Filter negative PE (loss-making) and extreme PE (>100, likely bubble)
            pe_factor = 1.0 / pe
        if pb and 0 < pb < 20:
            pb_factor = 1.0 / pb

    # Quality factor (ROE = net profit / net assets, from financial summary)
    roe_factor = 0.0
    try:
        fin = get_financial_abstract(code)
        if fin is not None and not fin.empty:
            # Financial summary row index includes various metrics; try to get ROE
            if 'ROE' in fin.index:
                roe = float(fin.loc['ROE'].iloc[-1])
                # ROE stored as decimal (e.g., 0.15 = 15%), valid range 0-1
                if 0 < roe < 1:
                    roe_factor = roe
    except Exception:
        pass

    return {
        'pe_factor':  pe_factor,
        'pb_factor':  pb_factor,
        'roe_factor': roe_factor,
    }
```

---

## 7. Factor Normalization and Combination

Different factors have different units (momentum is a percentage, volume ratio is a multiplier). Directly weighting them would allow one factor to dominate. Normalization is needed before combination.

### 7.1 Z-Score Normalization

```python
def zscore_normalize(values_dict):
    """
    Z-score normalization for factor values across multiple stocks.

    Input: {'code1': value1, 'code2': value2, ...}
    Output: {'code1': z_score1, 'code2': z_score2, ...}
    """
    import statistics

    valid_items = [(k, v) for k, v in values_dict.items() if v is not None]
    if len(valid_items) < 2:
        return {k: 0.0 for k in values_dict}

    codes, vals = zip(*valid_items)
    mean_val = statistics.mean(vals)
    std_val  = statistics.stdev(vals)

    if std_val == 0:
        return {k: 0.0 for k in values_dict}

    return {
        code: (val - mean_val) / std_val
        for code, val in valid_items
    }


def merge_factor_scores(factor_dicts, weights):
    """
    Merge multiple normalized factor dictionaries.

    factor_dicts: [{'code': z_score}, ...] Z-score dict for each factor
    weights:      [w1, w2, ...]            Corresponding weights, sum to 1
    Returns: {'code': combined_score}
    """
    combined = {}
    for fdict, weight in zip(factor_dicts, weights):
        for code, zscore in fdict.items():
            combined[code] = combined.get(code, 0.0) + zscore * weight
    return combined
```

### 7.2 Usage Example

```python
stock_pool = ['601390', '600519', '000858', '600036', '601318',
              '000333', '600887', '000651', '600276', '000001']

# Calculate raw factor values for each stock
raw_momentum  = {}
raw_vol_ratio = {}
raw_reversal  = {}

for code in stock_pool:
    result = score_stock_three_factor(code)
    if result is None:
        continue
    raw_momentum[code]  = result['momentum']
    raw_vol_ratio[code] = result['vol_ratio']
    raw_reversal[code]  = result['reversal']

# Z-score normalization
z_momentum  = zscore_normalize(raw_momentum)
z_vol_ratio = zscore_normalize(raw_vol_ratio)
z_reversal  = zscore_normalize(raw_reversal)

# Combine into composite score
combined = merge_factor_scores(
    [z_momentum, z_vol_ratio, z_reversal],
    weights=[0.4, 0.3, 0.3],
)

# Ranking
ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
print("Rank  Code    Composite Score")
for i, (code, score) in enumerate(ranked[:5]):
    print('%2d.  %s  %.3f' % (i + 1, code, score))
```

---

## 8. Complete Multi-Factor Strategy

```python
from eqlib import *
from eqlib import utils
import statistics

# ========== Strategy parameters (module-level constants, not cleared by engine) ==========
STOCK_POOL = [
    '601390', '600519', '000858', '600036', '000001',
    '601318', '000333', '600887', '000651', '600276',
]
TOP_N          = 3     # Hold the top 3 ranked stocks at a time
LOOKBACK_LONG  = 20    # Medium-term momentum lookback
LOOKBACK_SHORT = 5     # Short-term reversal lookback
POSITION_PCT   = 0.33  # Max 33% position per stock


# ========== Factor functions ==========

def compute_factors(code):
    """Compute raw three-factor values for a single stock; returns None on failure."""
    hist = attribute_history(code, LOOKBACK_LONG + 10, '1d', ['close', 'volume'])
    if hist.empty or len(hist) < LOOKBACK_LONG:
        return None

    close = hist['close']
    vol   = hist['volume']
    price = close.iloc[-1]

    # Price range filter: exclude penny stocks (< 3) and extremely high-priced stocks (> 500)
    if price < 3.0 or price > 500.0:
        return None

    momentum  = (close.iloc[-1] / close.iloc[-LOOKBACK_LONG]) - 1
    vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()
    reversal  = -((close.iloc[-1] / close.iloc[-LOOKBACK_SHORT]) - 1)

    return (momentum, vol_ratio, reversal)


def zscore_dict(values_dict):
    """Z-score normalization."""
    vals = list(values_dict.values())
    if len(vals) < 2:
        return {k: 0.0 for k in values_dict}
    mean_v = statistics.mean(vals)
    std_v  = statistics.stdev(vals) or 1e-9
    return {k: (v - mean_v) / std_v for k, v in values_dict.items()}


def rank_stocks(context):
    """
    Score and rank all stocks in the pool. Returns [(code, score)] sorted descending.
    """
    raw = {code: compute_factors(code) for code in STOCK_POOL}
    raw = {k: v for k, v in raw.items() if v is not None}

    if not raw:
        return []

    momentum_raw  = {code: v[0] for code, v in raw.items()}
    vol_ratio_raw = {code: v[1] for code, v in raw.items()}
    reversal_raw  = {code: v[2] for code, v in raw.items()}

    z_m = zscore_dict(momentum_raw)
    z_v = zscore_dict(vol_ratio_raw)
    z_r = zscore_dict(reversal_raw)

    scores = {
        code: z_m.get(code, 0) * 0.4 +
              z_v.get(code, 0) * 0.3 +
              z_r.get(code, 0) * 0.3
        for code in raw
    }

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ========== Strategy body ==========

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    context.universe = STOCK_POOL
    run_weekly(rebalance, day_of_week=0, time='every_bar')
    log.info('Multi-factor init: pool=%d, hold Top%d' % (
        len(STOCK_POOL), TOP_N))


def rebalance(context):
    """Re-score and rebalance every Monday."""
    ranked = rank_stocks(context)
    if not ranked:
        log.warn('No valid scores, skipping rebalance')
        return

    top_stocks = [code for code, _ in ranked[:TOP_N]]

    # Print current scores
    log.info('This week score ranking:')
    for i, (code, score) in enumerate(ranked[:TOP_N]):
        log.info('  %d. %s  score=%.3f' % (i + 1, code, score))

    # Sell positions not in Top N
    for sec in list(context.portfolio.positions.keys()):
        if sec not in top_stocks:
            order_target(sec, 0)
            log.info('Sell %s (not in this week Top%d)' % (sec, TOP_N))

    # Equal-weight buy Top N
    weight = 1.0 / TOP_N
    for sec in top_stocks:
        target_value = context.portfolio.total_value * weight
        order_target_value(sec, target_value)
        log.info('Rebalance %s, target position=%.0f' % (sec, target_value))


if __name__ == '__main__':
    result = run_strategy(
        initialize,
        start_date='2022-01-01',
        end_date='2024-12-31',
        starting_cash=300000,
        benchmark='000300.XSHG',
        securities=STOCK_POOL,
        report_dir='reports',
    )
```

---

## 9. Factor Effectiveness Testing

Before putting a factor into use, you need to verify whether it actually has predictive power.

### 9.1 IC (Information Coefficient) Test

IC is the correlation between factor values and next-period returns. The higher the absolute IC value, the stronger the predictive power:

```python
def compute_ic(stock_pool, factor_func, forward_period=5):
    """
    Calculate factor IC (correlation between factor values and future N-day returns).
    factor_func: function(code) -> float | None
    """
    import statistics

    factor_values = []
    forward_returns = []

    for code in stock_pool:
        # Factor value (computed today)
        f = factor_func(code)
        if f is None:
            continue

        # Future N-day return (for validation)
        hist = attribute_history(code, forward_period + 5, '1d', ['close'])
        if hist.empty or len(hist) < forward_period + 1:
            continue
        fwd_ret = (hist['close'].iloc[-1] / hist['close'].iloc[-(forward_period + 1)]) - 1

        factor_values.append(f)
        forward_returns.append(fwd_ret)

    if len(factor_values) < 5:
        return None

    # Calculate Pearson correlation coefficient
    n = len(factor_values)
    mean_f = statistics.mean(factor_values)
    mean_r = statistics.mean(forward_returns)
    cov  = sum((f - mean_f) * (r - mean_r)
               for f, r in zip(factor_values, forward_returns)) / n
    std_f = statistics.stdev(factor_values) or 1e-9
    std_r = statistics.stdev(forward_returns) or 1e-9
    ic = cov / (std_f * std_r)
    return ic


# Example: Test IC of the momentum factor
ic_value = compute_ic(
    g.stock_pool,
    lambda code: compute_momentum(code, period=20),
    forward_period=5,
)
if ic_value is not None:
    print('Momentum factor IC = %.4f' % ic_value)
    # IC > 0.03 is generally considered statistically meaningful
    # IC > 0.10 is a relatively strong predictive signal
```

### 9.2 Long-Short Quintile Return Analysis

Sort stocks into 5 groups (Q1-Q5) by factor value from high to low. If the factor is effective, Q1 (highest score) should clearly outperform Q5 (lowest score):

```python
def factor_quintile_analysis(stock_pool, factor_func, lookback=5):
    """Factor quintile analysis: sort stocks into 5 groups by factor value and compare returns."""
    data = []
    for code in stock_pool:
        f = factor_func(code)
        if f is None:
            continue
        hist = attribute_history(code, lookback + 3, '1d', ['close'])
        if hist.empty or len(hist) < lookback + 1:
            continue
        fwd = (hist['close'].iloc[-1] / hist['close'].iloc[-(lookback+1)]) - 1
        data.append((code, f, fwd))

    if len(data) < 5:
        return

    data.sort(key=lambda x: x[1], reverse=True)
    n = len(data)
    group_size = max(n // 5, 1)

    print('Factor quintile analysis (%d stocks total):' % n)
    for q in range(5):
        start = q * group_size
        end   = min((q + 1) * group_size, n) if q < 4 else n
        group = data[start:end]
        avg_ret = sum(r for _, _, r in group) / len(group)
        print('  Q%d (Top %d%%): avg return %.2f%%' % (
            q + 1, (q + 1) * 20, avg_ret * 100))
```

---

## 10. Limitations of Multi-Factor Selection

### 10.1 A-Share Retail Market Specifics

| Factor | In US Markets | In A-Shares |
|--------|---------------|-------------|
| Value factor | Effective long-term | Effective but with longer cycles; often overlooked short-term |
| Momentum factor | Effective medium-term (3-12 months) | Short-term momentum is prominent, but beware of overheated thematic stocks |
| Quality factor (high ROE) | Stably effective | Effective, but blue-chip stocks are sometimes overlooked |
| Growth factor | Effective | Stronger effect in bull markets |

### 10.2 Factor Decay and Rotation

No factor works forever — factors become "stale":
- When too much capital chases the same factor, predictive power declines
- It is recommended to test IC periodically (quarterly) to verify whether a factor is still effective

### 10.3 Data Bias

Backtests use current financial data (`get_valuation`) rather than the data that was actually published at that historical point in time. This can introduce **financial data look-ahead bias**. A rigorous multi-factor strategy should use historical financial data snapshots.

**Practical advice:** In backtests, primarily use **price and volume factors** (no look-ahead bias), and reserve financial factors as supplementary references or live-trading screening conditions.

---

## 11. Next Steps

Having mastered the basics of multi-factor stock selection, you can further:

- **[Tutorial 03: Strategy Optimization & Improvement](03-optimization.md)** — Parameter tuning, attribution analysis, and robustness testing for multi-factor strategies
- **[Tutorial 06: Sector Rotation](06-sector-rotation.md)** — Combine multi-factor selection with sector rotation: select the sector first, then the stock
- **[Example 17: Multi-Factor Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py)** — Complete runnable multi-factor example code
- **[Example 09: Performance Attribution Analysis](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/09_attribution.py)** — Deep attribution of strategy returns: selection effect vs. allocation effect
- **[Utils Library Reference](../reference/utils.md)** — Detailed descriptions of `utils.zscore`, `utils.rolling_sharpe`, `utils.max_drawdown`, and more

### Exercises

1. Modify factor weights (e.g., change momentum weight from 40% to 60%) and observe how the strategy changes
2. Add a fourth factor: 60-day return (long-term momentum) at 20% weight, reducing other factors by 5% each
3. Change the rebalance frequency from weekly to monthly and analyze changes in turnover and net returns
4. Use `analyze_returns` to compare the risk-adjusted returns of the multi-factor strategy vs. the dual moving average strategy
5. Expand the stock pool (add stocks you follow), re-backtest, and compare results
