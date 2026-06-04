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

The risk-free rate defaults to **`risk_free_rate=0.03`** (annualized 3%) and can be adjusted as needed.

---

## Markdown / JSON Reports

- **Markdown**: Suitable for pasting into notes or version control; provides a quick summary and trade log.
- **JSON**: Suitable for scripting batch comparisons across parameter sets, plotting custom charts, and integrating with dashboards.

### JSON Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `object` | Generation time, data source, methodology, disclaimer |
| `summary` | `object` | Backtest period, capital, P&L, trade count, benchmark |
| `risk_metrics` | `object` | Sharpe, Sortino, max drawdown, Alpha/Beta, etc. |
| `excess_return_metrics` | `object` | Excess return, excess drawdown, excess Sharpe |
| `brinson_attribution` | `object` | Brinson attribution (allocation / selection / interaction effects) |
| `factor_analysis` | `object` | Factor exposure analysis |
| `trades` | `array` | Individual fill records |
| `positions` | `object` | End-of-period holdings |
| `cumulative_returns` | `array` | Daily NAV series |
| `candlestick_data` | `array` | Candlestick data (TradingView format) |
| `volume_data` | `array` | Volume bar data |
| `ma5_data` / `ma20_data` / `ma60_data` | `array` | Moving average data |
| `rsi_data` | `array` | RSI(14) data |
| `macd_data` / `macd_signal_data` / `macd_hist_data` | `array` | MACD line / signal / histogram |
| `bb_upper_data` / `bb_middle_data` / `bb_lower_data` | `array` | Bollinger Bands |
| `support_data` / `resistance_data` | `array` | Support / Resistance |
| `markers` | `array` | Buy/sell signal markers |
| `cum_return_data` | `array` | Strategy cumulative returns |
| `ret_hs300_data` / `ret_sse_data` | `array` | CSI 300 / SSE Index cumulative returns |
| `drawdown_data` | `array` | Drawdown series |
| `pnl_bar_data` | `array` | Daily P&L bars |
| `daily_returns_data` | `array` | Daily returns |

JSON top-level fields may be extended in future versions; refer to the generated file for the authoritative schema.

**Note when reading JSON:** `summary.num_trades` is typically the one-sided fill count, which differs from the paired trade count — see [FAQ](../project/faq.md#faq-json-num-trades).
