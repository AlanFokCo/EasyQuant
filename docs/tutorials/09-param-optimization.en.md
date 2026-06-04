# Tutorial 09: Strategy Parameter Optimization and Auditing

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Manage tunable parameters with `PARAMS` / `PARAM_RANGES`, and use `optimizer.py` and `audit_log.py` for reproducible parameter tuning |
    | **Estimated time** | ~40 minutes |
    | **Prerequisites** | [Tutorial 00](00-getting-started.md); for metric definitions see [Report Format Reference](../reference/reports-format.md) |

> This chapter explains how to parameterize strategies using **PARAMS / PARAM_RANGES**, combined with the in-repo `agent/optimizer.py` (rule-based search reference), `agent/audit_log.py` (audit logging), and `eqlib` APIs to build a **reproducible** parameter tuning and recording workflow. You can also write your own Python scripts or orchestrate the same steps in any IDE; EasyQuant is **not tied to** any specific editor or commercial AI product.

---

## Table of Contents

1. [Why Parameterization and Auditing](#1-why-parameterization-and-auditing)
2. [Core Conventions](#2-core-conventions)
3. [Command Line: optimizer.py](#3-command-line-optimizerpy)
4. [Building Your Own Optimization Loop (Recommended Approach)](#4-building-your-own-optimization-loop-recommended-approach)
5. [Audit Logs](#5-audit-logs)
6. [Code Review Checklist (Recommended)](#6-code-review-checklist-recommended)
7. [Further Reading](#7-further-reading)

---

## 1. Why Parameterization and Auditing

| Pain Point | How Parameterization + Auditing Helps |
|-----------|--------------------------------------|
| Tuning by gut feel | `PARAM_RANGES` defines clear search boundaries; results are comparable |
| Decisions not traceable | `audit_log/` records metrics and change rationale for every iteration |
| Rule-based scripts too rigid | Run `optimizer.py` for a baseline first, then write custom diagnostic logic as needed |
| Overfitting | Multi-period backtesting + recording per-period metrics for stability review |

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

- Multi-metric thresholds for Sharpe ratio, max drawdown, annualized return, win rate, etc.
- Must cover at least **2 calendar years** or equivalent trading day span
- Multi-period metrics can be written to the audit log for manual review

Set specific thresholds according to your strategy's risk profile.

---

## 3. Command Line: optimizer.py

From the repository root (after `pip install -e .`), you can run the reference optimizer:

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

It demonstrates **programmatic** search. For more complex diagnostics (e.g., structural strategy changes), call `run_backtest`, `analyze_returns`, and other APIs directly in scripts or notebooks for custom extensions.

---

## 4. Building Your Own Optimization Loop (Recommended Approach)

```
Baseline backtest (run_backtest / run_strategy)
    ↓
analyze_returns(result) and other metrics
    ↓
If not meeting criteria: adjust PARAMS based on rules or manual judgment (keep consistent with PARAM_RANGES)
    ↓
(Optional) Static checks: are parameters referenced in code, is look-ahead bias introduced, etc.
    ↓
Re-backtest → Write summary to audit_log (if using audit_log.py)
    ↓
Stop condition met or max iterations reached
```

The implementation approach is entirely up to you: Shell + Python, Makefile, CI tasks — all are valid.

---

## 5. Audit Logs

When using `agent/audit_log.py`, each session generates files in `audit_log/`:

```
audit_log/
├── session_<timestamp>.jsonl   # Machine-readable
└── session_<timestamp>.md      # Markdown summary
```

`jq` examples:

```bash
jq 'select(.type=="adjustment")' audit_log/session_*.jsonl
jq 'select(.type=="final")' audit_log/session_*.jsonl
```

---

## 6. Code Review Checklist (Recommended)

After each modification to `PARAMS` or strategy logic, verify at minimum:

1. New values fall within `PARAM_RANGES` and satisfy cross-parameter constraints (e.g., `fast_period < slow_period`).
2. The tuned parameters are read via `PARAMS["..."]` in the strategy, not hardcoded.
3. No future data is used; no accidental use of today's closing price in signals (avoid look-ahead bias).
4. Backtest period is consistent with the data source; abnormal trading (suspensions, etc.) is handled.

---

## 7. Further Reading

- [Tutorial 03: Strategy Optimization & Improvement](03-optimization.md) — Manual analysis and improvement ideas
- [Tutorial 08: All-Weather Alpha Combined Strategy](08-combined-strategy.md) — Multi-module combination example
- [Running Backtests](../how-to/run-backtest.md) · [Reading Reports](../how-to/read-reports.md)
- [API Reference — Lifecycle & Attribution](../reference/api-analysis.md)
