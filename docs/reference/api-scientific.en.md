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
