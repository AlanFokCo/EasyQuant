# Parameter Optimization & Auditing

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Parameterize a strategy, run optimization, and keep audit records |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Parameter Optimization & Auditing

### 1. Parameterized Strategy

The strategy must define `PARAMS` and `PARAM_RANGES`:

```python
PARAMS = {
    'fast_period':      5,
    'slow_period':      20,
    'stop_loss_pct':    0.08,
    'position_pct':     1.0,
    'vol_confirm_mul':  1.5,
}

PARAM_RANGES = {
    'fast_period':      (2,   15,   1),
    'slow_period':      (10,  60,   5),
    'stop_loss_pct':    (0.03, 0.15, 0.01),
    'position_pct':     (0.3,  1.0,  0.1),
    'vol_confirm_mul':  (1.0,  3.0,  0.25),
}

def initialize(context):
    g.fast_period    = PARAMS['fast_period']
    g.slow_period    = PARAMS['slow_period']
    g.stop_loss_pct  = PARAMS['stop_loss_pct']
    g.position_pct   = PARAMS['position_pct']
    g.vol_confirm_mul = PARAMS['vol_confirm_mul']
```

### 2. Running optimizer.py

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

### 3. Audit Log

When using `audit_log.py`, the session artifacts look like:

```
audit_log/
├── session_<timestamp>.jsonl
└── session_<timestamp>.md
```

See [Tutorial 09: Strategy Parameter Optimization & Auditing](../tutorials/09-param-optimization.md) for details.

---

