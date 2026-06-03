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
