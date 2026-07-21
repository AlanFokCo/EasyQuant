# A 股行业龙头支撑压力策略原理

本文解释 `eqlib.strategies.ashare_sr_leader` 的最终实现逻辑：它如何从行业龙头池中选股，如何用支撑压力结构判断入场，如何通过大盘状态控制总仓位，以及研究脚本如何从候选策略中选择最终版本。

这不是投资建议，也不是对未来收益的承诺。本文只说明当前代码中的策略设计和回测研究口径。

## 策略定位

该策略不是单纯的突破策略，也不是单纯的低吸策略。它的核心思想是：

> 在流动性较好的 A 股行业龙头池中，寻找没有破位、靠近支撑或形成突破确认、相对基准仍有强度的股票；再根据大盘结构决定总仓位，用月度换仓和周度破位复查降低交易频率和回撤风险。

代码入口主要分为两部分：

| 文件 | 职责 |
|------|------|
| `eqlib/strategies/ashare_sr_leader.py` | 策略信号、打分、仓位、调仓、风控的可测试实现 |
| `scripts/run_ashare_sr_leader_research.py` | 参数网格、回测运行、稳定性评分、报告生成 |

回测报告 `reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html` 对应的最优变体是 `pullback_market_gate`，即“突破回踩 + 市场闸门”版本。

## 策略框架

策略运行可以拆成五层：

```text
行业龙头股票池
    ↓
个股支撑压力与相对强弱信号
    ↓
候选股票打分与排序
    ↓
大盘状态决定总仓位
    ↓
组合权重、流动性限制、月度调仓、周度风控
```

这种结构故意把“选什么”和“买多少”分开：

- 选什么：由个股支撑压力、突破、回踩、相对强弱、波动率和成交量决定。
- 买多少：由大盘结构、单股上限、行业上限和流动性限制决定。

## 股票池

策略使用一组预先定义的 A 股行业龙头，包括白酒、银行、保险、券商、医药、新能源、通信、计算机、工程机械、化工、有色、建筑、家电、电力等行业。

股票池有两个层次：

- `DEFAULT_LEADER_UNIVERSE`：策略模块内置的完整行业龙头清单。
- `RESEARCH_UNIVERSE`：研究脚本中用于参数搜索的较小候选池。

策略会排除科创板和常见北交所风格代码：

```python
bare.startswith(("688", "8", "4", "9"))
```

这样做的目的不是判断这些股票不好，而是让研究范围更接近主板、创业板中流动性更稳定、交易规则更一致的行业代表股。

## 核心参数

策略参数由 `StrategyParams` 统一管理。默认参数体现了中低频、组合化、风险约束优先的风格：

| 参数 | 默认值 | 含义 |
|------|------:|------|
| `level_window` | 120 | 长周期支撑压力窗口 |
| `short_level_window` | 60 | 短周期支撑压力窗口 |
| `atr_period` | 20 | ATR 波动缓冲窗口 |
| `atr_multiplier` | 0.5 | 支撑/压力突破或破位所需的 ATR 倍数 |
| `volume_window` | 20 | 成交量均值窗口 |
| `volume_ratio_min` | 1.0 | 突破信号所需最低量比 |
| `rs_window` | 60 | 相对基准强弱计算窗口 |
| `top_n` | 10 | 最多持仓数量 |
| `max_stock_weight` | 0.12 | 单股最高权重 |
| `max_industry_weight` | 0.30 | 单行业最高权重 |
| `strong_market_exposure` | 0.90 | 强势市场目标权益仓位 |
| `neutral_market_exposure` | 0.65 | 中性市场目标权益仓位 |
| `weak_market_exposure` | 0.35 | 弱势市场目标权益仓位 |
| `min_relative_strength` | -0.03 | 个股相对强弱下限 |
| `max_support_distance` | 0.12 | 允许距离支撑位的最大比例 |
| `max_position_drawdown` | 0.0 | 持仓相对近期高点的移动回撤退出阈值，默认关闭 |
| `rebalance_threshold` | 0.08 | 再平衡触发阈值 |
| `liquidity_volume_pct` | 0.03 | 单次增仓占均量成交额的上限 |

2020-2025 报告中的最优 `pullback_market_gate` 参数更保守：

| 参数 | 取值 |
|------|------:|
| `level_window` | 120 |
| `short_level_window` | 60 |
| `atr_multiplier` | 0.6 |
| `top_n` | 10 |
| `max_stock_weight` | 0.08 |
| `max_industry_weight` | 0.24 |
| `strong_market_exposure` | 0.82 |
| `neutral_market_exposure` | 0.50 |
| `weak_market_exposure` | 0.15 |
| `min_relative_strength` | 0.0 |
| `max_support_distance` | 0.08 |
| `rebalance_threshold` | 0.10 |
| `liquidity_volume_pct` | 0.03 |

这组参数说明最终版本不是激进追涨，而是更强调相对强度、靠近支撑、弱市降仓和低换手。

为了尝试把报告评级从 B 提升到 A，研究网格中还加入了一个更保守的 `drawdown-controlled` 候选。它不会改变默认策略，也不会替换 2020-2025 已有最优参数；它只是让下一轮研究多比较一种更偏控回撤的版本：

| 参数 | 取值 |
|------|------:|
| `atr_multiplier` | 0.65 |
| `volume_ratio_min` | 1.05 |
| `max_stock_weight` | 0.07 |
| `max_industry_weight` | 0.21 |
| `strong_market_exposure` | 0.76 |
| `neutral_market_exposure` | 0.44 |
| `weak_market_exposure` | 0.10 |
| `min_relative_strength` | 0.01 |
| `max_support_distance` | 0.06 |
| `max_position_drawdown` | 0.12 |

这个候选的目的很明确：牺牲一部分进攻性，尝试把最大回撤压低到评级函数更偏好的区间，并通过更平滑的净值路径改善 Sharpe。

## 支撑压力计算

策略用已经完成的历史窗口计算支撑和压力，避免在当前 bar 内使用未来信息。

`rolling_levels(frame, window)` 返回：

- 压力位：过去 `window` 根已完成 K 线的最高价。
- 支撑位：过去 `window` 根已完成 K 线的最低价。

实现上会排除当前最新 K 线：

```python
completed = frame.iloc[-window - 1:-1]
resistance = completed["high"].max()
support = completed["low"].min()
```

个股信号同时计算长短两个窗口：

- 长窗口：默认 120 日，代表更慢的结构边界。
- 短窗口：默认 60 日，代表更近的交易结构。

最终使用：

- 压力位取长短压力中的较低值：更容易触发“近期压力突破”。
- 支撑位取长短支撑中的较高值：更重视离当前价格更近的防守位。

这种处理让策略更关注“当前正在交易的结构”，而不是只看很远的历史高低点。

## ATR 波动缓冲

策略不会把“刚好站上压力”或“刚好跌破支撑”直接当作有效信号，而是加入 ATR 缓冲。

ATR 使用真实波幅计算：

```text
TR = max(
    high - low,
    abs(high - prev_close),
    abs(low - prev_close)
)
ATR = rolling_mean(TR, atr_period)
```

突破条件需要：

```text
close > resistance + atr_multiplier × ATR
```

破位条件需要：

```text
close < support - atr_multiplier × ATR
```

这相当于过滤支撑压力附近的小噪音。`atr_multiplier` 越大，信号越保守；2020-2025 最优参数使用 `0.6`，比默认 `0.5` 更谨慎。

## 相对强弱

策略不是只看个股自身涨跌，还会看个股是否跑赢基准。

相对强弱定义为：

```text
relative_strength =
    stock_close_today / stock_close_N_days_ago - 1
    -
    benchmark_close_today / benchmark_close_N_days_ago - 1
```

默认窗口是 60 日。

这个指标的作用是避免买入只是“跌得少一点”或“反弹但仍弱于市场”的股票。2020-2025 最优参数要求 `min_relative_strength = 0.0`，也就是候选股至少不能跑输基准。

## 个股信号快照

每只股票会被转换成一个 `SignalSnapshot`，里面包含：

| 字段 | 含义 |
|------|------|
| `close` | 当前收盘价 |
| `resistance` | 计算出的压力位 |
| `support` | 计算出的支撑位 |
| `atr` | 当前 ATR |
| `avg_volume` | 成交量均值 |
| `volume_ratio` | 当前成交量 / 均量 |
| `relative_strength` | 相对基准强弱 |
| `volatility` | 近 20 日收益率波动 |
| `support_distance` | 当前价距离支撑位比例 |
| `resistance_distance` | 当前价距离压力位比例 |
| `breakout` | 是否有效突破 |
| `pullback` | 是否有效回踩 |
| `breakdown` | 是否破位 |

在生成快照前会先过滤：

- 历史数据不足。
- 价格低于 `min_price`。
- 平均成交量低于 `min_avg_volume`。
- 相对强弱低于阈值。
- 非突破、非回踩，而且距离支撑过远。

这一步把明显不适合交易的标的尽早剔除，后续打分只处理结构较清晰的候选。

## 突破、回踩与破位

策略识别三类结构状态。

**突破 `breakout`**

需要同时满足：

```text
close > resistance + atr_multiplier × ATR
volume_ratio >= volume_ratio_min
relative_strength > 0
```

含义是价格有效越过压力位，同时成交量不弱，并且相对基准有超额强度。

**回踩 `pullback`**

需要同时满足：

```text
not breakdown
close >= support
support_distance <= max(max_support_distance, 3 × atr_multiplier × ATR / close)
relative_strength >= -0.03
```

含义是价格仍守在支撑上方，距离支撑不远，相对强弱没有明显恶化。这里允许用 ATR 扩展支撑距离，是为了适应不同价格和波动水平的股票。

**破位 `breakdown`**

定义为：

```text
close < support - atr_multiplier × ATR
```

破位股票会被排除；如果已经持有，周度风控复查中会清仓。

## 四个策略变体

研究脚本会测试四种 `StrategyKind`：

| 变体 | 风格 |
|------|------|
| `defensive_support` | 防守型支撑策略，偏好靠近支撑、低波动、相对强度为正的股票 |
| `resistance_breakout` | 压力突破策略，偏好有效突破、相对强度和量能 |
| `pullback_market_gate` | 突破回踩 + 市场闸门，偏好回踩确认，同时保留突破加分 |
| `adaptive_composite` | 综合型策略，把回踩、突破、支撑距离、相对强弱、低波动和量能综合打分 |

2020-2025 的最优报告选择了 `pullback_market_gate`。这说明在该回测区间中，“等价格回到可防守区域、同时不明显跑输市场”的逻辑，比单纯追突破更稳定。

## 打分逻辑

所有候选股会先构造信号快照，再按策略变体打分。若 `breakdown=True`，直接返回 `-100`。

公共组件包括：

```text
low_vol_bonus = max(0, 0.05 - volatility) × 10
rs_score = relative_strength × 100
volume_score = min(volume_ratio, 2.0)
support_score = max(0, 0.20 - support_distance) × 20
breakout_score = 8 if breakout else 0
pullback_score = 10 if pullback else 0
```

`pullback_market_gate` 的最终分数为：

```text
pullback_score
+ 0.7 × breakout_score
+ 0.7 × rs_score
+ 0.3 × support_score
+ low_vol_bonus
```

可以看出它最重视回踩，其次是突破确认和相对强弱，支撑距离提供额外加分，低波动也会被奖励。

只有分数大于 0 的股票会进入候选列表，然后按分数从高到低排序。

## 大盘状态与总仓位

策略每月先判断基准指数状态，再决定组合总权益仓位。

市场状态分三类：

| 状态 | 条件概要 | 仓位含义 |
|------|----------|----------|
| `STRONG` | 指数有效突破压力，或在均线上方且守住支撑 | 使用强市仓位 |
| `NEUTRAL` | 未明显破位，也未形成强势确认 | 使用中性仓位 |
| `WEAK` | 指数跌破支撑并超过 ATR 缓冲 | 使用弱市仓位 |

这就是“市场闸门”。它不是决定买哪只股票，而是决定当前组合整体应该承担多少风险。

2020-2025 最优参数的仓位映射是：

```text
STRONG  → 82%
NEUTRAL → 50%
WEAK    → 15%
```

这意味着即使个股信号很好，只要大盘结构较弱，策略也会显著降仓。

## 组合构建

候选股票排序后，策略会构建目标权重：

1. 最多选择 `top_n` 只股票。
2. 计算基础权重：`exposure / count`。
3. 单股权重不能超过 `max_stock_weight`。
4. 同一行业累计权重不能超过 `max_industry_weight`。
5. 已持有股票若仍在有效候选中，会优先保留，再用新候选补齐。

2020-2025 最优参数中：

- 最多 10 只。
- 单股最高 8%。
- 单行业最高 24%。

这使组合不会过度集中在单个龙头或单一行业上。

## 再平衡与流动性限制

策略不是每次目标权重有微小变化就交易。`should_rebalance_position()` 会比较当前市值和目标市值的差异：

```text
drift = abs(target_value - current_value) / total_value
```

只有 `drift >= rebalance_threshold` 时才触发交易。2020-2025 最优参数为 `10%`，因此换手会比较低。

新增或增持仓位还会受到流动性限制：

```text
liquidity_cap = close × avg_volume × liquidity_volume_pct
```

目标市值不能超过当前持仓市值加上这部分流动性额度。卖出和降仓不受这个限制，因为它们是风险降低操作。

## 调度与风控

策略由 `make_initialize()` 生成 EasyQuant 的 `initialize(context)` 回调。

初始化时会做四件事：

1. 设置基准。
2. 设置 A 股交易成本。
3. 保存策略参数、股票池和基准到 `g`。
4. 注册月度扫描和周度风控。

调度如下：

| 频率 | 回调 | 作用 |
|------|------|------|
| 每月第 1 个交易日 09:30 | `monthly_scan` | 判断大盘状态、选股、计算仓位、再平衡 |
| 每周五 09:30 | `weekly_review` | 检查持仓是否跌破支撑，破位则清仓 |

月度换仓降低了交易频率；周度复查用于及时处理结构破坏的持仓。

如果参数启用了 `max_position_drawdown`，周度复查还会做一层移动回撤保护：用最近 `short_level_window` 个交易日的已完成收盘价高点作为参考，若当前收盘价相对该高点的回撤超过阈值，则退出该持仓。默认值为 `0.0`，表示关闭；`drawdown-controlled` 候选使用 `0.12`。

## 交易成本

策略使用接近当前 A 股常见费率的成本设置：

```python
OrderCost(
    open_tax=0,
    close_tax=0.0005,
    open_commission=0.00025,
    close_commission=0.00025,
    close_today_commission=0,
    min_commission=5,
)
```

含义是：

- 买入无印花税。
- 卖出印花税 0.05%。
- 买卖佣金 0.025%。
- 最低佣金 5 元。

这与示例默认交易成本保持一致。

## 研究脚本如何选择最优策略

`scripts/run_ashare_sr_leader_research.py` 会做参数搜索：

1. 构建多个策略变体和参数组合。
2. 对全周期运行回测。
3. 用 `analyze_returns()` 提取收益、波动、Sharpe、最大回撤、交易次数等指标。
4. 计算稳定性评分。
5. 选择稳定性评分最高的全周期候选。
6. 对最优候选再跑分阶段回测。
7. 输出 `summary.json`、`summary.csv`、`final_report.md`、`final_report.html` 和 EasyQuant HTML 回测报告。

稳定性评分不是单纯追求最高收益，而是综合：

```text
1.5 × annual_return
+ 0.25 × sharpe
+ excess_return
- drawdown_penalty
- undertrade_penalty
- churn_penalty
```

其中：

- 最大回撤超过 20% 会受到惩罚。
- 交易次数太少会受到轻微惩罚，避免“几乎不交易”的偶然结果。
- 交易次数超过 120 会受到换手惩罚。

这解释了为什么“最高收益”的参数不一定被选为最终策略。

## 2020-2025 报告对应版本

`eqlib_best_backtest_2020_2025.html` 对应的摘要文件显示：

| 指标 | 值 |
|------|------:|
| 策略变体 | `pullback_market_gate` |
| 回测区间 | 2020-01-01 至 2025-12-31 |
| 总收益 | 123.17% |
| 基准收益 | 11.50% |
| 超额收益 | 111.67% |
| 年化收益 | 14.42% |
| 年化波动 | 16.49% |
| Sharpe | 0.72 |
| Sortino | 1.04 |
| 最大回撤 | -24.37% |
| 交易次数 | 12 |
| 原始成交笔数 | 32 |

从这些指标看，它是一个低频、较低换手、强调结构防守的组合策略。收益来自少数较长持仓周期，而不是频繁交易。

## 策略适合的市场环境

该策略更适合：

- 龙头股出现结构性机会，但市场不是全面单边下跌。
- 指数处于强势或中性状态，个股能维持相对强度。
- 股价回踩支撑后不破位，形成可定义风险的位置。
- 行业之间有轮动，组合能从候选池中切换到更强的龙头。

它可能承压的环境包括：

- 快速单边下跌，支撑位连续失效。
- 高波动震荡市，支撑压力频繁假突破。
- 小盘股、题材股强于龙头股的行情。
- 基准指数状态偏弱，但个别股票短期暴涨的行情，因为市场闸门会限制总仓位。

## 与普通支撑压力策略的区别

普通支撑压力策略常见逻辑是“接近支撑买、突破压力买、跌破支撑卖”。本策略多了几层约束：

| 维度 | 普通支撑压力策略 | 本策略 |
|------|------------------|--------|
| 股票池 | 可任意选股 | 预定义行业龙头池 |
| 支撑压力 | 单窗口或手工画线 | 120 日 + 60 日已完成窗口 |
| 有效信号 | 价格触线或突破 | 加 ATR 缓冲、量比、相对强弱 |
| 总仓位 | 常固定 | 由大盘结构控制 |
| 组合约束 | 可能较少 | 单股、行业、流动性、再平衡阈值 |
| 风控 | 个股止损 | 周度结构破位复查 |
| 参数选择 | 主观设定 | 通过候选网格和稳定性评分选择 |

## 主要风险与局限

1. **行业龙头池有幸存者偏差**  
   预定义股票池可能包含事后看起来更成功的公司。如果用于正式研究，应考虑按历史时点构建可交易股票池。

2. **支撑压力不是因果规律**  
   支撑压力只是价格结构描述，不保证未来一定反弹或突破成功。

3. **月度调仓可能错过快速变化**  
   月频扫描降低换手，但也可能对突发行情反应较慢。

4. **大盘闸门会牺牲部分进攻性**  
   弱市降仓能控制风险，但也可能错过逆势强股。

5. **参数来自历史回测**  
   `pullback_market_gate` 在 2020-2025 表现较好，不代表未来仍是最优。需要样本外测试、滚动验证和参数敏感性分析。

6. **数据源和复权处理会影响结果**  
   A 股日线、停牌、复权、成交量和指数数据的处理差异，会改变信号和成交结果。

## 读代码的推荐顺序

如果想从代码理解策略，可以按这个顺序阅读：

1. `StrategyParams`：先看参数和默认风格。
2. `rolling_levels()` 和 `compute_atr()`：理解支撑压力和波动缓冲。
3. `build_signal_snapshot()`：理解个股如何通过过滤并形成信号。
4. `score_snapshot()`：理解四个策略变体的打分差异。
5. `classify_market()` 和 `market_exposure()`：理解大盘闸门。
6. `target_weights()` 和 `rebalance_portfolio()`：理解组合权重和调仓。
7. `_risk_review()`：理解周度破位退出。
8. `make_initialize()`：理解 EasyQuant 生命周期注册。
9. `candidate_param_grid()` 和 `stability_score()`：理解研究脚本如何选择最终版本。

## 总结

`ashare_sr_leader` 的最终实现是一套偏稳健的 A 股行业龙头组合策略：

- 用支撑压力定义可交易结构。
- 用 ATR、量比、相对强弱过滤噪音。
- 用大盘状态控制总仓位。
- 用单股、行业和流动性约束控制集中度。
- 用月度换仓和周度破位复查降低换手与结构性风险。
- 用稳定性评分而非单纯收益挑选参数。

2020-2025 报告中的 `pullback_market_gate` 版本，最终呈现的是“回踩确认优先、突破加分、弱市降仓、低频持有”的策略风格。
