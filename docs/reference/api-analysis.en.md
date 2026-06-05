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
metrics = analyze_returns(result, risk_free_rate=0.03, trading_days=252)
```

Returns a `dict`: `total_return`, `annual_return`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `alpha`, `beta`, `information_ratio`, `win_rate`, `trading_days`, `num_trades`.

## brinson_attribution

Brinson attribution analysis. Returns a `dict` (`allocation_effect`, `selection_effect`, `interaction_effect`, `total_active_return`).

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
