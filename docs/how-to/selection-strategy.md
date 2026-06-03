# 选股策略框架

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 使用 TopNSelector 和 MultiFactorSelector 构建选股策略 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 选股策略框架

eqlib 提供 `TopNSelector` 和 `MultiFactorSelector` 两个选股框架，支持周期性调仓和因子筛选。

### 1.1 TopNSelector：排名选股

按因子值排名选出 Top N 只股票。

```python
from eqlib import TopNSelector

def initialize(context):
    g.selector = TopNSelector(
        universe=['600519', '601390', '000858', '600036', '601166'],
        factor_fn=momentum_factor,  # 自定义因子函数
        top_n=3,
        rebalance_freq='weekly',    # 每周调仓
    )
    run_daily(rebalance, time='every_bar')

def momentum_factor(security, context):
    """动量因子：过去 20 日涨幅"""
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

### 1.2 MultiFactorSelector：多因子选股

结合多个因子进行综合评分选股。

```python
from eqlib import MultiFactorSelector

def initialize(context):
    g.selector = MultiFactorSelector(
        universe=['600519', '601390', '000858', '600036', '601166'],
        factors={
            'momentum': (momentum_factor, 0.4),    # 权重 40%
            'volatility': (volatility_factor, 0.3), # 权重 30%
            'value': (value_factor, 0.3),           # 权重 30%
        },
        top_n=3,
        rebalance_freq='monthly',
    )

def volatility_factor(security, context):
    """波动率因子（逆向）：波动率越低越好"""
    hist = attribute_history(security, 20, '1d', ['close'])
    if hist.empty:
        return None
    returns = hist['close'].pct_change().dropna()
    return -returns.std()  # 取负，使低波动率得分高

def value_factor(security, context):
    """估值因子：PE 越低越好"""
    val = get_valuation(security)
    if val is None or val.get('pe_ratio') is None:
        return None
    return -val['pe_ratio']  # 取负，使低 PE 得分高

def rebalance(context):
    candidates = g.selector.select(context)
    # 调仓逻辑...
```

### 1.3 选股周期配置

| 参数 | 可选值 | 说明 |
|------|--------|------|
| `rebalance_freq` | `'daily'` | 每个交易日调仓 |
| | `'weekly'` | 每周一调仓 |
| | `'biweekly'` | 每两周调仓 |
| | `'monthly'` | 每月首个交易日调仓 |
| | `'quarterly'` | 每季度首个交易日调仓 |

### 1.4 因子函数规范

因子函数签名为：

```python
def my_factor(security: str, context: Context) -> float | None:
    """
    Args:
        security: 股票代码
        context: 策略上下文

    Returns:
        因子值（数值越大越好）或 None（该股票不参与排名）
    """
    pass
```

---

完整 API 参数说明见 [选股策略 API 参考](../reference/api-selection.md)。
