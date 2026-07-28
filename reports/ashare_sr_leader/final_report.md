# A股行业龙头支撑压力策略研究报告

- 最终推荐策略: `adaptive_composite`
- 选择原因: baseline_retained_no_robust_candidate
- 没有稳健候选通过全部稳健门槛，因此精确保留 adaptive_composite 基线参数集。
- 历史参数集标签 A/71.3；本次重跑评级 A/70.3。
- 评级: `A / 70.3`
- 稳定性评分: `1.5375`
- 年化收益: `14.66%`
- 基准收益: `11.50%`
- 超额收益: `114.41%`
- 最大回撤: `-20.27%`
- Sharpe: `0.73`
- 交易次数: `35`

## 全周期候选排名

| Rank | Strategy | Profile | Period | Grade | Annual | Benchmark | Excess | Max DD | Sharpe | Trades | Raw Trades |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | A / 70.3 | 14.66% | 11.50% | 114.41% | -20.27% | 0.73 | 35 | 78 |
| 2 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | A / 72.9 | 14.40% | 11.50% | 111.45% | -18.07% | 0.81 | 31 | 71 |
| 3 | pullback_market_gate | active-balanced | 2020-01-01 to 2025-12-31 | A / 71.2 | 11.37% | 11.50% | 78.52% | -17.59% | 0.69 | 13 | 33 |
| 4 | defensive_support | balanced | 2020-01-01 to 2025-12-31 | B / 69.0 | 13.99% | 11.50% | 106.65% | -25.43% | 0.71 | 21 | 48 |
| 5 | defensive_support | risk-managed | 2020-01-01 to 2025-12-31 | B / 65.6 | 10.79% | 11.50% | 72.62% | -23.57% | 0.64 | 10 | 29 |
| 6 | pullback_market_gate | risk-managed | 2020-01-01 to 2025-12-31 | B / 65.3 | 10.78% | 11.50% | 72.55% | -23.37% | 0.63 | 11 | 31 |
| 7 | defensive_support | guarded | 2020-01-01 to 2025-12-31 | B / 65.1 | 11.03% | 11.50% | 75.03% | -21.42% | 0.60 | 27 | 64 |
| 8 | adaptive_composite | guarded | 2020-01-01 to 2025-12-31 | B / 65.1 | 10.64% | 11.50% | 71.16% | -21.72% | 0.58 | 23 | 56 |
| 9 | defensive_support | balanced | 2020-01-01 to 2025-12-31 | B / 64.6 | 13.35% | 11.50% | 99.49% | -30.10% | 0.61 | 28 | 65 |
| 10 | resistance_breakout | guarded | 2020-01-01 to 2025-12-31 | B / 64.5 | 8.22% | 11.50% | 48.57% | -18.78% | 0.46 | 23 | 57 |

## 稳健门槛

已评估稳健种子: 10
通过全部稳健门槛: 0
失败原因汇总: annual_return_below_12pct: 10；grade_below_a: 10

没有稳健候选通过全部稳健门槛，因此精确保留 adaptive_composite 基线参数集。

| Candidate | Result | Failure codes | Neighbor pass | Worst validation excess |
|---|---|---|---:|---:|
| robust-1 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-2 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-3 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-4 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-5 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-6 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-7 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-8 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-9 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |
| robust-10 (adaptive_composite/balanced) | 未通过 | annual_return_below_12pct, grade_below_a | 不可用 | 不可用 |

## 滚动验证

| Candidate | Year | Annual | Excess | Max DD | Grade |
|---|---:|---:|---:|---:|---|
| N/A | 2023/2024/2025 | 不可用 | 不可用 | 不可用 | 不可用 |

## 风险状态

| Candidate | Days by state | Triggers | Recoveries |
|---|---|---:|---:|
| baseline | 不可用 | 不可用 | 不可用 |

## 主/候补通道

| Candidate | Channel | Entry fills | Average exposure | Average holdings | Return contribution |
|---|---|---:|---:|---:|---:|
| baseline | 主通道 | 不可用 | 不可用 | 不可用 | 不可用 |
| baseline | 候补通道 | 不可用 | 不可用 | 不可用 | 不可用 |

## 基线与稳健候选对比

| Candidate | Annual | Max DD | Sharpe | Grade | Full gate | 2023 gate | 2024 gate | 2025 gate | Neighborhood gate | Overall |
|---|---:|---:|---:|---|---|---|---|---|---|---|
| baseline | 14.66% | -20.27% | 0.73 | A / 70.3 | 未通过: max_drawdown_not_below_20pct | 未通过: 2023_validation_unavailable | 未通过: 2024_validation_unavailable | 未通过: 2025_validation_unavailable | 未通过: neighbor_pass_rate_below_60pct | 未通过: max_drawdown_not_below_20pct, 2023_validation_unavailable, 2024_validation_unavailable, 2025_validation_unavailable, neighbor_pass_rate_below_60pct |

## 长期回测压力诊断

以下分阶段结果只用于解释 2020-01-01 至 2025-12-31 策略在哪些市场环境中失效或承压，不作为收益参考，也不参与最终策略排名。

### 2020-2021

- 该长期策略: `adaptive_composite`
- 年化收益: `30.01%`
- 最大回撤: `-18.32%`
- 超额收益: `49.49%`
- 交易次数: `10`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑赢基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2022

- 该长期策略: `adaptive_composite`
- 年化收益: `-13.74%`
- 最大回撤: `-18.83%`
- 超额收益: `7.69%`
- 交易次数: `12`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑赢基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2023-2024

- 该长期策略: `adaptive_composite`
- 年化收益: `16.52%`
- 最大回撤: `-15.59%`
- 超额收益: `34.14%`
- 交易次数: `8`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑赢基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2025

- 该长期策略: `adaptive_composite`
- 年化收益: `6.68%`
- 最大回撤: `-9.74%`
- 超额收益: `-14.57%`
- 交易次数: `0`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑输基准，回撤可控，交易次数没有表现出高频或中高频特征。

## 最终推荐

最终推荐策略: `adaptive_composite`

推荐原因:

- 选择原因: baseline_retained_no_robust_candidate
- 没有稳健候选通过全部稳健门槛，因此精确保留 adaptive_composite 基线参数集。
- 历史参数集标签 A/71.3；本次重跑评级 A/70.3。
- 本次重跑稳定性评分为 `1.5375`。
- 本次重跑年化收益为 `14.66%`，超额收益为 `114.41%`。
- 本次重跑最大回撤为 `-20.27%`。
- 本次重跑交易次数为 `35`，交易次数没有表现出高频或中高频特征。

## 风险提示

- 历史回测不代表未来收益。
- 行业龙头池仍可能存在幸存者偏差。
- akshare 数据源可用性和复权处理会影响结果。
- 支撑压力不是确定性价格预测，只是结构化风险收益判断。

## 回测审计

- 审计结论: 审计未完全通过，不建议直接实盘；应继续降低回撤、修正失效阶段或扩大稳健参数验证。
- `warning` `subperiod_underperformance`: 2025 阶段明显跑输基准，需要检查该市场环境下的入场/仓位过滤。
- `warning` `trade_churn`: 存在交易次数超过 120 的回测结果，需要检查是否偏离中低频目标。
- `warning` `execution_fragmentation`: 存在原始成交笔数过高的结果，可能由复权低价、成交量限制或拆单造成，需要降低单次交易容量。
