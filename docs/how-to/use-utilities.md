# 计算工具库

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 使用技术指标、统计分析、资金管理工具 |
    | **前置** | [编写策略](write-strategy.md) |

---
## 1. 计算工具库

`eqlib.utils` 提供了技术指标、统计分析、资金管理和支撑阻力位计算工具。

### 1.1 技术指标

```python
from eqlib import utils

ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
rsi14 = utils.rsi(close, 14)
k, d, j = utils.kdj(high, low, close, period=9)
upper, mid, lower = utils.boll(close, period=20)
atr14 = utils.atr(high, low, close, 14)
```

### 1.2 统计分析

```python
sharpe = utils.rolling_sharpe(daily_returns, window=20)
max_dd, dd_start, dd_end = utils.max_drawdown(equity_curve)
var_5 = utils.value_at_risk(daily_returns, confidence=0.05)
```

### 1.3 资金管理

```python
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
shares = utils.atr_position_size(capital=100000, risk_pct=0.02, atr=0.30, n_atr=2.0)
weights = utils.risk_parity_weights([0.15, 0.25, 0.20])
```

### 1.4 支撑阻力位

```python
pp, r1, s1, r2, s2, r3, s3 = utils.pivot_classic(high, low, close)
sr = utils.support_resistance_levels(high, low, close)
fib = utils.fibonacci_retracement(high, low, close)
```

详细说明见 [工具库参考](../reference/utils.md)。

---

完整函数参数与数学定义见 [工具库参考](../reference/utils.md)。
