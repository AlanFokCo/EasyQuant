# 参数优化与审计

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 参数化策略、运行优化、保留审计记录 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 参数优化与审计

### 1. 参数化策略

策略须定义 `PARAMS` 与 `PARAM_RANGES`：

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

### 2. 运行 optimizer.py

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

### 3. 审计日志

使用 `audit_log.py` 时，会话产物示例：

```
audit_log/
├── session_<时间戳>.jsonl
└── session_<时间戳>.md
```

详细说明见 [Tutorial 09：策略参数优化与审计](../tutorials/09-param-optimization.md)。

---

