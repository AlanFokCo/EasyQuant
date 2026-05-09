# EasyQuant 工具库参考：计算原理与用法

> 本文档描述 `eqlib.utils` 中全部计算工具的 **具体用法** 和 **底层计算原理**。
> `eqlib.utils` 是 EasyQuant 项目的 Python 包，通过 `from eqlib import utils` 导入。

---

## 目录

1. [技术指标 (indicators)](#1-技术指标-indicators)
2. [统计分析 (stats)](#2-统计分析-stats)
3. [资金管理 (money)](#3-资金管理-money)
4. [支撑阻力位 (levels)](#4-支撑阻力位-levels)

---

## 1. 技术指标 (indicators)

### 1.1 移动平均线

#### `ma(series, period)` — 简单移动平均 (SMA)

**用法：**
```python
from eqlib import utils
ma5 = utils.ma(close, 5)
```

**计算原理：**
```
MA(t) = (C(t) + C(t-1) + ... + C(t-n+1)) / n
```
对最近 `n` 根 K 线的收盘价取算术平均。

#### `ema(series, period)` — 指数移动平均 (EMA)

**用法：**
```python
ema10 = utils.ema(close, 10)
```

**计算原理：**
```
EMA(t) = α * C(t) + (1 - α) * EMA(t-1)
α = 2 / (n + 1)
```
EMA 给予近期价格更高权重，反应更灵敏。初始值取 SMA。

#### `sma(series, period)` — 简单移动平均（`ma` 的别名）

**用法：**
```python
sma14 = utils.sma(close, 14)
```

**计算原理：**
```
SMA(t) = (C(t) + C(t-1) + ... + C(t-n+1)) / n
```
与 `ma` 完全一致，都是滚动算术平均。

#### `smma(series, period, weight=1.0)` — 平滑移动平均（Wilder MA，`weight` 控制平滑强度）

**用法：**
```python
smma14 = utils.smma(close, 14)
```
通常使用默认 `weight=1.0` 即可；只有在需要自定义平滑强度时才需要显式修改。
该默认值对应 Wilder 标准平滑权重。

**计算原理：**
```
SMMA(t) = (SMMA(t-1) * (n - w) + C(t) * w) / n
```
先用前 `n` 根初始化，再按递推公式平滑更新。ADX/RSI 等 Wilder 风格指标更适合用 `smma`。

#### `wma(series, period)` — 加权移动平均

**用法：**
```python
wma10 = utils.wma(close, 10)
```

**计算原理：**
```
WMA(t) = Σ [C(t-i) * (i+1)] / Σ (i+1),  i = 0..n-1
```
线性权重：最近一根 K 线权重最大（n），最远的最小（1）。

#### `vwap(high, low, close, volume, window=None)` — 成交量加权平均价

**用法：**
```python
vwap = utils.vwap(high, low, close, volume)           # 累计 VWAP
vwap20 = utils.vwap(high, low, close, volume, 20)     # 20 日滚动 VWAP
```

**计算原理：**
```
TP = (H + L + C) / 3          # 典型价格
window=None:  VWAP = Σ(TP * Volume) / Σ(Volume)   （累计）
window=N:     VWAP = rolling_sum(TP*Volume, N) / rolling_sum(Volume, N)
```
累计 VWAP（`window=None`）在任何频率都可计算，更适合同一交易会话内的分钟级序列。日线或跨会话分析通常应传入 `window` 使用滚动 VWAP，因为不分会话的累计结果会持续跨日累加。

---

### 1.2 MACD

#### `macd(close, fast=12, slow=26, signal=9)`

**用法：**
```python
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
```

**计算原理：**
```
EMA_fast = EMA(close, fast)
EMA_slow = EMA(close, slow)
DIF = EMA_fast - EMA_slow           # 差离值（快线）
DEA = EMA(DIF, signal)              # 信号线（慢线）
MACD柱 = 2 * (DIF - DEA)            # 直方图
```

**信号解读：**
- DIF 上穿 DEA → 金叉（买入信号）
- DIF 下穿 DEA → 死叉（卖出信号）
- 柱状图由负转正 → 多头动能增强

---

### 1.3 RSI

#### `rsi(close, period=14)`

**用法：**
```python
rsi14 = utils.rsi(close, 14)
```

**计算原理：**
```
Δ = C(t) - C(t-1)
AvgGain  = EMA(max(Δ, 0), period)
AvgLoss  = EMA(max(-Δ, 0), period)
RS = AvgGain / AvgLoss
RSI = 100 - 100 / (1 + RS)
```

**信号解读：**
- RSI > 70 → 超买
- RSI < 30 → 超卖
- RSI 在 50 上方 → 多头占优

---

### 1.4 KDJ

#### `kdj(high, low, close, period=9, smooth=3)`

**用法：**
```python
k, d, j = utils.kdj(high, low, close, period=9, smooth=3)
```

**计算原理：**
```
LLV = min(Low, period)
HHV = max(High, period)
RSV = (C - LLV) / (HHV - LLV) * 100    # 未成熟随机值
K   = EMA(RSV, smooth)                  # 平滑
D   = EMA(K, smooth)                    # 二次平滑
J   = 3*K - 2*D                         # 灵敏度
```

**信号解读：**
- K 上穿 D → 金叉
- J > 100 或 < 0 → 极端区域

---

### 1.5 布林带

#### `boll(close, period=20, num_std=2.0)`

**用法：**
```python
upper, mid, lower = utils.boll(close, period=20, num_std=2.0)
```

**计算原理：**
```
中轨 = MA(close, period)
σ   = STD(close, period)             # 标准差
上轨 = 中轨 + num_std * σ
下轨 = 中轨 - num_std * σ
```

**信号解读：**
- 价格触及上轨 → 可能超买
- 价格触及下轨 → 可能超卖
- 带口收窄（squeeze）→ 即将变盘

---

### 1.6 ATR

#### `atr(high, low, close, period=14)`

**用法：**
```python
atr14 = utils.atr(high, low, close, period=14)
```

**计算原理：**
```
TR(t) = max(H-L, |H-C(t-1)|, |L-C(t-1)|)    # 真实波幅
ATR = EMA(TR, period)                         # 平滑后
```

ATR 反映价格的波动性，不指示方向。常用于设置止损距离。

---

### 1.7 CCI

#### `cci(high, low, close, period=14)`

**用法：**
```python
cci_val = utils.cci(high, low, close, period=14)
```

**计算原理：**
```
TP = (H + L + C) / 3                     # 典型价格
MA_TP = MA(TP, period)                   # TP 的移动平均
MAD  = mean(|TP - MA_TP|, period)        # 平均偏差
CCI = (TP - MA_TP) / (0.015 * MAD)
```

0.015 是常数因子，使约 70%-80% 的 CCI 值落在 [-100, +100] 区间内。

**信号解读：**
- CCI > +100 → 超买
- CCI < -100 → 超卖

---

### 1.8 威廉指标 (Williams %R)

#### `wr(high, low, close, period=14)`

**用法：**
```python
wr_val = utils.wr(high, low, close, period=14)
```

**计算原理：**
```
HHV = max(High, period)
LLV = min(Low, period)
WR = (HHV - C) / (HHV - LLV) * (-100)
```

取值范围 [-100, 0]。与随机指标 KDJ 类似但反向。

**信号解读：**
- WR > -20 → 超买
- WR < -80 → 超卖

---

### 1.9 ROC

#### `roc(close, period=12)`

**用法：**
```python
roc_val = utils.roc(close, period=12)
```

**计算原理：**
```
ROC = (C(t) - C(t-n)) / C(t-n) * 100
```
衡量当前价格相对 `n` 期前价格的变化百分比。

---

### 1.10 OBV

#### `obv(close, volume)`

**用法：**
```python
obv_val = utils.obv(close, volume)
```

**计算原理：**
```
if C(t) > C(t-1):  OBV(t) = OBV(t-1) + Volume(t)
if C(t) < C(t-1):  OBV(t) = OBV(t-1) - Volume(t)
if C(t) == C(t-1): OBV(t) = OBV(t-1)
```
价格上涨时累加成交量，下跌时减去。OBV 趋势与价格趋势背离时可作为反转信号。

---

### 1.11 ADX

#### `adx(high, low, close, period=14)`

**用法：**
```python
pdi, mdi, adx, adxr = utils.adx(high, low, close, period=14)
```

**计算原理：**
```
+DM(t) = max(H(t) - H(t-1), 0)   且 +DM > -DM
-DM(t) = max(L(t-1) - L(t), 0)   且 -DM > +DM

+DI = 100 * WilderSmooth(+DM) / ATR
-DI = 100 * WilderSmooth(-DM) / ATR

DX   = |+DI - -DI| / (+DI + -DI) * 100
ADX  = WilderSmooth(DX, period)
ADXR = (ADX(t) + ADX(t-period)) / 2
```

**信号解读：**
- ADX > 25 → 趋势较强
- ADX < 20 → 无趋势/震荡
- +DI 上穿 -DI → 多头信号

---

### 1.12 金叉 / 死叉

#### `golden_cross(fast_ma, slow_ma)` / `death_cross(fast_ma, slow_ma)`

**用法：**
```python
is_golden = utils.golden_cross(ma5, ma20)
is_death = utils.death_cross(ma5, ma20)
```

**计算原理：**
```
金叉: fast_ma(t-1) <= slow_ma(t-1) AND fast_ma(t) > slow_ma(t)
死叉: fast_ma(t-1) >= slow_ma(t-1) AND fast_ma(t) < slow_ma(t)
```
检测两条均线是否发生交叉。

---

## 2. 统计分析 (stats)

### 2.1 滚动相关系数

#### `rolling_corr(x, y, window)`

**用法：**
```python
corr = utils.rolling_corr(stock_ret, market_ret, 20)
```

**计算原理：**
```
ρ(t) = Cov(x, y) / (σ_x * σ_y)    # 在 window 范围内计算
```

### 2.2 滚动 Beta

#### `rolling_beta(series, benchmark, window, risk_free=0.0)`

**计算原理：**
```
β(t) = Cov(series, benchmark) / Var(benchmark)    # 在 window 内
```

### 2.3 滚动夏普比率

#### `rolling_sharpe(returns, window, risk_free=0.0, annualize=252)`

**计算原理：**
```
Sharpe = (μ * annualize - risk_free) / (σ * √annualize)
```
其中 μ 和 σ 在 rolling window 内计算。

### 2.4 Z-Score

#### `zscore(series, window=None)`

**计算原理：**
```
若 window 设定：Z(t) = (x(t) - μ_window) / σ_window
否则：Z(t) = (x(t) - μ_full) / σ_full
```

### 2.5 百分位排名

#### `percentile_rank(series, window=None)`

**计算原理：**
```
PR(t) = rank(x(t)) / count * 100
```
返回 0-100 之间的值，表示当前值在窗口内的百分位。

### 2.6 线性回归

#### `linear_regression(x, y)`

**计算原理：**
```
β = SS_xy / SS_xx
α = ȳ - β * x̄
R² = 1 - SS_res / SS_tot
t_stat = β / SE(β)
```
返回 alpha、beta、R²、t 统计量和残差序列。

### 2.7 下行偏差

#### `downside_deviation(returns, target=0.0, annualize=252)`

**计算原理：**
```
DD = √[ mean(r²) for r in returns where r < target ] * √annualize
```
只考虑低于目标值的收益，是索提诺比率的分母。

### 2.8 风险价值 (VaR)

#### `value_at_risk(returns, confidence=0.05, method='historical')`

**计算原理：**
```
历史法: VaR = -quantile(returns, confidence)
参数法: VaR = -(μ + z_α * σ)    其中 z_α 为标准正态分位数
```
表示在给定置信度下，可能的最大单日亏损。

### 2.9 条件 VaR (CVaR / Expected Shortfall)

#### `conditional_var(returns, confidence=0.05)`

**计算原理：**
```
CVaR = -E[r | r ≤ -VaR]    # VaR 以外的尾部平均亏损
```
比 VaR 更保守，考虑了尾部极端损失。

### 2.10 回撤分析

#### `drawdown(equity)` / `max_drawdown(equity)`

**计算原理：**
```
Drawdown(t) = (Equity(t) - Peak(t)) / Peak(t)
Peak(t) = max(Equity(0), ..., Equity(t))
MaxDrawdown = min(Drawdown(t))
```

### 2.11 连赢/连亏计数

#### `consecutive_wins(returns)` / `consecutive_losses(returns)`

**计算原理：**
逐日扫描，正收益时递增赢计数（负收益时清零），反之亦然。

### 2.12 复利收益率

#### `compound_return(returns)`

**计算原理：**
```
CR = Π(1 + r_i) - 1
```

### 2.13 年化复合增长率

#### `cagr(start_value, end_value, years)`

**计算原理：**
```
CAGR = (end_value / start_value) ^ (1 / years) - 1
```

### 2.14 对数收益率

#### `log_return(prices)`

**计算原理：**
```
log_return(t) = ln(P(t) / P(t-1))
```

### 2.15 数学工具

| 函数 | 计算 |
|------|------|
| `fibonacci(n)` | 斐波那契数列前 n 项：1, 1, 2, 3, 5, 8, ... |
| `comb(n, k)` | 组合数 C(n,k) = n! / (k! * (n-k)!) |
| `perm(n, k)` | 排列数 P(n,k) = n! / (n-k)! |

---

## 3. 资金管理 (money)

### 3.1 Kelly Criterion

#### `kelly_criterion(win_rate, avg_win, avg_loss)`

**用法：**
```python
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
# 返回 0.25，即投入 25% 资金
```

**计算原理：**
```
b = avg_win / avg_loss     # 盈亏比
q = 1 - win_rate           # 亏损概率
Kelly = (b * win_rate - q) / b
```

Kelly 公式最大化资金的对数增长率。实际应用中常使用 Half-Kelly（一半仓位）以降低波动。

#### `half_kelly(win_rate, avg_win, avg_loss)`

返回 Kelly 值的 50%。

#### `kelly_from_returns(returns)`

从交易收益率序列自动计算 win_rate、avg_win、avg_loss。

---

### 3.2 固定比例风险仓位

#### `fixed_fraction_size(capital, risk_pct, entry_price, stop_price)`

**用法：**
```python
shares = utils.fixed_fraction_size(
    capital=100000, risk_pct=0.02,
    entry_price=10.0, stop_price=9.5,
)  # 最多 4000 股
```

**计算原理：**
```
risk_amount = capital * risk_pct
loss_per_share = |entry_price - stop_price|
shares = floor(risk_amount / loss_per_share / 100) * 100
```

控制单笔交易的最大亏损不超过资金的 risk_pct（通常 1-2%）。

---

### 3.3 固定比例分配

#### `fixed_ratio_size(capital, equity_ratio, entry_price)`

**计算原理：**
```
allocation = capital * equity_ratio
shares = floor(allocation / entry_price / 100) * 100
```

按资金的固定百分比（如 10%）分配给单只股票。

---

### 3.4 ATR 仓位管理

#### `atr_position_size(capital, risk_pct, atr, n_atr=2.0)`

**用法：**
```python
shares = utils.atr_position_size(
    capital=100000, risk_pct=0.02,
    atr=0.30, n_atr=2.0,
)
```

**计算原理：**
```
stop_distance = ATR * n_atr
shares = floor(capital * risk_pct / stop_distance / 100) * 100
```

波动大的股票自动减少仓位，波动小的增加仓位。

---

### 3.5 波动率目标仓位

#### `volatility_target_size(capital, target_vol, price, vol_per_share)`

**计算原理：**
```
target_value = capital * target_vol / vol_per_share
shares = floor(target_value / price / 100) * 100
```

使投资组合整体波动率等于 target_vol。

---

### 3.6 马丁格尔 / 反马丁格尔

#### `martingale_size(base_amount, loss_streak, multiplier=2.0)`

**计算原理：**
```
size = base_amount * multiplier ^ loss_streak
```
连亏后加倍下注，赌概率回归。风险极高。

#### `anti_martingale_size(base_amount, win_streak, multiplier=1.5)`

**计算原理：**
```
size = base_amount * multiplier ^ win_streak
```
连赢后加仓，顺势放大收益。

---

### 3.7 组合权重

#### `equal_weight(n)`

等权重：`w_i = 1/n`。

#### `risk_parity_weights(volatilities)`

**计算原理：**
```
w_i = (1/σ_i) / Σ(1/σ_j)
```
低波动资产获得更高权重，使各资产对组合风险的贡献相等。

#### `volatility_normalize(returns)`

**计算原理：**
```
normalized_return(t) = r(t) / σ_20(t)
```
用滚动 20 日标准差标准化收益率。

---

## 4. 支撑阻力位 (levels)

### 4.1 枢轴点 (Pivot Points)

枢轴点基于前一日的高低收价格计算次日的支撑/阻力位。

#### `pivot_classic(high, low, close)` — 经典枢轴点

**计算原理：**
```
PP  = (H + L + C) / 3
R1  = 2*PP - L
S1  = 2*PP - H
R2  = PP + (H - L)
S2  = PP - (H - L)
R3  = H + 2*(PP - L)
S3  = L - 2*(H - PP)
```

#### `pivot_fibonacci(high, low, close)` — 斐波那契枢轴点

**计算原理：**
```
PP = (H + L + C) / 3
R1 = PP + 0.382 * (H - L)    S1 = PP - 0.382 * (H - L)
R2 = PP + 0.618 * (H - L)    S2 = PP - 0.618 * (H - L)
R3 = PP + 1.000 * (H - L)    S3 = PP - 1.000 * (H - L)
```

#### `pivot_woodie(high, low, close)` — 伍迪枢轴点

**计算原理：**
```
PP = (H + L + 2*C) / 4       # 收盘价权重翻倍
R1 = 2*PP - L
S1 = 2*PP - H
R2 = PP + (H - L)
S2 = PP - (H - L)
```

#### `pivot_camarilla(high, low, close)` — 卡玛利拉枢轴点

**计算原理：**
```
R4 = (H - L) * 1.1 / 2  + C     R1 = (H - L) * 1.1 / 12 + C
R3 = (H - L) * 1.1 / 4  + C     S1 = C - (H - L) * 1.1 / 12
R2 = (H - L) * 1.1 / 6  + C     S2 = C - (H - L) * 1.1 / 6
                                S3 = C - (H - L) * 1.1 / 4
                                S4 = C - (H - L) * 1.1 / 2
```
区间更窄，适合日内交易。R4/S4 为突破级别。

#### `pivot_demark(high, low, close, open_=None)` — 德马克枢轴点

**计算原理：**
```
若 C < O:  X = H + 2*L + C
若 C > O:  X = 2*H + L + C
若 C = O:  X = H + L + 2*C

PP = X / 4
R1 = X/2 - L
S1 = X/2 - H
```

---

### 4.2 摆动高低点 (Swing Highs/Lows)

#### `swing_highs_lows(high, low, left_bars=5, right_bars=5)`

**计算原理：**
```
Swing High: H(t) > max(H(t-n) ... H(t+n))   即比左右各 N 根 bar 都高
Swing Low:  L(t) < min(L(t-n) ... L(t+n))   即比左右各 N 根 bar 都低
```

#### `support_resistance_levels(high, low, close=None, lookback=50, tolerance=0.02)`

**计算原理：**
1. 在 `lookback` 范围内找 Swing Highs/Lows
2. 将价格相近（相差 < tolerance%）的摆动点聚类
3. 聚类中心即为支撑/阻力位
4. 找出距离当前价最近的支撑位和阻力位

---

### 4.3 斐波那契回撤

#### `fibonacci_retracement(high, low, close=None, lookback=100)`

**用法：**
```python
fib = utils.fibonacci_retracement(high, low, close, lookback=100)
print(fib[0.382], fib[0.618])  # 关键回撤位
```

**计算原理：**
```
swing_high = max(High, lookback)
swing_low  = min(Low, lookback)
diff = swing_high - swing_low

上升趋势回撤位 = swing_high - ratio * diff
下降趋势回撤位 = swing_low + ratio * diff
```

关键回撤比率：0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

---

### 4.4 唐奇安通道

#### `donchian(high, low, close=None, period=20)`

**计算原理：**
```
上轨 = max(High, period)
下轨 = min(Low, period)
中轨 = (上轨 + 下轨) / 2
```

海龟交易法的核心信号：价格突破上轨买入，跌破下轨卖出。

---

### 4.5 整数心理价位

#### `psychological_levels(price, step=1.0, count=10)`

**计算原理：**
在当前价格附近生成以 `step` 为间隔的整数价位。例如 price=5.23, step=1.0 生成 1.0, 2.0, 3.0, ..., 10.0。整数价位常因交易心理形成支撑/阻力。

---

### 4.6 成交量分布 (Volume Profile)

#### `volume_profile_support_resistance(close, volume, n_bins=50, lookback=100)`

**计算原理：**
1. 将 `lookback` 范围内的价格区间分成 `n_bins` 个价格区间
2. 统计每个价格区间内的总成交量
3. 成交量最大的价格 = POC (Point of Control)
4. 从 POC 向外扩展，累计 70% 成交量的区间 = Value Area
   - VAH (Value Area High)：成交量分布上边界
   - VAL (Value Area Low)：成交量分布下边界
5. 高于中位数成交量的价格区间标记为重要节点

**信号解读：**
- POC 附近：价格反复争夺的平衡区域，形成支撑/阻力
- VAH/VAL：价值区边界，突破后可能加速

---

### 4.7 均线动态支撑阻力

#### `ma_support_resistance(close, periods=None)`

**用法：**
```python
levels = utils.ma_support_resistance(close, periods=[20, 50, 200])
```

**计算原理：**
对指定周期的 MA 均线，价格在均线上方时均线形成支撑，在下方时形成阻力。默认周期 [20, 50, 200] 分别对应短/中/长期。

---

### 4.8 前日高低收

#### `prev_day_levels(high, low, close)`

**计算原理：**
```
prev_high = high.shift(1)
prev_low  = low.shift(1)
prev_close = close.shift(1)
```
前日的高低收价格常作为当日的支撑/阻力参考。

---

### 4.9 ATR 追踪止损

#### `trailing_stop(close, atr=None, high=None, low=None, multiplier=2.0, period=14)`

**计算原理：**
```
stop_level(t) = close(t) - multiplier * ATR(t)
trailing_stop(t) = max(stop_level(0), ..., stop_level(t))
```

止损线只上移不下移，锁定利润。

---

### 4.10 缺口检测

#### `gap_up_down(open_, high, low, close)`

**计算原理：**
```
缺口向上: Low(t) > High(t-1)    缺口价位 = (High(t-1) + Low(t)) / 2
缺口向下: High(t) < Low(t-1)    缺口价位 = (Low(t-1) + High(t)) / 2
```

缺口区域常形成未来的支撑/阻力位。

---

## 附录：完整导入方式

```python
from eqlib import utils

# 技术指标
utils.ma(close, 5)
utils.rsi(close, 14)
utils.macd(close, 12, 26, 9)
utils.kdj(high, low, close, 9)
utils.boll(close, 20)
utils.atr(high, low, close, 14)

# 支撑阻力位
utils.pivot_classic(high, low, close)
utils.support_resistance_levels(high, low, close)
utils.fibonacci_retracement(high, low, close)
utils.donchian(high, low, close)
utils.volume_profile_support_resistance(close, volume)
utils.trailing_stop(close, atr=atr_val)
utils.gap_up_down(open_, high, low, close)

# 统计
utils.rolling_sharpe(returns, 20)
utils.value_at_risk(returns)
utils.max_drawdown(equity)
utils.cagr(100, 200, 2)

# 资金管理
utils.kelly_criterion(0.55, 1500, 1000)
utils.atr_position_size(100000, 0.02, 0.30)
utils.risk_parity_weights([0.15, 0.25, 0.20])
```
