# Tutorial 09: 全天候 Alpha 综合策略

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 将选股、轮动、风控等模块整合为可运行的综合策略，并对接回测与模拟盘 |
    | **预计用时** | 2 小时以上（可按目录分次阅读） |
    | **前置** | Tutorial 04～08 建议至少通读一遍；代码见 [`examples/21_combined_strategy/`](../examples/21_combined_strategy/README.md) |

> 本教程将之前所有教程和示例中的策略技术整合成一个完整的、可投入实盘的综合策略。
> 我们会逐步讲解每个组件的设计原理、数学公式和代码实现，
> 并提供完整的回测和模拟盘代码，可直接运行。

**说明：** [`examples/21_combined_strategy/README.md`](../examples/21_combined_strategy/README.md) 目录内脚本会将子目录加入 `sys.path` 以导入 `combined_strategy`，与 `eqlib` 的安装方式无关。

---

## 目录

1. [策略概述](#1-策略概述)
2. [第一层：多因子选股（Z-Score 标准化）](#2-第一层多因子选股z-score-标准化)
3. [第二层：行业轮动评分加成](#3-第二层行业轮动评分加成)
4. [第三层：技术指标入场 / 离场信号](#4-第三层技术指标入场--离场信号)
5. [第四层：风险管理与仓位控制](#5-第四层风险管理与仓位控制)
6. [生命周期回调集成](#6-生命周期回调集成)
7. [完整策略代码说明](#7-完整策略代码说明)
8. [回测验证](#8-回测验证)
9. [模拟盘部署](#9-模拟盘部署)
10. [策略解读与改进方向](#10-策略解读与改进方向)

---

## 1. 策略概述

### 1.1 设计目标

"全天候 Alpha"（All-Weather Alpha）策略的设计目标是：

- **鲁棒性**：在牛市、熊市、震荡市都能有效运行，不依赖单一市场环境
- **多维度**：同时利用基本面（因子得分）、技术面（RSI / MACD / 布林带）和结构面（支撑阻力位）
- **风险可控**：多层止损（硬止损 + ATR 追踪止损），严格的仓位上限
- **可解释性**：每一个买卖决策都有可追溯的量化依据

### 1.2 策略架构

```
┌──────────────────────────────────────────────────────────┐
│              每周一 — 多因子 + 行业轮动选股              │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 动量因子 │  │ 成交量   │  │ 反转修正 │  │ 波动率 │  │
│  │ (35%)    │  │ (30%)    │  │ (15%)    │  │ (20%)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       └──────────────┴─────────────┴─────────────┘       │
│                        Z-Score 标准化                     │
│                     ↓ 合成综合得分                        │
│              行业动量评分加成（+10%）                     │
│                     ↓ 排名选 Top 5                       │
└──────────────────────────────────────────────────────────┘
                          ↓ g.selected_stocks

┌──────────────────────────────────────────────────────────┐
│              每日 — 技术指标入场 / 离场                  │
│                                                          │
│  入场条件（必须同时满足 C + D + E）：                    │
│    C. 超卖信号：RSI < 35  OR  价格 < 布林下轨            │
│                OR  价格触及唐奇安下轨                    │
│    D. 确认信号：MACD 金叉  OR  接近支撑位                │
│    E. 成交量确认：当日量 ≥ 1.2 × 20日均量               │
│                                                          │
│  离场条件（任一满足即卖出）：                            │
│    1. 硬止损：亏损 > 8%                                  │
│    2. ATR 追踪止损                                       │
│    3. 布林上轨 + RSI 超买                               │
│    4. MACD 死叉                                          │
│    5. 唐奇安上轨突破                                    │
│    6. 接近阻力位 + RSI 超买                             │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    生命周期回调                          │
│  before_trading_start → 检查 ST 股，记录开盘前状态       │
│  after_trading_end    → 记录收盘后组合快照               │
└──────────────────────────────────────────────────────────┘
```

### 1.3 股票池（12 只，覆盖 8 个行业）

| 代码 | 名称 | 行业 | 选择理由 |
|------|------|------|---------|
| 601398 | 工商银行 | 银行 | 大盘蓝筹，波动低，适合均值回归 |
| 600519 | 贵州茅台 | 白酒 | 高 ROE 消费龙头，长期趋势强 |
| 002594 | 比亚迪 | 新能源 | 新能源板块龙头，波动大但趋势明显 |
| 601857 | 中国石油 | 石油天然气 | 能源板块，受大宗商品价格驱动 |
| 601088 | 中国神华 | 煤炭 | 高股息防御，与石油负相关 |
| 601390 | 中国中铁 | 基础设施 | 政策驱动，与经济周期相关 |
| 600276 | 恒瑞医药 | 医药 | 创新药龙头，抗周期性较强 |
| 000333 | 美的集团 | 家电 | 制造业龙头，ROE 稳定 |
| 600916 | 中国黄金 | 黄金 | 避险资产，与股票负相关 |
| 000858 | 五粮液 | 白酒 | 与茅台相关但相对折价 |
| 601318 | 中国平安 | 保险 | 大金融板块，估值低 |
| 600887 | 伊利股份 | 消费品 | 必需消费，抗跌性好 |

> **行业分散原则**：选入不同行业的股票，使得不同市场环境下总有一部分股票处于强势。

---

## 2. 第一层：多因子选股（Z-Score 标准化）

### 2.1 为什么用多因子选股

单一因子（如只看动量）容易在市场风格切换时失效。多因子模型通过综合多个维度，
使策略在不同市场环境中均保持一定的选股能力（参考 [Tutorial 08](08_multi_factor.md)）。

### 2.2 四个因子定义

#### 因子 1：动量因子（权重 35%）

```
momentum = (P_t / P_{t-20}) − 1
```

- **经济含义**：过去 20 个交易日的涨幅。动量越高，近期趋势越强。
- **权重最高** 的原因：A 股市场"追涨杀跌"特征明显，动量效应在中短期有效。

```python
momentum = (close.iloc[-1] / close.iloc[-20]) - 1.0
```

#### 因子 2：成交量放大因子（权重 30%）

```
volume_ratio = mean(vol[-5:]) / mean(vol[-20:])
```

- **经济含义**：近期成交量相对历史均量的倍数。
  量比 > 1 说明近期资金关注度上升，价格上涨更可靠。

```python
vol_ratio = vol.tail(5).mean() / vol.tail(20).mean()
```

#### 因子 3：短期反转修正（权重 15%）

```
reversal = −((P_t / P_{t-5}) − 1)
```

- **经济含义**：对近 5 日涨幅取反值。
  短期涨太多的股票（追高风险大）因子值低；
  短期略有回调的股票因子值高（更安全的买点）。
- 这是**动量因子的补偿**：避免选出近期已经涨了很多、性价比不高的股票。

```python
reversal = -((close.iloc[-1] / close.iloc[-5]) - 1.0)
```

#### 因子 4：低波动率因子（权重 20%）

```
neg_volatility = −std(daily_returns[-20:])
```

- **经济含义**：低波动率股票在相同收益下风险更小（低波动溢价）。
  取负号是因为波动越低，因子值越高。

```python
daily_rets = close.pct_change().dropna().tail(20)
neg_vol    = -daily_rets.std()
```

### 2.3 Z-Score 标准化

不同因子的量纲不同（动量是百分比、量比是倍数），直接加权会导致某个因子主导结果。
Z-Score 标准化消除量纲差异：

```
z_i = (x_i − μ) / σ

其中：
  x_i = 股票 i 的因子原始值
  μ   = 所有股票该因子的均值
  σ   = 所有股票该因子的标准差（样本标准差，ddof=1）
```

```python
def _zscore_normalize(values_dict):
    vals = list(values_dict.values())
    mu   = statistics.mean(vals)
    sig  = statistics.stdev(vals) or 1e-9
    return {k: (v - mu) / sig for k, v in values_dict.items()}
```

### 2.4 综合得分合成

```
score = 0.35 × z_momentum
      + 0.30 × z_volume
      + 0.15 × z_reversal
      + 0.20 × z_neg_volatility
```

按 `score` 从高到低排名，选出 Top 5 股票。

---

## 3. 第二层：行业轮动评分加成

参考 [Tutorial 07](07_sector_rotation.md)，在多因子得分的基础上加入行业轮动维度。

### 3.1 行业动量计算

每个行业取一只代表性股票，计算近 10 日收益率：

```
sector_momentum = (P_{sector,t} / P_{sector,t-10}) − 1
```

同样进行 Z-Score 标准化，得到各行业的相对强弱。

### 3.2 行业加成

```
final_score = factor_score + 0.10 × sector_z_score
```

**加成权重只有 10%** 的原因：
行业信号通常比个股因子"滞后"（行业已经涨了很多才能被观测到），
权重过高容易形成追高。10% 的加成能给行业信号一定影响力，而不至于主导整个排名。

---

## 4. 第三层：技术指标入场 / 离场信号

多因子模型确定了"应该持有哪些股票"，但不告诉我们"什么时候买入最合适"。
技术指标负责这个"精确入场时机"的工作。

### 4.1 RSI 均值回归入场（Tutorial 06）

**公式：**
```
ΔP_t = P_t − P_{t-1}
AvgGain_t = EMA(max(ΔP_t, 0), N=14)
AvgLoss_t = EMA(max(−ΔP_t, 0), N=14)
RS        = AvgGain / AvgLoss
RSI       = 100 − 100 / (1 + RS)
```

**入场条件：** `RSI < 35`（超卖区）

**逻辑：** RSI < 35 说明近期下跌力度明显超过上涨力度，市场可能过度悲观，
存在反弹机会。

```python
rsi_series = utils.rsi(close, period=14)
oversold   = rsi_series.iloc[-1] < 35
```

### 4.2 布林带均值回归（Example 14）

**公式：**
```
Middle = MA(close, N=20)
Upper  = Middle + 2 × std(close, N=20)
Lower  = Middle − 2 × std(close, N=20)
```

**入场条件：** `price ≤ Lower`（价格跌破下轨，统计意义上的超卖）

**离场条件：** `price ≥ Upper AND RSI ≥ 65`（统计意义上的超买）

```python
bb_upper, bb_mid, bb_lower = utils.boll(close, period=20, num_std=2.0)
buy_signal  = price <= bb_lower.iloc[-1]
sell_signal = price >= bb_upper.iloc[-1] and rsi >= 65
```

### 4.3 MACD 趋势确认（Example 15）

**公式：**
```
EMA_fast = EMA(close, N=12)
EMA_slow = EMA(close, N=26)
DIF      = EMA_fast − EMA_slow
DEA      = EMA(DIF, N=9)           # Signal line
柱状图    = 2 × (DIF − DEA)
```

**金叉（看涨信号）：** DIF 由下穿上越过 DEA
```python
macd_golden = dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]
```

**死叉（看跌信号）：** DIF 由上穿下越过 DEA
```python
macd_death = dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]
```

### 4.4 ATR 追踪止损（Examples 15 / 20）

**ATR 公式：**
```
TR_t = max(High_t − Low_t,
           |High_t − Close_{t-1}|,
           |Low_t  − Close_{t-1}|)
ATR  = EMA(TR, N=14)
```

**追踪止损价：**
```
trailing_stop = max(close) 持仓以来最高价 − 2.5 × ATR
```

当 `current_price < trailing_stop` 时止损卖出。

**优势**：追踪止损随着价格上涨而上移，既保护了利润，又允许价格正常波动。
与固定百分比止损相比，ATR 止损能根据市场实际波动率动态调整。

```python
atr_values    = utils.atr(high, low, close, 14)
current_atr   = atr_values.iloc[-1]
trailing_stop = highest_since_buy - 2.5 * current_atr
```

### 4.5 支撑阻力位确认（Example 20）

支撑阻力位通过识别历史价格中的摆动高低点聚类得到：

```python
sr = utils.support_resistance_levels(
    high, low, close,
    lookback=60,       # 回看 60 根 K 线
    tolerance=0.025,   # 2.5% 容差
)
nearest_support    = sr.get("nearest_support")
nearest_resistance = sr.get("nearest_resistance")
```

**近支撑入场条件：**
```
dist_to_support = (price − nearest_support) / price < 2.5%
```

即价格距离支撑位不超过 2.5%，认为"接近支撑位"。

**近阻力离场条件：**
```
dist_to_resistance = (nearest_resistance − price) / price < 2.5%
```

### 4.6 成交量确认（Example 15）

**公式：**
```
vol_ratio = current_volume / mean(volume[-20:])
```

**确认条件：** `vol_ratio ≥ 1.2`

**逻辑：** 价格下跌到支撑位，同时成交量扩大，说明有资金在接盘，
下跌可能即将结束。Example 15 使用 1.5× 阈值；本策略使用 1.2× 阈值
（稍宽松，因为已经有多个其他条件把关）。

### 4.7 唐奇安通道（Example 20）

**公式：**
```
DC_upper = max(high[-20:])    # 20 日最高价
DC_lower = min(low[-20:])     # 20 日最低价
```

- **入场信号**：`price ≤ DC_lower`（价格创 20 日新低，超卖）
- **离场信号**：`price ≥ DC_upper`（价格创 20 日新高，获利了结）

---

## 5. 第四层：风险管理与仓位控制

### 5.1 入场条件的组合逻辑

```
入场 = A AND B AND C AND D AND E

A. 该股在本周 Top-5 选股列表中
B. 当前持仓数 < 5（仓位有空间）
C. 超卖信号（RSI < 35  OR  价格 ≤ 布林下轨  OR  价格 ≤ 唐奇安下轨）
D. 确认信号（MACD 金叉  OR  价格接近支撑位）
E. 成交量确认（当日量 ≥ 1.2 × 20 日均量）
```

**多条件 AND 设计的好处**：
减少假信号。每个单独的技术信号都有约 50% 的假信号率；
三个独立信号同时触发，假信号率理论上降低到 12.5%。

### 5.2 离场条件的优先级

```
离场 = 以下任一条件满足（按优先级从高到低）：

1. 硬止损：loss_pct < −8%          ← 无条件执行，保本为先
2. ATR 追踪止损                    ← 动态风险控制
3. 布林上轨 + RSI ≥ 65            ← 技术性获利了结
4. MACD 死叉                       ← 趋势转换信号
5. 唐奇安上轨                      ← 价格创新高后回落
6. 近阻力位 + RSI ≥ 65            ← 位置性获利了结
```

### 5.3 仓位控制

**等权配置**：
```
per_stock_value = min(
    total_value × 20%,          # 单股上限
    available_cash / num_buys,  # 按候选数量均分
)
```

**最大持仓数**：`1 / 20% = 5` 只股票。

**优势**：等权配置避免了过度集中风险。例如即使某只股票触发止损，
最多也只损失 20% × 8% = 1.6% 的总资金。

---

## 6. 生命周期回调集成

参考 [Example 08](../examples/08_lifecycle_callbacks.py)，策略注册了两个生命周期回调。

### 6.1 开盘前（before_trading_start）

```python
def _before_market_open(context):
    # 记录当前持仓状态
    log.info("PRE-MARKET | total=%.2f | cash=%.2f | positions=%d"
             % (...))

    # 检查 ST 股票（停牌、戴帽等异常情况）
    st_map    = get_extras("is_st", security_list=universe)
    st_stocks = [c for c, flag in st_map.items() if flag]
    if st_stocks:
        log.warning("ST stocks: %s" % st_stocks)
```

### 6.2 收盘后（after_trading_end）

```python
def _after_market_close(context):
    pnl_pct = (portfolio.total_value - portfolio.starting_cash) / portfolio.starting_cash
    record(
        total_value=portfolio.total_value,
        cash=portfolio.available_cash,
        num_holdings=held,
        pnl_pct=pnl_pct,
    )
```

`record()` 将数据保存到回测结果中，供 `generate_chart` 绘图使用。

---

## 7. 完整策略代码说明

### 7.1 文件结构

```
examples/21_combined_strategy/
├── combined_strategy.py    # 完整策略模块（可导入、可修改）
├── run_backtest.py         # 回测运行脚本（直接可运行）
├── run_paper_trade.py      # 模拟盘运行脚本（直接可运行）
└── README.md               # 本教程摘要
```

### 7.2 策略模块结构

```python
# combined_strategy.py 结构

STOCK_POOL     = [...]   # 12 只股票
SECTOR_MAP     = {...}   # 股票→行业映射
SECTOR_REPRES. = {...}   # 行业代表股（用于行业动量计算）

# 参数配置（按需修改，使用模块级常量）
TOP_N          = 5
RSI_OVERSOLD   = 35
ATR_MULTIPLIER = 2.5
...

# 核心函数
_zscore_normalize(values_dict)          # Z-Score 标准化工具
_compute_factors(code)                  # 计算单股四因子
_score_sector_momentum()                # 行业动量评分
rank_stocks_weekly(context)             # 每周选股排名
_compute_indicators(code)              # 计算技术指标
_check_sell(context, code, ind)        # 离场逻辑
_check_buy(context, code, ind)         # 入场逻辑
_before_market_open(context, data=None)    # 生命周期：开盘前
_after_market_close(context, data=None)    # 生命周期：收盘后
weekly_rebalance(context)              # 每周一调仓
daily_trading(context)                 # 每日信号处理

initialize(context)                    # 策略入口（必须有）
```

### 7.3 关键参数速查

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `TOP_N` | 5 | 每周选股数量 |
| `W_MOMENTUM` | 0.35 | 动量因子权重 |
| `W_VOLUME` | 0.30 | 成交量因子权重 |
| `W_REVERSAL` | 0.15 | 反转修正权重 |
| `W_VOLATILITY` | 0.20 | 低波动率权重 |
| `RSI_OVERSOLD` | 35 | RSI 超卖阈值 |
| `RSI_OVERBOUGHT` | 65 | RSI 超买阈值 |
| `BOLL_PERIOD` | 20 | 布林带周期 |
| `ATR_MULTIPLIER` | 2.5 | ATR 追踪止损倍数 |
| `SR_LOOKBACK` | 60 | 支撑阻力回看期（天） |
| `SR_TOLERANCE` | 0.025 | 支撑阻力容差（2.5%） |
| `MAX_SINGLE_PCT` | 0.20 | 单股最大仓位（20%） |
| `HARD_STOP_PCT` | 0.08 | 硬止损阈值（8%） |
| `VOL_CONFIRM_RATIO` | 1.2 | 成交量确认倍数 |

---

## 8. 回测验证

### 8.1 直接运行回测

```bash
# 在项目根目录下运行
python examples/21_combined_strategy/run_backtest.py
```

**回测参数：**
- 时间段：2022-01-01 至 2024-12-31（3 年）
- 初始资金：¥500,000
- 基准：沪深 300（000300.XSHG）
- 股票池：12 只（8 个行业）

**输出报告：**
- `reports/backtest_<时间戳>.png`  — 净值曲线图
- `reports/backtest_<时间戳>.html` — 交互式 HTML 报告
- `reports/backtest_<时间戳>.md`   — Markdown 摘要
- `reports/backtest_<时间戳>.json` — 完整回测数据

### 8.2 回测代码详解

```python
# run_backtest.py 核心片段

import sys, os
sys.path.insert(0, ".")                          # 项目根目录
sys.path.insert(0, "examples/21_combined_strategy")  # 策略所在目录

from combined_strategy import initialize, STOCK_POOL
from eqlib import run_strategy, analyze_returns

result = run_strategy(
    initialize_func=initialize,     # 策略入口函数
    start_date="2022-01-01",
    end_date="2024-12-31",
    starting_cash=500_000,
    benchmark="000300.XSHG",
    securities=STOCK_POOL,          # 预加载数据，加快回测速度
    report_dir="reports",
)

# 绩效分析
metrics = analyze_returns(result, risk_free_rate=0.03)
print("Sharpe ratio : %.4f" % metrics["sharpe_ratio"])
print("Max drawdown : %.2f%%" % (metrics["max_drawdown"] * 100))
print("Win rate     : %.2f%%" % (metrics["win_rate"] * 100))
```

### 8.3 回测结果解读指南

运行完成后，关注以下关键指标：

| 指标 | 含义 | 参考值 |
|------|------|--------|
| **夏普比率** | 每单位波动风险的超额收益 | > 1.0 为良好，> 2.0 为优秀 |
| **最大回撤** | 从历史峰值到最低点的跌幅 | < 20% 为可接受 |
| **Calmar 比率** | 年化收益率 / 最大回撤 | > 1.0 为良好 |
| **Alpha** | 相对基准的超额收益 | > 0 说明策略创造了价值 |
| **Beta** | 与大盘的相关性 | < 1.0 说明策略波动小于大盘 |
| **胜率** | 盈利交易数 / 总交易数 | > 50% 为较好 |

### 8.4 使用本地数据加速（推荐）

首次运行时下载并保存数据，后续运行直接从本地读取：

```bash
# 第一步：预下载数据（只需一次）
python examples/19_local_data_backtest.py --download-all

# 第二步：使用本地数据运行回测（速度更快）
# 在 run_backtest.py 中修改：
# result = run_strategy(..., use_local=True)
```

---

## 9. 模拟盘部署

### 9.1 运行模拟盘

```bash
# 默认设置（资金 ¥500,000，每 60 秒刷新一次报价）
python examples/21_combined_strategy/run_paper_trade.py

# 自定义参数
python examples/21_combined_strategy/run_paper_trade.py \
    --cash 200000 \
    --interval 120

# 按 Ctrl+C 停止
```

### 9.2 模拟盘注意事项

1. **运行时段**：建议在 9:30-15:00 的交易时段内运行，获取实时行情
2. **信号频率**：策略每日只在每根 bar 触发一次，每周一额外触发选股
3. **网络要求**：需要网络访问 akshare 数据源
4. **日志输出**：所有买卖决策都有详细的日志记录，方便监控

### 9.3 部署到 PTrade/QMT

参考 [Tutorial 05](05_live_trading.md) 和 [Example 13](../examples/13_ptrade_export.py)，
可以将本策略导出为 PTrade/QMT 格式：

```python
from eqlib.ptrade_adapter import export_ptrade_script

# 生成 QMT 可运行的策略文件
export_ptrade_script(
    initialize_func=initialize,
    output_path="combined_strategy_qmt.py",
)
```

---

## 10. 策略解读与改进方向

### 10.1 策略适用的市场环境

| 市场环境 | 策略表现预期 | 原因 |
|---------|-----------|------|
| **震荡市** | 较好 | RSI + 布林带均值回归起主导作用 |
| **牛市** | 较好 | 动量因子 + MACD 趋势跟踪有效 |
| **熊市** | 较弱 | 股票普跌，买入信号难以盈利；止损频繁触发 |
| **单边下跌** | 可控 | 硬止损 + ATR 止损限制最大损失 |

### 10.2 可能的改进方向

**1. 加入大盘过滤（推荐优先级最高）**

参考 Tutorial 04，在大盘趋势向下时暂停买入：

```python
def _market_is_bullish():
    """检查大盘是否处于上升趋势（5 日均线 > 20 日均线）。"""
    hist = attribute_history("000300.XSHG", 30, "1d", ["close"])
    if hist.empty:
        return True
    ma5  = hist["close"].tail(5).mean()
    ma20 = hist["close"].mean()
    return ma5 > ma20
```

在 `_check_buy()` 中增加：
```python
if not _market_is_bullish():
    return False, "Market filter: index below MA20"
```

**2. 扩大股票池**

可以将股票池从 12 只扩展到 20-30 只，涵盖更多行业，
同时增加 `top_n = 8`，提升分散度。

**3. 动态调整因子权重**

在牛市中提高动量因子权重（到 50%），在震荡市中提高低波动因子权重（到 35%）：

```python
def _get_factor_weights():
    """根据市场状态动态调整因子权重。"""
    if _market_is_bullish():
        return {"momentum": 0.50, "volume": 0.25, "reversal": 0.10, "volatility": 0.15}
    else:
        return {"momentum": 0.25, "volume": 0.25, "reversal": 0.20, "volatility": 0.30}
```

**4. 月度再平衡财务因子**

每月加入 PE/PB 财务因子（参考 Tutorial 08 第 5 节），但仅作为辅助参考：

```python
def _compute_pe_factor(code):
    val = get_valuation(code)
    if val and val.get("pe") and 0 < val["pe"] < 80:
        return 1.0 / val["pe"]
    return None
```

**5. Kelly 仓位调整**

根据历史胜率动态调整仓位大小（参考 Example 11）：

```python
from eqlib.utils import kelly_criterion
win_rate = historical_win_rate   # 从回测结果中提取
avg_win  = historical_avg_win
avg_loss = historical_avg_loss
kelly_f  = kelly_criterion(win_rate, avg_win, avg_loss)
# 使用 Half-Kelly 降低风险
position_pct = min(kelly_f * 0.5, g.max_single_pct)
```

### 10.3 过拟合风险警告

> ⚠️ **重要提示**
>
> 本策略的参数（如 RSI 阈值 35/65、ATR 倍数 2.5×、因子权重等）是根据量化研究文献
> 和 A 股市场特征设定的合理默认值，而**不是通过大量回测优化得到的最优参数**。
>
> 避免过拟合的最佳实践：
> 1. **样本外测试**：只用 2020-2022 年数据调参，用 2023-2024 年数据验证
> 2. **参数稳定性**：轻微改变参数（如 RSI 阈值从 35 改为 33 或 37），
>    如果收益大幅变化，说明参数不够鲁棒
> 3. **前瞻偏差检查**：确保没有使用未来数据（`attribute_history` 始终只看历史）

---

## 延伸阅读

| 教程 | 相关内容 |
|------|---------|
| [Tutorial 06: RSI 均值回归](06_rsi_mean_reversion.md) | RSI 原理、布林带对比 |
| [Tutorial 07: 行业轮动](07_sector_rotation.md) | 动量轮动、多维度行业评分 |
| [Tutorial 08: 多因子选股](08_multi_factor.md) | Z-Score 标准化、IC 检验 |
| [Tutorial 04: 策略优化](04_strategy_optimization.md) | 大盘过滤、止损设计 |

| 示例 | 相关代码 |
|------|---------|
| [Example 14: 布林带策略](../examples/14_bollinger_strategy.py) | Bollinger 均值回归 |
| [Example 15: MACD 策略](../examples/15_macd_volume_strategy.py) | MACD+成交量+ATR |
| [Example 16: 多因子策略](../examples/16_multi_factor_strategy.py) | 动量+成交量选股 |
| [Example 20: 支撑阻力策略](../examples/20_sr_strategy/README.md) | S/R+MACD+ATR 完整案例 |
| [Example 11: 工具库](../examples/11_utils_library.py) | 所有技术指标演示 |

---

## 附录：一键运行命令

```bash
# 克隆项目后，在项目根目录执行：

# 安装依赖（PyPI）
pip install easyquant-eqlib
# 或从源码安装
# pip install .

# 运行回测（约 60 秒）
python examples/21_combined_strategy/run_backtest.py

# 查看报告（浏览器打开生成的 HTML 文件）
# 报告路径：reports/backtest_<时间戳>.html

# 模拟盘（需要网络，交易时段内运行效果最佳）
python examples/21_combined_strategy/run_paper_trade.py
```
