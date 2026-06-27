# Scientific Validation & Walk-Forward API (Experimental)

!!! warning "Experimental Feature"

    The scientific validation and walk-forward APIs are experimental and may change in future versions.

---

## Walk-Forward API

### walk_forward

Walk-Forward Analysis: divides the historical period into alternating in-sample (IS) and out-of-sample (OOS) windows to detect overfitting.

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

| Parameter | Type | Description |
|-----------|------|-------------|
| `make_initialize` | `Callable` | Factory function that accepts a parameter dict and returns an `initialize` function |
| `optimize_fn` | `Callable` or `None` | Optional: `(train_result) -> dict` parameter selection function |
| `start_date` | `str` / `date` | Analysis start date |
| `end_date` | `str` / `date` | Analysis end date |
| `train_months` | `int` | Length of each training window (months) |
| `test_months` | `int` | Length of each test window (months) |
| `step_months` | `int` | Window sliding step (months) |
| `starting_cash` | `float` | Initial capital per window |
| `benchmark` | `str` | Benchmark ticker |
| `securities` | `list[str]` or `None` | Stock universe |

Returns a `WFAResult` object containing:

- `windows`: list of results for each window
- `oos_equity`: stitched OOS equity curve (`pd.Series`)
- `summary`: aggregated statistics (`total_oos_return`, `oos_sharpe`, etc.)

### walk_forward_analysis (Scientific layer)

`eqlib.scientific.overfitting.walk_forward_analysis` implements a true rolling walk-forward: the `[start_date, end_date]` range is sliced into multiple sliding train/test windows, each running an independent IS backtest and an OOS backtest, then aggregates Sharpe / return / max_drawdown decay.

```python
from eqlib.scientific.overfitting import walk_forward_analysis

result = walk_forward_analysis(
    initialize_func,         # callable initialize, or backtest_result dict
    param_ranges=None,       # reserved, only written to window metadata
    train_window='2Y',
    test_window='6M',
    step='6M',
    start_date='2020-01-01',
    end_date='2024-12-31',
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `initialize_func` | `Callable \| dict` | An `initialize` function (recommended — each segment runs an independent backtest) or an existing `run_backtest()` result dict (sliced by date; OOS segments inherit IS equity, so this is not true OOS) |
| `param_ranges` | `dict \| None` | Reserved for future expansion; currently only written to window metadata |
| `train_window` | `str` | Training segment length, e.g. `'2Y'` / `'6M'` / `'90D'` |
| `test_window` | `str` | Test segment length |
| `step` | `str` | Sliding step; `<=0` or omitted falls back to `test_window` (non-overlapping windows) |
| `start_date` | `str` | Total range start (used only when `initialize_func` is callable) |
| `end_date` | `str` | Total range end |

**Returns**: a `WalkForwardResult` object

| Attribute | Type | Description |
|-----------|------|-------------|
| `windows` | `list[dict]` | Per-window `train_start/end`, `test_start/end`, `is_metrics`, `oos_metrics` |
| `oos_is_ratio` | `float` | Mean OOS Sharpe / mean IS Sharpe |
| `is_sharpe_decay` | `bool` | Whether mean OOS Sharpe is below mean IS Sharpe |

!!! tip "callable vs dict"
    Passing a `callable` is recommended: each train/test segment runs an independent backtest, and the OOS segment starts from the initial cash — a true out-of-sample measurement. Passing a `dict` (existing backtest result) slices by date, with OOS segments inheriting the IS final equity — convenient for quick checks but not strictly OOS.

!!! warning "Parameter perturbation"
    `walk_forward_analysis` does **not** perturb strategy parameters (`param_ranges` is metadata-only). To detect parameter overfitting, combine with `parameter_sensitivity` or `out_of_sample_test`.

---

## Scientific Validation API

`eqlib.scientific` provides post-backtest scientific validation tools for overfitting detection, statistical confidence testing, bias detection, and extended risk metrics.

### validate_backtest

Run all validation checks in one call.

```python
from eqlib.scientific import validate_backtest, ValidationConfig

config = ValidationConfig()  # Optional custom configuration
validation = validate_backtest(backtest_result, config=config)
validation.summary()
```

### Submodules

| Module | Key Functions | Description |
|--------|---------------|-------------|
| `overfitting` | `out_of_sample_test`, `parameter_sensitivity`, `walk_forward_analysis` | Overfitting detection |
| `statistics` | `bootstrap_metrics`, `monte_carlo_simulation`, `significance_test`, `sample_size_assessment` | Statistical confidence |
| `bias` | `check_lookahead_bias`, `check_survivorship_bias`, `check_selection_bias`, `check_data_bias` | Bias detection |
| `risk` | `extended_risk_metrics`, `value_at_risk`, `conditional_var`, `stress_test`, `tail_risk_analysis` | Extended risk |
| `comparison` | `compare_with_platform`, `compare_metrics`, `verify_trades` | Platform comparison |
| `report` | `generate_validation_report` | Validation report generation |

### ValidationConfig

Validation configuration object with customizable thresholds and the ability to enable/disable individual validation modules.

```python
from eqlib import ValidationConfig
config = ValidationConfig()
```
