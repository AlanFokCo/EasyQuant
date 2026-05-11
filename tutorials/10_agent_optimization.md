# Tutorial 10: AI Agent 自动化策略优化

> 使用 Claude Code（AI 编码智能体）对 EasyQuant 策略进行全自动参数优化。Claude Code 本身驱动整个流程 —— 运行回测、分析结果、修改策略文件、调用代码审查子 Agent —— 而不是依赖独立的 Python 脚本。

**环境：** Python 3.10+，[`Tutorial 00`](00_environment_and_first_run.md) · **约定全文：** 仓库根目录 [`CLAUDE.md`](../CLAUDE.md)

---

## 目录

1. [为什么需要 AI Agent 优化](#1-为什么需要-ai-agent-优化)
2. [核心概念](#2-核心概念)
3. [快速上手](#3-快速上手)
4. [策略文件要求](#4-策略文件要求)
5. [优化目标（接受条件）](#5-优化目标接受条件)
6. [AI 驱动的自优化循环详解](#6-ai-驱动的自优化循环详解)
7. [审计日志解读](#7-审计日志解读)
8. [代码审查机制](#8-代码审查机制)
9. [高级用法](#9-高级用法)
10. [示例：完整优化流程](#10-示例完整优化流程)
11. [optimizer.py 的定位](#11-optimizerpy-的定位)
12. [下一步](#12-下一步)

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

传统脚本优化的局限：

| 局限 | 影响 |
|------|------|
| 规则死板 | 只能按预定义的规则调整参数 |
| 无法修改策略逻辑 | 超出参数范围的优化无能为力 |
| 诊断能力弱 | 只能识别预设的几种失败模式 |
| 无代码理解 | 无法理解策略逻辑来提出有意义的改进建议 |

AI Agent（Claude Code）优化的优势：

- **智能诊断** — 不仅识别"回撤太大"，还能分析回测数据找出根本原因
- **灵活调整** — 不仅能调参数，还能直接修改策略逻辑（例如添加大盘过滤）
- **完整审计** — 每一步决策都记录到审计日志，可追溯
- **代码理解** — 理解策略逻辑，能提出超越参数范围的改进建议
- **分工协作** — 主 Agent 负责分析决策，子 Agent 负责代码审查，各司其职

---

## 2. 核心概念

### 2.1 配置文件 CLAUDE.md

项目根目录的 `CLAUDE.md` 是 AI 智能体的"操作手册"：

- 描述项目结构和 API
- 规定自优化循环的完整步骤
- 定义参数调整规则
- 说明审计日志格式
- 规定代码审查要求

Claude Code 实例在进入仓库时自动识别并读取该文件，据此规划和执行工作。

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

### 2.3 AI 驱动的自优化循环

```
用户提出需求
     ↓
Claude Code 读取 CLAUDE.md + 策略文件
     ↓
Claude Code 运行基线回测（通过 eqlib API）
     ↓
Claude Code 分析结果，诊断问题
     ↓
Claude Code 提出参数调整方案（附数据依据）
     ↓
Claude Code 使用 Edit 工具直接修改策略文件
     ↓
Claude Code 调用代码审查子 Agent 验证修改
     ↓
子 Agent 返回审查结果
     ↓
Claude Code 记录审计日志，运行新回测
     ↓
重复评估-诊断-调整循环，直到满足要求
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

### 3.1 通过 Claude Code 优化策略

直接告诉 Claude Code 你的需求即可：

```
优化 agent/strategy_template.py，要求夏普比率 > 1.0，最大回撤 < 20%，
在 2021、2022、2023 三个年度分别验证。
```

Claude Code 会：

1. 读取 `CLAUDE.md` 获取操作指南
2. 读取策略文件理解参数结构
3. 使用 `eqlib` API 运行基线回测
4. 分析回测结果，诊断问题
5. 提出参数调整方案并直接修改策略文件
6. 调用代码审查子 Agent 验证
7. 运行新回测验证效果
8. 重复直到满足要求
9. 将完整过程记录到审计日志

### 3.2 自定义接受条件

你可以指定任意指标要求：

```
优化 my_strategy.py：
- 夏普比率 > 1.2
- 最大回撤 < 15%
- 年化收益 > 10%
- 交易胜率 > 45%
- 在 2020-2024 五个年度分别验证
```

### 3.3 超出参数范围的优化

如果参数调整已经无法进一步提升策略表现，可以让 Claude Code 直接修改策略逻辑：

```
当前参数已经优化到极限了。分析审计日志，找出瓶颈，
建议并实施策略逻辑改进（例如添加 RSI 过滤或大盘择时）。
```

Claude Code 会：

1. 读取审计日志找出当前瓶颈
2. 诊断是否需要修改策略结构
3. 直接编辑策略文件添加新逻辑
4. 重新运行回测验证效果

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
# 股票池（AI Agent 会传给 run_backtest）
SECURITIES = ['601390', '600519', ...]
# 或
STOCK_POOL = ['601390', '600519', ...]
```

### 4.3 完整示例

参见 `agent/strategy_template.py`，这是一个完整的参数化策略模板，可以直接复制修改。

### 4.4 不要硬编码参数

❌ 错误写法（AI Agent 无法修改这些值）：

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

直接告诉 Claude Code 你的目标：

```
夏普 > 1.2，回撤 < 15%，年化 > 12%，胜率 > 45%
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

## 6. AI 驱动的自优化循环详解

### 6.1 完整流程图

```
开始
 ↓
Claude Code 读取 CLAUDE.md 和策略文件
 ↓
迭代 0（基线回测）
 ├── 创建 Python 辅助脚本调用 eqlib.run_backtest + analyze_returns
 ├── 对所有时段运行回测
 ├── 计算聚合指标（avg_sharpe, worst_drawdown, ...）
 ├── 使用 AuditLog 记录到审计日志：type="iteration"
 └── 检查是否满足所有要求
      ├── 满足 → 跳到"完成"
      └── 不满足 → 进入调参流程
 ↓
Claude Code 分析失败指标，诊断根因
 ↓
生成数据驱动的参数调整方案（≤2 个参数）
 ├── 使用 AuditLog 记录：type="adjustment"（含诊断依据）
 └── 使用 Edit 工具修改策略文件中的 PARAMS
 ↓
Claude Code 调用代码审查子 Agent
 ├── 子 Agent 验证：值域、约束、参数使用、前视偏差
 ├── 子 Agent 返回审查结果
 └── Claude Code 记录：type="code_review"
 ↓
Claude Code 运行新回测验证
 ↓
迭代 1, 2, 3, ...（循环）
 ↓
完成（满足要求 or 达到最大迭代次数）
 └── Claude Code 记录：type="final"（含最优参数和建议）
```

### 6.2 参数调整规则

AI Agent 使用数据驱动的规则来决定调整哪个参数、往哪个方向调整：

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

### 6.3 与传统脚本的区别

| 方面 | 传统脚本 (`optimizer.py`) | AI Agent (Claude Code) |
|------|--------------------------|----------------------|
| 决策方式 | 预定义规则 | 智能分析 + 规则参考 |
| 参数修改 | 内存中修改 PARAMS | 直接编辑策略源文件 |
| 代码审查 | 简单的文本搜索检查 | 专门的子 Agent 审查 |
| 诊断能力 | 有限的预设诊断 | 深度分析 + 根因推断 |
| 策略修改 | 只能调参数 | 可修改策略逻辑 |
| 可追溯性 | 审计日志 | 审计日志 + git diff |

### 6.4 聚合指标

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

每次调参后，Claude Code 会**调用专门的代码审查子 Agent** 来执行以下 4 项检查：

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

### 检查 4：无前视偏差

确认修改不会引入前视偏差（look-ahead bias），即策略不会使用未来数据进行决策。

---

## 9. 高级用法

### 9.1 策略逻辑级优化

当参数优化达到极限时，可以让 Claude Code 直接改进策略结构：

```
当前参数优化已经无法进一步提升夏普比率。分析回测数据，
找出哪些交易日造成了最大回撤，建议并实施策略逻辑改进。
```

Claude Code 会：

1. 运行深度分析脚本查看每笔交易详情
2. 诊断问题（例如："2022 年 3-4 月的连续亏损占总回撤的 60%"）
3. 实施逻辑改进（例如：添加大盘择时过滤）
4. 重新运行完整优化循环

### 9.2 自定义多时段（滚动窗口验证）

```
使用 2020-2024 五个独立年度分别验证，确保参数稳健性。
```

### 9.3 策略逻辑对比

```
对比优化前后的策略：
1. 参数差异
2. 交易信号差异（哪些交易日会做出不同决策）
3. 指标差异（夏普、回撤、胜率）
```

Claude Code 会运行两组回测并生成对比报告。

---

## 10. 示例：完整优化流程

### 步骤 1：向 Claude Code 提出需求

```
优化 agent/strategy_template.py，要求：
- 夏普比率 > 1.0
- 最大回撤 < 20%
- 在 2021、2022、2023 三个年度分别验证
```

### 步骤 2：Claude Code 自动执行

Claude Code 会依次：

1. 读取 `CLAUDE.md` 和策略文件
2. 运行基线回测，记录初始指标
3. 分析结果，诊断问题
4. 修改参数，调用代码审查
5. 运行新回测验证
6. 重复直到满足要求

### 步骤 3：观察优化进度

Claude Code 会在每次迭代后报告进度：

```
[Baseline]  avg_sharpe=0.78  worst_dd=-24.3%  avg_ret=5.2%  avg_wr=38.1%  → ❌
  诊断：2022 年回撤 -24.3% 超过 -20% 限制；夏普不足
  调整：stop_loss_pct 0.08→0.07, vol_confirm_mul 1.5→1.75
  [代码审查子 Agent] ✅ 通过

[Iteration 1]  avg_sharpe=0.91  worst_dd=-19.8%  avg_ret=5.8%  avg_wr=40.2%  → ❌
  诊断：2022 年夏普 0.72 < 1.0
  调整：slow_period 20→25
  [代码审查子 Agent] ✅ 通过

...（继续迭代）...

[Iteration 5]  avg_sharpe=1.07  worst_dd=-17.2%  avg_ret=7.1%  avg_wr=43.5%  → ✅
  所有要求已满足。
```

### 步骤 4：查看审计报告

```bash
# 查看 Markdown 报告
cat audit_log/session_20240115_143022.md
```

报告会显示：
- 每次迭代的完整指标表
- 每次调参的具体依据
- 代码审查结果
- 最终推荐参数和使用建议

### 步骤 5：验证优化后的策略

```bash
# 查看 git diff 确认 PARAMS 变化
git diff agent/strategy_template.py

# 运行优化后的策略
python examples/03_run_backtest.py
```

---

## 11. optimizer.py 的定位

`agent/optimizer.py` 是一个**独立的规则基参数搜索工具**，作为 AI 驱动优化方法的参考和对比。

### 它的作用

- **参考实现**：展示规则基参数搜索的程序化实现方式
- **性能基准**：可以运行并与 AI 驱动方法的结果进行对比
- **快速验证**：不需要 AI Agent 时，可以直接运行进行简单的参数搜索

### 为什么不作为主要驱动

| 方面 | optimizer.py 的局限 |
|------|-------------------|
| 诊断能力 | 只能识别预定义的几种失败模式 |
| 灵活性 | 只能在 PARAM_RANGES 内搜索 |
| 策略理解 | 无法理解策略逻辑，不能提出结构性改进 |
| 代码审查 | 只做简单的文本检查，无深度分析 |

### AI 驱动方法的优势

Claude Code 直接驱动优化流程，可以：

1. 理解策略的完整逻辑和意图
2. 分析回测数据，推断根本原因
3. 修改策略逻辑（不仅是参数）
4. 使用专业的代码审查子 Agent
5. 在 git 中保留完整的修改历史

---

## 12. 下一步

- **[CLAUDE.md](../CLAUDE.md)** — AI Agent 完整操作手册（英文）
- **[agent/strategy_template.py](../agent/strategy_template.py)** — 可参数化策略模板
- **[Tutorial 04: 策略优化与改进](04_strategy_optimization.md)** — 手动优化方法（对比参考）
- **[Tutorial 09: 全天候 Alpha 综合策略](09_combined_strategy.md)** — 高级策略结构参考

---

## 附：AI Agent 工作原理速查

| 步骤 | 执行者 | 产出 |
|------|-------|------|
| 读取 CLAUDE.md | Claude Code | 理解项目结构和工作流 |
| 读取策略文件 | Claude Code | 理解 PARAMS / PARAM_RANGES / 策略逻辑 |
| 多时段回测 | Claude Code（调用 eqlib） | 每个时段的收益曲线和交易记录 |
| 指标分析 | Claude Code（调用 eqlib.analyze_returns） | sharpe, max_drawdown, win_rate 等 |
| 需求评估 | Claude Code | 满足 / 不满足列表 |
| 诊断与调参 | Claude Code | 数据驱动的参数变更方案 |
| 应用修改 | Claude Code（Edit 工具） | 策略文件 PARAMS 已更新 |
| 代码审查 | 代码审查子 Agent | 4 项检查 + 自动修正 |
| 审计记录 | Claude Code（audit_log.py） | JSONL + Markdown 文件 |
| 迭代终止 | Claude Code | 满足要求 / 达到最大次数 |
