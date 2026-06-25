# Machine Learning Stock Selection

!!! abstract "Overview"

    | Item | Description |
|------|-------------|
| **Goal** | Replace hand-tuned factor weights with `MLSelector` — let the model learn factor weights and interactions automatically |
| **Prerequisites** | [Run a backtest](02-backtesting.en.md), [Selection strategy framework](../how-to/selection-strategy.en.md) |

---

## 1. Why ML-based stock selection?

Traditional multi-factor selection uses **hand-tuned weights**:

```python
from eqlib import MultiFactorSelector

selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
    top_n=5,
)
```

**Problems**:
- Weights are author-tuned by experience and may only fit a specific market regime
- Interactions between factors are ignored (e.g., "momentum + high vol" behaves differently across regimes)
- Non-linear relationships cannot be captured

**ML selection** learns automatically:
- Per-factor importance (data-driven, not fixed)
- Interactions between factors
- Time-varying weights

---

## 2. A minimal ML selection strategy

```python
from eqlib import *
from eqlib.ml import MLSelector

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                              open_commission=0.00025, close_commission=0.00025))

    context.universe = ['601390', '600519', '000858', '002594', '601398']

    # ML selector: learns factor weights from data
    # target='past_return_5d' uses historical 5-day returns as labels (default).
    # For true forward-return prediction, pass pre-computed labels via label_data (panel).
    g.selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility'],
        target='past_return_5d',
        top_n=3,
    )

    before_trading_start(train_model)  # register pre-market training hook
    run_weekly(rebalance, day_of_week=0, time='every_bar')

def train_model(context, data=None):
    # Retrain the model before each trading day (uses latest data)
    g.selector.train(context.universe, context)

def rebalance(context):
    # Get the top-3 stocks selected by the model
    selected = g.selector.rank(context.universe, context)

    # Sell positions not in the selected list
    for pos in list(context.portfolio.positions.keys()):
        if pos not in selected:
            order_target(pos, 0)

    # Buy selected stocks
    if selected:
        cash_per_stock = context.portfolio.available_cash / len(selected)
        for stock in selected:
            order_value(stock, cash_per_stock)

# Run the backtest
result = run_strategy(
    initialize,
    start_date='2022-01-01',
    end_date='2024-01-01',
    securities=['601390', '600519', '000858', '002594', '601398'],
)
```

---

## 3. MLSelector parameters

```python
MLSelector(
    model='random_forest',           # model type
    features=['rsi', 'macd_hist'],  # features to use
    target='past_return_5d',         # prediction target (default: past 5-day return)
    top_n=5,                         # number of stocks to select
    train_start=None,                # training start date (optional)
    train_end=None,                  # training end date (optional)
    lookback=60,                     # historical lookback (days)
)
```

### model — model type

| Model | Description | Best for |
|-------|-------------|----------|
| `random_forest` | Random Forest (default) | General use; robust, less prone to overfit |
| `logistic_regression` | Logistic Regression | Simple scenarios; interpretable |
| `gradient_boosting` | Gradient Boosting | When accuracy matters |
| `xgboost` | XGBoost | When accuracy matters (requires `xgboost` installed) |

### features — available features

| Feature | Description |
|---------|-------------|
| `rsi` | RSI(14) relative strength |
| `macd_dif`, `macd_dea`, `macd_hist` | MACD lines |
| `atr` | ATR(14) average true range |
| `boll_upper`, `boll_mid`, `boll_lower` | Bollinger bands |
| `donchian_upper`, `donchian_mid`, `donchian_lower` | Donchian channel |
| `cci` | CCI(14) commodity channel index |
| `obv` | OBV on-balance volume |
| `volume_ratio` | 5-day avg volume / 20-day avg volume |
| `momentum` | 20-day momentum (price / price[-20] - 1) |
| `volatility` | 20-day return std |
| `roc` | 12-period rate of change |

### target — prediction target

| Target | Description |
|--------|-------------|
| `past_return_5d` | Past 5-day return (default; regression) |
| `past_return_10d` | Past 10-day return (regression) |
| `will_rise_5d` | Whether past 5 days were up (0/1 classification) |

!!! warning "About forward_return_5d"

    `target='forward_return_5d'` is **no longer supported** — passing
    it raises `NotImplementedError`. Reason: a single day's
    cross-section cannot construct true forward-return labels. For
    true forward-return prediction, pass pre-computed labels via the
    `label_data` parameter (a panel DataFrame with columns
    `['security', 'date', 'label']`).

---

## 4. Using FeaturePipeline standalone

Sometimes you want features directly (e.g., for visualization or analysis)
without MLSelector:

```python
from eqlib.ml import FeaturePipeline

g.pipeline = FeaturePipeline(features=['rsi', 'macd_hist', 'momentum'])

def rebalance(context):
    # Compute features
    features = g.pipeline.compute(context.universe, context, lookback=60)

    # features is a DataFrame
    # index = stock codes, columns = feature names
    print(features.head())
    #              rsi  macd_hist  momentum
    # 601390     45.2       0.12      0.03
    # 600519     62.1      -0.05     -0.01
```

---

## 5. Custom features

You can add your own feature functions:

```python
from eqlib.ml import FeaturePipeline, MLSelector

def price_to_ma_ratio(close, high, low, volume):
    """Price deviation from 20-day MA."""
    if len(close) < 20:
        return float('nan')
    ma20 = close.iloc[-20:].mean()
    return float(close.iloc[-1] / ma20 - 1.0)

# Create a pipeline with custom features
g.selector = MLSelector(
    features=['rsi', 'momentum', 'price_ma_ratio'],
    target='past_return_5d',
    top_n=3,
)
g.selector.pipeline = FeaturePipeline(
    features=['rsi', 'momentum', 'price_ma_ratio'],
    custom_features={'price_ma_ratio': price_to_ma_ratio},
)
```

---

## 6. Model comparison

Different models have different characteristics:

```python
from eqlib.ml import MLSelector

# Random Forest: general-purpose, robust
rf = MLSelector(model='random_forest', features=[...], top_n=3)

# Logistic Regression: simple, interpretable
lr = MLSelector(model='logistic_regression', features=[...], top_n=3)

# Gradient Boosting: high accuracy
gb = MLSelector(model='gradient_boosting', features=[...], top_n=3)
```

---

## 7. Best practices

### 7.1 Prevent overfitting

- Use simpler models (Random Forest is less prone to overfit than XGBoost)
- Limit `max_depth` and `n_estimators`
- Retrain regularly, but not too frequently
- Validate with Walk-Forward Analysis

### 7.2 Feature selection

- Don't use too many features at once (5–10 recommended)
- Prefer features with a direct logical relationship to the target
- Avoid highly correlated features (e.g., RSI and CCI together)

### 7.3 Training frequency

```python
# Option 1: Retrain before every trading day (recommended)
def train_model(context, data=None):
    g.selector.train(context.universe, context)

# Register in initialize: before_trading_start(train_model)

# Option 2: Retrain monthly (every 4 weeks)
g.train_counter = 0
def train_model(context, data=None):
    g.train_counter += 1
    if g.train_counter % 20 == 0:  # roughly every 20 trading days
        g.selector.train(context.universe, context)
```

---

## 8. Complete examples

See:
- `examples/21_ml_selector.py` — basic ML selection
- `examples/22_feature_pipeline.py` — standalone feature computation
- `examples/23_model_comparison.py` — model comparison
- `examples/24_custom_features.py` — custom features
