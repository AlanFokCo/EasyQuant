---
hide:
  - navigation.path
---

<div align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="280" alt="EasyQuant logo"/></a>
</div>

# EasyQuant

Event-driven quantitative backtesting framework for the China A-share market.

```bash
pip install easyquant-eqlib
```

<div class="hero-cards">
<a class="hero-card" href="tutorials/00-getting-started/">
<span class="hero-card-icon">🚀</span>
<h3>Getting Started</h3>
<p>From installation to running your first backtest — up and running in 15 minutes.</p>
<span class="card-link">Start →</span>
</a>
<a class="hero-card" href="how-to/">
<span class="hero-card-icon">📖</span>
<h3>How-to Guides</h3>
<p>Find what you need by scenario: writing strategies, running backtests, reading reports.</p>
<span class="card-link">Browse →</span>
</a>
<a class="hero-card" href="tutorials/">
<span class="hero-card-icon">🎓</span>
<h3>Tutorials</h3>
<p>An 11-part series from zero to live trading, with real strategy examples.</p>
<span class="card-link">Learn →</span>
</a>
<a class="hero-card" href="reference/">
<span class="hero-card-icon">🔧</span>
<h3>API Reference</h3>
<p>Parameters, return values, and examples for every public API in <code>eqlib</code>.</p>
<span class="card-link">Reference →</span>
</a>
<a class="hero-card" href="how-to/web-studio/">
<span class="hero-card-icon">🌐</span>
<h3>Web Studio</h3>
<p>Write strategies, run backtests, and view reports — all in your browser.</p>
<span class="card-link">Try it →</span>
</a>
</div>

## Core Capabilities

- **Event-driven backtesting** — `initialize` → `run_daily` → `handle_data`, consistent with JoinQuant / Zipline
- **Comprehensive A-share data** — Daily / minute / tick bars, financial summaries, money flow, northbound capital, limit up/down statistics
- **Risk analysis** — Sharpe / Sortino / Max Drawdown / Alpha & Beta / Brinson attribution
- **Portfolio risk control** — VaR, strategy correlation, concentration risk, Kill Switch circuit breaker
- **Paper trading + PTrade/QMT adapter** — Pre-live verification + one-click export to broker platforms

## Minimal Example

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

> **Order execution model:** `order*` APIs only place orders within the current callback; they are actually filled at the **next trading day's opening price** to avoid look-ahead bias. See [Backtest Execution Model](explanation/backtest-model.md) for details.

## Report Preview

| MACD Trend + Volume | Bollinger Band Mean Reversion | Support/Resistance |
|:---:|:---:|:---:|
| **+103.48%** | **+57.77%** | **+119.97%** |
| [![MACD](assets/tutorials/example_report_macd_volume.png)](assets/tutorials/example_report_macd_volume.png) | [![Bollinger](assets/tutorials/example_report_bollinger.png)](assets/tutorials/example_report_bollinger.png) | [![Support/Resistance](assets/tutorials/example_report_sr_strategy.png)](assets/tutorials/example_report_sr_strategy.png) |

---

!!! info

    This documentation is for learning and research purposes only and does not constitute investment advice.
