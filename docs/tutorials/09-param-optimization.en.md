# Tutorial 09: Strategy Parameter Optimization & Auditing

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Manage tunable parameters with `PARAMS` / `PARAM_RANGES`; search with `optimizer.py`, validate on rolling out-of-sample windows with `walk_forward` / `walk_forward_analysis`, and audit overfitting and bias with `validate_backtest` |
    | **Est. Time** | ~60 minutes |
    | **Prerequisites** | [Tutorial 00](00-getting-started.md), [Tutorial 02](02-backtesting.md) (backtesting & metrics), [Tutorial 03](03-optimization.md) (manual optimization); for metric definitions see [Report Format Reference](../reference/reports-format.md) |

> This chapter explains how to parameterize strategies using **PARAMS / PARAM_RANGES**, combined with the in-repo `agent/optimizer.py` (rule-based search reference), `agent/audit_log.py` (audit logging), and eqlib's built-in rolling-validation and scientific-validation APIs to build a **reproducible** parameter tuning and auditing workflow. You can also write your own Python scripts or orchestrate the same steps in any IDE; EasyQuant is **not tied to** any specific editor or commercial AI product.

---

## Table of Contents

1. [Why Parameterization and Auditing](#1-why-parameterization-and-auditing)
2. [Core Conventions](#2-core-conventions)
3. [Command Line: optimizer.py](#3-command-line-optimizerpy)
4. [Rolling Out-of-Sample Validation: walk_forward](#4-rolling-out-of-sample-validation-walk_forward)
5. [Overfitting Detection: walk_forward_analysis](#5-overfitting-detection-walk_forward_analysis)
6. [One-Stop Scientific Validation: validate_backtest & ValidationConfig](#6-one-stop-scientific-validation-validate_backtest--validationconfig)
7. [ML Hyperparameter Search: optimize_hyperparams](#7-ml-hyperparameter-search-optimize_hyperparams)
8. [Building Your Own Optimization Loop (Recommended Approach)](#8-building-your-own-optimization-loop-recommended-approach)
9. [Audit Logs](#9-audit-logs)
10. [Code Review Checklist (Recommended)](#10-code-review-checklist-recommended)
11. [Further Reading](#11-further-reading)

---

## 1. Why Parameterization and Auditing

| Pain Point | How Parameterization + Auditing Helps |
|-----------|--------------------------------------|
| Tuning by gut feel | `PARAM_RANGES` defines clear search boundaries; results are comparable |
| Decisions not traceable | `audit_log/` records metrics and change rationale for every iteration |
| Great in-sample, poor out-of-sample | `walk_forward` / `walk_forward_analysis` quantify decay over rolling OOS windows |
| Rule-based scripts too rigid | Run `optimizer.py` for a baseline first, then write custom diagnostic logic as needed |

---

## 2. Core Conventions

### 2.1 Relevant Repository Files

| Path | Purpose |
|------|---------|
| [`agent/strategy_template.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/strategy_template.py) | Copy-ready parameterized strategy skeleton |
| [`agent/optimizer.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/optimizer.py) | Rule-based parameter search (**reference implementation**, independently runnable) |
| [`agent/audit_log.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/audit_log.py) | Writes JSONL + Markdown audit entries |

### 2.2 `PARAMS` and `PARAM_RANGES`

Strategies should define two **module-level** dictionaries: current values and search space. `initialize` must read from `PARAMS`; hardcoded magic numbers are prohibited.

```python
PARAMS = {
    "fast_period": 5,
    "slow_period": 20,
    "stop_loss_pct": 0.08,
    "position_pct": 1.0,
    "vol_confirm_mul": 1.5,
}

PARAM_RANGES = {
    "fast_period": (2, 15, 1),
    "slow_period": (10, 60, 5),
    "stop_loss_pct": (0.03, 0.15, 0.01),
    "position_pct": (0.3, 1.0, 0.1),
    "vol_confirm_mul": (1.0, 3.0, 0.25),
}
```

```python
def initialize(context):
    g.fast_period = PARAMS["fast_period"]
    g.slow_period = PARAMS["slow_period"]
    # ...
```

### 2.3 Common Acceptance Criteria (Examples)

- Multi-metric thresholds: Sharpe, max drawdown, annual return, win rate
- Cover at least **2 calendar years** or an equivalent trading-day span
- Out-of-sample Sharpe stays above a chosen fraction of the in-sample Sharpe (see §4-5)

Set concrete thresholds according to your strategy's risk profile.

---

## 3. Command Line: optimizer.py

From the repository root (with `pip install -e .` done), run the reference optimizer, for example:

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

It demonstrates **programmatic** search; for more complex diagnostics (e.g., structural strategy changes), call `run_backtest`, `analyze_returns`, and other APIs directly in your own scripts or notebooks.

---

## 4. Rolling Out-of-Sample Validation: walk_forward

A single "tune on the first 70%, validate on the last 30%" split gives you exactly one out-of-sample verdict. `eqlib.wfa.walk_forward()` slices the full range into alternating, rolling in-sample (IS) / out-of-sample (OOS) windows: each window selects parameters on its IS segment, runs an independent OOS backtest with those parameters, and finally stitches all OOS segments into one equity curve.

```python
from eqlib import walk_forward, analyze_returns

def make_initialize(**params):
    """Parameter factory: params chosen by optimize_fn arrive as keywords."""
    merged = {**PARAMS, **params}

    def initialize(context):
        g.fast_period = merged["fast_period"]
        g.slow_period = merged["slow_period"]
        g.stop_loss_pct = merged["stop_loss_pct"]
        # ... rest of initialization ...
    return initialize

def optimize_fn(train_result):
    """IS-segment parameter selection: the returned dict goes to make_initialize. Return {} to keep defaults."""
    metrics = analyze_returns(train_result)
    if metrics["sharpe_ratio"] < 1.0:
        return {"slow_period": 30}   # example: slower MA in weak windows
    return {}

result = walk_forward(
    make_initialize,
    optimize_fn=optimize_fn,        # pass None to use default params everywhere
    start_date="2020-01-01",
    end_date="2024-12-31",
    train_months=12,                # each IS window is 12 months
    test_months=3,                  # each OOS window is 3 months
    step_months=3,                  # step == test window -> non-overlapping OOS
    starting_cash=100_000,
)

print(result.summary)               # aggregated statistics
result.oos_equity.plot()            # stitched OOS equity curve
```

The three `WFAResult` attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `windows` | `list[dict]` | Per-window `train_start/end`, `test_start/end`, `params`, `oos_result`, `oos_metrics` |
| `oos_equity` | `pd.Series` | Stitched OOS equity curve (per-window normalized, then chained) |
| `summary` | `dict` | `n_windows`, `profitable_pct` (share of profitable OOS windows), `avg_oos_sharpe`, `total_oos_return`, `oos_max_drawdown`, etc. |

How to read it: if `profitable_pct` is far below what the full-sample win rate suggested, or `oos_equity` drifts sideways for years, the strategy is regime-sensitive. `summary["avg_oos_sharpe"]` is the Sharpe you may quote — the full-sample Sharpe embeds data you tuned on.

---

## 5. Overfitting Detection: walk_forward_analysis

The `eqlib.scientific` layer's `walk_forward_analysis()` is lighter-weight: it does not select parameters on the IS segment. It runs fixed-parameter IS and OOS backtests per window and quantifies **out-of-sample decay**.

```python
from eqlib.scientific import walk_forward_analysis

wfa = walk_forward_analysis(
    initialize,              # initialize callable (recommended); a run_backtest result dict also works
    param_ranges=None,       # reserved; currently only recorded in window metadata
    train_window="2Y",
    test_window="6M",
    step="6M",
    start_date="2020-01-01",
    end_date="2024-12-31",
)

print("OOS/IS Sharpe ratio:", round(wfa.oos_is_ratio, 2))
print("OOS decay:", wfa.is_sharpe_decay)
for w in wfa.windows:
    print(w["train_start"], "->", w["test_end"],
          "IS sharpe:", round(w["is_metrics"]["sharpe"], 2),
          "OOS sharpe:", round(w["oos_metrics"]["sharpe"], 2))
```

| Return value | Type | Description |
|--------------|------|-------------|
| `windows` | `list[dict]` | Per-window `train_start/end`, `test_start/end`, `is_metrics`, `oos_metrics` (each with `sharpe` / `annual_return` / `max_drawdown`) |
| `oos_is_ratio` | `float` | Mean OOS Sharpe / mean IS Sharpe; well below 1 means out-of-sample decay |
| `is_sharpe_decay` | `bool` | Whether mean OOS Sharpe is below mean IS Sharpe |

!!! tip "Callable or dict"
    Passing an `initialize` callable runs every IS / OOS segment as an independent backtest from the initial cash — a true out-of-sample measurement. Passing an existing backtest result dict only slices the equity curve by date, so OOS segments inherit the IS segment's cumulative equity — fast, but not strictly OOS.

!!! warning "Parameter perturbation"
    `walk_forward_analysis` currently does **not** perturb strategy parameters (`param_ranges` is metadata-only). For parameter sensitivity, combine it with `parameter_sensitivity` / `out_of_sample_test` from `eqlib.scientific`.

---

## 6. One-Stop Scientific Validation: validate_backtest & ValidationConfig

`validate_backtest()` chains bias detection (look-ahead / survivorship / selection / data), statistical confidence (bootstrap, Monte Carlo, significance), overfitting detection, and extended risk metrics into one pipeline over a single backtest result:

```python
from eqlib import run_backtest, ValidationConfig
from eqlib.scientific import validate_backtest

result = run_backtest(initialize, "2022-01-01", "2024-12-31")

config = ValidationConfig(
    n_bootstrap=1000,           # bootstrap resamples
    n_monte_carlo=500,          # Monte-Carlo simulations
    significance_level=0.05,    # p-value threshold for significance tests
    perturbation_pct=0.10,      # parameter perturbation size
    random_state=42,            # seed for reproducibility
)
validation = validate_backtest(result, config=config)
print(validation.summary())      # overall trust rating + per-module summary
print(validation.trust_rating)
```

To skip a module, switch it off in `ValidationConfig`: `ValidationConfig(overfitting=False, statistics=False)` runs only bias and risk checks. The full parameter list is in the [Scientific Validation API](../reference/api-scientific.md).

---

## 7. ML Hyperparameter Search: optimize_hyperparams

If your strategy uses `MLSelector` (see [Tutorial 11](11-ml-selection.md)), do not tune model hyperparameters with random-split cross-validation — time series leak. `optimize_hyperparams()` runs a grid search with `TimeSeriesSplit`:

```python
from eqlib.ml.tuning import optimize_hyperparams

best = optimize_hyperparams(
    pipeline,                    # FeaturePipeline instance
    model_type="random_forest",
    X=X_train,                   # feature matrix
    y=y_train,                   # labels
    param_grid={"n_estimators": [50, 100, 200], "max_depth": [3, 5, 8]},
    cv_method="time_series_split",
    n_splits=5,
    scoring="roc_auc",
)
```

With fewer than `n_splits * 2` rows it returns an empty dict and falls back to default parameters. For one-line tuning inside a strategy, use `auto_tune_selector` (pulls data straight from the selector's pipeline); see the [ML API reference](../reference/api-ml.md).

---

## 8. Building Your Own Optimization Loop (Recommended Approach)

```
Baseline backtest (run_backtest / run_strategy)
    |
    v
analyze_returns(result) and other metrics
    |
    v
If below target: adjust PARAMS by rule or judgment (stay within PARAM_RANGES)
    |
    v
Out-of-sample review: walk_forward or walk_forward_analysis (Sections 4-5)
    |
    v
(Optional) Full validate_backtest audit (Section 6)
    |
    v
Re-run backtest -> write summary into audit_log (if using audit_log.py)
    |
    v
Stop condition or max iterations reached
```

The implementation is entirely up to you: Shell + Python, Makefile, CI jobs all work. One discipline matters: **any parameter informed by full-sample data must prove itself again on OOS windows.**

---

## 9. Audit Logs

If you use `agent/audit_log.py`, each session produces:

```
audit_log/
├── session_<timestamp>.jsonl   # machine-readable
└── session_<timestamp>.md      # Markdown summary
```

`jq` examples:

```bash
jq 'select(.type=="adjustment")' audit_log/session_*.jsonl
jq 'select(.type=="final")' audit_log/session_*.jsonl
```

Log the key numbers from Sections 4-6 (`oos_is_ratio`, `profitable_pct`, `trust_rating`) into the audit entries as well — they say more about strategy quality than any single full-sample metric.

---

## 10. Code Review Checklist (Recommended)

After each change to `PARAMS` or strategy logic, check at least:

1. New values fall within `PARAM_RANGES` and satisfy cross-constraints (e.g., `fast_period < slow_period`).
2. Tuned parameters are read via `PARAMS["..."]`, not hardcoded.
3. No future data, no misuse of same-day closing prices in signals (avoid look-ahead); when in doubt, run `validate_backtest` and read the bias report.
4. Backtest range and data source are consistent; anomalous trading (suspensions, etc.) is handled.
5. New parameters pass at least one rolling OOS check (`profitable_pct` from `walk_forward`, `oos_is_ratio` from `walk_forward_analysis`) — not just the full-sample Sharpe.

---

## 11. Further Reading

- [Tutorial 03: Strategy Optimization & Improvement](03-optimization.md) — manual analysis and improvement
- [Tutorial 08: All-Weather Alpha Combined Strategy](08-combined-strategy.md) — multi-module combined example
- [Tutorial 11: Machine Learning Stock Selection](11-ml-selection.md) — MLSelector and feature pipelines
- [Run a Backtest](../how-to/run-backtest.md) · [Read Reports](../how-to/read-reports.md)
- [Scientific & Walk-Forward Validation API](../reference/api-scientific.md) · [ML API Reference](../reference/api-ml.md)
- [API Reference — Lifecycle & Attribution](../reference/api-analysis.md)
