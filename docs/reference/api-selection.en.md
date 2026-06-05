# Stock Selection API

> Stock selection functions, filters, TopN and multi-factor selectors.

---

## Writing a Stock Selection Strategy

**Pattern 1: Plain function**

```python
def my_selection(context):
    candidates = filter_st_stocks(["601390", "600519"])
    df = fetch_factor_data(candidates, fields=["pe"])
    return df.sort_values("pe").head(5).index.tolist()
```

**Pattern 2: StockSelector subclass**

```python
class MySelector(StockSelector):
    def filter(self, candidates, context):
        return filter_st_stocks(candidates)
    def rank(self, securities, context):
        return TopNSelector(factor="pe", top_n=5).rank(securities, context)
```

**Pattern 3: Built-in selectors**

```python
TopNSelector(factor="pe", top_n=5, ascending=True)
MultiFactorSelector(factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4}, top_n=5)
```

## Registration & Invocation

```python
# Call in initialize
run_selection(my_selection, rebalance="monthly:1")

# Or via run_strategy parameters
result = run_strategy(initialize, selection_func=my_selection, selection_rebalance="weekly:0")
```

## Utility Functions

| API | Description |
|-----|-------------|
| `StockSelector` | Stock selection base class |
| `filter_st_stocks(securities)` | Remove ST stocks |
| `filter_paused_stocks(securities, context)` | Remove suspended stocks |
| `filter_low_price_stocks(securities, min_price=2.0)` | Remove low-price stocks |
| `filter_high_pe_stocks(securities, max_pe=100.0)` | Remove high-PE stocks |
| `fetch_factor_data(securities, fields=None)` | Fetch multi-dimensional factor data |
| `TopNSelector(factor, top_n, ascending)` | Single-factor Top-N selector |
| `MultiFactorSelector(factors, top_n)` | Multi-factor weighted selector |

### TopNSelector

Single-factor Top-N selector — ranks by a single factor and selects the top N stocks.

```python
TopNSelector(factor="pe", top_n=5, ascending=True)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `factor` | `str` | Factor name, e.g., `"pe"`, `"pb"`, `"pct_change"` |
| `top_n` | `int` | Number of stocks to select |
| `ascending` | `bool` | `True` for ascending (lower is better), `False` for descending (higher is better) |

```python
# Select the 5 stocks with the lowest PE
selector = TopNSelector(factor="pe", top_n=5, ascending=True)
top_stocks = selector.rank(candidates, context)
```

### MultiFactorSelector

Multi-factor weighted selector — ranks by a weighted composite score and selects the top N stocks.

```python
MultiFactorSelector(factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4}, top_n=5)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `factors` | `dict` | Factor weight mapping; negative weights mean lower is better |
| `top_n` | `int` | Number of stocks to select |

```python
# Multi-factor selection: low PE (40%), low PB (20%), high momentum (40%)
selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
    top_n=10
)
selected = selector.rank(candidates, context)
```

### fetch_factor_data

Fetch multi-dimensional factor data for stock screening and scoring.

```python
fetch_factor_data(securities, fields=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `securities` | `list[str]` | List of stock tickers |
| `fields` | `list[str]` | Factor field list; defaults to all |

Available fields: `price`, `pct_change`, `total_value`, `pe`, `pb`, `turnover`, `ma5`, `ma10`, `ma20`, `rsi14`.

```python
# Fetch PE, PB, and momentum factors for candidate stocks
candidates = ["601390", "600519", "000858"]
df = fetch_factor_data(candidates, fields=["pe", "pb", "pct_change"])

# Sort by PE
df_sorted = df.sort_values("pe", ascending=True)
```
