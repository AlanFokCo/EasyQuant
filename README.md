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

EasyQuant includes a built-in **AI agent workflow** that lets Claude Code (or any compatible AI coding agent) run a complete, human-free strategy optimization loop.

### What the agent does

1. Loads your strategy and its tunable `PARAMS` / `PARAM_RANGES`
2. Runs backtests across multiple historical periods
3. Analyzes results with `analyze_returns` (Sharpe, drawdown, win rate, alpha, …)
4. Generates **data-driven** parameter adjustments with explicit rationale
5. Performs a code review before applying each change
6. Repeats until all your requirements are met (or max iterations is reached)
7. Logs every decision to a structured audit trail (JSONL + Markdown)

### Quick start

```bash
# Optimize the bundled template strategy (default requirements)
python agent/optimizer.py

# Optimize your own strategy with custom targets
python agent/optimizer.py \
    --strategy my_strategy.py \
    --min-sharpe 1.0 \
    --max-drawdown 0.20 \
    --max-iterations 15 \
    --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31" "2024-01-01:2024-12-31" \
    --output-strategy my_strategy_optimized.py
```

### Agent configuration

- **[`CLAUDE.md`](CLAUDE.md)** — AI agent configuration recognized by Claude Code.
  Contains the full self-optimization workflow, parameter adjustment rules, audit log format,
  and code review requirements.
- **[`agent/optimizer.py`](agent/optimizer.py)** — Self-optimization orchestrator.
- **[`agent/audit_log.py`](agent/audit_log.py)** — Structured audit logging (JSONL + Markdown).
- **[`agent/strategy_template.py`](agent/strategy_template.py)** — Parameterized strategy template.
- **[`tutorials/10_agent_optimization.md`](tutorials/10_agent_optimization.md)** — Tutorial (Chinese).

### Audit log

Every optimization session writes two files to `audit_log/`:

```
audit_log/
├── session_<timestamp>.jsonl   # machine-readable; query with jq
└── session_<timestamp>.md      # human-readable Markdown report
```

Every parameter change is logged with: the specific metric values that triggered it, the
expected effect, and the code review result. Users can trace every decision back to data.

---

## License

MIT
