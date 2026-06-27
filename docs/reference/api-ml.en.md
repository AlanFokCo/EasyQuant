# Machine Learning API

> ML selection, feature engineering, and model wrappers.

---

## FeaturePipeline

Feature engineering pipeline — computes technical-indicator features from OHLCV data.

### Constructor

```python
FeaturePipeline(
    features: list[str] | None = None,
    custom_features: dict[str, Callable] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `features` | `list[str]` | Feature names to compute. If `None`, uses the default set. |
| `custom_features` | `dict[str, Callable]` | Custom feature functions: `{name: func(close, high, low, volume) -> float}` |

### Methods

#### compute

```python
compute(securities, context, lookback=60) -> pd.DataFrame
```

Compute the feature matrix for the given securities.

| Parameter | Type | Description |
|-----------|------|-------------|
| `securities` | `list[str]` | List of security codes |
| `context` | `Context` | Current backtest context |
| `lookback` | `int` | Lookback window in days |

**Returns**: `pd.DataFrame` — index is security codes, columns are feature names

---

## BaseMLModel

ML model wrapper — unifies the sklearn model interface.

### Constructor

```python
BaseMLModel(
    model_type: str = 'random_forest',
    **kwargs,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_type` | `str` | Model type: `random_forest`, `logistic_regression`, `gradient_boosting`, `xgboost` |
| `**kwargs` | | Passed to the underlying model |

### Methods

#### fit

```python
fit(X: pd.DataFrame, y: pd.Series) -> None
```

Train the model.

#### predict

```python
predict(X: pd.DataFrame) -> np.ndarray
```

Predict. For classifiers, returns the positive-class probability (0–1).

#### predict_proba

```python
predict_proba(X: pd.DataFrame) -> np.ndarray
```

Return probabilities for all classes.

#### feature_importances

```python
feature_importances() -> pd.Series
```

Return feature importances (sorted).

#### save / load

```python
model.save(path: str)
loaded = BaseMLModel.load(path: str)
```

Serialize / deserialize the model.

---

## MLSelector

ML-based stock selector, inherits from `StockSelector`.

!!! warning "Single-cross-section training"

    The default training path uses **one day's data** to fit the model.
    With small universes (<50 stocks) this produces few samples and the
    model cannot learn meaningful patterns. For robust training, provide
    `label_data` as a panel DataFrame with historical features and labels
    across many dates.

### Constructor

```python
MLSelector(
    model: str = 'random_forest',
    features: list[str] | None = None,
    target: str = 'past_return_5d',
    top_n: int = 5,
    train_start: str | None = None,
    train_end: str | None = None,
    lookback: int = 60,
    label_data: pd.DataFrame | None = None,
    custom_features: dict[str, Callable] | None = None,
    **model_kwargs,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Model type or `BaseMLModel` instance |
| `features` | `list[str]` | Feature list |
| `target` | `str` | Target variable: `past_return_5d`, `past_return_10d`, `will_rise_5d`. `forward_return_5d` raises `NotImplementedError` — use `label_data` for true forward-return prediction. |
| `top_n` | `int` | Number of stocks to select |
| `train_start` | `str` | Training start date (`YYYY-MM-DD`) |
| `train_end` | `str` | Training end date (`YYYY-MM-DD`) |
| `lookback` | `int` | Historical lookback in days |
| `label_data` | `pd.DataFrame \| None` | Pre-computed label panel DataFrame. Must contain columns `['security', 'date', 'label']`. When provided, the training stage uses this panel instead of computing labels from `target` — this is the recommended path for true forward-return prediction. |
| `custom_features` | `dict[str, Callable] \| None` | Custom feature functions: `{name: func(close, high, low, volume) -> float}`. Function names must also appear in `features` to be invoked. |
| `**model_kwargs` | | Extra model parameters |

### Methods

#### train

```python
train(securities: list[str], context) -> None
```

Train the model on historical data.

#### rank

```python
rank(securities: list[str], context) -> list[str]
```

Return the top-N stocks ranked by model prediction score.

**Returns**: `list[str]` — stock codes (best first)

---

## optimize_hyperparams

Hyperparameter optimization with time-series-aware cross-validation.

```python
from eqlib.ml.tuning import optimize_hyperparams

best_params = optimize_hyperparams(
    pipeline,
    model_type='random_forest',
    X=X_train,
    y=y_train,
    param_grid={'n_estimators': [50, 100, 200]},
    cv_method='time_series_split',
    n_splits=5,
    scoring='roc_auc',
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `pipeline` | `FeaturePipeline` | Feature pipeline instance |
| `model_type` | `str` | Model type |
| `X` | `pd.DataFrame` | Feature matrix |
| `y` | `pd.Series` | Target variable |
| `param_grid` | `dict` | Parameter grid |
| `cv_method` | `str` | `time_series_split` or `walk_forward` |
| `n_splits` | `int` | Number of CV folds |
| `scoring` | `str` | Scoring metric: `roc_auc`, `accuracy`, `neg_log_loss` |

---

## validate_ml_strategy

ML strategy validation.

```python
from eqlib.ml.validation import validate_ml_strategy

report = validate_ml_strategy(
    backtest_result,
    model,
    feature_importance_threshold=0.01,
)
```

**Return fields**:
- `feature_importance`: per-feature importance
- `concentration_risk`: whether importance is too concentrated
- `model_stability`: model stability

---

## check_feature_drift

Detect feature-distribution drift between train and live data via the Kolmogorov-Smirnov statistic.

```python
from eqlib.ml.validation import check_feature_drift

drift = check_feature_drift(X_train, X_live, threshold=0.1)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `X_train` | `pd.DataFrame` | Training feature matrix |
| `X_test` | `pd.DataFrame` | Live / test feature matrix |
| `threshold` | `float` | KS-statistic threshold above which a feature is flagged as drifted |

**Return fields**:
- `drift_scores`: per-feature `{ks_stat, p_value}` dict
- `drifted_features`: list of feature names that exceeded the threshold
- `drift_detected`: boolean — whether any drift was found

!!! tip "When to use"
    Call before each daily / weekly live run to compare the day's feature distribution against the training set. Features that drift need model retraining or monitoring alerts.

---

## auto_tune_selector

Auto-tune hyperparameters for an `MLSelector` instance, using time-series-aware cross-validation.

```python
from eqlib.ml.tuning import auto_tune_selector

best_params = auto_tune_selector(
    selector,
    context,
    param_grid=None,             # default grid by model_type
    cv_method='time_series_split',
    n_splits=3,
    scoring='roc_auc',
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `selector` | `MLSelector` | Configured selector instance |
| `context` | `Context` | Current backtest context (used to read universe and compute features) |
| `param_grid` | `dict \| None` | Parameter grid; `None` selects a default grid by `model_type` |
| `cv_method` | `str` | `'time_series_split'` or `'walk_forward'` (both use `TimeSeriesSplit` underneath) |
| `n_splits` | `int` | Number of CV folds |
| `scoring` | `str` | Scoring metric: `roc_auc`, `accuracy`, `neg_log_loss` |

**Returns**: `dict` — best parameters. Returns an empty dict when data is insufficient or no universe is available.

!!! note "Difference from `optimize_hyperparams`"
    `optimize_hyperparams` requires the caller to prepare `X` / `y`; `auto_tune_selector` pulls data directly from `selector.pipeline.compute(...)` and `selector._compute_target(...)`, suitable for a one-line call inside a strategy's `initialize`.

---

## Built-in features

| Feature | Computation |
|---------|-------------|
| `rsi` | RSI(14) |
| `macd_dif` | MACD difference |
| `macd_dea` | MACD signal line |
| `macd_hist` | MACD histogram |
| `atr` | ATR(14) |
| `boll_upper` | Bollinger upper band |
| `boll_mid` | Bollinger middle band |
| `boll_lower` | Bollinger lower band |
| `donchian_upper` | Donchian upper |
| `donchian_mid` | Donchian middle |
| `donchian_lower` | Donchian lower |
| `cci` | CCI(14) |
| `obv` | OBV |
| `volume_ratio` | 5-day avg volume / 20-day avg volume |
| `momentum` | 20-day momentum |
| `volatility` | 20-day return std |
| `roc` | 12-period rate of change |
