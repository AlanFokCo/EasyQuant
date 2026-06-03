# Installation & Quick Start

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Install `eqlib` and run your first backtest |
    | **Estimated time** | 15 minutes |

---
## 1. Four Steps for Beginners

If this is your first time using EasyQuant, complete this minimal loop first:

1. Install:
   ```bash
   # Install from PyPI (recommended — no need to clone the repo)
   pip install easyquant-eqlib
   # Or install from source (for developers / contributors, from the repo root)
   # pip install .
   ```
2. Verify the import:
   ```bash
   python -c "from eqlib import *; print('eqlib OK')"
   ```
3. Run a full backtest (requires running the example from the repo directory):
   ```bash
   python examples/03_run_backtest.py
   ```
4. Open the latest `.html` file under `reports/` and confirm that charts and metrics display correctly.

Optional tests:

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```

> **Alternative: Web Strategy Studio**
> If you prefer a browser-based interface, try the [Web Strategy Studio](https://github.com/AlanFokCo/EasyQuant/tree/main/web_strategy_studio/).
> No Python environment needed — open your browser to write strategies, run backtests, view reports, and compare metrics.
> See the [Web Studio documentation](web-studio.md) for details.

---

## 2. Introduction & Scope

`eqlib` is a quantitative strategy backtesting framework for the **China A-share market**. It sources data from `akshare`, uses an event-driven strategy API, and supports a complete workflow from backtesting to paper trading.

**Supported use cases:**
- A-share daily / minute-level backtesting
- Strategy development and validation
- Paper trading
- Stock screening / sector rotation / money flow analysis
- Portfolio optimization

**Not supported:**
- Non-A-share instruments: Hong Kong stocks, US stocks, futures, options, cryptocurrencies
- High-frequency T+0 strategies (A-shares operate on a T+1 trading schedule)

---

## 3. Installation

**Requires Python 3.10 or later.**

```bash
# Install from PyPI (recommended)
pip install easyquant-eqlib
# For development (from the repo root): pip install -e .
```

Verify the installation:

```python
from eqlib import *
print("eqlib OK")
```

For more troubleshooting, see the [FAQ](../project/faq.md).

---

