!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §12](12_paper_trading.md) · [下一章 §14](14_faq.md)

---

## 13. 参数优化、审计与参考脚本

若要对策略做**可复现**的参数搜索与记录，推荐采用以下仓库内约定与工具（均不绑定特定 IDE 或商业 AI）：

| 组件 | 说明 |
|------|------|
| `PARAMS` / `PARAM_RANGES` | 模块级字典：`PARAMS` 为当前参数，`PARAM_RANGES` 为搜索边界；`initialize` 必须从 `PARAMS` 读取 |
| [`agent/strategy_template.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/strategy_template.py) | 参数化策略模板 |
| [`agent/optimizer.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/optimizer.py) | 规则基参数搜索，可在命令行独立运行，作基线对比 |
| [`agent/audit_log.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/audit_log.py) | 将迭代摘要写入 `audit_log/`（JSONL + Markdown） |

### 13.1 推荐工作流

```
基线回测（run_backtest / run_strategy）
    ↓
analyze_returns(result) 等指标
    ↓
若不达标：在 PARAM_RANGES 内调整 PARAMS（或扩展策略逻辑）
    ↓
（可选）人工核对：参数是否在代码中通过 PARAMS 读取、是否引入前视等
    ↓
再回测；需要可追溯时调用 audit_log 写入会话记录
```

### 13.2 运行 optimizer.py（示例）

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

### 13.3 参数化策略要求

策略须定义 `PARAMS` 与 `PARAM_RANGES`，并在 `initialize` 中从 `PARAMS` 赋值给 `g.*` 等，例如：

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
```

```python
def initialize(context):
    g.fast_period    = PARAMS['fast_period']
    g.slow_period    = PARAMS['slow_period']
    g.stop_loss_pct  = PARAMS['stop_loss_pct']
    g.position_pct   = PARAMS['position_pct']
    g.vol_confirm_mul = PARAMS['vol_confirm_mul']
```

完整说明见 **[Tutorial 10：策略参数优化与审计](../../tutorials/10_agent_optimization.md)**。

### 13.4 审计日志目录

使用 `audit_log.py` 时，会话产物示例：

```
audit_log/
├── session_<时间戳>.jsonl
└── session_<时间戳>.md
```

可用 `jq` 过滤 `adjustment`、`final` 等类型行做批量分析。
