# Report Format Specification

> Field definitions and data structures for JSON, PNG, HTML, and Markdown reports.

---

## analyze_returns Metrics Dictionary

For the return value of `result = run_backtest(...)` or `run_strategy`:

```python
from eqlib import analyze_returns

m = analyze_returns(result, risk_free_rate=0.03, trading_days=252)
```

When `result["recorded_values"]` is insufficient to construct a daily NAV series, the function may return **`None`**, in which case some metrics will also be missing from the HTML report.

| Key | Description |
|-----|-------------|
| `total_return` | Total return over the full period (based on start/end portfolio value) |
| `annual_return` | Annualized return derived from geometric annualization of daily returns |
| `annual_volatility` | Daily return standard deviation × √252 |
| `sharpe_ratio` | Sharpe ratio (annualized, net of risk-free rate) |
| `sortino_ratio` | Sortino ratio |
| `max_drawdown` | Max drawdown (negative number) |
| `calmar_ratio` | Annualized return / \|max drawdown\| |
| `alpha` | Annualized Alpha (relative to benchmark) |
| `beta` | Beta |
| `information_ratio` | Information ratio |
| `win_rate_daily` | Daily win rate |
| `win_rate_trade` | Paired-trade win rate |
| `trade_count` | Number of completed paired trades |
| `win_count` / `loss_count` | Number of profitable / losing trades |
| `profit_loss_ratio` | Profit/loss ratio |
| `annual_turnover` | Annualized turnover (relative trade volume) |
| `total_commission` | Total commissions (for reporting; NAV already reflects costs) |
| `net_return` | Same meaning as `total_return` (see source code comments) |
| `excess_return` | Strategy total return − benchmark total return |
| `benchmark_return` | Benchmark total return |
| `excess_return_max_drawdown` | Max drawdown of the excess return series |
| `excess_return_sharpe` | Excess return Sharpe |
| `daily_excess_return` | Annualized mean daily excess return |
| `benchmark_volatility` | Benchmark annualized volatility |
| `max_drawdown_start` | Start date of the maximum drawdown |
| `max_drawdown_end` | End date of the maximum drawdown |
| `trading_days` | Number of trading days |
| `num_trades` | Total fills (one-sided) |
| `monthly_returns` | Monthly returns dict (`{"2024-01": 0.03, ...}`) |
| `rolling_sharpe_60d` | 60-day rolling Sharpe series (`[{"date": "...", "value": ...}]`) |
| `rolling_volatility_60d` | 60-day rolling volatility series |
| `daily_returns_stats` | Daily return statistics (mean, std, skewness, kurtosis, best/worst day, histogram) |
| `per_stock_pnl` | Per-stock P&L dict (FIFO matching, `{"000001": 5000.0, ...}`) |
| `drawdown_periods` | Top 5 drawdown periods (start/trough/recovery dates, depth, duration days) |

The risk-free rate defaults to **`risk_free_rate=0.03`** (annualized 3%) and can be adjusted as needed.

---

## Markdown / JSON Reports

- **Markdown**: Suitable for pasting into notes or version control; provides a quick summary and trade log.
- **JSON**: Suitable for scripting batch comparisons across parameter sets, plotting custom charts, and integrating with dashboards.

### JSON Top-Level Fields (Agent-First Schema)

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | `object` | Overall grade (S/A/B/C/D), score, strongest/weakest dimension |
| `targets` | `object` | Target metric values and pass/fail status |
| `diagnostics` | `array` | Diagnostic findings (max drawdown, Sharpe, win rate, Alpha violations) |
| `recommendations` | `array` | Parameter tuning suggestions (priority, parameter, current/suggested value) |
| `grade` | `object` | 6-dimension score breakdown (return, risk, risk-adjusted, trade quality, excess, stability) |
| `metrics` | `object` | Full metrics (same as `analyze_returns` output; inf/nan serialized as `null`) |
| `time_series` | `object` | Monthly returns, rolling Sharpe, rolling volatility, drawdown periods |
| `daily_returns_stats` | `object` | Daily return statistics (mean, std, skewness, kurtosis) |
| `per_stock_pnl` | `object` | Per-stock P&L (FIFO matching) |
| `summary` | `object` | Backtest period, capital, P&L, trade count, benchmark |
| `trades` | `array` | Individual fill records |
| `positions` | `object` | End-of-period holdings |
| `chart_data` | `object` | Candlestick, volume, cumulative return, drawdown chart data (nested) |
| `factor_analysis` | `object` | Factor analysis (simplified Fama-French) |
| `brinson_attribution` | `object` | Brinson attribution |
| `risk_metrics` | `object` | **Backward-compat**: flat metrics dict (Sharpe, drawdown, Alpha, etc.) |
| `cumulative_returns` | `array` | **Backward-compat**: daily NAV series `[{date, total_value, cumulative_return}]` |
| `strategy_params` | `object` | (optional) Current parameters and parameter ranges |
| `iteration` | `object` | (optional) Iteration context (run_id, changes, score delta) |

JSON top-level fields may be extended in future versions; refer to the generated file for the authoritative schema.

**Note when reading JSON:** `summary.num_trades` is typically the one-sided fill count, which differs from the paired trade count — see [FAQ](../project/faq.md#faq-json-num-trades).
