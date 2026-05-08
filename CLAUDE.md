# CLAUDE.md — EasyQuant AI Agent Configuration

This file is the primary configuration for Claude Code (and other AI coding agents) working with the **EasyQuant** repository. It describes how the agent should orient itself, run backtests, and execute the autonomous self-optimization loop for quantitative strategies.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Layout](#2-repository-layout)
3. [Setup and Commands](#3-setup-and-commands)
4. [Strategy Format and Parameterization](#4-strategy-format-and-parameterization)
5. [Self-Optimization Loop — Step-by-Step](#5-self-optimization-loop--step-by-step)
6. [Metrics and Acceptance Criteria](#6-metrics-and-acceptance-criteria)
7. [Parameter Adjustment Rules](#7-parameter-adjustment-rules)
8. [Audit Log Requirements](#8-audit-log-requirements)
9. [Code Review Process](#9-code-review-process)
10. [Running the Automated Optimizer](#10-running-the-automated-optimizer)

---

## 1. Project Overview

EasyQuant is an event-driven quantitative backtesting framework for the **China A-share market**.
Core library: `eqlib` (Python package under `eqlib/`).
Data source: `akshare` (free China stock market data).

Key capabilities available to the agent:
- `run_backtest(initialize, start_date, end_date, ...)` — execute a strategy backtest
- `analyze_returns(result, risk_free_rate=0.03)` — compute Sharpe, max drawdown, alpha, beta, win rate, etc.
- `brinson_attribution(result)` — allocation/selection/interaction effects
- `fama_french_analysis(result)` — factor exposure (market beta, SMB, HML, alpha)
- `run_strategy(initialize_func, ...)` — high-level runner that also generates reports

---

## 2. Repository Layout

```
EasyQuant/
├── CLAUDE.md                      ← This file (AI agent configuration)
├── eqlib/                         ← Core library (do not modify during optimization)
│   ├── engine.py                  ← Backtest engine
│   ├── attribution.py             ← analyze_returns, brinson_attribution, etc.
│   └── ...
├── agent/                         ← AI agent tools
│   ├── optimizer.py               ← Autonomous optimization orchestrator
│   ├── audit_log.py               ← Audit logging (JSONL + Markdown)
│   └── strategy_template.py      ← Parameterized strategy template
├── audit_log/                     ← Generated audit logs (created on first run)
├── examples/                      ← Reference strategy examples
├── tutorials/                     ← Learning tutorials
│   └── 10_agent_optimization.md  ← AI agent optimization tutorial
├── tests/                         ← Test suite
└── doc/                           ← API and user documentation
```

---

## 3. Setup and Commands

### Install

```bash
pip install akshare pandas numpy matplotlib scipy
pip install pyarrow   # optional, faster disk cache
pip install -e .      # install eqlib from source
```

### Run tests

```bash
python -m pytest tests/
```

### Run a single backtest (quick smoke test)

```bash
python examples/03_run_backtest.py
```

### Run the self-optimization loop

```bash
# Optimize the bundled template strategy with default requirements
python agent/optimizer.py

# Optimize a custom strategy file with explicit requirements
python agent/optimizer.py \
    --strategy path/to/my_strategy.py \
    --min-sharpe 1.0 \
    --max-drawdown 0.20 \
    --min-annual-return 0.10 \
    --max-iterations 15 \
    --periods "2021-01-01:2022-12-31" "2022-01-01:2023-12-31" "2023-01-01:2024-12-31"
```

---

## 4. Strategy Format and Parameterization

For a strategy to participate in AI optimization, it **must** define two module-level dicts:

### `PARAMS` — current parameter values

```python
PARAMS = {
    'fast_period':      5,     # fast MA period
    'slow_period':      20,    # slow MA period
    'stop_loss_pct':    0.08,  # hard stop-loss (fraction, e.g. 0.08 = −8%)
    'position_pct':     1.0,   # fraction of available cash to deploy per trade
    'rsi_period':       14,    # RSI lookback
    'rsi_oversold':     30,    # RSI oversold threshold (buy signal)
    'rsi_overbought':   70,    # RSI overbought threshold (sell signal)
    'vol_confirm_mul':  1.5,   # volume confirmation multiplier
}
```

### `PARAM_RANGES` — valid search space `(min, max, step)`

```python
PARAM_RANGES = {
    'fast_period':      (2,   20,  1),
    'slow_period':      (10,  60,  5),
    'stop_loss_pct':    (0.03, 0.15, 0.01),
    'position_pct':     (0.3,  1.0, 0.1),
    'rsi_period':       (7,   28,  1),
    'rsi_oversold':     (20,  40,  5),
    'rsi_overbought':   (60,  80,  5),
    'vol_confirm_mul':  (1.0, 3.0, 0.25),
}
```

### `initialize` and `market_open` must read from `PARAMS`

```python
def initialize(context):
    g.fast_period   = PARAMS['fast_period']
    g.slow_period   = PARAMS['slow_period']
    g.stop_loss_pct = PARAMS['stop_loss_pct']
    # ...
```

The optimizer modifies `PARAMS` between iterations (mutating the dict in-place) and then re-runs the backtest. The strategy code itself is **not** modified on disk; only `PARAMS` values change in memory during the optimization run. When the final best parameters are found, the optimizer writes the optimized `PARAMS` block to the audit log and optionally patches the strategy file.

---

## 5. Self-Optimization Loop — Step-by-Step

The autonomous optimization loop proceeds as follows. The agent must follow **all** steps in order.

### Step 0: Understand User Requirements

Before starting, read any user-provided requirement file or command-line arguments. Default requirements if none are given:

| Metric            | Default target   |
|-------------------|-----------------|
| Sharpe ratio      | ≥ 1.0           |
| Max drawdown      | ≤ 20 %          |
| Annual return     | ≥ 0 % (beat cash)|
| Win rate (trade)  | ≥ 40 %          |
| Periods tested    | at least 2 separate years |

### Step 1: Baseline Backtest

Run the strategy **as provided** (with its original `PARAMS`) across all configured time periods. Compute `analyze_returns` for each period. Log all metrics to the audit log with label `iteration=0, type=baseline`.

### Step 2: Evaluate Against Requirements

For each period and for the aggregate (average across periods), check every requirement. Record:
- Which requirements pass ✓
- Which requirements fail ✗ and by how much
- Log a structured `evaluation` entry to the audit log

If **all** requirements pass across **all** periods → proceed to Step 6 (Done).

### Step 3: Data-Driven Diagnosis

Examine the failing metrics and identify the likely cause. Use the following decision table:

| Failing metric             | Likely cause                          | Diagnostic check                          |
|---------------------------|---------------------------------------|-------------------------------------------|
| Sharpe < target            | High volatility or low returns        | Check annual_return vs annual_volatility  |
| Max drawdown > limit       | Missing/weak stop-loss                | Inspect stop_loss_pct; check trade log    |
| Annual return < target     | Bad entry/exit timing                 | Check win_rate_trade; check alpha         |
| Win rate < 40 %            | Too many noise trades                 | Check trade_count; check vol_confirm_mul  |
| Too few trades (< 5/year)  | Conditions too restrictive            | Check period thresholds                   |
| Beta > 1.5                 | Over-exposure to market moves         | Check position_pct; add index filter      |
| Alpha < 0                  | Strategy underperforms benchmark      | Check entry signals; reconsider factors   |

Record the diagnosis as a `rationale` field in the audit log adjustment entry.

### Step 4: Generate Parameter Adjustments

Based on the diagnosis, propose **one or more** parameter changes. Rules:

1. **Change at most 2 parameters per iteration** to maintain interpretability.
2. **Step size** must be exactly 1 step from `PARAM_RANGES` (never jump more than 1 step without evidence).
3. **Direction** must be justified by the diagnostic data (e.g., "max_drawdown=0.28 > 0.20 limit, tightening stop_loss_pct from 0.10 to 0.09").
4. **Constraints**: `fast_period` must always be < `slow_period`; `rsi_oversold` must always be < `rsi_overbought`.

For each proposed change, write an `adjustment` entry to the audit log containing:
- `parameter`: name of the parameter being changed
- `old_value`: current value
- `new_value`: proposed value
- `data_evidence`: the specific metric value(s) that motivated this change
- `expected_effect`: what improvement is expected

### Step 5: Code Review

Before applying the adjustment:
1. Verify the new parameter values are within their allowed ranges from `PARAM_RANGES`.
2. Verify cross-parameter constraints are satisfied (fast < slow, oversold < overbought, etc.).
3. Verify the strategy code actually uses `PARAMS[key]` for each changed parameter (not a hardcoded value).
4. Log the code review result as a `code_review` entry: `passed=True/False`, and if `False`, describe what was corrected.

If the code review fails (e.g., parameter not actually used), correct the strategy code before proceeding, and log what was changed.

### Step 6 (Done): Record Final Result

When all requirements are met (or max iterations is reached):
1. Write a `final` entry to the audit log with:
   - The best `PARAMS` found
   - Metrics for each tested period
   - Whether requirements were met or max iterations was the stopping reason
   - A human-readable recommendation summary
2. Print a summary to stdout.
3. If `--output-strategy` was specified, write the optimized strategy file with the final `PARAMS` block.

---

## 6. Metrics and Acceptance Criteria

All metrics come from `analyze_returns(result, risk_free_rate=0.03)`:

| Key                   | Description                                   | Good range          |
|-----------------------|-----------------------------------------------|---------------------|
| `sharpe_ratio`        | Risk-adjusted return (annualized)             | > 1.0               |
| `sortino_ratio`       | Downside-adjusted return                      | > 1.0               |
| `max_drawdown`        | Worst peak-to-trough loss (negative fraction) | > −0.20 (i.e., < 20%)|
| `annual_return`       | Annualized compound return                    | > 0.08 (8%)         |
| `calmar_ratio`        | Annual return / max drawdown                  | > 0.5               |
| `alpha`               | Excess return vs benchmark (annualized)       | > 0                 |
| `beta`                | Market exposure                               | 0.3 – 1.3 preferred |
| `win_rate_trade`      | Round-trip trade win rate                     | > 0.40              |
| `trade_count`         | Number of completed round-trip trades         | ≥ 3 per year        |
| `total_commission`    | Total commissions paid                        | monitor only        |
| `information_ratio`   | Active return / tracking error                | > 0.3               |

### Aggregation across periods

For multi-period runs, compute:
- `avg_sharpe` = mean of `sharpe_ratio` across all periods
- `worst_drawdown` = min of `max_drawdown` across all periods (most negative)
- `avg_annual_return` = mean of `annual_return` across all periods
- `consistency_score` = fraction of periods where `annual_return > 0`

Requirements are checked against **both** per-period and aggregate values.

---

## 7. Parameter Adjustment Rules

### When Sharpe is too low

```
if sharpe_ratio < target_sharpe:
    if annual_return < 0.05 and annual_volatility > 0.20:
        # Both low return and high vol: improve signal quality
        → increase vol_confirm_mul by 1 step (require more volume confirmation)
        → or increase slow_period by 1 step (use longer trend filter)
    elif annual_return >= 0.05:
        # Decent return but high volatility
        → decrease position_pct by 1 step (reduce per-trade exposure)
```

### When max drawdown is too large

```
if abs(max_drawdown) > max_drawdown_limit:
    → decrease stop_loss_pct by 1 step (tighter stop loss)
    → or decrease position_pct by 1 step (smaller positions)
```

### When win rate is too low

```
if win_rate_trade < 0.40:
    → increase vol_confirm_mul by 1 step (require stronger volume confirmation)
    → or adjust rsi_oversold upward by 1 step (enter on less oversold conditions)
```

### When there are too few trades

```
if trade_count / years < 3:
    → decrease vol_confirm_mul by 1 step (relax volume requirement)
    → or widen rsi bands (decrease rsi_oversold, increase rsi_overbought)
```

### When alpha is negative

```
if alpha < 0:
    → review entry signals: consider combining fast_period × slow_period crossover
      with RSI confirmation
    → or increase fast_period by 1 step (slower signals, less noise)
```

---

## 8. Audit Log Requirements

Every optimization session writes structured logs to `audit_log/` (created automatically).

### File naming

```
audit_log/
├── session_<YYYYMMDD_HHMMSS>.jsonl   ← machine-readable JSONL (one entry per line)
└── session_<YYYYMMDD_HHMMSS>.md      ← human-readable Markdown summary
```

### JSONL entry types

Each line in the `.jsonl` file is a JSON object with a `type` field:

```jsonc
// Iteration result
{
  "type": "iteration",
  "session_id": "20240115_143022",
  "iteration": 0,
  "timestamp": "2024-01-15T14:30:22",
  "params": { "fast_period": 5, "slow_period": 20, ... },
  "periods": [
    {
      "start": "2022-01-01", "end": "2022-12-31",
      "sharpe_ratio": 0.85, "max_drawdown": -0.23, "annual_return": 0.07,
      "win_rate_trade": 0.38, "trade_count": 8, "alpha": 0.01, "beta": 1.1
    },
    ...
  ],
  "aggregate": {
    "avg_sharpe": 0.85, "worst_drawdown": -0.23,
    "avg_annual_return": 0.07, "consistency_score": 0.67
  },
  "requirements_met": false,
  "failing": ["sharpe_ratio < 1.0", "max_drawdown < -0.20"]
}

// Adjustment decision
{
  "type": "adjustment",
  "session_id": "20240115_143022",
  "iteration": 0,
  "timestamp": "2024-01-15T14:32:01",
  "diagnosis": "Sharpe 0.85 < 1.0; max_drawdown -23% exceeds -20% limit. High vol causing both issues.",
  "changes": [
    {
      "parameter": "stop_loss_pct",
      "old_value": 0.10,
      "new_value": 0.09,
      "data_evidence": "max_drawdown=-0.23 in 2022 period; tightening stop should reduce tail losses",
      "expected_effect": "Reduce max drawdown by 2-3%; may slightly reduce win rate"
    },
    {
      "parameter": "vol_confirm_mul",
      "old_value": 1.5,
      "new_value": 1.75,
      "data_evidence": "win_rate_trade=0.38 < 0.40; many low-volume false signals observed",
      "expected_effect": "Improve signal quality; expect fewer but higher-quality trades"
    }
  ]
}

// Code review
{
  "type": "code_review",
  "session_id": "20240115_143022",
  "iteration": 0,
  "timestamp": "2024-01-15T14:32:02",
  "checks": [
    { "check": "values_in_range", "passed": true },
    { "check": "cross_param_constraints", "passed": true },
    { "check": "params_used_in_code", "passed": true, "verified_params": ["stop_loss_pct", "vol_confirm_mul"] }
  ],
  "overall_passed": true,
  "corrections": []
}

// Final result
{
  "type": "final",
  "session_id": "20240115_143022",
  "timestamp": "2024-01-15T14:45:00",
  "total_iterations": 7,
  "stopping_reason": "requirements_met",
  "final_params": { "fast_period": 5, "slow_period": 25, ... },
  "final_metrics": { ... },
  "requirements_met": true,
  "recommendation": "Strategy meets all targets. Best performance in 2023 (Sharpe 1.42). Weakest in 2022 bear market (Sharpe 0.95). Consider reducing position_pct in high-VIX environments."
}
```

---

## 9. Code Review Process

After every parameter change, perform these checks **in order**. Log each check result.

### Check 1: Values in range

For each changed parameter `p`:
```python
lo, hi, step = PARAM_RANGES[p]
assert lo <= new_value <= hi
```

### Check 2: Cross-parameter constraints

```python
assert PARAMS['fast_period'] < PARAMS['slow_period']
if 'rsi_oversold' in PARAMS and 'rsi_overbought' in PARAMS:
    assert PARAMS['rsi_oversold'] < PARAMS['rsi_overbought']
if 'stop_loss_pct' in PARAMS:
    assert 0 < PARAMS['stop_loss_pct'] < 0.30  # sanity: not > 30% stop
```

### Check 3: Parameter used in strategy code

Scan the strategy source for references to `PARAMS['<key>']` or `PARAMS["<key>"]`.
If a changed parameter is not referenced, flag it and either:
- Fix the strategy code to use `PARAMS[key]` instead of a hardcoded value, **or**
- Remove that parameter from the search if the strategy doesn't support it

### Check 4: No look-ahead bias introduced

Verify the strategy does not reference `context.current_dt` for future dates and does not access data beyond the bar being processed.

---

## 10. Running the Automated Optimizer

### Minimal invocation (use template strategy)

```bash
python agent/optimizer.py
```

### Full invocation with custom strategy

```bash
python agent/optimizer.py \
    --strategy examples/03_run_backtest.py \
    --min-sharpe 1.2 \
    --max-drawdown 0.15 \
    --min-annual-return 0.12 \
    --min-win-rate 0.45 \
    --max-iterations 20 \
    --periods "2021-01-01:2022-12-31" "2022-01-01:2023-12-31" "2023-01-01:2024-12-31" \
    --output-strategy optimized_strategy.py \
    --audit-dir audit_log
```

### Reading the audit log after a run

```bash
# View the Markdown summary (human-readable)
cat audit_log/session_<timestamp>.md

# Query a specific iteration (jq required)
jq 'select(.type=="iteration" and .iteration==3)' audit_log/session_<timestamp>.jsonl

# Show all adjustment rationales
jq 'select(.type=="adjustment") | {iter: .iteration, diagnosis: .diagnosis, changes: .changes}' \
    audit_log/session_<timestamp>.jsonl
```

---

## Agent Behaviour Guidelines

When operating autonomously in this repository, the agent must:

1. **Never skip the audit log** — every iteration must produce a complete audit entry before proceeding.
2. **Never change more than 2 parameters per iteration** — maintain interpretability.
3. **Never modify `eqlib/`** — the core library is not part of strategy optimization.
4. **Always run the test suite** (`python -m pytest tests/`) after modifying any `.py` file in `eqlib/` (should not happen during optimization).
5. **Stop and report** if data download fails — do not proceed with incomplete data.
6. **Prefer robustness over peak performance** — a strategy with consistent Sharpe 1.1 across 3 years is better than one with Sharpe 2.5 in one year and −0.3 in another.
7. **Document every decision** — the audit log is the primary artifact; a human must be able to trace every parameter change back to specific data evidence.
