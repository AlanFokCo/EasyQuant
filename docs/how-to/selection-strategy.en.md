# Stock Selection Framework

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Build stock selection strategies using TopNSelector and MultiFactorSelector |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Stock Selection Framework

eqlib provides two stock selection frameworks — `TopNSelector` and `MultiFactorSelector` — supporting periodic rebalancing and factor-based screening.

### 1.1 TopNSelector: Rank-Based Selection

Selects the top N stocks by factor value ranking.

```python
from eqlib import TopNSelector

def initialize(context):
    g.selector = TopNSelector(
        universe=['600519', '601390', '000858', '600036', '601166'],
        factor_fn=momentum_factor,  # custom factor function
        top_n=3,
        rebalance_freq='weekly',    # rebalance weekly
    )
    run_daily(rebalance, time='every_bar')

def momentum_factor(security, context):
    """Momentum factor: return over the past 20 days"""
    hist = attribute_history(security, 20, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return None
    return (hist['close'].iloc[-1] / hist['close'].iloc[0] - 1)

def rebalance(context):
    candidates = g.selector.select(context)
    if candidates:
        for sec in candidates:
            order_value(sec, context.portfolio.available_cash / len(candidates))
```

### 1.2 MultiFactorSelector: Multi-Factor Selection

Combines multiple factors for composite scoring and selection.

```python
from eqlib import MultiFactorSelector

def initialize(context):
    g.selector = MultiFactorSelector(
        universe=['600519', '601390', '000858', '600036', '601166'],
        factors={
            'momentum': (momentum_factor, 0.4),    # 40% weight
            'volatility': (volatility_factor, 0.3), # 30% weight
            'value': (value_factor, 0.3),           # 30% weight
        },
        top_n=3,
        rebalance_freq='monthly',
    )

def volatility_factor(security, context):
    """Volatility factor (inverse): lower volatility scores higher"""
    hist = attribute_history(security, 20, '1d', ['close'])
    if hist.empty:
        return None
    returns = hist['close'].pct_change().dropna()
    return -returns.std()  # negate so low volatility scores higher

def value_factor(security, context):
    """Valuation factor: lower PE scores higher"""
    val = get_valuation(security)
    if val is None or val.get('pe_ratio') is None:
        return None
    return -val['pe_ratio']  # negate so low PE scores higher

def rebalance(context):
    candidates = g.selector.select(context)
    # rebalancing logic...
```

### 1.3 Rebalancing Frequency Configuration

| Parameter | Options | Description |
|-----------|---------|-------------|
| `rebalance_freq` | `'daily'` | Rebalance every trading day |
| | `'weekly'` | Rebalance every Monday |
| | `'biweekly'` | Rebalance every two weeks |
| | `'monthly'` | Rebalance on the first trading day of each month |
| | `'quarterly'` | Rebalance on the first trading day of each quarter |

### 1.4 Factor Function Specification

The factor function signature is:

```python
def my_factor(security: str, context: Context) -> float | None:
    """
    Args:
        security: stock code
        context: strategy context

    Returns:
        Factor value (higher is better) or None (stock excluded from ranking)
    """
    pass
```

---

See the [Stock Selection API Reference](../reference/api-selection.md) for full parameter documentation.
