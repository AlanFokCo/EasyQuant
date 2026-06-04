# Portfolio Risk API (Experimental)

!!! warning "Experimental Feature"

    The Portfolio Risk API is experimental and may change in future versions.

---

## PortfolioRiskMonitor

Multi-strategy portfolio risk monitor for tracking VaR, correlation, concentration, and other risk metrics.

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

# Create a monitor (with optional custom thresholds)
thresholds = RiskThresholds(
    max_drawdown_yellow=0.15,
    max_drawdown_red=0.20,
    correlation_yellow=0.60,
)
monitor = PortfolioRiskMonitor(thresholds=thresholds)

# Add strategy backtest results
monitor.add_strategy("trend_following", result_a)
monitor.add_strategy("mean_reversion", result_b)
```

### add_strategy

Add a strategy backtest result.

```python
monitor.add_strategy(name, backtest_result)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Strategy name |
| `backtest_result` | `dict` | Result returned by `run_backtest()` |

### portfolio_var

Calculate portfolio VaR (historical simulation method).

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
```

Returns `(VaR amount, VaR percentage)`. VaR represents the maximum expected loss of the portfolio over a given period at the specified confidence level.

### correlation_matrix

Calculate the inter-strategy correlation matrix.

```python
corr_matrix = monitor.correlation_matrix()
```

Returns a `DataFrame` with strategy names as both rows and columns, values being Pearson correlation coefficients.

### concentration_risk

Calculate position concentration risk.

```python
concentration = monitor.concentration_risk()
```

Returns a `dict`:

| Field | Description |
|-------|-------------|
| `max_single_stock` | Maximum single-stock position weight |
| `max_single_sector` | Maximum single-sector position weight |
| `small_cap_pct` | Micro-cap proportion (market cap < ¥5 billion) |
| `num_holdings` | Number of stocks held |
| `top3_concentration` | Top 3 holdings concentration |

### daily_check

Daily comprehensive risk check (main entry point).

```python
from eqlib import AlertLevel

report = monitor.daily_check()
```

Returns a `RiskReport` object:

| Attribute | Description |
|-----------|-------------|
| `timestamp` | Check time |
| `alert_level` | Alert level: `YELLOW` / `RED` / `KILL_SWITCH` |
| `triggers` | List of triggered alert messages |
| `portfolio_var` | Portfolio VaR (amount) |
| `portfolio_var_pct` | Portfolio VaR (percentage) |
| `correlation_matrix` | Strategy correlation matrix |
| `concentration` | Concentration metrics |
| `regime` | Current market regime: `bull` / `bear` / `oscillation` / `unknown` |
| `recommendations` | List of recommended actions |

## check_kill_switch

Kill switch check — returns a list of kill-switch actions that need to be executed immediately.

```python
from eqlib import check_kill_switch

actions = check_kill_switch(report)
# Returns e.g.: ["⚠️ Kill switch triggered: pause all strategies, await manual confirmation"]
```

## RiskThresholds

Risk threshold configuration.

```python
RiskThresholds(
    max_drawdown_yellow=0.15,   # Yellow alert drawdown
    max_drawdown_red=0.20,      # Red alert drawdown
    max_drawdown_kill=0.25,     # Kill switch drawdown
    correlation_yellow=0.60,    # Yellow alert correlation
    correlation_red=0.75,       # Red alert correlation
    correlation_kill=0.85,      # Kill switch correlation
    single_stock_max=0.10,      # Max single-stock weight
    single_sector_max=0.30,     # Max single-sector weight
    var_confidence=0.95,        # VaR confidence level
)
```

## AlertLevel

Alert level enumeration.

| Value | Description |
|-------|-------------|
| `YELLOW` | Monitor — no action triggered |
| `RED` | Requires human intervention |
| `KILL_SWITCH` | Automatic kill switch + manual confirmation required |

## Usage Example

```python
from eqlib import (
    PortfolioRiskMonitor,
    RiskThresholds,
    check_kill_switch,
    run_backtest,
)

# Run two strategies
result_a = run_backtest(strategy_a, ...)
result_b = run_backtest(strategy_b, ...)

# Create risk monitor
monitor = PortfolioRiskMonitor()
monitor.add_strategy("trend", result_a)
monitor.add_strategy("reversion", result_b)

# Daily check
report = monitor.daily_check()
print(f"Alert level: {report.alert_level.value}")
print(f"Triggers: {report.triggers}")

# Kill switch evaluation
actions = check_kill_switch(report)
for action in actions:
    print(action)
```
