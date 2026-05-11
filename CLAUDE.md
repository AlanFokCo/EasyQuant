# CLAUDE.md — EasyQuant AI Agent Configuration

This file is the primary configuration for Claude Code (and other AI coding agents) working with the **EasyQuant** repository. It describes how the agent should orient itself, run backtests, and execute the AI-driven self-optimization loop for quantitative strategies — **with Claude Code as the orchestrator, not a standalone Python script**.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Layout](#2-repository-layout)
3. [Setup and Commands](#3-setup-and-commands)
4. [Strategy Format and Parameterization](#4-strategy-format-and-parameterization)
5. [AI-Driven Self-Optimization Loop](#5-ai-driven-self-optimization-loop)
6. [Metrics and Acceptance Criteria](#6-metrics-and-acceptance-criteria)
7. [Parameter Adjustment Rules](#7-parameter-adjustment-rules)
8. [Audit Log Requirements](#8-audit-log-requirements)
9. [Code Review Process](#9-code-review-process)
10. [Agent Workflow: Roles and Responsibilities](#10-agent-workflow-roles-and-responsibilities)

---

## 1. Project Overview

EasyQuant is an event-driven quantitative backtesting framework for the **China A-share market**.
Core library: `eqlib` (Python package under `eqlib/`).
Data source: `akshare` (free China stock market data).

**AI Agent role**: Claude Code is the primary orchestrator of strategy optimization. It reads strategy files, runs backtests via `eqlib` APIs, analyzes results, diagnoses issues, proposes and applies parameter changes, writes audit logs, and spawns specialized sub-agents for code review. The `agent/optimizer.py` file exists only as a **reference utility** — it demonstrates a rule-based parameter search but is **not** the driver of the optimization workflow. All intelligent decisions, analysis, and code modifications are performed directly by Claude Code.

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
│   ├── stock_query.py             ← Fluent query API (query, valuation, get_fundamentals)
│   └── ...
├── agent/                         ← AI agent support utilities
│   ├── optimizer.py               ← Reference utility (rule-based param search, NOT the driver)
│   ├── audit_log.py               ← Audit logging (JSONL + Markdown) — agent uses this directly
│   └── strategy_template.py       ← Parameterized strategy template
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

### Run the AI-driven self-optimization loop

There is **no command to run** — the user tells Claude Code to optimize a strategy, and Claude Code performs the entire workflow interactively:

```
优化 my_strategy.py，要求夏普比率 > 1.0，最大回撤 < 20%，在 2022-2024 三个年度分别验证。
```

Claude Code then:
1. Reads `CLAUDE.md` and the strategy file
2. Runs baseline backtests using `eqlib` APIs (via Bash: `python -c "..."` or a small helper script)
3. Analyzes results, diagnoses issues, proposes parameter changes
4. Edits the strategy file directly to apply changes
5. Spawns a code-review sub-agent to verify changes
6. Writes structured audit log entries
7. Repeats until requirements are met or max iterations reached

### Reference utility (optional)

The `agent/optimizer.py` script can still be used as a standalone rule-based optimizer for comparison:

```bash
python agent/optimizer.py \
    --strategy path/to/my_strategy.py \
    --min-sharpe 1.0 \
    --max-drawdown 0.20 \
    --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

But this is **not** the primary workflow. It exists for reference and benchmarking against the AI-driven approach.

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

During optimization, Claude Code modifies the `PARAMS` dict **directly in the strategy source file** using the Edit tool between iterations, then re-runs the backtest. Unlike a standalone script that mutates `PARAMS` in memory, Claude Code's approach writes each parameter change to disk, making the full history visible in `git diff`.

---

## 5. AI-Driven Self-Optimization Loop

The autonomous optimization loop is orchestrated by **Claude Code itself**. Follow **all** steps in order.

### Step 0: Understand User Requirements

Read user-provided requirements from conversation or default to:

| Metric            | Default target   |
|-------------------|-----------------|
| Sharpe ratio      | ≥ 1.0           |
| Max drawdown      | ≤ 20 %          |
| Annual return     | ≥ 0 % (beat cash)|
| Win rate (trade)  | ≥ 40 %          |
| Periods tested    | at least 2 separate years |

### Step 1: Baseline Backtest

1. Read the strategy file and verify it has `PARAMS` and `PARAM_RANGES`.
2. Write a small Python helper script (or use `python -c`) that imports the strategy module, calls `run_backtest` and `analyze_returns` for each time period, and prints the results as JSON.
3. Run the helper script via Bash. Capture the output.
4. Log the baseline results to the audit log (`iteration=0, type=baseline`).

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
3. **Direction** must be justified by the diagnostic data.
4. **Constraints**: `fast_period` must always be < `slow_period`; `rsi_oversold` must always be < `rsi_overbought`.

For each proposed change, write an `adjustment` entry to the audit log containing:
- `parameter`: name of the parameter being changed
- `old_value`: current value
- `new_value`: proposed value
- `data_evidence`: the specific metric value(s) that motivated this change
- `expected_effect`: what improvement is expected

### Step 5: Apply Changes and Code Review

1. Use the **Edit tool** to update the `PARAMS` block in the strategy source file with the new values.
2. **Spawn a code-review sub-agent** to verify:
   - New parameter values are within `PARAM_RANGES`
   - Cross-parameter constraints are satisfied
   - The strategy code actually reads each changed parameter from `PARAMS` (not hardcoded)
3. If the code review fails, fix the issues before proceeding.
4. Log the code review result as a `code_review` entry to the audit log.

### Step 6 (Done): Record Final Result

When all requirements are met (or max iterations is reached):
1. Write a `final` entry to the audit log with:
   - The best `PARAMS` found
   - Metrics for each tested period
   - Whether requirements were met or max iterations was the stopping reason
   - A human-readable recommendation summary
2. Print a summary to the user.

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
        → increase vol_confirm_mul by 1 step (require more volume confirmation)
        → or increase slow_period by 1 step (use longer trend filter)
    elif annual_return >= 0.05:
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

Every optimization session writes structured logs to `audit_log/` (created automatically). Use `agent/audit_log.py` directly:

```python
from agent.audit_log import AuditLog
log = AuditLog(output_dir="audit_log")
```

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
  "diagnosis": "Sharpe 0.85 < 1.0; max_drawdown -23% exceeds -20% limit.",
  "changes": [
    {
      "parameter": "stop_loss_pct",
      "old_value": 0.10,
      "new_value": 0.09,
      "data_evidence": "max_drawdown=-0.23 in 2022 period; tightening stop should reduce tail losses",
      "expected_effect": "Reduce max drawdown by 2-3%; may slightly reduce win rate"
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
    { "check": "params_used_in_code", "passed": true, "verified_params": ["stop_loss_pct"] }
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
  "recommendation": "Strategy meets all targets. ..."
}
```

---

## 9. Code Review Process

After every parameter change, the code review is performed by a **spawned code-review sub-agent** (via Claude Code's `Agent` tool with `subagent_type` configured for code review). The sub-agent verifies these checks **in order**:

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
    assert 0 < PARAMS['stop_loss_pct'] < 0.30
```

### Check 3: Parameter used in strategy code

Scan the strategy source for references to `PARAMS['<key>']` or `PARAMS["<key>"]`.
If a changed parameter is not referenced, flag it and either:
- Fix the strategy code to use `PARAMS[key]` instead of a hardcoded value, **or**
- Remove that parameter from the search if the strategy doesn't support it

### Check 4: No look-ahead bias introduced

Verify the strategy does not reference `context.current_dt` for future dates and does not access data beyond the bar being processed.

---

## 10. Agent Workflow: Roles and Responsibilities

### Claude Code (Primary Orchestrator)

Claude Code drives the entire optimization workflow:

1. **Reads** strategy files and `CLAUDE.md` for context
2. **Runs** backtests using `eqlib` APIs via Bash (small Python helper scripts)
3. **Analyzes** backtest results — computes metrics, compares against requirements
4. **Diagnoses** root causes of failures using the decision table in §7
5. **Proposes** parameter adjustments with data-driven rationale
6. **Edits** strategy files directly via the Edit tool to apply changes
7. **Spawns** code-review sub-agents to verify changes before proceeding
8. **Writes** structured audit log entries via `agent/audit_log.py`
9. **Reports** progress and final results to the user

### Code Review Sub-Agent

Claude Code spawns a specialized sub-agent after each parameter change to:

1. Verify parameter values are within `PARAM_RANGES`
2. Verify cross-parameter constraints
3. Verify each changed parameter is actually used in the strategy code
4. Check for look-ahead bias
5. Return a structured pass/fail report

Claude Code uses the Agent tool to spawn this sub-agent:

```python
# Conceptual — Claude Code does this when performing code review
Agent({
    "description": "Code review for parameter change",
    "subagent_type": "code-reviewer",
    "prompt": "Review the parameter changes in <strategy_file>. Check: (1) values within PARAM_RANGES, (2) cross-param constraints (fast < slow, oversold < overbought), (3) each changed param is referenced as PARAMS[key] in source, (4) no look-ahead bias. Report pass/fail per check with details."
})
```

### agent/optimizer.py (Reference Utility)

The `agent/optimizer.py` file is a **standalone rule-based optimizer** that demonstrates a programmatic parameter search approach. It is **not** the primary optimization driver. Its role:

- **Reference**: Shows how a rule-based parameter search can be implemented
- **Benchmark**: Can be run to compare against AI-driven optimization results
- **Utility**: Provides `AuditLog` usage patterns and metric aggregation logic

Claude Code should **not** delegate the optimization loop to this script. Instead, Claude Code performs all steps directly, using `agent/audit_log.py` for logging and `eqlib` APIs for backtesting.

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
8. **Edit strategy files directly** — use the Edit tool to modify `PARAMS` in the source file, not in-memory mutation. This makes changes visible in `git diff`.
9. **Spawn sub-agents for code review** — don't self-review parameter changes. Use a specialized sub-agent to verify changes before proceeding to the next iteration.
