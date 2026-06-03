# 组合风控 API（实验性）

!!! warning "实验性功能"

    组合风控 API 为实验性功能，未来版本可能有变动。

---

## PortfolioRiskMonitor

多策略组合风控监控器，用于监测 VaR、相关性、集中度等风险指标。

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

# 创建监控器（可选自定义阈值）
thresholds = RiskThresholds(
    max_drawdown_yellow=0.15,
    max_drawdown_red=0.20,
    correlation_yellow=0.60,
)
monitor = PortfolioRiskMonitor(thresholds=thresholds)

# 添加策略回测结果
monitor.add_strategy("trend_following", result_a)
monitor.add_strategy("mean_reversion", result_b)
```

### add_strategy

添加策略回测结果。

```python
monitor.add_strategy(name, backtest_result)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 策略名称 |
| `backtest_result` | `dict` | `run_backtest()` 返回的结果 |

### portfolio_var

计算组合 VaR（历史模拟法）。

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
```

返回 `(VaR金额, VaR百分比)`。VaR 表示在给定置信度下，组合在未来一段时间内的最大预期损失。

### correlation_matrix

计算策略间相关性矩阵。

```python
corr_matrix = monitor.correlation_matrix()
```

返回 `DataFrame`，行列均为策略名称，值为 Pearson 相关系数。

### concentration_risk

计算持仓集中度风险。

```python
concentration = monitor.concentration_risk()
```

返回 `dict`：

| 字段 | 说明 |
|------|------|
| `max_single_stock` | 单股票最大持仓占比 |
| `max_single_sector` | 单板块最大持仓占比 |
| `small_cap_pct` | 微盘股占比（市值<50亿） |
| `num_holdings` | 持仓股票数量 |
| `top3_concentration` | 前三大持仓占比 |

### daily_check

每日综合风控检查（主入口）。

```python
from eqlib import AlertLevel

report = monitor.daily_check()
```

返回 `RiskReport` 对象：

| 属性 | 说明 |
|------|------|
| `timestamp` | 检查时间 |
| `alert_level` | 预警级别：`YELLOW` / `RED` / `KILL_SWITCH` |
| `triggers` | 触发的预警信息列表 |
| `portfolio_var` | 组合 VaR（金额） |
| `portfolio_var_pct` | 组合 VaR（百分比） |
| `correlation_matrix` | 策略相关性矩阵 |
| `concentration` | 集中度指标 |
| `regime` | 当前市场 regime：`bull` / `bear` / `oscillation` / `unknown` |
| `recommendations` | 建议操作列表 |

## check_kill_switch

熔断检查，返回需要立即执行的熔断操作列表。

```python
from eqlib import check_kill_switch

actions = check_kill_switch(report)
# 返回如：["⚠️ 熔断触发：暂停所有策略，等待人工确认"]
```

## RiskThresholds

风控阈值配置。

```python
RiskThresholds(
    max_drawdown_yellow=0.15,   # 黄色预警回撤
    max_drawdown_red=0.20,      # 红色预警回撤
    max_drawdown_kill=0.25,     # 熔断回撤
    correlation_yellow=0.60,    # 黄色预警相关性
    correlation_red=0.75,       # 红色预警相关性
    correlation_kill=0.85,      # 熔断相关性
    single_stock_max=0.10,      # 单股票最大占比
    single_sector_max=0.30,     # 单板块最大占比
    var_confidence=0.95,        # VaR 置信水平
)
```

## AlertLevel

预警级别枚举。

| 值 | 说明 |
|------|------|
| `YELLOW` | 监控关注，不触发动作 |
| `RED` | 需要人工介入 |
| `KILL_SWITCH` | 自动熔断 + 人工确认 |

## 使用示例

```python
from eqlib import (
    PortfolioRiskMonitor,
    RiskThresholds,
    check_kill_switch,
    run_backtest,
)

# 运行两个策略
result_a = run_backtest(strategy_a, ...)
result_b = run_backtest(strategy_b, ...)

# 创建风控监控器
monitor = PortfolioRiskMonitor()
monitor.add_strategy("trend", result_a)
monitor.add_strategy("reversion", result_b)

# 每日检查
report = monitor.daily_check()
print(f"预警级别: {report.alert_level.value}")
print(f"触发因素: {report.triggers}")

# 熔断判断
actions = check_kill_switch(report)
for action in actions:
    print(action)
```
