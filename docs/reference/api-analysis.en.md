# Reporting & Analysis API

> Generate backtest reports, calculate risk metrics, perform attribution analysis, and optimize portfolios.

---

## generate_chart

Generate a backtest chart (PNG).

```python
generate_chart(result, out_path)
```

## generate_report_md

Generate a Markdown-format report.

## generate_report_json

Generate a JSON-format report. The returned JSON includes: `metadata` (generation info), `summary` (capital gains/losses), `risk_metrics` (risk metrics), `excess_return_metrics` (excess return metrics), `brinson_attribution` (Brinson attribution), `factor_analysis` (factor analysis), `trades` (fill list), `positions` (holdings), `cumulative_returns` (NAV series), and all **chart data arrays**: `candlestick_data`, `volume_data`, `ma5/20/60_data`, `rsi_data`, `macd_data`/`macd_signal_data`/`macd_hist_data`, `bb_upper/middle/lower_data`, `support_data`, `resistance_data`, `markers`, `cum_return_data`, `ret_hs300_data`, `ret_sse_data`, `drawdown_data`, `pnl_bar_data`, `daily_returns_data`.

## generate_html_report

Generate an interactive HTML report. The HTML report includes candlestick charts (with MA overlays, volume, buy/sell signals), RSI(14), MACD(12,26,9), Bollinger Bands(20,2), cumulative returns, drawdown, daily P&L, and trade log. The candlestick chart supports an indicator toggle panel and crosshair-linked legend.

## analyze_returns

Calculate comprehensive risk metrics.

```python
metrics = analyze_returns(result, risk_free_rate=0.03)
```

Returns a `dict`: `total_return`, `annual_return`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `alpha`, `beta`, `information_ratio`, `win_rate`, `trading_days`, `num_trades`. Returns **`None`** when `result["recorded_values"]` is empty, lacks `total_value`, or the initial cash is not positive.

Conventions:

- Annualization uses **244** trading days (the A-share value; see `eqlib/constants.py`).
- `alpha` / `beta` / `information_ratio` depend on the benchmark series: they are `NaN` (rendered `N/A` in reports and examples) when benchmark data is unavailable or has fewer than 10 overlapping trading days — silent defaults of 0.0/1.0 are no longer returned.
- Benchmark returns prefer the engine-recorded benchmark NAV series (same source as report charts), falling back to a network fetch only when unavailable.
- `win_rate_trade` / `profit_loss_ratio` / `per_stock_pnl` are based on FIFO-matched round trips **inclusive of both-side fees** (buy commission amortized into cost, sell fees deducted from proceeds), consistent with the engine's cash ledger.

## grade_strategy

Strategy scoring across 6 dimensions.

```python
grade_info = grade_strategy(analytics)
```

Accepts the dict returned by `analyze_returns()`. Returns a `dict`: `overall` (S/A/B/C/D), `score` (0-100), `dimensions` (list of 6 dimension scores), `weakest`/`strongest` (dimension names), `summary_text` (one-sentence summary).

The 6 scoring dimensions: return capability (20%), risk control (20%), risk-adjusted (20%), trade quality (15%), excess capability (15%), stability (10%).

## diagnose_bottleneck

Identify failing metrics and root causes.

```python
diagnostics = diagnose_bottleneck(analytics, grade_info)
```

Returns a `list[dict]`, each with: `metric`, `severity` (critical/warning), `finding` (description), `root_cause`, `affected_period`, `related_metrics`.

Checked metrics: max drawdown (< -20%), Sharpe (< 1.0), win rate (< 40%), Alpha (< 0).

## recommend_params

Parameter tuning recommendations.

```python
recommendations = recommend_params(analytics, grade_info, current_params, param_ranges)
```

Suggests parameter adjustments based on diagnostics. `current_params` and `param_ranges` are the `PARAMS` and `PARAM_RANGES` dicts from the strategy file. Returns a `list[dict]`, each with: `priority`, `target_metric`, `action`, `parameter`, `current`, `suggested`, `range`, `rationale`, `expected_effect`, `risk`.

## brinson_attribution

Single-period Brinson-Hood-Beebower attribution. The whole backtest window is treated as one holding period and the active return is decomposed at the sector level into allocation, selection and interaction effects, mathematically closed: `allocation + selection + interaction == portfolio_return − benchmark_return`.

```python
attr = brinson_attribution(result, sector_data={"601398.XSHG": "Financials", ...})
```

| Parameter | Description |
|-----------|-------------|
| `result` | Result dict returned by `run_backtest` |
| `sector_data` | Security → sector-name mapping; unmapped securities fall into `"Unclassified"`. Without it all securities share one sector, so allocation and interaction are identically zero and the entire active return is reported as selection (the correct BHB statement when no sector structure is known) |
| `benchmark_returns` | Optional `pd.Series` of benchmark daily returns; when given, that scalar return is applied uniformly across sectors, otherwise the benchmark is the equal-weight buy-and-hold return of the backtest universe (from the engine-exported OHLCV panel, same qfq series the engine traded on) |

Returns a `dict`: `allocation_effect`, `selection_effect`, `interaction_effect`, `total_active_return`, `portfolio_return`, `benchmark_return`, `benchmark_model` (`"universe_equal_weight"` / `"scalar_series"`), and a per-sector breakdown under `sectors` (weights, returns and the three effects per sector).

## simple_factor_analysis

Simplified factor analysis. Decomposes strategy returns into a market factor (beta), a momentum proxy (lagged return autocorrelation), and Alpha (residual).

> **Note:** This function does **not** implement the true Fama-French three-factor model. The `momentum_correlation` field is return autocorrelation, not true momentum factor exposure.

```python
from eqlib import simple_factor_analysis
ff = simple_factor_analysis(result)
```

Returns a `dict` (`market_beta`, `market_exposure`, `alpha_annual`, `momentum_correlation`, `vol_of_vol`, `residual_volatility`, `explained_variance`).

!!! warning "Deprecated Alias"

    `fama_french_analysis` is still available but deprecated. Use `simple_factor_analysis` instead.

---

## Portfolio Optimization API

### portfolio_optimizer

Portfolio weight optimization.

```python
portfolio_optimizer(securities, prices, target=None, constraints=None, bounds=None,
                    default_range=(0.0, 1.0), ftol=1e-9, return_none_if_fail=True)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `securities` | `list[str]` | List of stock tickers |
| `prices` | `DataFrame` | Price matrix |
| `target` | `MinVariance`/`MaxSharpe`/`RiskParity` | Optimization objective |
| `constraints` | `dict` | e.g., `{'max_weight': 0.3}` |
| `bounds` | `list[Bound]` | Per-stock weight lower/upper bounds |

Returns optimized weights as a `Series`, or `None`.

#### Optimization Targets

```python
MinVariance()
MaxSharpe(risk_free_rate=0.03)
RiskParity()
```
