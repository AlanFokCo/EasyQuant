# Frequently Asked Questions (FAQ)

> Troubleshooting and common questions. For operational guides, see the [How-to Guides](../how-to/index.md).

### Jump by Topic

| Issue you're facing | Jump to |
|---------------------|---------|
| Python version, `pip install`, `import eqlib` | [Installation & Environment](#installationenvironment) |
| Slow first backtest, no data, minute bars / ticks | [Data & Network](#datanetwork) |
| No trades, T+1, order quantity, benchmark | [Backtest & Strategy](#backteststrategy) |
| Empty PNG, blank HTML, mismatched JSON numbers | [Reports & Analysis](#reportsanalysis) |
| Paper trading, exporting to PTrade / QMT | [Paper Trading & Export](#papertradingexport) |
| Modifying source code, running unit tests | [Development & Testing](#developmenttesting) |

---

## Installation & Environment

### Q: `pip install .` fails with "requires a different Python: 3.9.x not in '>=3.10'"

**Cause:** `eqlib` requires **Python ≥ 3.10** (see `requires-python` in `pyproject.toml`).

**Solution:** Install and use Python 3.10 / 3.11 / 3.12, for example:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Q: Installed `akshare` and other dependencies, but `import eqlib` still fails

**Cause:** `eqlib` is the project package and must be installed from PyPI or the repository.

**Solution:**

```bash
# Option 1: Install from PyPI (recommended, no need to clone the repo)
pip install easyquant-eqlib

# Option 2: Install from source (from the repo root)
cd /path/to/EasyQuant
pip install .
```

After installation, `import eqlib` will work from any working directory. Before running scripts under `examples/`, it's also recommended to complete the installation above (examples no longer automatically modify `sys.path` to import `eqlib`).

### Q: What dependencies do I need to install?

**Minimum set (already installed by `pip install .` or `pip install easyquant-eqlib`):** `akshare`, `pandas`, `numpy`, `matplotlib`, `scipy`.

**Optional:** `pip install pyarrow` to improve disk cache performance for some operations (see `[project.optional-dependencies]` in `pyproject.toml`).

---

## Data & Network

### Q: First backtest is very slow or hangs

**Common cause:** `akshare` fetches historical data online, which depends on network conditions and data source availability.

**Recommendations:**

- Use `run_strategy(..., use_local=True)` or `run_backtest(..., use_local=True)`: downloads and writes to `data/` on the first run, then reads local CSV files on subsequent runs.
- For multi-stock backtests, always pass **`securities=[...]`** to preload only the stocks that will be traded, significantly reducing the number of requests.
- See `set_cache_dir` / `set_local_data_dir` in the [API Reference](../reference/index.md).

### Q: `get_price` / `attribute_history` returns empty data

**Check:**

1. Is the code a **6-digit A-share code** (e.g., `601390`)? Index benchmarks should be in the form `000300.XSHG`.
2. Is the date range after the stock's listing date and does it include trading days?
3. Is the network connection working? Try retrying at a different time or using local data with `use_local=True`.

### Q: Minute bars / ticks fail or have incomplete data

Minute bars and tick data depend on the corresponding `akshare` interfaces and stock liquidity. The available historical length varies by stock. See [API Reference — Minute Bars / Ticks](../reference/api-data.md) for details.

### Q: Northbound capital flow API returns empty data

**Possible causes:**

1. **Trading day restriction:** Northbound capital flow data is only updated on trading days; no data is available on weekends and holidays.
2. **Network issues:** The data source (East Money) API may be unstable; try again later.
3. **Date range:** `get_north_money_flow(count=N)` returns data for the most recent N trading days. If N is too large, it may exceed the data source limit.

**Solution:**

```python
from eqlib import get_north_money_flow

df = get_north_money_flow(count=30)
if df.empty:
    log.warn("Northbound capital flow data unavailable, using fallback logic")
    # Use cached data or historical averages as a substitute
```

It's recommended to preload and cache northbound capital flow data in `initialize` to avoid making requests on every `handle_data` call.

### Q: Why does get_limit_up_down_stats only return the last 30 days?

**Cause:** This function calls `ak.stock_zt_pool_em`, and the data source (East Money) only provides limit-up and limit-down statistics for the most recent 30 trading days. Earlier history is not available.

**Alternatives:**

- For backtesting scenarios, use `attribute_history` to get individual stock price changes and calculate limit-up/limit-down counts yourself.
- For longer history, consider using third-party paid data sources.

```python
from eqlib import get_limit_up_down_stats

df = get_limit_up_down_stats()
# Contains only the most recent ~30 trading days
```

### Q: Why is the first row of `margin_repay` in margin trading data NaN?

**Cause:** `margin_repay` (margin repayment amount) is calculated as the difference between consecutive days' margin balances. The first row has no previous day's data, so the result is NaN. This is normal data processing behavior.

**Solution:**

```python
from eqlib import get_margin_trading

df = get_margin_trading('601390', count=30)
# Remove the first row with NaN
df = df.dropna(subset=['margin_repay'])

# Or fill with a default value
df['margin_repay'] = df['margin_repay'].fillna(0)
```

---

## Backtest & Strategy

### Q: HTML is generated after backtest, but PNG is empty or missing equity curve

**Common cause:** `record()` was not used in the strategy to log **`total_value`**, or `recorded_values` is missing daily portfolio values, causing `generate_chart` / HTML to be unable to render some series.

**Solution:** Call the framework's record function at the end of your daily logic (if using `run_daily`, the engine typically records the portfolio automatically; for custom implementations, ensure consistency with official examples). See `examples/03_run_backtest.py` and [Running Backtests](../how-to/run-backtest.md).

### Q: Bought stocks and want to sell the same day, but available quantity shows 0

**Cause:** A-shares operate on a **T+1** settlement. Shares bought today are added to `closeable_amount` and can only be sold the next trading day. The engine enforces this restriction on sell quantities.

### Q: `order` / `order_value` quantity is not what I expected

**Cause:** Buy quantities are **rounded down to the nearest multiple of 100 shares**. If funds are insufficient, the maximum affordable quantity will be used.

### Q: What does setting benchmark to `000300.XSHG` do?

It's used to calculate **alpha, beta, information ratio, and excess returns**, and to compare strategy returns against the benchmark in HTML/PNG reports. See [Report Format Specification](../reference/reports-format.md) for details.

---

## Reports & Analysis

### Q: HTML shows different "daily win rate" and "trade win rate"?

**Cause:** `analyze_returns` provides both **`win_rate_daily`** (proportion of profitable trading days) and **`win_rate_trade`** (win rate after pairing complete buy-sell trades). These have different meanings and should not be confused. See [Report Format Specification](../reference/reports-format.md) for the complete list.

<a id="faq-html-blank"></a>

### Q: Charts in HTML report are blank?

**Cause:** The interactive HTML loads **Lightweight Charts** scripts via **CDN** (such as jsDelivr / unpkg). Corporate intranets, proxies, or offline environments may block external scripts, causing **candlestick charts, cumulative returns, and drawdown charts to appear blank**. The header, summary, and metric cards are typically embedded data and usually remain visible.

**Solution:** Switch to a network with internet access; or whitelist `cdn.jsdelivr.net` and `unpkg.com` and refresh; or open in an internet-connected environment and take screenshots for archival.

<a id="faq-json-num-trades"></a>

### Q: Why does JSON `summary.num_trades` differ from "trade count (paired)"?

**Cause:** `summary.num_trades` typically represents the **number of one-sided executions** (each `BUY` / `SELL` counted separately, e.g., 8 buys + 8 sells = **16**). If the report/HTML shows **"trade count" as paired rounds**, it refers to complete buy-sell cycles (the example above would be **8**). When reading JSON, check both `risk_metrics` and the `trades` list.

<a id="faq-benchmark-null"></a>

### Q: `benchmark_return` is `null` and Alpha / Beta are close to 0 — is this normal?

**Possible causes:** When fetching or aligning **benchmark index daily returns** fails (network issues, index code conversion errors, empty date intersection, etc.), excess returns and CAPM-related displays may show **0 or placeholder values**. **Strategy NAV, PNG static charts, and trade tables still use strategy data**. Check your network connection and rerun, or verify that `set_benchmark` has valid index data for the backtest period.

### Q: How to run backtest only without automatically generating all four reports?

Use **`run_backtest`** and manually call `generate_html_report`, `analyze_returns`, etc. as needed. See [API Reference](../reference/api-analysis.md).

---

## Paper Trading & Export

### Q: What's the difference between `run_paper_trade` and backtest?

Paper trading fetches **real-time or latest market data** at configured intervals and loops through strategy execution **indefinitely** until manually interrupted (Ctrl+C). See [Paper Trading](../how-to/paper-trade.md) for details.

### Q: How to export to PTrade / QMT?

See [Export to PTrade/QMT](../how-to/export-ptrade.md) and the example `examples/13_ptrade_export.py`.

---

## Web Strategy Studio

### Q: Why am I automatically logged out after login?

**Cause:** When the JWT Token expires or becomes invalid, the frontend automatically clears authentication state and redirects to the login page.

**Solution:**
- Check if the backend is running normally
- In production, configure a stable JWT secret (environment variable `EQ_JWT_SECRET`); otherwise, key changes after restart will invalidate all tokens
- If the backend restarts, you need to log in again

### Q: Backtest always shows positions=0, no trades?

**Cause:** The strategy code may not have properly set `context.universe = [...]`. The Web Studio's data preloading relies on this configuration to determine which stocks' historical data to load.

**Solution:** Explicitly set the stock universe in `initialize(context)`:

```python
def initialize(context):
    context.universe = ['601390', '600519']
```

For more Web Studio issues, see [Web Strategy Studio](../how-to/web-studio.md).

---

## Development & Testing

### Q: How to verify changes after modifying `eqlib` source code?

```bash
python -m pytest tests/
```

(When optimizing strategies, you typically do **not** modify `eqlib/` — only strategy and example files are changed.)
