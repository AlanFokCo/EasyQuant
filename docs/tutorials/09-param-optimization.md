# Tutorial 09: 策略参数优化与审计

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 用 `PARAMS` / `PARAM_RANGES` 管理可调参数，结合 `optimizer.py` 与 `audit_log.py` 做可复现调参 |
    | **预计用时** | 约 40 分钟 |
    | **前置** | [Tutorial 00](00-getting-started.md)；指标含义见 [报告格式详解](../reference/reports-format.md) |

> 本章说明如何用 **PARAMS / PARAM_RANGES** 参数化策略，结合仓库内 `agent/optimizer.py`（规则搜索参考）、`agent/audit_log.py`（审计日志）与 `eqlib` API，搭建**可复现**的调参与记录流程。你也可以自行编写 Python 脚本或在常用 IDE 里编排相同步骤；EasyQuant **不绑定**任何特定编辑器或商业 AI 产品。

---

## 目录

1. [为什么需要参数化与审计](#1-为什么需要参数化与审计)
2. [核心约定](#2-核心约定)
3. [命令行：optimizer.py](#3-命令行optimizerpy)
4. [自建优化循环（推荐思路）](#4-自建优化循环推荐思路)
5. [审计日志](#5-审计日志)
6. [代码审查清单（建议）](#6-代码审查清单建议)
7. [延伸阅读](#7-延伸阅读)

---

## 1. 为什么需要参数化与审计

| 痛点 | 参数化 + 审计能带来的帮助 |
|------|---------------------------|
| 调参凭感觉 | `PARAM_RANGES` 明确搜索边界，结果可对比 |
| 决策不可追溯 | `audit_log/` 记录每次迭代的指标与变更依据 |
| 规则脚本太死板 | 先跑 `optimizer.py` 做基线，再按需手写诊断逻辑 |
| 过拟合 | 多时段回测 + 记录各段指标，便于检查稳定性 |

---

## 2. 核心约定

### 2.1 仓库内相关文件

| 路径 | 作用 |
|------|------|
| [`agent/strategy_template.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/strategy_template.py) | 可复制的参数化策略骨架 |
| [`agent/optimizer.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/optimizer.py) | 规则基参数搜索（**参考实现**，可独立运行） |
| [`agent/audit_log.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/audit_log.py) | 写入 JSONL + Markdown 审计条目 |

### 2.2 `PARAMS` 与 `PARAM_RANGES`

策略中应使用**模块级**两个字典：当前值与搜索空间；`initialize` 必须从 `PARAMS` 读取，禁止魔法数硬编码。

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

### 2.3 常用接受条件（示例）

- 夏普、最大回撤、年化收益、胜率等多指标门槛  
- 至少覆盖 **2 个自然年** 或等价交易日跨度  
- 多时段的指标可写入审计，便于人工复核  

具体阈值请按策略风险自行设定。

---

## 3. 命令行：optimizer.py

在仓库根目录（已 `pip install -e .`）可运行参考优化器，例如：

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

它演示**程序化**搜索；若需更复杂的诊断（例如结构性改策略），请在脚本或 Notebook 中直接调用 `run_backtest`、`analyze_returns` 等 API 自行扩展。

---

## 4. 自建优化循环（推荐思路）

```
基线回测（run_backtest / run_strategy）
    ↓
analyze_returns(result) 等指标
    ↓
若不达标：根据规则或人工判断调整 PARAMS（保持与 PARAM_RANGES 一致）
    ↓
（可选）静态检查：参数是否被代码引用、是否引入前视等
    ↓
再回测 → 将摘要写入 audit_log（若使用 audit_log.py）
    ↓
达到停止条件或最大迭代次数
```

实现方式完全由你决定：Shell + Python、Makefile、CI 任务均可。

---

## 5. 审计日志

若使用 `agent/audit_log.py`，每次会话可在 `audit_log/` 生成：

```
audit_log/
├── session_<时间戳>.jsonl   # 机器可读
└── session_<时间戳>.md      # Markdown 摘要
```

`jq` 示例：

```bash
jq 'select(.type=="adjustment")' audit_log/session_*.jsonl
jq 'select(.type=="final")' audit_log/session_*.jsonl
```

---

## 6. 代码审查清单（建议）

每次修改 `PARAMS` 或策略逻辑后，建议至少核对：

1. 新值落在 `PARAM_RANGES` 内，且满足交叉约束（如 `fast_period < slow_period`）。  
2. 被调参数在策略中通过 `PARAMS["…"]` 读取，而非硬编码。  
3. 未使用未来数据、未在信号中误用当日收盘价等（避免前视）。  
4. 回测区间与数据源一致，异常交易（停牌等）有处理。  

---

## 7. 延伸阅读

- [Tutorial 03: 策略优化与改进](03-optimization.md) — 手动分析与改进思路
- [Tutorial 08: 全天候 Alpha 综合策略](08-combined-strategy.md) — 多模块组合示例
- [运行回测](../how-to/run-backtest.md) · [阅读报告](../how-to/read-reports.md)
- [API 参考 — 生命周期与归因](../reference/api-analysis.md)
