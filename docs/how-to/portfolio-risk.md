# 组合风控

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 用 PortfolioRiskMonitor 对多个策略的回测结果做组合级风险审查 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 组合风控

`PortfolioRiskMonitor` 回答的问题是"把这几个策略放在一起跑，组合层面风险有多大"：整体 VaR、策略间相关性、持仓集中度、三级预警（黄/红/熔断）。

它的工作方式是**事后审查**：先把每个策略各跑一次 `run_backtest()`，把返回的 result dict 喂给监控器，再调 `daily_check()` 出报告。它不是盘中实时监测器——没有 `update()`，没有回调，不接模拟盘。可运行的完整示例是 `examples/14_portfolio_risk.py`。

### 1.1 基本用法

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

monitor = PortfolioRiskMonitor()  # 默认阈值

# 每个策略各跑一次回测，把 result dict 加进来
result_a = run_backtest(initialize_a, start_date="2024-01-01", end_date="2024-12-31")
result_b = run_backtest(initialize_b, start_date="2024-01-01", end_date="2024-12-31")
monitor.add_strategy("趋势策略", result_a)
monitor.add_strategy("均值回复", result_b)

report = monitor.daily_check()
print(report.alert_level)     # AlertLevel.YELLOW / RED / KILL_SWITCH
print(report.triggers)        # 触发的预警列表
print(report.recommendations) # 建议操作
```

`add_strategy(name, backtest_result)` 要求 result 含非空的 `recorded_values`，否则抛 `ValueError`；重名会覆盖并发出 `UserWarning`。

### 1.2 阈值配置：RiskThresholds

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

thresholds = RiskThresholds(
    max_drawdown_yellow=0.15,   # 组合回撤：黄色预警
    max_drawdown_red=0.20,      # 组合回撤：红色预警
    max_drawdown_kill=0.25,     # 组合回撤：熔断
    correlation_yellow=0.60,    # 策略相关性：黄色预警
    correlation_red=0.75,       # 策略相关性：红色预警
    correlation_kill=0.85,      # 策略相关性：熔断
    single_stock_max=0.10,      # 单只股票最大占比
    single_sector_max=0.30,     # 单个板块最大占比
    small_cap_max=0.20,         # 微盘股（市值 < 50 亿）最大占比
    var_confidence=0.95,        # VaR 置信水平
)
monitor = PortfolioRiskMonitor(thresholds=thresholds)
```

上表即全部字段与默认值。回撤和相关性按三级阈值逐级升级；集中度只做阈值比较（见 §1.6 的触发规则）。

### 1.3 组合 VaR

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
print(f"日 VaR: {var_amount:,.0f} 元 ({var_pct:.2%})")
```

历史模拟法：按各策略最新资产加权合成组合日收益率序列，取左尾分位数。解读：95% 置信下，组合单日亏损超过该值的概率约 5%。

约束：

- 每个策略至少需要 30 个交易日的收益率，不足的被排除并记入内部问题列表。
- 所有策略都不足时返回 `(nan, nan)`，用 `pd.isna(var_amount)` 判断。
- `confidence` 默认取 `thresholds.var_confidence`。

单条收益率序列的 VaR 另有 `eqlib.utils.value_at_risk(returns, confidence=0.05, method=...)`，支持 `'historical'`、`'parametric'`、`'cornish_fisher'` 三种方法——cornish_fisher 用偏度/峰度修正正态假设，更贴合 A 股的肥尾收益分布。注意它的 `confidence` 是尾部概率（0.05），与 `portfolio_var` 的置信水平（0.95）方向相反。

### 1.4 策略相关性矩阵

```python
corr = monitor.correlation_matrix()
if not corr.empty:
    print(corr)
```

返回行、列均为策略名的 Pearson 相关系数 DataFrame。策略数不足 2 个、或够 30 天数据的策略不足 2 个时，返回空 DataFrame。相关性高的策略同涨同跌，组合分散等于没做——`daily_check()` 会对最高两两相关性按 §1.2 的阈值分级预警。

### 1.5 集中度风险

```python
conc = monitor.concentration_risk()
print(conc["num_holdings"])        # 持仓股票数
print(conc["max_single_stock"])    # 单只股票最大占比
print(conc["top3_concentration"])  # 前三大持仓合计占比
```

返回字段：`max_single_stock`、`max_single_sector`、`small_cap_pct`、`num_holdings`、`top3_concentration`。数据来自各策略 result 的 `context.portfolio`（回测结束时的持仓快照）。

两个字段要打折看：

- `max_single_sector` 没有接板块数据，保守地等于 `max_single_stock`。
- `small_cap_pct` 没有接市值数据，恒为 0.0。

### 1.6 每日检查与熔断

`daily_check()` 把上面所有指标过一遍阈值，返回 `RiskReport`：

| 字段 | 内容 |
|------|------|
| `timestamp` | 报告时间 |
| `alert_level` | `AlertLevel.YELLOW` / `RED` / `KILL_SWITCH` |
| `triggers` | 触发的预警文案列表 |
| `portfolio_var` / `portfolio_var_pct` | 组合 VaR 金额与占比 |
| `correlation_matrix` | 相关性矩阵（不足时 None） |
| `concentration` | 集中度字典（无持仓时 None） |
| `regime` | 市场状态：`'bull'` / `'bear'` / `'oscillation'` / `'unknown'` |
| `recommendations` | 建议操作列表 |

级别语义：未触发任何升级条件时也是 `YELLOW`（基线，不代表有事）；`RED` 需要人工介入；`KILL_SWITCH` 表示组合回撤 ≥ `max_drawdown_kill` 或最高相关性 ≥ `correlation_kill`，建议停策略等人工确认。单股票占比超 `single_stock_max` 两倍也会升到 `RED`。

`check_kill_switch(report)` 把报告翻译成待办动作列表，空列表表示无需动作：

```python
from eqlib import check_kill_switch, AlertLevel

actions = check_kill_switch(report)
if report.alert_level == AlertLevel.KILL_SWITCH:
    for action in actions:
        print(action)  # 暂停策略 / 降低高相关策略仓位 等
```

`regime` 一项用 `get_price` 拉沪深 300 近 90 个**真实自然日**的行情判断牛熊，与回测区间无关，需要联网；取不到数据时返回 `'unknown'`。

---

完整 API 参数说明见 [组合风控 API 参考](../reference/api-risk.md)。端到端可运行示例见 `examples/14_portfolio_risk.py`。
