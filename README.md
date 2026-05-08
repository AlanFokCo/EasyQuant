# EasyQuant

A quantitative strategy and backtesting tool for the **China A-share market**.

This project provides the `eqlib` Python package — the core library that implements the event-driven backtesting engine, data APIs, and analysis tools.

[中文文档](README_zh.md) · [新手教程](tutorials/) · [用户手册](doc/user_guide.md) · [API 参考](doc/api_reference.md) · [示例](examples/)

---

## Features

- **Event-driven backtesting** — initialize, scheduled functions, daily bars, portfolio tracking
- **A-share data** — daily OHLCV, minute K-lines, tick data, real-time quotes, fundamentals, money flow
- **Position management** — buy/sell by shares, value, or target; automatic lot-size rounding and commission calculation
- **Risk analysis** — Sharpe, Sortino, max drawdown, alpha/beta, Brinson attribution, Fama-French factor analysis
- **Portfolio optimization** — minimum variance, maximum Sharpe, risk parity
- **Paper trading** — run strategies live with real-time market data
- **PTrade/QMT adapter** — export EasyQuant strategies to PTrade/QMT platform with minimal changes
- **Stock selection** — periodic portfolio rebalancing with factor-based screening (ST/PB/PE/momentum filters, Top-N, multi-factor scoring)
- **Utility library** — technical indicators (MA, MACD, RSI, KDJ, Bollinger, ATR), statistical tools, position sizing (Kelly, ATR-based, fixed fractional)
- **Reports** — chart (PNG), Markdown, and JSON output

---

## Performance

- **Memory-aware data loading** — preload data from disk cache (parquet) or local CSV files
  with automatic memory limit (default 1 GB). Exceed the limit? The engine falls back to
  compact slicing — results are identical, just slightly slower.
- **Fast I/O** — `attribute_history` reads from in-memory data instead of hitting disk/network
  on every call, reducing typical 6+ year backtests from ~20 min to ~1 min.
- **Parallel data loading** — multi-threaded preload for faster startup.

---

## Installation

```bash
pip install akshare pandas numpy matplotlib scipy
# optional: faster disk cache
pip install pyarrow
```

Or install from source:

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install -e .
```

---

## Quick Start

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        order_target(g.security, 0)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    securities=['601390'],
)
```

---

## Examples

See the [`examples/`](examples/) directory for complete scripts:

| # | File | Description |
|---|------|-------------|
| 01 | `01_fetch_data.py` | Download stock data |
| 02 | `02_write_strategy.py` | Write strategies (MA crossover, RSI, multi-stock) |
| 03 | `03_run_backtest.py` | Run a full backtest |
| 04 | `04_stock_screener.py` | Stock screening |
| 05 | `05_paper_trade.py` | Paper trading |
| 06 | `06_advanced_api.py` | Advanced data APIs |
| 07 | `07_market_data.py` | Market data: financials, index, minute, tick |
| 08 | `08_lifecycle_callbacks.py` | Lifecycle callbacks |
| 09 | `09_attribution_analysis.py` | Attribution analysis |
| 10 | `10_index_concept.py` | Index & concept boards |
| 11 | `11_utils_library.py` | Technical indicators, statistics, money management |
| 12 | `12_portfolio_backtest.py` | Portfolio backtest with `StrategyConfig` |
| 13 | `13_ptrade_export.py` | Export strategies to PTrade/QMT |
| 14 | `14_bollinger_strategy.py` | Bollinger Band mean reversion |
| 15 | `15_macd_volume_strategy.py` | MACD trend + volume confirmation |
| 16 | `16_multi_factor_strategy.py` | Multi-factor stock selection |
| 17 | `17_grid_trading_strategy.py` | Grid trading for range-bound markets |
| 18 | `18_strategy_comparison.py` | Compare multiple strategies side by side |
| 19 | `19_local_data_backtest.py` | Local data mode (download once, backtest offline) |
| 20 | `20_sr_strategy/` | Support & Resistance portfolio strategy (real-world case) |
| 21 | `21_combined_strategy/` | **All-Weather Alpha** — comprehensive combined strategy (multi-factor + sector rotation + RSI/MACD/Bollinger + ATR) |
| 22 | `22_stock_selection_strategy.py` | **Stock Selection** — periodic rebalancing with factor-based screening (ST/PE/momentum filters, TopNSelector, MultiFactorSelector) |

---

## Documentation

- [**Tutorials**](tutorials/) — beginner guide: from zero to live trading, plus AI agent optimization
- [**User Guide**](doc/user_guide.md) — tutorial: writing strategies, running backtests, reading reports
- [**API Reference**](doc/api_reference.md) — full API: structures, parameters, usage
- [**Utils Reference**](doc/utils_reference.md) — calculation tools: indicators, statistics, money management, support/resistance
- [**PTrade/QMT Adapter**](doc/ptrade_adapter.md) — export EasyQuant strategies to PTrade/QMT platform
- [**CLAUDE.md**](CLAUDE.md) — AI agent configuration: self-optimization workflow, audit log format, code review rules

---

## AI Agent — Autonomous Strategy Optimization

EasyQuant includes a built-in **AI agent workflow** orchestrated by **Claude Code**. The AI agent (Claude Code itself) reads strategy files, runs backtests via `eqlib` APIs, analyzes results, edits strategy files directly, spawns a code-review sub-agent, and logs every decision — all without running a standalone optimization script.

### How it works

1. You tell Claude Code your requirements (e.g. "Sharpe > 1.0, max drawdown < 20%")
2. Claude Code reads `CLAUDE.md` and your strategy file
3. It runs backtests using `eqlib` APIs, then analyzes the results
4. Diagnoses issues and proposes data-driven parameter adjustments
5. Edits the strategy file directly via the Edit tool
6. Spawns a specialized code-review sub-agent to verify changes
7. Repeats until all requirements are met
8. Logs every decision to a structured audit trail (JSONL + Markdown)

For the full workflow details, see [`CLAUDE.md`](CLAUDE.md) and [`tutorials/10_agent_optimization.md`](tutorials/10_agent_optimization.md).

### Quick start

Just tell Claude Code what you want:

```
Optimize agent/strategy_template.py, requiring Sharpe > 1.0,
max drawdown < 20%, validated across 2021, 2022, and 2023.
```

Claude Code handles the rest — no command to run.

### Reference utility

The [`agent/optimizer.py`](agent/optimizer.py) script provides a standalone rule-based parameter search for comparison with the AI-driven approach. It can be run independently but is **not** the primary optimization driver.

### Agent files

- **[`CLAUDE.md`](CLAUDE.md)** — AI agent configuration: full self-optimization workflow, parameter rules, audit log format, code review
- **[`agent/audit_log.py`](agent/audit_log.py)** — Structured audit logging (JSONL + Markdown)
- **[`agent/strategy_template.py`](agent/strategy_template.py)** — Parameterized strategy template
- **[`agent/optimizer.py`](agent/optimizer.py)** — Reference rule-based optimizer (optional, for comparison)
- **[`tutorials/10_agent_optimization.md`](tutorials/10_agent_optimization.md)** — Tutorial (Chinese)

### Audit log

Every optimization session writes two files to `audit_log/`:

```
audit_log/
├── session_<timestamp>.jsonl   # machine-readable; query with jq
└── session_<timestamp>.md      # human-readable Markdown report
```

Every parameter change is logged with: the specific metric values that triggered it, the expected effect, and the code review result. Users can trace every decision back to data.

---

## Stock Selection

EasyQuant supports periodic portfolio rebalancing through a stock selection interface. Instead of hardcoding your stock pool, you define a selection function that runs weekly, monthly, or at any custom frequency.

### Quick start

```python
from eqlib import *

def my_selection(context):
    """Return the stocks you want to trade this period."""
    # Filter ST, then pick top 5 by lowest PE
    candidates = filter_st_stocks(["601390", "600519", "000858", "600036"])
    df = fetch_factor_data(candidates, fields=["pe"])
    df = df.dropna(subset=["pe"]).sort_values("pe", ascending=True)
    return df.head(5).index.tolist()

def initialize(context):
    context.universe = ["601390"]  # initial universe
    run_selection(my_selection, rebalance="monthly:1")  # run on 1st of month
    run_daily(trade, time="every_bar")

def trade(context):
    selected = context.universe
    # ... sell stocks not in selected, buy selected stocks ...
```

### Rebalance frequencies

| Value | Meaning | Example |
|-------|---------|---------|
| `"monthly:N"` | Nth day of month (1-31) | `"monthly:1"` (1st), `"monthly:15"` (15th) |
| `"weekly:N"` | Nth weekday (0=Mon, 4=Fri) | `"weekly:0"` (Monday), `"weekly:4"` (Friday) |
| `"daily"` | Every trading day | `"daily"` |

### Three ways to define selection

**1. Plain function** (simplest):

```python
def simple_selection(context):
    candidates = filter_st_stocks(CANDIDATE_POOL)
    return TopNSelector(factor="pe", top_n=5).rank(candidates, context)
```

**2. StockSelector subclass** (complex logic):

```python
class MySelector(StockSelector):
    def filter(self, candidates, context):
        candidates = filter_st_stocks(candidates)
        return filter_high_pe_stocks(candidates, max_pe=50)
    def rank(self, securities, context):
        return MultiFactorSelector(
            factors={"pe": -0.4, "pb": -0.3, "pct_change": 0.3},
            top_n=5
        ).rank(securities, context)
```

**3. Via `run_strategy` parameter**:

```python
result = run_strategy(
    initialize_func=initialize,
    selection_func=my_selection,
    selection_rebalance="weekly:0",
)
```

### Available filters and selectors

| API | Description |
|-----|-------------|
| `filter_st_stocks(securities)` | Remove ST / *ST stocks |
| `filter_paused_stocks(securities, context)` | Remove paused/suspended stocks |
| `filter_low_price_stocks(securities, min_price)` | Remove stocks below price threshold |
| `filter_high_pe_stocks(securities, max_pe)` | Remove stocks with PE above threshold |
| `fetch_factor_data(securities, fields)` | Get multi-dimensional data (PE/PB/momentum/MA/RSI) |
| `TopNSelector(factor, top_n, ascending)` | Rank by single factor |
| `MultiFactorSelector(factors, top_n)` | Rank by weighted composite score |

See [`examples/22_stock_selection_strategy.py`](examples/22_stock_selection_strategy.py) for a complete example.

---

## License

MIT
