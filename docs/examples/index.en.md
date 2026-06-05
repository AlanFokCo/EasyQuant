# Examples Overview

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Quickly locate each script under `examples/` by number and find the recommended way to run it |
    | **Prerequisite** | Run `pip install -e .` from the repository root |

20 examples across a three-tier progressive learning path: Foundations (01–07) → Intermediate (08–14) → Real-World Projects (15–20).

## Quick Start

Install `eqlib` from the repository root (if not already installed):

```bash
pip install -e .
```

Run an example:

```bash
python examples/<file>.py
```

All examples use relative dates and a unified trading cost configuration (`examples/_defaults.py`).

---

## Foundations (01–07): Essential First Steps

| # | File | Description | Command |
|---|------|-------------|---------|
| 01 | `01_fetch_data.py` | Data API: historical quotes, CSV download, market scanning | `python examples/01_fetch_data.py` |
| 02 | `02_write_strategy.py` | Strategy template: dual moving average crossover, `initialize`/`run_daily`/`g` object | `python examples/02_write_strategy.py` |
| 03 | `03_run_backtest.py` | Low-level backtest: `run_backtest`, trade log, `analyze_returns` | `python examples/03_run_backtest.py` |
| 04 | `04_stock_screener.py` | Stock screener: `scan_market`, golden cross detection, restricted share unlock filtering, `query()` API | `python examples/04_stock_screener.py` |
| 05 | `05_reports.py` | Report generation: PNG/HTML/MD/JSON four formats + metrics dictionary reference | `python examples/05_reports.py` |
| 06 | `06_local_data.py` | Local data: download cache, backtest with `use_local=True` | `python examples/06_local_data.py` |
| 07 | `07_lifecycle.py` | Lifecycle hooks: `before_trading_start`, ST detection, monthly rebalancing | `python examples/07_lifecycle.py` |

---

## Intermediate (08–14): Analysis Tools & A-Share Features

| # | File | Description | Command |
|---|------|-------------|---------|
| 08 | `08_utils_library.py` | `utils.*` utility library: technical indicators, statistics, position sizing | `python examples/08_utils_library.py` |
| 09 | `09_attribution.py` | Performance attribution: `brinson_attribution`, `simple_factor_analysis` | `python examples/09_attribution.py` |
| 10 | `10_index_concept.py` | Index / concept / sector: constituent stocks, sector rotation | `python examples/10_index_concept.py` |
| 11 | `11_portfolio_backtest.py` | Portfolio backtest: `StrategyConfig`, `PortfolioRiskMonitor` | `python examples/11_portfolio_backtest.py` |
| 12 | `12_paper_trade.py` | Paper trading: `run_paper_trade`, webhook notifications | `python examples/12_paper_trade.py` |
| 13 | `13_ashare_sentiment.py` | A-share sentiment: North-bound capital, margin trading, limit up/down, composite sentiment | `python examples/13_ashare_sentiment.py` |
| 14 | `14_portfolio_risk.py` | Portfolio risk management: VaR, correlation, concentration, circuit breaker | `python examples/14_portfolio_risk.py` |

---

## Real-World Projects (15–20): Complete Strategy Implementations

| # | File/Directory | Strategy | Core Technique | Command |
|---|----------------|----------|----------------|---------|
| 15 | `15_bollinger_strategy.py` | Bollinger Bands mean reversion | `utils.boll()`, ATR trailing stop | `python examples/15_bollinger_strategy.py` |
| 16 | `16_macd_volume.py` | MACD trend following | `utils.macd()`, volume confirmation | `python examples/16_macd_volume.py` |
| 17 | `17_multi_factor.py` | Multi-factor stock selection | Z-Score ranking, North-bound capital gating | `python examples/17_multi_factor.py` |
| 18 | `18_grid_trading.py` | Grid trading | Price grids, range-bound oscillation detection | `python examples/18_grid_trading.py` |
| 19 | `19_sr_portfolio/` | Support/Resistance portfolio | S/R levels, RSI/MACD confirmation | `python examples/19_sr_portfolio/run_backtest.py` |
| 20 | `20_all_weather_alpha/` | All-Weather Alpha | Multi-factor + sector rotation + risk management | `python examples/20_all_weather_alpha/run_backtest.py` |

---

## Trading Cost Standards

All examples use a unified 2024 fee schedule (`examples/_defaults.py`):

| Cost | Rate | Description |
|------|------|-------------|
| Stamp duty | 0.05% | Charged only on sells (halved from August 2023) |
| Commission | 0.025% | Both buy and sell (includes regulatory fees) |
| Minimum commission | 5 CNY | Per trade |

---

## Shared Infrastructure

- **`examples/_defaults.py`** — Unified trading costs, stock codes, relative dates, data validation
- **`tests/test_examples_smoke.py`** — Smoke tests: syntax checks, import checks, code conventions

---

## Running Notes

- Backtest examples output reports to the `reports/` directory
- Example 12 (paper trading) is a long-running script; use `Ctrl+C` to stop
- In local backtests, `order*` calls are order requests: they are filled at the **next trading day's open** price (T+1 settlement)
- For first-time runs, it is recommended to pre-download data with `python examples/06_local_data.py --download`
