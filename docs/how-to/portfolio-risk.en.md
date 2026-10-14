# Portfolio Risk Monitoring

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Run portfolio-level risk reviews over multiple strategy backtest results with PortfolioRiskMonitor |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Portfolio Risk Monitoring

`PortfolioRiskMonitor` answers one question: "if I run these strategies together, how risky is the combined portfolio?" It covers portfolio VaR, cross-strategy correlation, position concentration, and a four-level alert system (normal / yellow / red / kill-switch).

It works as a **post-backtest review**: run each strategy through `run_backtest()`, feed the returned result dicts into the monitor, then call `daily_check()` for a report. It is not a live intraday monitor — there is no `update()`, no callbacks, and no paper-trading hookup. The runnable end-to-end demo is `examples/14_portfolio_risk.py`.

### 1.1 Basic Usage

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

monitor = PortfolioRiskMonitor()  # default thresholds

# Backtest each strategy separately and register its result dict
result_a = run_backtest(initialize_a, start_date="2024-01-01", end_date="2024-12-31")
result_b = run_backtest(initialize_b, start_date="2024-01-01", end_date="2024-12-31")
monitor.add_strategy("trend", result_a)
monitor.add_strategy("mean_reversion", result_b)

report = monitor.daily_check()
print(report.alert_level)     # AlertLevel.NORMAL / YELLOW / RED / KILL_SWITCH
print(report.triggers)        # triggered alerts
print(report.recommendations) # suggested actions
```

`add_strategy(name, backtest_result)` requires a result dict with a non-empty `recorded_values`, otherwise it raises `ValueError`; reusing a name overwrites the entry and emits a `UserWarning`.

### 1.2 Threshold Configuration: RiskThresholds

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

thresholds = RiskThresholds(
    max_drawdown_yellow=0.15,   # portfolio drawdown: yellow alert
    max_drawdown_red=0.20,      # portfolio drawdown: red alert
    max_drawdown_kill=0.25,     # portfolio drawdown: kill switch
    correlation_yellow=0.60,    # strategy correlation: yellow alert
    correlation_red=0.75,       # strategy correlation: red alert
    correlation_kill=0.85,      # strategy correlation: kill switch
    single_stock_max=0.10,      # max single-stock weight
    single_sector_max=0.30,     # max single-sector weight
    small_cap_max=0.20,         # max small-cap (< 5B CNY market cap) weight
    var_confidence=0.95,        # VaR confidence level
)
monitor = PortfolioRiskMonitor(thresholds=thresholds)
```

The table above lists every field with its default. Drawdown and correlation escalate through the three levels; concentration checks are plain threshold comparisons (see §1.6 for the trigger rules).

### 1.3 Portfolio VaR

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
print(f"Daily VaR: {var_amount:,.0f} CNY ({var_pct:.2%})")
```

Historical simulation: combine the strategies' daily return series weighted by latest portfolio value, then take the left-tail quantile. Reading: at 95% confidence, the chance of the portfolio losing more than this in a single day is about 5%.

Constraints:

- Each strategy needs at least 30 trading days of returns; shorter series are excluded and recorded in the internal issue list.
- If all strategies fall short, it returns `(nan, nan)` — check with `pd.isna(var_amount)`.
- `confidence` defaults to `thresholds.var_confidence`.

For a single return series there is also `eqlib.utils.value_at_risk(returns, confidence=0.05, method=...)` with `'historical'`, `'parametric'`, and `'cornish_fisher'` methods — cornish_fisher adjusts the normal assumption for sample skew and kurtosis, which fits fat-tailed A-share returns better. Note its `confidence` is the tail probability (0.05), the opposite direction of `portfolio_var`'s confidence level (0.95).

### 1.4 Strategy Correlation Matrix

```python
corr = monitor.correlation_matrix()
if not corr.empty:
    print(corr)
```

Returns a DataFrame of Pearson correlations with strategy names on both axes. With fewer than 2 strategies — or fewer than 2 strategies having 30+ days of data — it returns an empty DataFrame. Highly correlated strategies move together and the portfolio gets no diversification; `daily_check()` grades the maximum pairwise correlation against the §1.2 thresholds.

### 1.5 Concentration Risk

```python
conc = monitor.concentration_risk()
print(conc["num_holdings"])        # number of holdings
print(conc["max_single_stock"])    # max single-stock weight
print(conc["top3_concentration"])  # combined weight of the top 3 holdings
```

Returned keys: `max_single_stock`, `max_single_sector`, `small_cap_pct`, `num_holdings`, `top3_concentration`. Data comes from each strategy result's `context.portfolio` (the position snapshot at backtest end).

Take two fields with a grain of salt:

- `max_single_sector` has no sector data source — it conservatively equals `max_single_stock`.
- `small_cap_pct` has no market-cap data source — it is always 0.0.

### 1.6 Daily Check and Kill Switch

`daily_check()` runs every metric above through the thresholds and returns a `RiskReport`:

| Field | Content |
|-------|---------|
| `timestamp` | Report time |
| `alert_level` | `AlertLevel.NORMAL` / `YELLOW` / `RED` / `KILL_SWITCH` |
| `triggers` | Triggered alert messages |
| `portfolio_var` / `portfolio_var_pct` | Portfolio VaR amount and percentage |
| `correlation_matrix` | Correlation matrix (None if insufficient) |
| `concentration` | Concentration dict (None if no holdings) |
| `regime` | Market regime: `'bull'` / `'bear'` / `'oscillation'` / `'unknown'` |
| `recommendations` | Suggested actions |

Level semantics: `NORMAL` when no condition triggered at all; any trigger (even "choppy market right now") means at least `YELLOW`; `RED` calls for human review; `KILL_SWITCH` means portfolio drawdown reached `max_drawdown_kill` or the maximum correlation reached `correlation_kill` — pause strategies and wait for manual confirmation. A single-stock weight beyond twice `single_stock_max` also escalates to `RED`.

`check_kill_switch(report)` translates the report into a list of action items; an empty list means no action needed:

```python
from eqlib import check_kill_switch, AlertLevel

actions = check_kill_switch(report)
if report.alert_level == AlertLevel.KILL_SWITCH:
    for action in actions:
        print(action)  # pause strategies / cut correlated positions by 50%, etc.
```

The `regime` field fetches the CSI 300 over the last 90 **real calendar days** via `get_price` to classify bull/bear — it is independent of the backtest window and requires network access; it returns `'unknown'` when data is unavailable.

---

See the [Portfolio Risk API Reference](../reference/api-risk.md) for full parameter documentation. The runnable end-to-end demo is `examples/14_portfolio_risk.py`.
