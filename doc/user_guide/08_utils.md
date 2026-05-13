!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §7](07_data.md) · [下一章 §9](09_backtest.md)

---

## 8. 计算工具库

`eqlib.utils` 提供了完整的技术指标、统计分析、资金管理和支撑阻力位计算工具。

### 8.1 技术指标

```python
from eqlib import utils

# 均线
ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)

# MACD
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)

# RSI
rsi14 = utils.rsi(close, 14)

# KDJ
k, d, j = utils.kdj(high, low, close, period=9)

# 布林带
upper, mid, lower = utils.boll(close, period=20)

# ATR（波动率）
atr14 = utils.atr(high, low, close, 14)

# ADX（趋势强度）
pdi, mdi, adx, adxr = utils.adx(high, low, close, 14)
```

更多指标：`cci`, `wr`（威廉指标）, `roc`（变化率）, `obv`（能量潮）, `golden_cross`, `death_cross`

### 8.2 统计分析

```python
# 滚动夏普比率
sharpe = utils.rolling_sharpe(daily_returns, window=20)

# 最大回撤
max_dd, dd_start, dd_end = utils.max_drawdown(equity_curve)

# 风险价值
var_5 = utils.value_at_risk(daily_returns, confidence=0.05)

# Z-Score
z = utils.zscore(close, window=20)

# 年化复合增长率
cagr_val = utils.cagr(start_value, end_value, years)
```

### 8.3 资金管理

```python
# Kelly 公式
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
# 返回 0.25，即建议投入 25% 资金

# ATR 仓位管理
shares = utils.atr_position_size(
    capital=100000, risk_pct=0.02,
    atr=0.30, n_atr=2.0,
)  # 根据波动率自动计算股数

# 固定比例风险
shares = utils.fixed_fraction_size(
    capital=100000, risk_pct=0.02,
    entry_price=10.0, stop_price=9.5,
)  # 最多亏 2% 资金的股数

# 风险平价权重
weights = utils.risk_parity_weights([0.15, 0.25, 0.20])
```

### 8.4 支撑阻力位

```python
# 枢轴点（返回 pp, r1, s1, r2, s2, r3, s3 共 7 个值）
pp, r1, s1, r2, s2, r3, s3 = utils.pivot_classic(high, low, close)

# 支撑/阻力位（摆动点聚类）
sr = utils.support_resistance_levels(high, low, close)
print(sr['nearest_support'])
print(sr['nearest_resistance'])

# 斐波那契回撤
fib = utils.fibonacci_retracement(high, low, close)
print(fib[0.382], fib[0.618])

# 唐奇安通道（海龟交易法）
upper, mid, lower = utils.donchian(high, low, close)

# 成交量分布
vp = utils.volume_profile_support_resistance(close, volume)
print(vp['poc'])  # 最大成交量价格

# ATR 追踪止损
stop = utils.trailing_stop(close, atr=atr_val, multiplier=2.0)

# 缺口检测
gap_up, gap_down = utils.gap_up_down(open_, high, low, close)
```

> **详细说明**：每个工具的具体算法和计算原理见 [**工具库参考**](../utils_reference.md)。
