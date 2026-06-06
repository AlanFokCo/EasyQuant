# 机器学习 API

> ML 选股、特征工程、模型封装。

---

## FeaturePipeline

特征工程管道，从 OHLCV 数据计算技术指标特征。

### 构造函数

```python
FeaturePipeline(
    features: list[str] | None = None,
    custom_features: dict[str, Callable] | None = None,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `features` | `list[str]` | 要计算的特征列表。如果为 `None`，使用默认特征集 |
| `custom_features` | `dict[str, Callable]` | 自定义特征函数，格式：`{name: func(close, high, low, volume) -> float}` |

### 方法

#### compute

```python
compute(securities, context, lookback=60) -> pd.DataFrame
```

计算给定证券的特征矩阵。

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 证券代码列表 |
| `context` | `Context` | 当前回测上下文 |
| `lookback` | `int` | 回看天数 |

**返回**: `pd.DataFrame`，index 为证券代码，columns 为特征名

---

## BaseMLModel

ML 模型封装，统一 sklearn 模型接口。

### 构造函数

```python
BaseMLModel(
    model_type: str = 'random_forest',
    **kwargs,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `model_type` | `str` | 模型类型：`random_forest`, `logistic_regression`, `gradient_boosting`, `xgboost` |
| `**kwargs` | | 传递给底层模型的参数 |

### 方法

#### fit

```python
fit(X: pd.DataFrame, y: pd.Series) -> None
```

训练模型。

#### predict

```python
predict(X: pd.DataFrame) -> np.ndarray
```

预测。对于分类器，返回正类的概率（0-1）。

#### predict_proba

```python
predict_proba(X: pd.DataFrame) -> np.ndarray
```

返回所有类别的概率。

#### feature_importances

```python
feature_importances() -> pd.Series
```

返回特征重要性（已排序）。

#### save / load

```python
model.save(path: str)
loaded = BaseMLModel.load(path: str)
```

序列化/反序列化模型。

---

## MLSelector

基于机器学习的股票选择器，继承自 `StockSelector`。

### 构造函数

```python
MLSelector(
    model: str = 'random_forest',
    features: list[str] | None = None,
    target: str = 'forward_return_5d',
    top_n: int = 5,
    train_start: str | None = None,
    train_end: str | None = None,
    lookback: int = 60,
    **model_kwargs,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `str` | 模型类型或 `BaseMLModel` 实例 |
| `features` | `list[str]` | 特征列表 |
| `target` | `str` | 目标变量：`forward_return_5d`, `forward_return_10d`, `will_rise_5d` |
| `top_n` | `int` | 选出股票数量 |
| `train_start` | `str` | 训练开始日期（`YYYY-MM-DD`） |
| `train_end` | `str` | 训练结束日期（`YYYY-MM-DD`） |
| `lookback` | `int` | 历史数据回看天数 |
| `**model_kwargs` | | 模型额外参数 |

### 方法

#### train

```python
train(securities: list[str], context) -> None
```

在 historical 数据上训练模型。

#### rank

```python
rank(securities: list[str], context) -> list[str]
```

返回按模型预测得分排序的 Top-N 股票列表。

**返回**: `list[str]` — 股票代码列表（best first）

---

## optimize_hyperparams

超参数优化（时间序列感知的交叉验证）。

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

| 参数 | 类型 | 说明 |
|------|------|------|
| `pipeline` | `FeaturePipeline` | 特征管道实例 |
| `model_type` | `str` | 模型类型 |
| `X` | `pd.DataFrame` | 特征矩阵 |
| `y` | `pd.Series` | 目标变量 |
| `param_grid` | `dict` | 参数网格 |
| `cv_method` | `str` | `time_series_split` 或 `walk_forward` |
| `n_splits` | `int` | 交叉验证折数 |
| `scoring` | `str` | 评分指标：`roc_auc`, `accuracy`, `neg_log_loss` |

---

## validate_ml_strategy

ML 策略验证。

```python
from eqlib.ml.validation import validate_ml_strategy

report = validate_ml_strategy(
    backtest_result,
    model,
    feature_importance_threshold=0.01,
)
```

**返回字段**：
- `feature_importance`: 各特征重要性
- `concentration_risk`: 特征重要性是否过于集中
- `model_stability`: 模型稳定性

---

## 内置特征列表

| 特征名 | 计算方式 |
|--------|----------|
| `rsi` | RSI(14) |
| `macd_dif` | MACD 差离值 |
| `macd_dea` | MACD 信号线 |
| `macd_hist` | MACD 柱状图 |
| `atr` | ATR(14) |
| `boll_upper` | 布林带上轨 |
| `boll_mid` | 布林带中轨 |
| `boll_lower` | 布林带下轨 |
| `donchian_upper` | 唐奇安通道上轨 |
| `donchian_mid` | 唐奇安通道中轨 |
| `donchian_lower` | 唐奇安通道下轨 |
| `cci` | CCI(14) |
| `obv` | OBV |
| `volume_ratio` | 5日平均成交量 / 20日平均成交量 |
| `momentum` | 20日动量 |
| `volatility` | 20日收益率标准差 |
| `roc` | 12期变动率 |
