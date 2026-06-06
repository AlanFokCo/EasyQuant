# 机器学习选股

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 使用 MLSelector 替代手工权重，让模型自动学习因子权重与交互 |
    | **前置** | [运行回测](run-backtest.md)、[选股策略框架](../how-to/selection-strategy.md) |

---

## 1. 为什么需要机器学习选股？

传统多因子选股使用**手工权重**：

```python
from eqlib import MultiFactorSelector

selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
    top_n=5,
)
```n
**问题**：
- 权重是作者凭经验手工调的，可能只适合特定市场环境
- 因子之间的交互关系被忽略（如"动量 + 高波动"在不同 regime 下效果不同）
- 无法处理非线性关系

**ML 选股**用模型自动学习：
- 每个因子的重要性（不是固定的，而是数据驱动的）
- 因子之间的交互关系
- 随时间变化的权重

---

## 2. 最简单的 ML 选股策略

```python
from eqlib import *
from eqlib.ml import MLSelector

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                              open_commission=0.0003, close_commission=0.0003))

    context.universe = ['601390', '600519', '000858', '002594', '601398']

    # ML 选股器：自动学习因子权重
    g.selector = MLSelector(
        model='random_forest',
        features=['rsi', 'macd_hist', 'atr', 'momentum', 'volatility'],
        target='forward_return_5d',
        top_n=3,
    )

    run_weekly(rebalance, day_of_week=0, time='every_bar')

def before_trading_start(context):
    # 每周重新训练模型（使用最新数据）
    g.selector.train(context.universe, context)

def rebalance(context):
    # 获取模型选出的 Top-3 股票
    selected = g.selector.rank(context.universe, context)

    # 卖出不在选中列表的股票
    for pos in list(context.portfolio.positions.keys()):
        if pos not in selected:
            order_target(pos, 0)

    # 买入选中的股票
    if selected:
        cash_per_stock = context.portfolio.available_cash / len(selected)
        for stock in selected:
            order_value(stock, cash_per_stock)

# 运行回测
result = run_strategy(
    initialize,
    start_date='2022-01-01',
    end_date='2024-01-01',
    securities=['601390', '600519', '000858', '002594', '601398'],
)
```

---

## 3. MLSelector 参数详解

```python
MLSelector(
    model='random_forest',           # 模型类型
    features=['rsi', 'macd_hist'],  # 使用的特征
    target='forward_return_5d',      # 预测目标
    top_n=5,                         # 选出股票数量
    train_start=None,                # 训练开始日期（可选）
    train_end=None,                  # 训练结束日期（可选）
    lookback=60,                     # 历史数据回看天数
)
```

### model — 模型类型

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| `random_forest` | 随机森林（默认） | 通用场景，稳健，不易过拟合 |
| `logistic_regression` | 逻辑回归 | 简单场景，可解释性强 |
| `gradient_boosting` | 梯度提升 | 需要高精度时 |
| `xgboost` | XGBoost | 需要高精度时（需安装 xgboost） |

### features — 可用特征

| 特征 | 说明 |
|------|------|
| `rsi` | RSI(14) 相对强弱指标 |
| `macd_dif`, `macd_dea`, `macd_hist` | MACD 三线的值 |
| `atr` | ATR(14) 平均真实波幅 |
| `boll_upper`, `boll_mid`, `boll_lower` | 布林带 |
| `donchian_upper`, `donchian_mid`, `donchian_lower` | 唐奇安通道 |
| `cci` | CCI(14) 商品通道指标 |
| `obv` | OBV 能量潮 |
| `volume_ratio` | 5 日平均成交量 / 20 日平均成交量 |
| `momentum` | 20 日动量 (price / price[-20] - 1) |
| `volatility` | 20 日收益率标准差 |
| `roc` | 12 期变动率 |

### target — 预测目标

| 目标 | 说明 |
|------|------|
| `forward_return_5d` | 未来 5 日收益率（分类或回归） |
| `forward_return_10d` | 未来 10 日收益率 |
| `will_rise_5d` | 未来 5 日是否上涨（0/1 分类） |

---

## 4. 使用 FeaturePipeline 独立计算特征

有时你需要直接使用特征（如可视化、分析），不经过 MLSelector：

```python
from eqlib.ml import FeaturePipeline

g.pipeline = FeaturePipeline(features=['rsi', 'macd_hist', 'momentum'])

def rebalance(context):
    # 计算特征
    features = g.pipeline.compute(context.universe, context, lookback=60)

    # features 是一个 DataFrame
    # index = 股票代码, columns = 特征名
    print(features.head())
    #              rsi  macd_hist  momentum
    # 601390     45.2       0.12      0.03
    # 600519     62.1      -0.05     -0.01
```

---

## 5. 自定义特征

你可以添加自己的特征函数：

```python
from eqlib.ml import FeaturePipeline, MLSelector

def price_to_ma_ratio(close, high, low, volume):
    """价格相对 20 日均线的偏离度"""
    if len(close) < 20:
        return float('nan')
    ma20 = close.iloc[-20:].mean()
    return float(close.iloc[-1] / ma20 - 1.0)

# 创建带有自定义特征的 Pipeline
g.selector = MLSelector(
    features=['rsi', 'momentum', 'price_ma_ratio'],
    target='forward_return_5d',
    top_n=3,
)
g.selector.pipeline = FeaturePipeline(
    features=['rsi', 'momentum', 'price_ma_ratio'],
    custom_features={'price_ma_ratio': price_to_ma_ratio},
)
```

---

## 6. 模型对比

不同模型有不同的特点：

```python
from eqlib.ml import MLSelector

# Random Forest: 通用、稳健
rf = MLSelector(model='random_forest', features=[...], top_n=3)

# Logistic Regression: 简单、可解释
lr = MLSelector(model='logistic_regression', features=[...], top_n=3)

# Gradient Boosting: 高精度
 gb = MLSelector(model='gradient_boosting', features=[...], top_n=3)
```

---

## 7. 最佳实践

### 7.1 防止过拟合

- 使用简单的模型（Random Forest 比 XGBoost 更不容易过拟合）
- 限制 `max_depth` 和 `n_estimators`
- 定期重新训练，但不要过于频繁
- 使用 Walk-Forward Analysis 验证

### 7.2 特征选择

- 不要一次使用太多特征（建议 5-10 个）
- 优先使用与目标有直接逻辑关系的特征
- 避免高度相关的特征（如同时使用 RSI 和 CCI）

### 7.3 训练频率

```python
# 方式一：每周重新训练（推荐）
def before_trading_start(context):
    g.selector.train(context.universe, context)

# 方式二：每月重新训练
g.train_counter = 0
def before_trading_start(context):
    g.train_counter += 1
    if g.train_counter % 4 == 0:  # 每 4 周训练一次
        g.selector.train(context.universe, context)
```

---

## 8. 完整示例

详见 `examples/21_ml_selector.py`（基础 ML 选股）、
`examples/22_feature_pipeline.py`（独立特征计算）、
`examples/23_model_comparison.py`（模型对比）、
`examples/24_custom_features.py`（自定义特征）。
