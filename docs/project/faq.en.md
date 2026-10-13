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

## Installation & Environment { #installationenvironment }

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

**Minimum set (already installed by `pip install .` or `pip install easyquant-eqlib`):** `akshare`, `chinese_calendar`, `pandas`, `numpy`, `matplotlib`, `scipy`, `scikit-learn`, and `requests`.

**Optional:** `pip install pyarrow` to improve disk cache performance for some operations (see `[project.optional-dependencies]` in `pyproject.toml`).

---

## Data & Network { #datanetwork }

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
3. **Date range:** `get_north_money_flow(start_date=None, end_date=None)` covers the last 30 days up to today by default; ranges too far back may exceed the data source's coverage.

**Solution:**

```python
from eqlib import get_north_money_flow

df = get_north_money_flow()  # default: last 30 days up to today
# or pass an explicit date range
df = get_north_money_flow(start_date='2026-09-01', end_date='2026-10-01')
if df.empty:
    log.warn("Northbound capital flow data unavailable, using fallback logic")
    # Use cached data or historical averages as a substitute
```

Columns: `date` / `net_buy` / `total_buy` / `total_sell` (unit: 100M CNY; Shanghai + Shenzhen Connect combined).

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
from eqlib import get_margin_data

df = get_margin_data()  # default: last 30 days up to today
# Remove the first row with NaN
df = df.dropna(subset=['margin_repay'])

# Or fill with a default value
df['margin_repay'] = df['margin_repay'].fillna(0)
```

Note: `get_margin_data(start_date=None, end_date=None)` returns **market-wide aggregates** (Shanghai + Shenzhen combined) with columns `date` / `margin_balance` / `margin_buy` / `margin_repay` / `short_balance` (unit: 100M CNY). There is no per-stock granularity and no `count` parameter.

### Q: Why did the `g.xxx` I set outside `run_backtest` disappear?

**Cause:** `run_backtest` (and `run_strategy`) **clears the `g` object** on every call. This is by design — each backtest session should have its own independent state, avoiding data pollution between runs.

**Solution:** Set `g` attributes inside `initialize()` instead of outside `run_backtest`:

```python
# ❌ Wrong
g.security = '601398'
result = run_backtest(initialize, ...)

# ✅ Correct
def initialize(context):
    g.security = '601398'
    run_daily(market_open, time='every_bar')

result = run_backtest(initialize, ...)
```

For module-level configuration, use plain Python variables instead of `g`:

```python
# Module-level constant (not cleared)
MY_SECURITY = '601398'

def initialize(context):
    g.security = MY_SECURITY
```

---

## Backtest & Strategy { #backteststrategy }

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

## Reports & Analysis { #reportsanalysis }

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

### Q: `benchmark_return` is `null` and Alpha / Beta show N/A — is this normal?

**Possible causes:** When fetching or aligning **benchmark index daily returns** fails (network issues, index code conversion errors, empty date intersection, etc.), `alpha` / `beta` / `information_ratio` are returned as **NaN**, rendered as **N/A** with a methodology note in HTML / Markdown reports, and the corresponding JSON checks are marked `pass: null` (the old silent defaults of 0.0 / 1.0 are gone). **Strategy NAV, PNG static charts, and trade tables still use strategy data**. Check your network connection and rerun, or verify that `set_benchmark` has valid index data for the backtest period.

### Q: How to run backtest only without automatically generating all four reports?

Use **`run_backtest`** and manually call `generate_html_report`, `analyze_returns`, etc. as needed. See [API Reference](../reference/api-analysis.md).

---

## Paper Trading & Export { #papertradingexport }

### Q: What's the difference between `run_paper_trade` and backtest?

Paper trading fetches **real-time or latest market data** at configured intervals and loops through strategy execution **indefinitely** until manually interrupted (Ctrl+C). See [Paper Trading](../how-to/paper-trade.md) for details.

### Q: How to export to PTrade / QMT?

See [Export to PTrade/QMT](../how-to/export-ptrade.md) and the example `examples/12_paper_trade.py`.

---

## Development & Testing { #developmenttesting }

### Q: How to verify changes after modifying `eqlib` source code?

```bash
python -m pytest tests/
```

(When optimizing strategies, you typically do **not** modify `eqlib/` — only strategy and example files are changed.)
