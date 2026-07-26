# A股行业龙头支撑压力策略研究报告

- 最终推荐策略: `adaptive_composite`
- 选择原因: baseline_retained_no_robust_candidate
- 没有稳健候选通过全部稳健门槛，因此精确保留 adaptive_composite 基线参数集。
- 历史参数集标签 A/71.3；本次重跑评级 D/29.8。
- 评级: `D / 29.8`
- 稳定性评分: `-0.4727`
- 年化收益: `1.93%`
- 基准收益: `11.50%`
- 超额收益: `0.57%`
- 最大回撤: `-17.33%`
- Sharpe: `-0.08`
- 交易次数: `7`

## 全周期候选排名

| Rank | Strategy | Profile | Period | Grade | Annual | Benchmark | Excess | Max DD | Sharpe | Trades | Raw Trades |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | D / 29.8 | 1.93% | 11.50% | 0.57% | -17.33% | -0.08 | 7 | 22 |
| 2 | defensive_support | balanced | 2020-01-01 to 2025-12-31 | D / 36.2 | 4.08% | 11.50% | 15.42% | -14.56% | 0.16 | 4 | 15 |
| 3 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | D / 36.2 | 4.08% | 11.50% | 15.42% | -14.56% | 0.16 | 4 | 15 |
| 4 | resistance_breakout | balanced | 2020-01-01 to 2025-12-31 | D / 34.6 | 3.47% | 11.50% | 11.01% | -16.27% | 0.09 | 7 | 25 |
| 5 | resistance_breakout | balanced | 2020-01-01 to 2025-12-31 | D / 34.4 | 3.73% | 11.50% | 12.91% | -14.19% | 0.12 | 4 | 15 |
| 6 | pullback_market_gate | balanced | 2020-01-01 to 2025-12-31 | D / 34.4 | 3.73% | 11.50% | 12.91% | -14.19% | 0.12 | 4 | 15 |
| 7 | defensive_support | balanced | 2020-01-01 to 2025-12-31 | D / 34.2 | 3.47% | 11.50% | 11.03% | -16.50% | 0.09 | 9 | 29 |
| 8 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | D / 34.0 | 3.52% | 11.50% | 11.37% | -16.50% | 0.10 | 8 | 27 |
| 9 | pullback_market_gate | balanced | 2020-01-01 to 2025-12-31 | D / 33.7 | 3.39% | 11.50% | 10.47% | -16.50% | 0.08 | 8 | 27 |
| 10 | adaptive_composite | balanced | 2020-01-01 to 2025-12-31 | D / 32.5 | 2.44% | 11.50% | 3.97% | -15.65% | -0.01 | 5 | 21 |

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
| baseline | normal: 1455 | 0 | 0 |

## 主/候补通道

| Candidate | Channel | Trades | Average exposure | Average holdings | Return contribution |
|---|---|---:|---:|---:|---:|
| baseline | 主通道 | 0 | 0.00% | 0.00 | 0.00% |
| baseline | 候补通道 | 0 | 0.00% | 0.00 | 0.00% |

## 基线与稳健候选对比

| Candidate | Annual | Max DD | Sharpe | Grade | Full gate | 2023 gate | 2024 gate | 2025 gate | Neighborhood gate | Overall |
|---|---:|---:|---:|---|---|---|---|---|---|---|
| baseline | 1.93% | -17.33% | -0.08 | D / 29.8 | 未通过: annual_return_below_12pct, grade_below_a | 未通过: 2023_validation_unavailable | 未通过: 2024_validation_unavailable | 未通过: 2025_validation_unavailable | 未通过: neighbor_pass_rate_below_60pct | 未通过: annual_return_below_12pct, grade_below_a, 2023_validation_unavailable, 2024_validation_unavailable, 2025_validation_unavailable, neighbor_pass_rate_below_60pct |

## 长期回测压力诊断

以下分阶段结果只用于解释 2020-01-01 至 2025-12-31 策略在哪些市场环境中失效或承压，不作为收益参考，也不参与最终策略排名。

### 2020-2021

- 该长期策略: `adaptive_composite`
- 年化收益: `0.00%`
- 最大回撤: `0.00%`
- 超额收益: `-18.98%`
- 交易次数: `0`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑输基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2022

- 该长期策略: `adaptive_composite`
- 年化收益: `0.00%`
- 最大回撤: `0.00%`
- 超额收益: `21.27%`
- 交易次数: `0`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑赢基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2023-2024

- 该长期策略: `adaptive_composite`
- 年化收益: `4.82%`
- 最大回撤: `-14.05%`
- 超额收益: `8.55%`
- 交易次数: `6`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑赢基准，回撤可控，交易次数没有表现出高频或中高频特征。

### 2025

- 该长期策略: `adaptive_composite`
- 年化收益: `3.61%`
- 最大回撤: `-11.42%`
- 超额收益: `-17.61%`
- 交易次数: `1`
- 解释: 该阶段结果仅用于诊断所保留 adaptive_composite 基线参数集的承压环境，不参与策略推荐。跑输基准，回撤可控，交易次数没有表现出高频或中高频特征。

## 最终推荐

最终推荐策略: `adaptive_composite`

推荐原因:

- 选择原因: baseline_retained_no_robust_candidate
- 没有稳健候选通过全部稳健门槛，因此精确保留 adaptive_composite 基线参数集。
- 历史参数集标签 A/71.3；本次重跑评级 D/29.8。
- 本次重跑稳定性评分为 `-0.4727`。
- 本次重跑年化收益为 `1.93%`，超额收益为 `0.57%`。
- 本次重跑最大回撤为 `-17.33%`。
- 本次重跑交易次数为 `7`，交易次数没有表现出高频或中高频特征。

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
