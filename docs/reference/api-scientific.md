# 科学验证与滚动验证 API（实验性）

!!! warning "实验性功能"

    科学验证和滚动验证 API 为实验性功能，未来版本可能有变动。

---

## 滚动验证 API

### walk_forward

滚动验证（Walk-Forward Analysis）：将历史期间分为交替的样本内（IS）和样本外（OOS）窗口，用于检测过拟合。

```python
from eqlib import walk_forward

wfa_result = walk_forward(
    make_initialize,
    optimize_fn=optimize,
    start_date='2020-01-01',
    end_date='2024-12-31',
    train_months=12,
    test_months=3,
    step_months=3,
    starting_cash=100_000,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `make_initialize` | `Callable` | 工厂函数，接受参数字典并返回 `initialize` 函数 |
| `optimize_fn` | `Callable` 或 `None` | 可选，`(train_result) -> dict` 参数选择函数 |
| `start_date` | `str` / `date` | 分析起始日期 |
| `end_date` | `str` / `date` | 分析结束日期 |
| `train_months` | `int` | 每个训练窗口长度（月） |
| `test_months` | `int` | 每个测试窗口长度（月） |
| `step_months` | `int` | 窗口滑动步长（月） |
| `starting_cash` | `float` | 每个窗口的初始资金 |
| `benchmark` | `str` | 基准代码 |
| `securities` | `list[str]` 或 `None` | 股票池 |

返回 `WFAResult` 对象，包含：

- `windows`：每个窗口的结果列表
- `oos_equity`：拼接的 OOS 权益曲线（`pd.Series`）
- `summary`：聚合统计（`total_oos_return`、`oos_sharpe` 等）

### walk_forward_analysis（科学验证层）

`eqlib.scientific.overfitting.walk_forward_analysis` 实现真正的滚动 walk-forward：将 `[start_date, end_date]` 切为多个滑动 train/test 窗口，每个窗口独立跑一段 IS backtest 和一段 OOS backtest，并聚合 Sharpe / return / max_drawdown 衰减情况。

```python
from eqlib.scientific.overfitting import walk_forward_analysis

result = walk_forward_analysis(
    initialize_func,         # callable initialize, 或 backtest_result dict
    param_ranges=None,       # 保留接口，仅写入 window 元数据
    train_window='2Y',
    test_window='6M',
    step='6M',
    start_date='2020-01-01',
    end_date='2024-12-31',
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `initialize_func` | `Callable \| dict` | `initialize` 函数（推荐，每段窗口独立跑回测）或已有的 `run_backtest()` 结果 dict（按日期切片，OOS 段会继承 IS 权益，因此不是真正的 OOS） |
| `param_ranges` | `dict \| None` | 保留用于未来扩展，目前仅写入窗口元数据 |
| `train_window` | `str` | 训练段长度，如 `'2Y'` / `'6M'` / `'90D'` |
| `test_window` | `str` | 测试段长度 |
| `step` | `str` | 滑动步长；`<=0` 或省略时退化为 `test_window`（非重叠窗口） |
| `start_date` | `str` | 总区间起始（仅在 `initialize_func` 为 callable 时使用） |
| `end_date` | `str` | 总区间结束 |

**返回**：`WalkForwardResult` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| `windows` | `list[dict]` | 每个窗口的 `train_start/end`、`test_start/end`、`is_metrics`、`oos_metrics` |
| `oos_is_ratio` | `float` | 平均 OOS Sharpe / 平均 IS Sharpe |
| `is_sharpe_decay` | `bool` | 平均 OOS Sharpe 是否低于平均 IS Sharpe |

!!! tip "callable vs dict"
    推荐传 `callable`：每个 train/test 段独立跑回测，OOS 段从初始资金重新开始，是真正的样本外测量。传 `dict`（已有回测结果）时按日期切片，OOS 段会继承 IS 段最终权益——适合快速检查但不是严格的 OOS。

!!! warning "参数扰动"
    `walk_forward_analysis` 当前**不**扰动策略参数（`param_ranges` 仅作元数据保留）。如需检测参数过拟合，请配合 `parameter_sensitivity` 或 `out_of_sample_test` 使用。

---

## 科学验证 API

`eqlib.scientific` 提供回测后的科学验证工具，用于过拟合检测、统计置信度测试、偏差检测和扩展风险指标。

### validate_backtest

一键运行全部验证检查。

```python
from eqlib.scientific import validate_backtest, ValidationConfig

config = ValidationConfig()  # 可选自定义配置
validation = validate_backtest(backtest_result, config=config)
validation.summary()
```

### 子模块

| 模块 | 主要函数 | 说明 |
|------|----------|------|
| `overfitting` | `out_of_sample_test`、`parameter_sensitivity`、`walk_forward_analysis` | 过拟合检测 |
| `statistics` | `bootstrap_metrics`、`monte_carlo_simulation`、`significance_test`、`sample_size_assessment` | 统计置信度 |
| `bias` | `check_lookahead_bias`、`check_survivorship_bias`、`check_selection_bias`、`check_data_bias` | 偏差检测 |
| `risk` | `extended_risk_metrics`、`value_at_risk`、`conditional_var`、`stress_test`、`tail_risk_analysis` | 扩展风险 |
| `comparison` | `compare_with_platform`、`compare_metrics`、`verify_trades` | 平台对比 |
| `report` | `generate_validation_report` | 验证报告生成 |

### ValidationConfig

验证配置对象，可自定义阈值和启用/禁用各验证模块。

```python
from eqlib import ValidationConfig
config = ValidationConfig()
```
