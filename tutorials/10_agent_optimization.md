# Tutorial 10: AI Agent 自动化策略优化

> 使用 Claude Code（或任何兼容的 AI 编码智能体）对 EasyQuant 策略进行全自动参数优化，无需人工干预。

---

## 目录

1. [为什么需要 AI Agent 优化](#1-为什么需要-ai-agent-优化)
2. [核心概念](#2-核心概念)
3. [快速上手](#3-快速上手)
4. [策略文件要求](#4-策略文件要求)
5. [优化目标（接受条件）](#5-优化目标接受条件)
6. [自优化循环详解](#6-自优化循环详解)
7. [审计日志解读](#7-审计日志解读)
8. [代码审查机制](#8-代码审查机制)
9. [高级用法](#9-高级用法)
10. [示例：完整优化流程](#10-示例完整优化流程)
11. [下一步](#11-下一步)

---

## 1. 为什么需要 AI Agent 优化

手动参数调优的问题：

| 问题 | 影响 |
|------|------|
| 参数空间太大 | 无法穷举所有组合 |
| 缺乏客观依据 | 容易凭感觉选参数 |
| 过拟合风险 | 只在单一区间表现好 |
| 决策无法追溯 | 不知道为什么选了这组参数 |
| 耗时费力 | 每次调参都要人工介入 |

AI Agent 优化的优势：

- **全自动** — 无需人工干预，从回测到调参到再回测全流程自动
- **数据驱动** — 每次调参都有具体指标数据支撑
- **多时段验证** — 同时在多个历史区间回测，避免过拟合
- **完整审计** — 每一步决策都记录到审计日志，可追溯
- **代码审查** — 每次调参后自动检查参数合理性

---

## 2. 核心概念

### 2.1 配置文件 CLAUDE.md

项目根目录的 `CLAUDE.md` 是 AI 智能体的"操作手册"：

- 描述项目结构和 API
- 规定自优化循环的完整步骤
- 定义参数调整规则
- 说明审计日志格式
- 规定代码审查要求

Claude Code 实例在进入仓库时会自动识别并读取该文件，据此规划和执行工作。

### 2.2 策略参数化

要让 AI Agent 能够自动调参，策略文件必须将所有可调参数集中到两个模块级字典：

```python
PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    ...
}

PARAM_RANGES = {
    'fast_period': (2, 15, 1),   # (最小值, 最大值, 步长)
    'slow_period': (10, 60, 5),
    ...
}
```

### 2.3 自优化循环

```
用户需求 → 基线回测 → 评估指标 → 诊断问题 → 数据驱动调参
    ↑                                              ↓
达到目标 ← 再次评估 ← 新回测 ← 代码审查 ← 记录审计日志
```

### 2.4 审计日志

每次优化会话产生两个文件：

```
audit_log/
├── session_20240115_143022.jsonl   # 机器可读 JSONL
└── session_20240115_143022.md      # 人类可读 Markdown
```

---

## 3. 快速上手

### 3.1 使用内置模板策略

最简单的方式：直接运行优化器，它会使用内置的双均线模板策略。

```bash
# 使用默认参数运行
python agent/optimizer.py
```

这将：
1. 加载 `agent/strategy_template.py`（双均线 + 成交量确认）
2. 在默认 3 个时段（2021、2022、2023 年）运行回测
3. 目标：夏普比率 ≥ 1.0，最大回撤 ≤ 20%
4. 最多迭代 15 次
5. 将审计日志写入 `audit_log/`

### 3.2 优化自定义策略

```bash
python agent/optimizer.py \
    --strategy my_strategy.py \
    --min-sharpe 1.2 \
    --max-drawdown 0.15 \
    --min-annual-return 0.12 \
    --max-iterations 20 \
    --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31" "2024-01-01:2024-12-31" \
    --output-strategy my_strategy_optimized.py
```

### 3.3 通过 Claude Code 运行

如果你使用 Claude Code（Claude 的 AI 编码智能体），只需描述你的需求：

```
优化 my_strategy.py，要求夏普比率 > 1.2，最大回撤 < 15%，
在 2021-2024 年三个时段上均满足要求。
```

Claude Code 会：
1. 读取 `CLAUDE.md` 获取操作指南
2. 读取策略文件理解参数结构
3. 调用 `python agent/optimizer.py ...`
4. 监控优化进度
5. 读取并解释审计日志
6. 如有需要，直接修改策略逻辑（超出参数范围的情况）

---

## 4. 策略文件要求

### 4.1 必须包含的内容

```python
# ① 模块级 PARAMS 字典（当前参数值）
PARAMS = {
    'fast_period':      5,
    'slow_period':      20,
    'stop_loss_pct':    0.08,
    'position_pct':     1.0,
    'vol_confirm_mul':  1.5,
}

# ② 模块级 PARAM_RANGES 字典（搜索空间）
PARAM_RANGES = {
    'fast_period':      (2,   15,   1),    # (min, max, step)
    'slow_period':      (10,  60,   5),
    'stop_loss_pct':    (0.03, 0.15, 0.01),
    'position_pct':     (0.3,  1.0,  0.1),
    'vol_confirm_mul':  (1.0,  3.0,  0.25),
}

# ③ initialize(context) 函数，从 PARAMS 读取参数
def initialize(context):
    g.fast_period    = PARAMS['fast_period']
    g.slow_period    = PARAMS['slow_period']
    g.stop_loss_pct  = PARAMS['stop_loss_pct']
    g.position_pct   = PARAMS['position_pct']
    g.vol_confirm_mul = PARAMS['vol_confirm_mul']
    # ...
```

### 4.2 可选但推荐

```python
# 股票池（优化器会自动传给 run_backtest）
SECURITIES = ['601390', '600519', ...]
# 或
STOCK_POOL = ['601390', '600519', ...]
```

### 4.3 完整示例

参见 `agent/strategy_template.py`，这是一个完整的参数化策略模板，可以直接复制修改。

### 4.4 不要硬编码参数

❌ 错误写法（优化器无法修改这些值）：

```python
def market_open(context):
    fast_ma = close.tail(5).mean()   # 硬编码 5
    slow_ma = close.tail(20).mean()  # 硬编码 20
```

✅ 正确写法：

```python
def market_open(context):
    fast_ma = close.tail(g.fast_period).mean()   # 从 g 读取
    slow_ma = close.tail(g.slow_period).mean()   # g 在 initialize 中从 PARAMS 赋值
```

---

## 5. 优化目标（接受条件）

### 5.1 默认接受条件

| 指标 | 默认目标 | 说明 |
|------|---------|------|
| 夏普比率 | ≥ 1.0 | 风险调整后收益 |
| 最大回撤 | ≤ 20% | 最大峰谷跌幅 |
| 年化收益率 | ≥ 0% | 至少跑赢现金 |
| 交易胜率 | ≥ 40% | 完整交易对胜率 |

以上条件在**每个**测试时段均需满足。

### 5.2 自定义接受条件

命令行参数：

```bash
--min-sharpe 1.2          # 最低夏普比率
--max-drawdown 0.15       # 最大允许回撤（正数，0.15 = 15%）
--min-annual-return 0.12  # 最低年化收益率
--min-win-rate 0.45       # 最低交易胜率
```

### 5.3 如何设定合理目标

**初学者参考：**

| 策略类型 | 夏普目标 | 回撤限制 | 说明 |
|---------|---------|---------|------|
| 趋势跟踪 | 0.8–1.2 | ≤ 25% | 趋势策略回撤天然较大 |
| 均值回归 | 1.0–1.5 | ≤ 15% | 胜率高但单次收益小 |
| 多因子选股 | 0.8–1.0 | ≤ 20% | 分散化降低波动 |
| 综合策略 | 1.0–1.5 | ≤ 20% | 多层过滤提高质量 |

**注意**：目标设太高会导致优化器无法收敛。如果 10+ 次迭代都无法达标，考虑适当放宽目标或改进策略逻辑。

---

## 6. 自优化循环详解

### 6.1 完整流程图

```
开始
 ↓
读取用户需求（命令行参数或默认值）
 ↓
加载策略模块（读取 PARAMS / PARAM_RANGES / initialize）
 ↓
迭代 0（基线回测）
 ├── 对所有时段运行 run_backtest + analyze_returns
 ├── 计算聚合指标（avg_sharpe, worst_drawdown, ...）
 ├── 记录到审计日志：type="iteration"
 └── 检查是否满足所有要求
      ├── 满足 → 跳到"完成"
      └── 不满足 → 进入调参流程
 ↓
诊断失败指标（回撤太大？夏普不足？胜率低？）
 ↓
生成数据驱动的参数调整方案（≤2 个参数）
 ├── 记录到审计日志：type="adjustment"（含诊断依据）
 └── 记录到审计日志：type="code_review"
 ↓
应用参数调整（修改 PARAMS 字典）
 ↓
迭代 1, 2, 3, ...（循环）
 ↓
完成（满足要求 or 达到最大迭代次数）
 └── 记录到审计日志：type="final"（含最优参数和建议）
```

### 6.2 参数调整规则

优化器使用数据驱动的规则来决定调整哪个参数、往哪个方向调整：

| 失败指标 | 诊断 | 调整方向 |
|---------|------|---------|
| 最大回撤超标 | 止损太松 | `stop_loss_pct` 减小 1 步 |
| 夏普低，波动率高 | 仓位过大 | `position_pct` 减小 1 步 |
| 夏普低，收益不足 | 信号质量差 | `slow_period` 增大 1 步 |
| 胜率低 | 假信号多 | `vol_confirm_mul` 增大 1 步 |
| 交易次数太少 | 条件太严 | `vol_confirm_mul` 减小 1 步 |

**规则约束：**
- 每次迭代最多修改 2 个参数
- 步长严格为 `PARAM_RANGES` 中定义的 1 步
- 始终满足 `fast_period < slow_period`

### 6.3 聚合指标

对多个时段的结果进行聚合：

```
avg_sharpe        = 各时段夏普的平均值
worst_drawdown    = 各时段中最大的回撤（最严重）
avg_annual_return = 各时段年化收益的平均值
consistency_score = 年化收益 > 0 的时段占比
```

---

## 7. 审计日志解读

### 7.1 JSONL 文件结构

每行是一个独立的 JSON 对象，有 4 种类型：

#### type=iteration（迭代结果）

```json
{
  "type": "iteration",
  "session_id": "20240115_143022",
  "iteration": 0,
  "timestamp": "2024-01-15T14:30:22",
  "params": { "fast_period": 5, "slow_period": 20 },
  "periods": [
    {
      "start": "2022-01-01", "end": "2022-12-31",
      "sharpe_ratio": 0.85, "max_drawdown": -0.23,
      "annual_return": 0.07, "win_rate_trade": 0.38,
      "trade_count": 8
    }
  ],
  "aggregate": {
    "avg_sharpe": 0.85, "worst_drawdown": -0.23
  },
  "requirements_met": false,
  "failing": ["2022-01-01–2022-12-31: sharpe 0.85 < 1.0"]
}
```

#### type=adjustment（调参决策）

```json
{
  "type": "adjustment",
  "iteration": 0,
  "diagnosis": "Max drawdown -23.0% exceeds -20% limit. Avg Sharpe 0.85 < 1.0.",
  "changes": [
    {
      "parameter": "stop_loss_pct",
      "old_value": 0.10, "new_value": 0.09,
      "data_evidence": "worst_drawdown=-23.0%; tightening stop to reduce tail loss",
      "expected_effect": "Reduce max drawdown by cutting losing positions earlier"
    }
  ]
}
```

#### type=code_review（代码审查）

```json
{
  "type": "code_review",
  "iteration": 0,
  "checks": [
    { "check": "values_in_range",      "passed": true, "detail": "All new values within PARAM_RANGES" },
    { "check": "cross_param_constraints", "passed": true, "detail": "All constraints satisfied" },
    { "check": "params_used_in_code",  "passed": true, "detail": "All changed parameters referenced via PARAMS[key]" }
  ],
  "overall_passed": true,
  "corrections": []
}
```

#### type=final（最终结果）

```json
{
  "type": "final",
  "total_iterations": 7,
  "stopping_reason": "requirements_met",
  "final_params": { "fast_period": 5, "slow_period": 25, "stop_loss_pct": 0.07 },
  "final_metrics": { "avg_sharpe": 1.12, "worst_drawdown": -0.17 },
  "requirements_met": true,
  "recommendation": "Strategy meets all user-defined requirements. ..."
}
```

### 7.2 Markdown 报告

`.md` 文件是人类可读的优化报告，包含：
- 每次迭代的参数表和指标表
- 每次调参的诊断依据
- 代码审查结果
- 最终推荐参数和建议

用浏览器或 Markdown 查看器打开即可。

### 7.3 使用 jq 查询

```bash
# 查看所有调参决策
jq 'select(.type=="adjustment") | {iter: .iteration, diagnosis: .diagnosis}' \
    audit_log/session_20240115_143022.jsonl

# 查看指定迭代的聚合指标
jq 'select(.type=="iteration" and .iteration==3) | .aggregate' \
    audit_log/session_20240115_143022.jsonl

# 查看最终结果
jq 'select(.type=="final")' audit_log/session_20240115_143022.jsonl
```

---

## 8. 代码审查机制

每次调参后，优化器会自动执行 3 项检查：

### 检查 1：值域合法性

验证所有新参数值在 `PARAM_RANGES` 定义的 `[min, max]` 范围内。如果越界，自动截断到边界并记录修正。

### 检查 2：跨参数约束

```python
# 始终确保
fast_period < slow_period
rsi_oversold < rsi_overbought
0 < stop_loss_pct < 0.30
```

如果约束违反，自动修正并记录。

### 检查 3：参数实际被使用

扫描策略源码，确认修改的参数通过 `PARAMS['key']` 引用。
如果某参数没有被策略代码使用，记录警告（参数修改可能无效）。

---

## 9. 高级用法

### 9.1 编程调用

```python
from agent.optimizer import StrategyOptimizer

optimizer = StrategyOptimizer(
    strategy_path="my_strategy.py",
    requirements={
        "min_sharpe":        1.2,
        "max_drawdown":      0.15,
        "min_annual_return": 0.10,
        "min_win_rate":      0.45,
    },
    periods=[
        ("2021-01-01", "2021-12-31"),
        ("2022-01-01", "2022-12-31"),
        ("2023-01-01", "2023-12-31"),
    ],
    max_iterations=20,
    output_strategy="my_strategy_optimized.py",
    audit_dir="audit_log",
)

best_params = optimizer.run()
print("最优参数:", best_params)
```

### 9.2 自定义多时段（滚动窗口验证）

```bash
python agent/optimizer.py \
    --strategy my_strategy.py \
    --periods \
        "2020-01-01:2020-12-31" \
        "2021-01-01:2021-12-31" \
        "2022-01-01:2022-12-31" \
        "2023-01-01:2023-12-31" \
        "2024-01-01:2024-12-31"
```

使用 5 个独立年度验证，大幅提升参数稳健性。

### 9.3 保存优化后的策略文件

```bash
python agent/optimizer.py \
    --strategy my_strategy.py \
    --output-strategy my_strategy_optimized.py
```

优化器会将 `PARAMS` 块替换为最优参数并写入新文件。

### 9.4 通过 Claude Code 进行深度优化

对于超出参数范围的情况（例如需要修改策略逻辑），可以直接让 Claude Code：

```
分析 audit_log/session_xxx.jsonl，找出哪些问题无法通过参数调整解决，
建议并实施策略逻辑改进，然后重新运行优化器验证效果。
```

Claude Code 会：
1. 读取审计日志找出瓶颈
2. 诊断是否需要修改逻辑（例如添加大盘过滤）
3. 实施代码修改
4. 重新运行优化器
5. 记录所有决策

---

## 10. 示例：完整优化流程

下面是一个完整的优化流程示例（基于内置模板策略）：

### 步骤 1：查看模板策略的初始参数

```python
# agent/strategy_template.py 中的初始参数
PARAMS = {
    'fast_period':      5,
    'slow_period':      20,
    'stop_loss_pct':    0.08,
    'position_pct':     1.0,
    'vol_confirm_mul':  1.5,
}
```

### 步骤 2：运行优化器

```bash
python agent/optimizer.py \
    --min-sharpe 1.0 \
    --max-drawdown 0.20 \
    --max-iterations 10
```

### 步骤 3：观察优化进度

```
=================================================================
EasyQuant Autonomous Strategy Optimizer
=================================================================
Strategy   : agent/strategy_template.py
Periods    : 3 × ['2021-01-01→2021-12-31', '2022-01-01→2022-12-31', '2023-01-01→2023-12-31']
Requirements:
  min_sharpe             = 1.0
  max_drawdown           = 0.2
  min_annual_return      = 0.0
  min_win_rate           = 0.4

─────────────────────────────────────────────────────────────────
[Baseline] params: {'fast_period': 5, 'slow_period': 20, ...}
  avg_sharpe=0.78  worst_dd=-24.3%  avg_ret=5.2%  avg_wr=38.1%  → ❌ NOT MET
    ✗ 2022-01-01–2022-12-31: sharpe 0.62 < 1.0
    ✗ 2022-01-01–2022-12-31: max_drawdown -24.3% worse than -20%
  → Adjustment: ['stop_loss_pct: 0.08→0.07', 'vol_confirm_mul: 1.5→1.75']

─────────────────────────────────────────────────────────────────
[Iteration 1] params: {'fast_period': 5, 'slow_period': 20, 'stop_loss_pct': 0.07, ...}
  avg_sharpe=0.91  worst_dd=-19.8%  avg_ret=5.8%  avg_wr=40.2%  → ❌ NOT MET
    ✗ 2022-01-01–2022-12-31: sharpe 0.72 < 1.0
  → Adjustment: ['slow_period: 20→25']

...（继续迭代）...

─────────────────────────────────────────────────────────────────
[Iteration 5] params: {'fast_period': 5, 'slow_period': 30, 'stop_loss_pct': 0.06, ...}
  avg_sharpe=1.07  worst_dd=-17.2%  avg_ret=7.1%  avg_wr=43.5%  → ✅ MET

✅  All requirements met after 5 iteration(s).

Audit log  : audit_log/session_20240115_143022.jsonl
Summary MD : audit_log/session_20240115_143022.md

Final params: {'fast_period': 5, 'slow_period': 30, 'stop_loss_pct': 0.06, ...}
Best avg Sharpe: 1.074
```

### 步骤 4：查看审计报告

```bash
# 查看 Markdown 报告
cat audit_log/session_20240115_143022.md
```

报告会显示：
- 每次迭代的完整指标表
- 每次调参的具体依据（"2022 年回撤 -24.3% 超过 -20% 限制，收紧止损"）
- 代码审查结果
- 最终推荐参数和使用建议

### 步骤 5：使用优化后的参数

```bash
# 生成优化后的策略文件
python agent/optimizer.py --output-strategy my_strategy_optimized.py

# 运行优化后的策略
python examples/03_run_backtest.py
```

---

## 11. 下一步

- **[CLAUDE.md](../CLAUDE.md)** — AI Agent 完整操作手册（英文）
- **[agent/strategy_template.py](../agent/strategy_template.py)** — 可参数化策略模板
- **[Tutorial 04: 策略优化与改进](04_strategy_optimization.md)** — 手动优化方法（对比参考）
- **[Tutorial 09: 全天候 Alpha 综合策略](09_combined_strategy.md)** — 高级策略结构参考

---

## 附：AI Agent 工作原理速查

| 步骤 | 执行者 | 产出 |
|------|-------|------|
| 读取 CLAUDE.md | Claude Code | 理解项目结构和工作流 |
| 加载策略模块 | optimizer.py | PARAMS / PARAM_RANGES / initialize |
| 多时段回测 | eqlib.run_backtest | 每个时段的收益曲线和交易记录 |
| 指标分析 | eqlib.analyze_returns | sharpe, max_drawdown, win_rate 等 |
| 需求评估 | optimizer.py | 满足 / 不满足列表 |
| 诊断与调参 | optimizer.py | 数据驱动的参数变更方案 |
| 代码审查 | optimizer.py | 3 项检查 + 自动修正 |
| 审计记录 | audit_log.py | JSONL + Markdown 文件 |
| 迭代终止 | optimizer.py | 满足要求 / 达到最大次数 |
