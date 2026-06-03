# 组合风控

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 使用 PortfolioRiskMonitor 监测组合风险 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 组合风控

`PortfolioRiskMonitor` 提供实时的组合风险监测，包括集中度、波动率和最大回撤预警。

### 1.1 基本用法

```python
from eqlib import PortfolioRiskMonitor

# 创建监测器
monitor = PortfolioRiskMonitor(
    max_single_position_pct=0.20,  # 单只股票最大仓位 20%
    max_sector_pct=0.40,            # 单行业最大仓位 40%
    max_drawdown_alert=0.10,        # 回撤超过 10% 预警
    volatility_window=20,           # 波动率计算窗口
)

# 在策略中更新监测器
def market_open(context):
    # 更新持仓数据
    positions = context.portfolio.positions
    total_value = context.portfolio.total_value

    monitor.update(positions, total_value, context.current_dt)

    # 检查风险预警
    alerts = monitor.check_alerts()
    for alert in alerts:
        log.warn("风险预警: %s" % alert)
```

### 1.2 集中度检查

```python
# 检查持仓集中度
concentration = monitor.get_concentration()
print("前三大持仓占比: %.2f%%" % (concentration['top3_pct'] * 100))
print("赫芬达尔指数: %.4f" % concentration['hhi'])
```

### 1.3 波动率监测

```python
# 获取组合波动率
vol = monitor.get_portfolio_volatility()
print("组合年化波动率: %.2f%%" % (vol['annual_volatility'] * 100))
```

### 1.4 回撤预警

```python
# 设置回撤预警回调
def on_drawdown_alert(level, current_dd):
    log.warn("回撤预警! 当前回撤: %.2f%%, 阈值: %.2f%%" % (
        current_dd * 100, level * 100))

monitor.set_drawdown_callback(on_drawdown_alert)
```

### 1.5 与选股框架联动

```python
from eqlib import TopNSelector

def initialize(context):
    g.selector = TopNSelector(universe=['600519', '601390', '000858'])
    g.risk_monitor = PortfolioRiskMonitor(max_single_position_pct=0.15)

def market_open(context):
    # 选股
    candidates = g.selector.select(context)

    # 风控检查
    if g.risk_monitor.check_position_limit(candidates):
        for sec in candidates:
            order_value(sec, context.portfolio.available_cash / len(candidates))
    else:
        log.info("风控限制，本日不调仓")
```

---

完整 API 参数说明见 [组合风控 API 参考](../reference/api-risk.md)。
