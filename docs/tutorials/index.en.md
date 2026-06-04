<div align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="../assets/logo.svg" width="240" alt="EasyQuant"/></a>
</div>

# Tutorials

This series covers everything from zero experience to live deployment, spanning trend following, mean reversion, sector rotation, and multi-factor stock selection.

!!! tip "Reading Format"

    Starting from Tutorial 00, each tutorial begins with an **"Overview"** table at the top, so you can quickly assess the **goal, estimated time, and prerequisites**; the full table of contents and in-depth explanations follow as usual.

**First time here? Start with: [Tutorial 00 — Environment Setup & First Run / Quantitative Trading Fundamentals](00-getting-started.md)** (Python 3.10+, `pip install .`, running `examples/03_run_backtest.py`, opening HTML reports, quantitative basics). **Documentation hub:** [How-To Overview](../how-to/index.md) (user guide, API index, FAQ, report metrics reference).

---

## Directory Structure

```
docs/tutorials/
├── prerequisites/          ← Prerequisite knowledge (read as needed)
│   ├── index.md            ← Prerequisites overview
│   ├── python-basics.md    ← Python syntax, pandas/numpy, virtual environments
│   ├── technical-concepts.md  ← Moving averages, RSI, MACD, Bollinger Bands, ATR, KDJ, etc.
│   └── ashare-knowledge.md ← A-share code rules, T+1, limit up/down, indices, fees
├── 00-getting-started.md   ← Environment setup, first backtest, quant basics (required reading)
├── 01-first-strategy.md    ← Write a dual moving average strategy
├── 02-backtesting.md       ← Interpret backtest reports and metrics
├── 03-optimization.md      ← Parameter tuning, portfolio optimization, attribution analysis
├── 04-live-trading.md      ← Paper trading to live deployment
├── 05-rsi-mean-reversion.md  ← RSI mean reversion strategy
├── 06-sector-rotation.md   ← Sector rotation strategy
├── 07-multi-factor.md      ← Multi-factor stock selection
├── 08-combined-strategy.md ← Combined strategy (All-Weather Alpha)
├── 09-param-optimization.md  ← Strategy parameter optimization and auditing
└── 10-ashare-data-risk.md  ← A-share specific data and risk control
```

---

## Prerequisites (Read as Needed)

If you lack a foundation in any of the following areas, we recommend reading the corresponding prerequisite file before starting Tutorial 00:

| File | Content | Who It's For |
|------|---------|-------------|
| [Python Basics & Environment Setup](prerequisites/python-basics.md) | Syntax cheat sheet, core pandas/numpy usage, virtual environments | Never written Python before |
| [Technical Analysis Fundamentals](prerequisites/technical-concepts.md) | OHLCV, moving averages, RSI, MACD, Bollinger Bands, ATR, KDJ, ADX, support/resistance | Never worked with technical indicators |
| [A-Share Market Fundamentals](prerequisites/ashare-knowledge.md) | Stock codes, T+1 settlement, limit up/down, major indices, ST (Special Treatment) stocks, fees & taxes, fundamental data | No A-share investment experience |

→ Full prerequisites index: [prerequisites/index.md](prerequisites/index.md)

---

## First-Day Checklist (Recommended in Order)

1. Install and verify:
   ```bash
   # PyPI install (recommended, no repo clone needed)
   pip install easyquant-eqlib
   # Or install from source (from repo root)
   # pip install .
   python -c "from eqlib import *; print('eqlib OK')"
   ```
2. Run your first complete report (run from the repo directory):
   ```bash
   python examples/03_run_backtest.py
   ```
3. Open `reports/*.html` to view metric cards, drawdown curves, and trade records.
4. For quick offline validation, run the local data example (optional):
   ```bash
   python examples/06_local_data.py --download-all
   python examples/06_local_data.py
   ```
5. Minimal functional validation (optional):
   ```bash
   python examples/01_fetch_data.py
   pip install -e ".[dev]"
   python -m pytest tests/
   ```

> **Alternative: Web Strategy Studio**
> If you prefer a browser-based interface, try the [Web Strategy Studio](https://github.com/AlanFokCo/EasyQuant/tree/main/web_strategy_studio/).
> No Python environment or repo clone needed — write strategies, run backtests, and view reports directly in your browser.
> Ideal for users who want to skip environment setup. See [Web Studio Documentation](../how-to/web-studio.md).

After completing these steps, continue with [Tutorial 01](01-first-strategy.md) and [Tutorial 02](02-backtesting.md).

---

## Tutorial List

### Prerequisites (Optional, Read as Needed)

| File | Summary | Est. Reading |
|------|---------|-------------|
| [Python Basics & Environment Setup](prerequisites/python-basics.md) | Variables, functions, core pandas/numpy operations, virtual environments | 20 min |
| [Technical Analysis Fundamentals](prerequisites/technical-concepts.md) | OHLCV, MA / RSI / MACD / Bollinger Bands / ATR / KDJ / ADX, support & resistance | 25 min |
| [A-Share Market Fundamentals](prerequisites/ashare-knowledge.md) | Stock code format, T+1 settlement, limit up/down, common indices, ST stocks, fees & taxes | 20 min |

### Environment & Getting Started

| # | Tutorial | Topic | Est. Reading |
|---|----------|-------|-------------|
| 00 | [**Environment & Quant Basics**](00-getting-started.md) | Environment setup, first backtest, quantitative concepts, strategy components, common errors | 25 min |
| 01 | [Write Your First Strategy](01-first-strategy.md) | Write a dual moving average strategy, run a backtest | 20 min |
| 02 | [Backtest Validation](02-backtesting.md) | Interpret reports, risk metrics, portfolio backtesting | 20 min |
| 03 | [Strategy Optimization & Improvement](03-optimization.md) | Parameter tuning, portfolio optimization, attribution analysis | 20 min |
| 04 | [Paper Trading to Live](04-live-trading.md) | Paper trading validation, PTrade/QMT export & deployment | 15 min |

### Strategy-Specific Tutorials (Read by Interest)

| # | Tutorial | Strategy Type | Core Techniques | Est. Reading |
|---|----------|--------------|-----------------|-------------|
| 05 | [RSI Mean Reversion Strategy](05-rsi-mean-reversion.md) | Mean reversion | RSI, Bollinger Band double confirmation, stop-loss | 20 min |
| 06 | [Sector Rotation Strategy](06-sector-rotation.md) | Sector rotation | Momentum scoring, equal-weight rebalancing, industry API | 20 min |
| 07 | [Multi-Factor Stock Selection](07-multi-factor.md) | Factor selection | Z-score normalization, factor combination, IC testing | 25 min |
| 08 | [All-Weather Alpha Combined Strategy](08-combined-strategy.md) | Combined strategy | Multi-factor + sector rotation + RSI/Bollinger/MACD + ATR stop-loss | 30 min |
| 09 | [Strategy Parameter Optimization & Auditing](09-param-optimization.md) | Parameterization & tools | PARAMS, `optimizer.py`, audit logs, review checklist | 20 min |
| 10 | [A-Share Data & Risk Control](10-ashare-data-risk.md) | A-share specific data | North-bound capital, margin trading, limit up/down, restricted share unlock, portfolio risk control | 25 min |

---

## Learning Paths

Based on your background and goals, choose the most suitable learning path:

### Path A: Zero-Foundation Onboarding (Recommended for Beginners)

```
00 Environment & Quant Basics → 01 First Strategy → 02 Backtest Validation → 03 Strategy Optimization → 04 Live Deployment
```

Suited for: First-time quantitative traders who want a systematic overview of the entire workflow

### Path B: Trend Following Strategy Track

```
01 First Strategy (Dual MA) → 02 Backtest Validation → 03 Strategy Optimization (Stop-Loss/Market Filter) → 06 Sector Rotation
```

Suited for: Aspiring trend traders focused on momentum and moving average breakouts

### Path C: Mean Reversion Strategy Track

```
01 First Strategy → 02 Backtest Validation → 05 RSI Mean Reversion → 03 Strategy Optimization
```

Suited for: Traders looking to buy low and sell high in range-bound markets, focused on RSI and Bollinger Bands

### Path D: Stock Selection & Portfolio Track

```
01 First Strategy → 02 Backtest Validation → 07 Multi-Factor Selection → 06 Sector Rotation → 03 Strategy Optimization
```

Suited for: Users building multi-stock portfolio strategies, focused on quantitative stock selection

### Path E: Fast-Track to Live Trading

```
01 First Strategy → 02 Backtest Validation → 04 Paper Trading to Live
```

Suited for: Users with some foundation who want to deploy strategies to PTrade/QMT as quickly as possible

### Path F: Combined Strategy in Practice (Recommended for Advanced Users)

```
05 RSI Mean Reversion → 06 Sector Rotation → 07 Multi-Factor Selection → 08 Combined Strategy
```

Suited for: Users who have mastered individual strategies and want to fuse all techniques into a single production-grade strategy

### Path G: Parameter Optimization & Auditing (Recommended for Users with Some Foundation)

```
01 First Strategy → 02 Backtest Validation → 03 Strategy Optimization → 09 Parameter Optimization & Auditing
```

Suited for: Users who want to tune parameters via scripts or custom workflows while maintaining auditable records

---

## Browse by Strategy Type

| Strategy Type | Tutorial | Related Examples |
|--------------|----------|-----------------|
| **Trend Following (Dual MA)** | [Tutorial 01](01-first-strategy.md), [Tutorial 03](03-optimization.md) | [Example 02](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/02_write_strategy.py), [Example 03](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/03_run_backtest.py) |
| **Mean Reversion (RSI)** | [Tutorial 05](05-rsi-mean-reversion.md) | [Example 15](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) |
| **Mean Reversion (Bollinger Bands)** | [Tutorial 05 Section 8](05-rsi-mean-reversion.md#8comparisonwithbollingerbandsstrategy) | [Example 15](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) |
| **MACD Trend Confirmation** | [Tutorial 03 Section 3.4](03-optimization.md#34-macd-confirmation) | [Example 16](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/16_macd_volume.py) |
| **Sector Rotation** | [Tutorial 06](06-sector-rotation.md) | [Example 10](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py) |
| **Multi-Factor Selection** | [Tutorial 07](07-multi-factor.md) | [Example 17](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py), [Example 09](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/09_attribution.py) |
| **Combined Strategy (All-Weather Alpha)** | [Tutorial 08](08-combined-strategy.md) | [Example 20](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md) |
| **Grid Trading** | — | [Example 18](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/18_grid_trading.py) |
| **Support/Resistance** | — | [Example 08](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/08_utils_library.py), [Example 19](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md) |
| **Portfolio Backtesting** | [Tutorial 02 Section 8](02-backtesting.md#8-portfolio-backtesting) | [Example 11](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/11_portfolio_backtest.py) |
| **Parameter Optimization & Auditing** | [Tutorial 09](09-param-optimization.md) | [agent/optimizer.py](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/optimizer.py), [agent/strategy_template.py](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/strategy_template.py) |
| **Paper Trading / Live Trading** | [Tutorial 04](04-live-trading.md) | [Example 12](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/12_paper_trade.py) |
| **A-Share Specific Data & Risk Control** | [Tutorial 10](10-ashare-data-risk.md) | — |

---

## Prerequisites

- Python **3.10+** (see [Tutorial 00](00-getting-started.md))
- eqlib installed: `pip install easyquant-eqlib` (PyPI) or `pip install .` / `pip install -e .` (source)
- Python basics (variables, functions, loops, conditionals) → No foundation? See [Python Basics & Environment Setup](prerequisites/python-basics.md)
- Technical indicator basics (moving averages, RSI, etc.) → No foundation? See [Technical Analysis Fundamentals](prerequisites/technical-concepts.md)
- A-share market knowledge (T+1 settlement, limit up/down, stock codes, etc.) → No foundation? See [A-Share Market Fundamentals](prerequisites/ashare-knowledge.md)

**Troubleshooting & API quick reference:** [FAQ](../project/faq.md), [API Reference](../reference/index.md).

---

## Difference Between Tutorials and Examples

| | Tutorials (docs/tutorials/) | Examples (examples/) |
|--|---------------------------|---------------------|
| Format | Markdown docs + code snippets | Runnable Python scripts |
| Goal | Systematically learn concepts and methods | Quick reference and copy-paste-run |
| Content | Explains "why" and "how" | Shows "what the code looks like" |

Recommendation: Use tutorials to learn concepts, then run examples to deepen understanding.

---

## Real-World Case Studies

After completing the tutorials, explore these real strategy cases:

### All-Weather Alpha Combined Strategy (Complete Production-Grade Case)

**[Tutorial 08: All-Weather Alpha Combined Strategy](08-combined-strategy.md)** —
Fuses all tutorial strategy techniques into a single complete production-grade combined strategy, including multi-factor stock selection, sector rotation,
RSI/Bollinger Bands/MACD/ATR technical signals, support/resistance levels, and lifecycle callbacks, with complete backtesting and paper trading code.

**[Example 20: All-Weather Alpha Combined Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md)** —
Complete runnable combined strategy code, including the strategy module, backtest script, and paper trading script.

### Support/Resistance Portfolio Strategy (Complete Live Trading Case)

**[Example 19: Support/Resistance Portfolio Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** —
A complete multi-stock portfolio strategy case study, including pre-generated backtest reports (HTML/PNG/Markdown/JSON)
that can be opened directly in a browser to review strategy performance, or re-run via backtesting.

**Strategy highlights:** 8 A-share stocks across different sectors, combining support/resistance + RSI + MACD + ATR stop-loss,
total return of +137% over the backtest period (2020-2026).
