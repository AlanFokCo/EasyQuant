# Tutorial 09: 策略参数优化与审计

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 用 `PARAMS` / `PARAM_RANGES` 管理可调参数；用 `optimizer.py` 搜索、`walk_forward` / `walk_forward_analysis` 做滚动样本外验证、`validate_backtest` 做过拟合与偏差审计 |
    | **预计用时** | 约 60 分钟 |
    | **前置** | [Tutorial 00](00-getting-started.md)、[Tutorial 02](02-backtesting.md)（回测与指标）、[Tutorial 03](03-optimization.md)（手动优化思路）；指标含义见 [报告格式详解](../reference/reports-format.md) |

> 本章说明如何用 **PARAMS / PARAM_RANGES** 参数化策略，结合仓库内 `agent/optimizer.py`（规则搜索参考）、`agent/audit_log.py`（审计日志）与 `eqlib` 自带的滚动验证、科学验证 API，搭建**可复现**的调参与审计流程。你也可以自行编写 Python 脚本或在常用 IDE 里编排相同步骤；EasyQuant **不绑定**任何特定编辑器或商业 AI 产品。

---

## 目录

1. [为什么需要参数化与审计](#1-为什么需要参数化与审计)
2. [核心约定](#2-核心约定)
3. [命令行：optimizer.py](#3-命令行optimizerpy)
4. [滚动样本外验证：walk_forward](#4-滚动样本外验证walk_forward)
5. [过拟合检测：walk_forward_analysis](#5-过拟合检测walk_forward_analysis)
6. [一键科学验证：validate_backtest 与 ValidationConfig](#6-一键科学验证validate_backtest-与-validationconfig)
7. [ML 超参数搜索：optimize_hyperparams](#7-ml-超参数搜索optimize_hyperparams)
8. [自建优化循环（推荐思路）](#8-自建优化循环推荐思路)
9. [审计日志](#9-审计日志)
10. [代码审查清单（建议）](#10-代码审查清单建议)
11. [延伸阅读](#11-延伸阅读)

---

## 1. 为什么需要参数化与审计

| 痛点 | 参数化 + 审计能带来的帮助 |
|------|---------------------------|
| 调参凭感觉 | `PARAM_RANGES` 明确搜索边界，结果可对比 |
| 决策不可追溯 | `audit_log/` 记录每次迭代的指标与变更依据 |
| 样本内好看、样本外拉胯 | `walk_forward` / `walk_forward_analysis` 用滚动 OOS 窗口量化衰减 |
| 规则脚本太死板 | 先跑 `optimizer.py` 做基线，再按需手写诊断逻辑 |

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
- 样本外窗口的夏普不低于样本内的某个比例（见 §4–5）

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

## 4. 滚动样本外验证：walk_forward

单段"前 70% 调参、后 30% 验证"只给你一个样本外结论。`eqlib.wfa.walk_forward()` 把整个区间切成交替滚动的样本内（IS）/ 样本外（OOS）窗口：每个窗口先在 IS 段选参，再用选出的参数跑一段独立 OOS 回测，最后把所有 OOS 段的净值拼接成一条曲线。

```python
from eqlib import walk_forward, analyze_returns

def make_initialize(**params):
    """参数工厂：optimize_fn 选出的参数会作为关键字传进来。"""
    merged = {**PARAMS, **params}

    def initialize(context):
        g.fast_period = merged["fast_period"]
        g.slow_period = merged["slow_period"]
        g.stop_loss_pct = merged["stop_loss_pct"]
        # ... 其余初始化 ...
    return initialize

def optimize_fn(train_result):
    """IS 段选参：返回的 dict 会传给 make_initialize。不选就返回 {}。"""
    metrics = analyze_returns(train_result)
    if metrics["sharpe_ratio"] < 1.0:
        return {"slow_period": 30}   # 示例：弱势窗口改用更慢的均线
    return {}

result = walk_forward(
    make_initialize,
    optimize_fn=optimize_fn,        # 传 None 则所有窗口用默认参数
    start_date="2020-01-01",
    end_date="2024-12-31",
    train_months=12,                # 每个 IS 窗口 12 个月
    test_months=3,                  # 每个 OOS 窗口 3 个月
    step_months=3,                  # 步长 = 测试窗口 → OOS 段不重叠
    starting_cash=100_000,
)

print(result.summary)               # 聚合统计
result.oos_equity.plot()            # 拼接后的 OOS 净值曲线
```

`WFAResult` 的三个属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `windows` | `list[dict]` | 每窗口的 `train_start/end`、`test_start/end`、`params`、`oos_result`、`oos_metrics` |
| `oos_equity` | `pd.Series` | 拼接后的 OOS 净值曲线（逐窗口归一后连乘） |
| `summary` | `dict` | `n_windows`、`profitable_pct`（盈利 OOS 窗口占比）、`avg_oos_sharpe`、`total_oos_return`、`oos_max_drawdown` 等 |

怎么读：`profitable_pct` 明显低于单段回测的胜率直觉、或 `oos_equity` 长期横盘，都说明策略对区间敏感。`summary["avg_oos_sharpe"]` 才是你能对外引用的夏普——全样本回测的夏普包含调参时用过的数据。

---

## 5. 过拟合检测：walk_forward_analysis

`eqlib.scientific` 层的 `walk_forward_analysis()` 更轻量：不在 IS 段选参，只用固定参数分别跑 IS / OOS 两段回测，量化**样本外衰减**。

```python
from eqlib.scientific import walk_forward_analysis

wfa = walk_forward_analysis(
    initialize,              # initialize callable（推荐）；也可传 run_backtest 的结果 dict
    param_ranges=None,       # 保留参数，目前仅写入窗口元数据
    train_window="2Y",
    test_window="6M",
    step="6M",
    start_date="2020-01-01",
    end_date="2024-12-31",
)

print("OOS/IS 夏普比:", round(wfa.oos_is_ratio, 2))
print("样本外衰减:", wfa.is_sharpe_decay)
for w in wfa.windows:
    print(w["train_start"], "->", w["test_end"],
          "IS sharpe:", round(w["is_metrics"]["sharpe"], 2),
          "OOS sharpe:", round(w["oos_metrics"]["sharpe"], 2))
```

| 返回值 | 类型 | 说明 |
|--------|------|------|
| `windows` | `list[dict]` | 每窗口的 `train_start/end`、`test_start/end`、`is_metrics`、`oos_metrics`（含 `sharpe` / `annual_return` / `max_drawdown`） |
| `oos_is_ratio` | `float` | 平均 OOS 夏普 / 平均 IS 夏普；明显小于 1 说明样本外衰减 |
| `is_sharpe_decay` | `bool` | 平均 OOS 夏普是否低于平均 IS 夏普 |

!!! tip "callable 还是 dict"
    传 `initialize` callable 时，每个 IS / OOS 段都从初始资金独立跑回测，是真正的样本外测量。传已有的回测结果 dict 时只按日期切片净值曲线，OOS 段会继承 IS 段的累计权益——快，但不是严格的 OOS。

!!! warning "参数扰动"
    `walk_forward_analysis` 当前**不**扰动策略参数（`param_ranges` 仅作元数据保留）。需要参数敏感性结论时，配合 `eqlib.scientific` 的 `parameter_sensitivity` / `out_of_sample_test` 使用。

---

## 6. 一键科学验证：validate_backtest 与 ValidationConfig

`validate_backtest()` 把偏差检测（前视 / 幸存者 / 选股 / 数据）、统计置信度（bootstrap、蒙特卡洛、显著性）、过拟合检测与扩展风险指标串成一条流水线，回测跑一次即可出总评：

```python
from eqlib import run_backtest, ValidationConfig
from eqlib.scientific import validate_backtest

result = run_backtest(initialize, "2022-01-01", "2024-12-31")

config = ValidationConfig(
    n_bootstrap=1000,           # bootstrap 重采样次数
    n_monte_carlo=500,          # 蒙特卡洛模拟次数
    significance_level=0.05,    # 显著性检验 p 值阈值
    perturbation_pct=0.10,      # 参数扰动幅度
    random_state=42,            # 复现用随机种子
)
validation = validate_backtest(result, config=config)
print(validation.summary())      # 总体信任度 + 各模块摘要
print(validation.trust_rating)
```

不需要某个模块就在 `ValidationConfig` 里关掉：`ValidationConfig(overfitting=False, statistics=False)` 只跑偏差与风险检查。完整参数清单见 [科学验证 API](../reference/api-scientific.md)。

---

## 7. ML 超参数搜索：optimize_hyperparams

如果策略里用了 `MLSelector`（见 [Tutorial 11](11-ml-selection.md)），模型超参数不要用随机拆分交叉验证——时间序列会泄漏。`optimize_hyperparams()` 用 `TimeSeriesSplit` 做网格搜索：

```python
from eqlib.ml.tuning import optimize_hyperparams

best = optimize_hyperparams(
    pipeline,                    # FeaturePipeline 实例
    model_type="random_forest",
    X=X_train,                   # 特征矩阵
    y=y_train,                   # 标签
    param_grid={"n_estimators": [50, 100, 200], "max_depth": [3, 5, 8]},
    cv_method="time_series_split",
    n_splits=5,
    scoring="roc_auc",
)
```

数据量不足 `n_splits * 2` 行时返回空 dict 并回退默认参数。在策略内一键调参可用 `auto_tune_selector`（直接从 selector 的 pipeline 取数），见 [ML API 参考](../reference/api-ml.md)。

---

## 8. 自建优化循环（推荐思路）

```
基线回测（run_backtest / run_strategy）
    ↓
analyze_returns(result) 等指标
    ↓
若不达标：根据规则或人工判断调整 PARAMS（保持与 PARAM_RANGES 一致）
    ↓
样本外复核：walk_forward 或 walk_forward_analysis（§4–5）
    ↓
（可选）validate_backtest 全量审计（§6）
    ↓
再回测 → 将摘要写入 audit_log（若使用 audit_log.py）
    ↓
达到停止条件或最大迭代次数
```

实现方式完全由你决定：Shell + Python、Makefile、CI 任务均可。关键纪律只有一条：**任何被全样本数据"喂"出来的参数，都要在 OOS 窗口里重新证明一次。**

---

## 9. 审计日志

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

建议把 §4–6 的关键数字（`oos_is_ratio`、`profitable_pct`、`trust_rating`）一并写入审计条目——它们比单段回测指标更能代表策略质量。

---

## 10. 代码审查清单（建议）

每次修改 `PARAMS` 或策略逻辑后，建议至少核对：

1. 新值落在 `PARAM_RANGES` 内，且满足交叉约束（如 `fast_period < slow_period`）。
2. 被调参数在策略中通过 `PARAMS["…"]` 读取，而非硬编码。
3. 未使用未来数据、未在信号中误用当日收盘价等（避免前视）；拿不准就跑一次 `validate_backtest` 看偏差检测结论。
4. 回测区间与数据源一致，异常交易（停牌等）有处理。
5. 新参数至少通过一个滚动 OOS 验证（`walk_forward` 的 `profitable_pct`、`walk_forward_analysis` 的 `oos_is_ratio`），而不是只看全样本夏普。

---

## 11. 延伸阅读

- [Tutorial 03: 策略优化与改进](03-optimization.md) — 手动分析与改进思路
- [Tutorial 08: 全天候 Alpha 综合策略](08-combined-strategy.md) — 多模块组合示例
- [Tutorial 11: 机器学习选股](11-ml-selection.md) — MLSelector 与特征管道
- [运行回测](../how-to/run-backtest.md) · [阅读报告](../how-to/read-reports.md)
- [科学验证与滚动验证 API](../reference/api-scientific.md) · [ML API 参考](../reference/api-ml.md)
- [API 参考 — 生命周期与归因](../reference/api-analysis.md)
