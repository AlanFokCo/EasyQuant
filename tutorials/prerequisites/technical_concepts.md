# 前置知识：技术分析基础概念

> 本文面向**从未接触过技术分析**的读者。如果你已经了解均线、RSI、MACD，可直接跳过，从 [Tutorial 01](../01_quant_basics.md) 开始。

---

## 目录

1. [价格数据：OHLCV](#1-价格数据ohlcv)
2. [移动均线（MA）](#2-移动均线ma)
3. [RSI：相对强弱指标](#3-rsi相对强弱指标)
4. [MACD：异同移动平均](#4-macd异同移动平均)
5. [布林带（Bollinger Bands）](#5-布林带bollinger-bands)
6. [ATR：平均真实波幅](#6-atr平均真实波幅)
7. [KDJ / 随机指标](#7-kdj--随机指标)
8. [ADX：趋势强度](#8-adx趋势强度)
9. [成交量相关概念](#9-成交量相关概念)
10. [支撑与阻力](#10-支撑与阻力)
11. [eqlib.utils 对应的函数](#11-eqlibutils-对应的函数)
12. [下一步](#12-下一步)

---

## 1. 价格数据：OHLCV

每一根 K 线（Candlestick / Bar）包含 5 个字段，合称 **OHLCV**：

| 字段 | 英文 | 含义 |
|------|------|------|
| `open` | Open | 开盘价 |
| `high` | High | 最高价 |
| `low` | Low | 最低价 |
| `close` | Close | 收盘价 |
| `volume` | Volume | 成交量（股数） |

有时还有 `money`（成交额，单位元）= 价格 × 成交量 的近似。

```python
# eqlib 中获取 OHLCV 数据
hist = attribute_history('601390', 20, '1d', ['open', 'high', 'low', 'close', 'volume'])
#           open   high    low  close      volume
# 2024-01-02  4.85   4.92   4.80   4.88  1234567890
# 2024-01-03  4.89   4.95   4.85   4.92  987654321
```

**为什么常用收盘价？**  
大多数策略用 `close`，因为它代表当天市场最终定价，最被广泛引用。某些策略会同时用到 `high` / `low` / `volume`（如 ATR 需要三者，布林带只需收盘价）。

---

## 2. 移动均线（MA）

### 2.1 简单移动均线（SMA）

最近 N 天收盘价的**算术平均**：

```
MA(N) = (close[0] + close[1] + ... + close[N-1]) / N
```

**典型参数：** MA5（周线）、MA10（两周）、MA20（月线）、MA60（季线）、MA120（半年）、MA250（年线）

```python
from eqlib import *
from eqlib.utils import ma

hist = attribute_history('601390', 60, '1d', ['close'])
close = hist['close']

# 手动计算
ma5  = close.tail(5).mean()
ma20 = close.tail(20).mean()

# 用 eqlib.utils
ma5_series  = ma(close, 5)    # 返回整个 Series，iloc[-1] 取最新值
ma20_series = ma(close, 20)
```

### 2.2 指数移动均线（EMA）

对近期数据**赋予更高权重**的均线，比 SMA 对价格变化反应更快：

```python
from eqlib.utils import ema

ema12 = ema(close, 12)
ema26 = ema(close, 26)
```

### 2.3 Wilder 平滑均线（SMMA）

RSI、ATR、ADX 内部使用的平滑方法（也叫 RMA / Wilder's Smoothing）：

```python
from eqlib.utils import smma

smma14 = smma(close, 14)
```

> **注意（来自项目约定）**：`eqlib.utils.sma()` = 简单滚动均值；`eqlib.utils.smma()` = Wilder 平滑均线。RSI / ATR 相关指标请用 `smma()`。

### 2.4 均线的用途

| 场景 | 用法 |
|------|------|
| 趋势判断 | 价格在均线上方 = 多头；在均线下方 = 空头 |
| 金叉 / 死叉 | 短期均线上穿长期均线 = 买入信号（金叉）；下穿 = 卖出信号（死叉） |
| 支撑 / 压力 | 均线本身常成为价格的支撑或压力位 |
| 趋势强度 | 多条均线多头排列（短 > 中 > 长）表示强趋势 |

---

## 3. RSI：相对强弱指标

**RSI（Relative Strength Index）** 衡量价格上涨动力与下跌动力的比值，结果映射到 0–100 区间。

### 3.1 计算逻辑（简化）

```
1. 计算过去 N 天的涨幅（up）和跌幅（down）的平均值
2. RS = 平均涨幅 / 平均跌幅
3. RSI = 100 - 100 / (1 + RS)
```

**典型参数：** `period=14`（最常用）

### 3.2 读法

| RSI 数值 | 含义 | 策略含义 |
|---------|------|---------|
| > 70 | 超买（Overbought） | 可能下跌，考虑卖出 |
| 50–70 | 偏强 | 多头市场 |
| 30–50 | 偏弱 | 空头市场 |
| < 30 | 超卖（Oversold） | 可能反弹，考虑买入 |

```python
from eqlib.utils import rsi

hist = attribute_history('601390', 60, '1d', ['close'])
rsi14 = rsi(hist['close'], 14)   # 返回 Series
current_rsi = rsi14.iloc[-1]

if current_rsi < 30:
    print('超卖，关注买入机会')
```

---

## 4. MACD：异同移动平均

**MACD（Moving Average Convergence/Divergence）** 由两条均线的差值派生出三条线：

| 线 | 计算 | 含义 |
|----|------|------|
| **DIF（MACD Line）** | EMA(12) − EMA(26) | 短期与长期均线的差 |
| **DEA（Signal Line）** | EMA(DIF, 9) | DIF 的 9 日均线（平滑） |
| **柱状图（Histogram）** | (DIF − DEA) × 2 | 两线距离，正/负代表多/空 |

### 读法

- **DIF 上穿 DEA**（柱状图由负转正）→ 买入信号（"金叉"）
- **DIF 下穿 DEA**（柱状图由正转负）→ 卖出信号（"死叉"）
- **柱状图由缩短转放大**（量能增加）→ 趋势强化

```python
from eqlib.utils import macd

hist = attribute_history('601390', 60, '1d', ['close'])
dif, dea, histogram = macd(hist['close'], fast=12, slow=26, signal=9)

latest_dif = dif.iloc[-1]
latest_dea = dea.iloc[-1]

if latest_dif > latest_dea:
    print('MACD 多头排列')
```

---

## 5. 布林带（Bollinger Bands）

**布林带** 由三条线组成，基于收盘价的均值和标准差：

| 线 | 计算 |
|----|------|
| **上轨（Upper Band）** | MA(N) + k × Std(N) |
| **中轨（Middle Band）** | MA(N)（通常 N=20） |
| **下轨（Lower Band）** | MA(N) − k × Std(N) |

**典型参数：** `N=20`，`k=2`（即 ±2 个标准差）

### 读法

- 价格触及**上轨** → 超买，可能回落
- 价格触及**下轨** → 超卖，可能反弹
- **带宽收窄** → 波动率下降，可能酝酿大行情
- 价格持续沿上轨运行 → 强趋势，不宜做空

```python
from eqlib.utils import boll

hist = attribute_history('601390', 60, '1d', ['close'])
upper, middle, lower = boll(hist['close'], period=20, std_dev=2)

price = hist['close'].iloc[-1]

if price < lower.iloc[-1]:
    print('触及布林下轨，均值回归买入信号')
```

---

## 6. ATR：平均真实波幅

**ATR（Average True Range）** 衡量每天价格的**波动幅度**，用于设置止损和仓位大小。

### 真实波幅（TR）的计算

```
TR = max(High - Low, |High - PrevClose|, |Low - PrevClose|)
ATR(N) = Wilder平滑均值(TR, N)
```

**典型参数：** `period=14`

### 用法

```python
from eqlib.utils import atr

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
atr14 = atr(hist['high'], hist['low'], hist['close'], 14)
current_atr = atr14.iloc[-1]

# ATR 止损：当前价 - 2倍 ATR
stop_loss_price = current_price - 2 * current_atr

# ATR 仓位管理：按照每次最多亏损总资金 1% 确定买入股数
risk_per_trade = total_value * 0.01
shares = risk_per_trade / (2 * current_atr)
```

---

## 7. KDJ / 随机指标

**KDJ（也叫随机指标 Stochastic）** 由三条线组成，通过价格在区间内的相对位置衡量超买超卖：

| 线 | 含义 |
|----|------|
| **K** | 快速随机值（对 D 更敏感） |
| **D** | K 的均线（慢速，即 Signal） |
| **J** | 3K − 2D（领先指标，超买超卖更极端） |

- J < 0 → 极度超卖
- J > 100 → 极度超买
- K 上穿 D → 买入信号；K 下穿 D → 卖出信号

```python
from eqlib.utils import kdj

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
k, d, j = kdj(hist['high'], hist['low'], hist['close'])
```

---

## 8. ADX：趋势强度

**ADX（Average Directional Index）** 衡量趋势的**强弱**，不判断方向：

| ADX 数值 | 趋势强度 |
|---------|---------|
| < 20 | 无趋势或弱趋势（震荡市） |
| 20–40 | 中等趋势 |
| > 40 | 强趋势 |

ADX 不告诉你涨还是跌，只告诉你是否在趋势中。常配合均线使用：ADX > 25 时才用趋势策略，ADX < 20 时切换均值回归策略。

```python
from eqlib.utils import adx

hist = attribute_history('601390', 30, '1d', ['high', 'low', 'close'])
adx_val, plus_di, minus_di = adx(hist['high'], hist['low'], hist['close'], period=14)
current_adx = adx_val.iloc[-1]
```

---

## 9. 成交量相关概念

| 概念 | 含义 | 在 eqlib 中 |
|------|------|------------|
| **成交量（Volume）** | 当日成交的股数 | `hist['volume']` |
| **成交额（Amount/Money）** | 当日成交的金额 | `hist['money']` |
| **量比** | 当日成交量 / 过去 N 日平均成交量 | 手动计算 |
| **OBV（On-Balance Volume）** | 累积价涨时加成交量、价跌时减 | `eqlib.utils.obv()` |

**成交量的意义**：
- 放量上涨 → 多头力量强，信号可信度高
- 缩量上涨 → 上涨乏力，需谨慎
- 放量下跌 → 空头力量强
- 缩量下跌 → 下跌或将结束，关注反弹机会

```python
# 量比（当日成交量 / 20 日均量）
hist = attribute_history('601390', 25, '1d', ['close', 'volume'])
avg_vol = hist['volume'].tail(20).mean()
today_vol = hist['volume'].iloc[-1]
volume_ratio = today_vol / avg_vol

if volume_ratio > 1.5:
    print('放量，信号更可信')
```

---

## 10. 支撑与阻力

**支撑位（Support）**：价格跌到某个水平时反复停止下跌并反弹的价格区域。  
**阻力位（Resistance）**：价格涨到某个水平时反复停止上涨并回落的价格区域。

常见支撑/阻力的来源：
- 历史高点和低点
- 整数价位（心理关口，如 5 元、10 元、100 元）
- 均线（MA20、MA60 等）
- 布林带上下轨
- 斐波那契回撤位（38.2%、61.8%）
- 成交量集中区（Volume Profile）

```python
from eqlib.utils import support_resistance_levels, donchian

# 斐波那契回撤
from eqlib.utils import fibonacci_retracement

hist = attribute_history('601390', 60, '1d', ['high', 'low', 'close'])
high = hist['high'].max()
low  = hist['low'].min()
fib_levels = fibonacci_retracement(high, low)
# 返回 [0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%] 对应的价格

# 唐奇安通道（N 日最高/最低价）
upper_ch, lower_ch = donchian(hist['high'], hist['low'], period=20)
```

---

## 11. eqlib.utils 对应的函数

以下是本文提到的技术指标在 `eqlib.utils` 中的对应函数：

| 指标 | 函数 | 返回 |
|------|------|------|
| SMA（简单均线） | `utils.ma(series, period)` | Series |
| EMA（指数均线） | `utils.ema(series, period)` | Series |
| Wilder 均线 | `utils.smma(series, period)` | Series |
| RSI | `utils.rsi(close, period=14)` | Series |
| MACD | `utils.macd(close, fast, slow, signal)` | (dif, dea, hist) |
| 布林带 | `utils.boll(close, period=20, std_dev=2)` | (upper, mid, lower) |
| ATR | `utils.atr(high, low, close, period=14)` | Series |
| KDJ | `utils.kdj(high, low, close, ...)` | (k, d, j) |
| ADX | `utils.adx(high, low, close, period=14)` | (adx, +di, -di) |
| OBV | `utils.obv(close, volume)` | Series |
| 斐波那契回撤 | `utils.fibonacci_retracement(high, low)` | list of prices |
| 唐奇安通道 | `utils.donchian(high, low, period)` | (upper, lower) |

完整函数列表和参数说明见 [工具库参考](../../doc/utils_reference.md)。

---

## 12. 下一步

- **继续前置知识**：[A 股市场基础知识](ashare_knowledge.md)
- **进入正式教程**：[Tutorial 00：环境与第一次运行](../00_environment_and_first_run.md)
- **Tutorial 06** 详细讲解 RSI 均值回归策略的实战应用：[06_rsi_mean_reversion.md](../06_rsi_mean_reversion.md)
