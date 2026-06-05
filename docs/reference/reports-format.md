# 报告格式规范

> JSON、PNG、HTML、Markdown 报告的字段定义与数据结构。

---

## analyze_returns 指标字典

对 `result = run_backtest(...)` 或 `run_strategy` 的返回值：

```python
from eqlib import analyze_returns

m = analyze_returns(result, risk_free_rate=0.03, trading_days=252)
```

当 `result["recorded_values"]` 不足以构造日净值序列时，函数可能返回 **`None`**，此时 HTML 中部分指标也会缺失。

| 键名 | 含义 |
|------|------|
| `total_return` | 全区间总收益率（基于起止组合价值） |
| `annual_return` | 由日收益几何年化得到的年化收益 |
| `annual_volatility` | 日收益标准差 × √252 |
| `sharpe_ratio` | 夏普比率（年化，扣无风险利率） |
| `sortino_ratio` | 索提诺比率 |
| `max_drawdown` | 最大回撤（负数） |
| `calmar_ratio` | 年化收益 / \|最大回撤\| |
| `alpha` | 年化 Alpha（相对基准） |
| `beta` | Beta |
| `information_ratio` | 信息比率 |
| `win_rate_daily` | 日胜率 |
| `win_rate_trade` | 配对交易胜率 |
| `trade_count` | 完成配对交易次数 |
| `win_count` / `loss_count` | 盈利 / 亏损交易笔数 |
| `profit_loss_ratio` | 盈亏比 |
| `annual_turnover` | 年化换手率（成交额相对规模） |
| `total_commission` | 佣金合计（报告用；净值已反映成本） |
| `net_return` | 与 `total_return` 一致含义（见源码注释） |
| `excess_return` | 策略总收益 − 基准总收益 |
| `benchmark_return` | 基准总收益 |
| `excess_return_max_drawdown` | 超额收益序列最大回撤 |
| `excess_return_sharpe` | 超额收益夏普 |
| `daily_excess_return` | 日超额收益年化均值 |
| `benchmark_volatility` | 基准年化波动率 |
| `max_drawdown_start` | 最大回撤起始日期 |
| `max_drawdown_end` | 最大回撤结束日期 |
| `trading_days` | 交易天数 |
| `num_trades` | 成交总笔数（单边） |
| `monthly_returns` | 月度收益率字典（`{"2024-01": 0.03, ...}`） |
| `rolling_sharpe_60d` | 60 日滚动夏普序列（`[{"date": "...", "value": ...}]`） |
| `rolling_volatility_60d` | 60 日滚动波动率序列 |
| `daily_returns_stats` | 日收益统计（均值、标准差、偏度、峰度、最佳/最差日、直方图） |
| `per_stock_pnl` | 个股盈亏字典（FIFO 配对，`{"000001": 5000.0, ...}`） |
| `drawdown_periods` | 前 5 大回撤周期（起始/谷底/恢复日期、深度、持续天数） |

无风险利率默认 **`risk_free_rate=0.03`**（年化 3%），可按研究习惯修改。

---

## Markdown / JSON 报告

- **Markdown**：适合贴到笔记或版本库，快速浏览摘要与成交表。
- **JSON**：适合写脚本批量对比多组参数、画自定义图、接入仪表板。

### JSON 顶层字段（Agent-First Schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `verdict` | `object` | 策略综合评级（S/A/B/C/D）、得分、最强/最弱维度 |
| `targets` | `object` | 指标目标值与当前达标状态 |
| `diagnostics` | `array` | 诊断发现（最大回撤、夏普、胜率、Alpha 等不达标项） |
| `recommendations` | `array` | 参数调优建议（优先级、参数名、当前值、建议值） |
| `grade` | `object` | 6 维评分详情（收益率、风控、风险调整、交易质量、超额能力、稳定性） |
| `metrics` | `object` | 全量指标（同 `analyze_returns` 返回值，inf/nan 序列化为 `null`） |
| `time_series` | `object` | 月度收益、滚动夏普、滚动波动率、回撤周期 |
| `daily_returns_stats` | `object` | 日收益统计（均值、标准差、偏度、峰度） |
| `per_stock_pnl` | `object` | 个股盈亏（FIFO 配对） |
| `summary` | `object` | 回测区间、资金、盈亏、交易次数、基准 |
| `trades` | `array` | 每笔成交记录 |
| `positions` | `object` | 期末持仓 |
| `chart_data` | `object` | K 线、成交量、累计收益、回撤等图表数据（嵌套） |
| `factor_analysis` | `object` | 因子分析（简化 Fama-French） |
| `brinson_attribution` | `object` | Brinson 归因 |
| `risk_metrics` | `object` | **向后兼容**：扁平指标字典（夏普、回撤、Alpha 等） |
| `cumulative_returns` | `array` | **向后兼容**：每日净值序列 `[{date, total_value, cumulative_return}]` |
| `strategy_params` | `object` | （可选）当前参数与参数范围 |
| `iteration` | `object` | （可选）迭代上下文（run_id、变更、得分变化） |

JSON 顶层字段随版本可能扩展，以生成文件为准。

**读 JSON 时注意：**`summary.num_trades` 多为单边成交条数，与「配对交易笔数」不同，见 [FAQ](../project/faq.md#faq-json-num-trades)。
