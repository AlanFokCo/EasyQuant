# EasyQuant

A quantitative strategy and backtesting tool for the **China A-share market**.

This project provides the `eqlib` Python package — the core library that implements the event-driven backtesting engine, data APIs, and analysis tools.

[中文文档](README_zh.md) · [用户手册](doc/user_guide.md) · [API 参考](doc/api_reference.md) · [示例](examples/)

---

## Features

- **Event-driven backtesting** — initialize, scheduled functions, daily bars, portfolio tracking
- **A-share data** — daily OHLCV, minute K-lines, tick data, real-time quotes, fundamentals, money flow
- **Position management** — buy/sell by shares, value, or target; automatic lot-size rounding and commission calculation
- **Risk analysis** — Sharpe, Sortino, max drawdown, alpha/beta, Brinson attribution, Fama-French factor analysis
- **Portfolio optimization** — minimum variance, maximum Sharpe, risk parity
- **Paper trading** — run strategies live with real-time market data
- **Utility library** — technical indicators (MA, MACD, RSI, KDJ, Bollinger, ATR), statistical tools, position sizing (Kelly, ATR-based, fixed fractional)
- **Reports** — chart (PNG), Markdown, and JSON output

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

---

## Documentation

- [**User Guide**](doc/user_guide.md) — tutorial: writing strategies, running backtests, reading reports
- [**API Reference**](doc/api_reference.md) — full API: structures, parameters, usage
- [**Utils Reference**](doc/utils_reference.md) — calculation tools: indicators, statistics, money management, support/resistance

---

## License

MIT
