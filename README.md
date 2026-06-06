<div align="center">

<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="280" alt="EasyQuant logo"/></a>

# EasyQuant

Event-driven quantitative backtesting framework for China A-share market.

[![Tests](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/test.yml?label=Tests)](https://github.com/AlanFokCo/EasyQuant/actions/workflows/test.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/deploy-docs.yml?label=Docs)](https://AlanFokCo.github.io/EasyQuant/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/AlanFokCo/EasyQuant/blob/main/LICENSE)

<p>
<a href="README_zh.md">中文文档</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/">Docs Site</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/tutorials/">Tutorials</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/reference/">API Reference</a>
</p>

</div>

---

## Features

- **Event-driven backtesting** — `initialize` → `run_daily` → `handle_data` (JoinQuant/Zipline compatible)
- **A-share data** — Daily/minute/tick, fundamentals, money flow, north-bound capital, limit up/down stats
- **Risk analysis** — Sharpe, Sortino, max drawdown, alpha/beta, Brinson attribution
- **Portfolio risk** — VaR, correlation, concentration, kill switch
- **Paper trading** — Run strategies with real-time data + DingTalk/Feishu notifications
- **PTrade/QMT adapter** — One-click export to broker platforms
- **Web Studio** — Browser-based strategy development (no Python install needed)

---

## Quick Start

```bash
pip install easyquant-eqlib

python -c "from eqlib import *; print('eqlib OK')"
```

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist['close'].iloc[-1] > hist['close'].mean() * 1.02:
        order_value(g.security, context.portfolio.available_cash)

result = run_strategy(initialize, start_date='2024-01-01',
                      end_date='2024-12-31', securities=['601390'])
```

---

## Documentation

| Resource | Description |
|----------|-------------|
| [**Docs Site**](https://AlanFokCo.github.io/EasyQuant/) | Full documentation with search and dark theme |
| [**Tutorials**](https://AlanFokCo.github.io/EasyQuant/tutorials/) | Zero to production, 11 step-by-step guides |
| [**How-to Guides**](https://AlanFokCo.github.io/EasyQuant/how-to/) | Task-oriented guides by scenario |
| [**API Reference**](https://AlanFokCo.github.io/EasyQuant/reference/) | All public APIs with parameters and examples |
| [**Examples**](examples/) | 20+ runnable example scripts + Web Studio bonus strategies |
| [**FAQ**](https://AlanFokCo.github.io/EasyQuant/project/faq/) | Troubleshooting and common questions |

---

## Installation

```bash
# From PyPI (recommended)
pip install easyquant-eqlib

# From source (for contributors)
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install -e ".[dev]"
python -m pytest tests/
```

**Requirements:** Python 3.10+ · macOS / Linux / Windows

---

## Contributing

See [CONTRIBUTING.md](docs/project/contributing.md) for guidelines.

## License

[MIT License](LICENSE)

> **Disclaimer:** This project is for educational and research purposes only. It does not constitute investment advice.
