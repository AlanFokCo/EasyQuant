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

!!! warning "单日横截面训练"

    默认训练路径使用**单日数据**拟合模型。当 universe 较小（<50 只）
    时样本量很少，模型无法学到有意义的模式。如需稳健训练，请通过
    `label_data` 传入 panel DataFrame（包含多日特征与标签）。

### 构造函数

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

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `str` | 模型类型或 `BaseMLModel` 实例 |
| `features` | `list[str]` | 特征列表 |
| `target` | `str` | 目标变量：`past_return_5d`、`past_return_10d`、`will_rise_5d`。`forward_return_5d` 会抛 `NotImplementedError`——如需真正的 forward-return 预测，请通过 `label_data` 传入预计算标签。 |
| `top_n` | `int` | 选出股票数量 |
| `train_start` | `str` | 训练开始日期（`YYYY-MM-DD`） |
| `train_end` | `str` | 训练结束日期（`YYYY-MM-DD`） |
| `lookback` | `int` | 历史数据回看天数 |
| `label_data` | `pd.DataFrame \| None` | 预计算标签 panel DataFrame，必须包含 `['security', 'date', 'label']` 三列。传入后训练阶段将使用此 panel 而非按 `target` 现算——这是实现真正 forward-return 预测的推荐路径 |
| `custom_features` | `dict[str, Callable] \| None` | 自定义特征函数映射，格式 `{name: func(close, high, low, volume) -> float}`。函数名必须同时出现在 `features` 列表中才会被调用 |
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

## check_feature_drift

检测训练集与样本外特征分布是否发生漂移（KS 检验）。

```python
from eqlib.ml.validation import check_feature_drift

drift = check_feature_drift(
    X_train,
    X_test,
    threshold=0.1,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `X_train` | `pd.DataFrame` | 训练集特征矩阵 |
| `X_test` | `pd.DataFrame` | 样本外 / 实盘特征矩阵 |
| `threshold` | `float` | KS 统计量阈值，超过则标记为漂移（默认 0.1） |

**返回字段**：
- `drift_scores`: 各特征的 `{ks_stat, p_value}` 字典
- `drifted_features`: 超过阈值的特征名列表
- `drift_detected`: 是否存在漂移（布尔）

!!! tip "何时使用"
    在每日 / 每周实盘运行前调用，比较当日特征分布与训练集。出现漂移的特征需要重新训练模型或加入监控告警。

---

## auto_tune_selector

基于 `MLSelector` 的 universe 自动调参（时间序列感知交叉验证）。

```python
from eqlib.ml.tuning import auto_tune_selector

best_params = auto_tune_selector(
    selector,
    context,
    param_grid=None,             # 默认网格按 model_type 选取
    cv_method='time_series_split',
    n_splits=3,
    scoring='roc_auc',
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `selector` | `MLSelector` | 已配置好的选股器实例 |
| `context` | `Context` | 当前回测上下文（用于取 universe 和计算特征） |
| `param_grid` | `dict \| None` | 参数网格，`None` 时按 `model_type` 使用默认网格 |
| `cv_method` | `str` | `'time_series_split'` 或 `'walk_forward'`（底层均使用 `TimeSeriesSplit`） |
| `n_splits` | `int` | 交叉验证折数 |
| `scoring` | `str` | 评分指标：`roc_auc`、`accuracy`、`neg_log_loss` |

**返回**：`dict` —— 最优参数。数据量不足或无 universe 时返回空字典。

!!! note "与 `optimize_hyperparams` 的区别"
    `optimize_hyperparams` 需要调用方自行准备 `X` / `y`；`auto_tune_selector` 直接从 `selector.pipeline.compute(...)` 和 `selector._compute_target(...)` 取数据，适合在策略 `initialize` 中一行调用。

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
