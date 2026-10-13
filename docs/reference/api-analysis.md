# 报告与分析 API

> 生成回测报告、计算风险指标、归因分析和组合优化。

---

## generate_chart

生成回测图表（PNG）。

```python
generate_chart(result, out_path)
```

## generate_report_md

生成 Markdown 格式报告。

## generate_report_json

生成 JSON 格式报告。返回的 JSON 包含：`metadata`（生成信息）、`summary`（资金盈亏）、`risk_metrics`（风险指标）、`excess_return_metrics`（超额收益指标）、`brinson_attribution`（Brinson 归因）、`factor_analysis`（因子分析）、`trades`（成交列表）、`positions`（持仓）、`cumulative_returns`（净值序列），以及全部 **图表数据数组**：`candlestick_data`、`volume_data`、`ma5/20/60_data`、`rsi_data`、`macd_data`/`macd_signal_data`/`macd_hist_data`、`bb_upper/middle/lower_data`、`support_data`、`resistance_data`、`markers`、`cum_return_data`、`ret_hs300_data`、`ret_sse_data`、`drawdown_data`、`pnl_bar_data`、`daily_returns_data`。

## generate_html_report

生成交互式 HTML 报告。HTML 报告内含 K 线图（含 MA 均线、成交量、买卖信号）、RSI(14)、MACD(12,26,9)、Bollinger Bands(20,2)、累计收益、回撤、每日盈亏、成交记录。K 线图支持指标切换面板和十字光标联动图例。

## analyze_returns

计算综合风险指标。

```python
metrics = analyze_returns(result, risk_free_rate=0.03)
```

返回 `dict`：`total_return`, `annual_return`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `alpha`, `beta`, `information_ratio`, `win_rate`, `trading_days`, `num_trades`。当 `result["recorded_values"]` 为空、缺少 `total_value` 或初始资金非正时，返回 **`None`**。

口径说明：

- 年化基准为 **244** 个交易日（A 股实际值，见 `eqlib/constants.py`）。
- `alpha` / `beta` / `information_ratio` 依赖基准序列：基准数据不可用或重叠不足 10 个交易日时为 `NaN`（报告与示例渲染为 `N/A`），不再静默默认 0.0/1.0。
- 基准收益优先复用引擎记录的基准净值序列（与报告图表同源），取不到才回退网络拉取。
- `win_rate_trade` / `profit_loss_ratio` / `per_stock_pnl` 基于 FIFO 配对的往返盈亏，**已含双边费用**（买入佣金摊入成本、卖出费用从收入扣减），与引擎现金账一致。

## grade_strategy

策略综合评分（6 维度）。

```python
grade_info = grade_strategy(analytics)
```

接受 `analyze_returns()` 返回的字典，返回 `dict`：`overall`（S/A/B/C/D）、`score`（0-100）、`dimensions`（6 维评分列表）、`weakest`/`strongest`（最弱/最强维度名）、`summary_text`（一句话总结）。

6 个评分维度：收益率能力（20%）、风险控制（20%）、风险调整（20%）、交易质量（15%）、超额能力（15%）、稳定性（10%）。

## diagnose_bottleneck

诊断策略瓶颈指标。

```python
diagnostics = diagnose_bottleneck(analytics, grade_info)
```

返回 `list[dict]`，每项包含：`metric`、`severity`（critical/warning）、`finding`（发现描述）、`root_cause`（根因分析）、`affected_period`、`related_metrics`。

检查的指标：最大回撤（< -20%）、夏普（< 1.0）、胜率（< 40%）、Alpha（< 0）。

## recommend_params

参数调优建议。

```python
recommendations = recommend_params(analytics, grade_info, current_params, param_ranges)
```

根据诊断结果推荐参数调整。`current_params` 和 `param_ranges` 为策略文件中定义的 `PARAMS` 和 `PARAM_RANGES` 字典。返回 `list[dict]`，每项包含：`priority`、`target_metric`、`action`、`parameter`、`current`、`suggested`、`range`、`rationale`、`expected_effect`、`risk`。

## brinson_attribution

Brinson-Hood-Beebower 单期归因。将整个回测区间视为一个持有期，在行业层面把超额收益分解为配置、选股、交互三项，数学上严格闭合：`allocation + selection + interaction == portfolio_return − benchmark_return`。

```python
attr = brinson_attribution(result, sector_data={"601398.XSHG": "Financials", ...})
```

| 参数 | 说明 |
|------|------|
| `result` | `run_backtest` 返回的结果字典 |
| `sector_data` | 证券 → 行业名映射；缺省映射的证券归入 `"Unclassified"`。不传时所有证券同属一个行业，配置与交互效应恒为 0，全部超额收益计入选股效应（这是无行业结构时 BHB 的正确表述） |
| `benchmark_returns` | 可选的基准日收益 `pd.Series`；提供时按该标量收益作为各行业基准，否则用 universe 等权买入持有收益（基于引擎导出的 OHLCV 面板，与成交同一 qfq 口径） |

返回 `dict`：`allocation_effect`, `selection_effect`, `interaction_effect`, `total_active_return`, `portfolio_return`, `benchmark_return`, `benchmark_model`（`"universe_equal_weight"` / `"scalar_series"`），以及分行业明细 `sectors`（各行业权重、收益与三项效应）。

## simple_factor_analysis

简化因子分析。将策略收益分解为市场因子（beta）、动量代理（滞后收益自相关）和 Alpha（残差）。

> **注意：** 本函数**不实现**真正的 Fama-French 三因子模型。`momentum_correlation` 字段为收益自相关，非真正的动量因子暴露。

```python
from eqlib import simple_factor_analysis
ff = simple_factor_analysis(result)
```

返回 `dict`（`market_beta`, `market_exposure`, `alpha_annual`, `momentum_correlation`, `vol_of_vol`, `residual_volatility`, `explained_variance`）。

!!! warning "已弃用别名"

    `fama_french_analysis` 仍可使用，但已弃用。请改用 `simple_factor_analysis`。

---

## 组合优化 API

### portfolio_optimizer

投资组合权重优化。

```python
portfolio_optimizer(securities, prices, target=None, constraints=None, bounds=None,
                    default_range=(0.0, 1.0), ftol=1e-9, return_none_if_fail=True)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 股票代码列表 |
| `prices` | `DataFrame` | 价格矩阵 |
| `target` | `MinVariance`/`MaxSharpe`/`RiskParity` | 优化目标 |
| `constraints` | `dict` | `{'max_weight': 0.3}` |
| `bounds` | `list[Bound]` | 每只股票权重上下限 |

返回优化后的权重 `Series` 或 `None`。

#### 优化目标

```python
MinVariance()
MaxSharpe(risk_free_rate=0.03)
RiskParity()
```
