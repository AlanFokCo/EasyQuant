<div align="center">

<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="280" alt="EasyQuant logo"/></a>

# EasyQuant

Event-driven quantitative backtesting framework for China A-share market.

[![Tests](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/test.yml?label=Tests)](https://github.com/AlanFokCo/EasyQuant/actions/workflows/test.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/deploy-docs.yml?label=Docs)](https://AlanFokCo.github.io/EasyQuant/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/AlanFokCo/EasyQuant/blob/main/LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.1-gray.svg)](https://github.com/AlanFokCo/EasyQuant/releases)

<p>
<a href="README_zh.md">中文文档</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/">Docs Site</a> ·
<a href="tutorials/README.md">Tutorials</a> ·
<a href="doc/README.md">Doc Center</a> ·
<a href="doc/api_reference.md">API Reference</a> ·
<a href="examples/Examples.md">Examples</a> ·
<a href="doc/FAQ.md">FAQ</a>
</p>

</div>

---

## Features

- **Event-driven backtesting** — `initialize` → `run_daily` → `handle_data`, compatible with JoinQuant / Zipline programming model
- **A-share data** — daily OHLCV, minute K-lines, tick data, real-time quotes, fundamentals, money flow via free AKShare API
- **Position management** — buy/sell by shares, value, or target; automatic lot-size rounding (100 shares), commission calculation
- **Risk analysis** — Sharpe, Sortino, max drawdown, alpha/beta, Brinson attribution, Fama-French factor analysis
- **Portfolio optimization** — minimum variance, maximum Sharpe, risk parity
- **Paper trading** — run strategies live with real-time market data before going live
- **PTrade/QMT adapter** — one-click export to broker platforms
- **Stock selection** — periodic rebalancing with factor screening (ST/PB/PE/momentum filters, Top-N, multi-factor scoring)
- **Utility library** — 30+ technical indicators (MA, MACD, RSI, KDJ, Bollinger, ATR, ADX), statistical tools, position sizing (Kelly, ATR-based, fixed fractional)
- **Reports** — interactive HTML, chart PNG, Markdown, JSON with 20+ risk/return metrics
- **Chainable stock screening** — fluent API (`query` / `valuation` / `get_fundamentals`) for fundamental analysis

---

## Quick Start

```bash
pip install .
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

Open the generated `.html` report in `reports/` in your browser.

### Write Your First Strategy

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

> **Execution model:** `order*` APIs queue orders in the current callback; they are filled at the **next trading day's open** to avoid look-ahead bias.
>
> **Output:** 4 files in `reports/` — `.png` chart, `.html` interactive report, `.md` summary, `.json` data.

---

## Report Preview

`run_strategy` generates an **interactive HTML report** plus PNG, Markdown, and JSON. Below are snapshots from real backtest runs.

### Profitable Strategies

| MACD Trend + Volume (600536) | Bollinger Mean Reversion (601088) | Support/Resistance (8 stocks) |
|:---:|:---:|:---:|
| **+103.48%** · 16 trades | **+57.77%** · 8 trades | **+119.97%** · 171 trades |
| [![MACD](tutorials/assets/example_report_macd_volume.png)](tutorials/assets/example_report_macd_volume.png) | [![Bollinger](tutorials/assets/example_report_bollinger.png)](tutorials/assets/example_report_bollinger.png) | [![S/R](tutorials/assets/example_report_sr_strategy.png)](tutorials/assets/example_report_sr_strategy.png) |

### Losing Strategies (For Learning)

| Momentum Portfolio (5 stocks) | Local Data (000768) |
|:---:|:---:|
| **−25.69%** · 52 trades | **−33.28%** · 16 trades |
| [![Portfolio](tutorials/assets/example_report_portfolio.png)](tutorials/assets/example_report_portfolio.png) | [![Local](tutorials/assets/example_report_19_localdata.png)](tutorials/assets/example_report_19_localdata.png) |

> **How to read reports:** header summary → metric cards (Sharpe, max drawdown, alpha) → K-line chart → cumulative returns vs benchmark → drawdown curve → daily P&L → trade/position tabs. Full guide: [Report & Metrics](doc/reports_and_metrics.md).

---

## Project Structure

```
EasyQuant/
├── eqlib/                 # Core library (backtest engine, data API, analysis)
├── agent/                 # AI optimization utilities
│   ├── optimizer.py       # Rule-based parameter search (reference)
│   ├── audit_log.py       # Structured JSONL + Markdown audit logging
│   └── strategy_template.py  # Parameterized strategy template
├── examples/              # 24 runnable example scripts
├── tutorials/             # Step-by-step learning tutorials
│   └── prerequisites/     # Python, technical analysis, A-share basics
├── doc/                   # User manual, API reference, FAQ
├── docs/                  # GitHub Pages site source (MkDocs Material)
├── tests/                 # Test suite
├── assets/                # Brand assets (logo, icons)
├── CLAUDE.md              # AI agent configuration & optimization workflow
└── mkdocs.yml             # Documentation site configuration
```

## Examples

Full index at [`examples/Examples.md`](examples/Examples.md).

| # | File | Description |
|---|------|-------------|
| 01 | `01_fetch_data.py` | Data API: history, CSV, local loading, market scan |
| 02 | `02_write_strategy.py` | Strategy templates (MA crossover, RSI, multi-stock) |
| 03 | `03_run_backtest.py` | End-to-end backtest with reports |
| 04 | `04_stock_screener.py` | Real-time stock screening |
| 05 | `05_paper_trade.py` | Paper trading with live quotes |
| 06 | `06_advanced_api.py` | Scheduling, portfolio optimization, attribution |
| 07 | `07_market_data.py` | Financials, industry, index, minute, tick data |
| 08 | `08_lifecycle_callbacks.py` | Lifecycle callbacks & stock pool management |
| 09 | `09_attribution_analysis.py` | Brinson + Fama-French factor analysis |
| 10 | `10_index_concept.py` | Index & concept board strategies |
| 11 | `11_utils_library.py` | Full utility library demonstration |
| 12 | `12_portfolio_backtest.py` | Multi-stock portfolio backtest |
| 13 | `13_ptrade_export.py` | Export to PTrade/QMT platform |
| 14–17 | Strategies | Bollinger, MACD+Volume, Multi-Factor, Grid Trading |
| 18 | `18_strategy_comparison.py` | Side-by-side strategy comparison |
| 19 | `19_local_data_backtest.py` | Local data mode (download once, offline backtest) |
| 20 | `20_sr_strategy/` | Support & Resistance portfolio (production case) |
| 21 | `21_combined_strategy/` | All-Weather Alpha comprehensive strategy |
| 22 | `22_stock_selection_strategy.py` | Periodic stock selection with factor screening |
| 23 | `23_small_cap_query_example.py` | Small-cap screening with chainable query API |
| 24 | `24_quick_report_test.py` | Quick report format validation |

---

## Documentation

| Resource | Description |
|----------|-------------|
| [**Docs Site**](https://AlanFokCo.github.io/EasyQuant/) | Full documentation site with search, dark theme, navigation |
| [**Doc Center**](doc/README.md) | Entry point: user guide, API index, FAQ, report metrics |
| [**User Guide**](doc/user_guide.md) | Install → write strategy → run backtest → read reports |
| [**API Reference**](doc/api_reference.md) | All public APIs with parameters and examples |
| [**Utils Reference**](doc/utils_reference.md) | Technical indicators, statistics, position sizing |
| [**Tutorials**](tutorials/README.md) | Zero to production, with real strategy cases |
| [**Report & Metrics Guide**](doc/reports_and_metrics.md) | Field-by-field report walkthrough |
| [**FAQ**](doc/FAQ.md) | Installation, data, performance, troubleshooting |

---

## Installation

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install .
```

Editable install for development:

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

**Requirements:** Python 3.10+ · macOS / Linux / Windows

---

## Performance

- **Memory-aware data loading** — automatic memory limit (default 1 GB) with fallback to compact slicing; identical results, slightly slower
- **Fast I/O** — in-memory `attribute_history` reduces 6+ year backtests from ~20 min to ~1 min
- **Parallel data loading** — multi-threaded preload for faster startup

---

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
pip install -e ".[dev,docs]"
python -m pytest tests/ -v
```

### CI/CD

| Pipeline | Trigger | Description |
|----------|---------|-------------|
| [Tests](https://github.com/AlanFokCo/EasyQuant/blob/main/.github/workflows/test.yml) | Push / PR to `main` | Runs test suite on Python 3.10, 3.11, 3.12 |
| [Deploy Docs](https://github.com/AlanFokCo/EasyQuant/blob/main/.github/workflows/deploy-docs.yml) | Push to `main` (docs paths) | Builds and deploys MkDocs site to GitHub Pages |

---

## License

This project is licensed under the [MIT License](https://github.com/AlanFokCo/EasyQuant/blob/main/LICENSE).

---

> **Disclaimer:** This project is for educational and research purposes only. It does not constitute investment advice.
