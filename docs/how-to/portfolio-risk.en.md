# Portfolio Risk Control

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Use PortfolioRiskMonitor to monitor portfolio risk |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Portfolio Risk Control

`PortfolioRiskMonitor` provides real-time portfolio risk monitoring, including concentration, volatility, and max drawdown alerts.

### 1.1 Basic Usage

```python
from eqlib import PortfolioRiskMonitor

# Create a monitor
monitor = PortfolioRiskMonitor(
    max_single_position_pct=0.20,  # max single-stock position 20%
    max_sector_pct=0.40,            # max single-sector position 40%
    max_drawdown_alert=0.10,        # alert when drawdown exceeds 10%
    volatility_window=20,           # volatility calculation window
)

# Update the monitor in your strategy
def market_open(context):
    # Update position data
    positions = context.portfolio.positions
    total_value = context.portfolio.total_value

    monitor.update(positions, total_value, context.current_dt)

    # Check risk alerts
    alerts = monitor.check_alerts()
    for alert in alerts:
        log.warn("Risk alert: %s" % alert)
```

### 1.2 Concentration Check

```python
# Check position concentration
concentration = monitor.get_concentration()
print("Top 3 holdings weight: %.2f%%" % (concentration['top3_pct'] * 100))
print("Herfindahl index: %.4f" % concentration['hhi'])
```

### 1.3 Volatility Monitoring

```python
# Get portfolio volatility
vol = monitor.get_portfolio_volatility()
print("Portfolio annualized volatility: %.2f%%" % (vol['annual_volatility'] * 100))
```

### 1.4 Drawdown Alerts

```python
# Set up a drawdown alert callback
def on_drawdown_alert(level, current_dd):
    log.warn("Drawdown alert! Current drawdown: %.2f%%, Threshold: %.2f%%" % (
        current_dd * 100, level * 100))

monitor.set_drawdown_callback(on_drawdown_alert)
```

### 1.5 Integration with the Stock Selection Framework

```python
from eqlib import TopNSelector

def initialize(context):
    g.selector = TopNSelector(universe=['600519', '601390', '000858'])
    g.risk_monitor = PortfolioRiskMonitor(max_single_position_pct=0.15)

def market_open(context):
    # Stock selection
    candidates = g.selector.select(context)

    # Risk control check
    if g.risk_monitor.check_position_limit(candidates):
        for sec in candidates:
            order_value(sec, context.portfolio.available_cash / len(candidates))
    else:
        log.info("Risk control limit reached, no rebalancing today")
```

---

See the [Portfolio Risk Control API Reference](../reference/api-risk.md) for full parameter documentation.
