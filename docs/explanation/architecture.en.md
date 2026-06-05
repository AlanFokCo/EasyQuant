# System Architecture

EasyQuant consists of the core library `eqlib` and the Web Strategy Studio. This page explains how they relate and what each module does.

---

## Overall Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        User Layer                                │
│  Python Scripts / Jupyter Notebook / Web Strategy Studio         │
└─────────────┬───────────────────────────┬───────────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────────────┐
│  Strategy API            │  │  Web Studio                      │
│  initialize(context)     │  │  FastAPI Backend (studio_api/)   │
│  handle_data(ctx, data)  │  │  ┌───────────────────────────┐  │
│  run_daily(func)         │  │  │ isolated_runner.py         │  │
│  order*()                │  │  │ (runs backtests in          │  │
└─────────────┬───────────┘  │  │  isolated subprocesses)     │  │
              │               │  └───────────┬───────────────┘  │
              ▼               └──────────────┼───────────────────┘
┌─────────────────────────────────────────────┼───────────────────┐
│  Backtest Engine (eqlib/engine.py)          │                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │                   │
│  │ Scheduler │  │  Order   │  │ Portfolio│  │                   │
│  │run_daily  │  │ Matching │  │ Manager  │  │                   │
│  │run_weekly │  │ T+1 check│  │ Pos/Cash │  │                   │
│  └──────────┘  │ 100-lot  │  │ Fees     │  │                   │
│                └──────────┘  └──────────┘  │                   │
└─────────────┬───────────────┬───────────────┘                   │
              │               │                                    │
              ▼               ▼                                    │
┌──────────────────┐ ┌─────────────────────────────────────────────┤
│  Data Layer       │ │  Analysis & Reporting Layer                 │
│  eqlib/data.py   │ │  eqlib/attribution.py  (Brinson / Factor)   │
│  ┌────────────┐  │ │  eqlib/report.py       (HTML/PNG/MD/JSON)  │
│  │ AKShare API │  │ │  eqlib/scientific/     (overfitting /      │
│  │ Local CSV   │  │ │                         bias detection)    │
│  │ Cache Mgmt  │  │ └─────────────────────────────────────────────┤
│  └────────────┘  │
└──────────────────┘
```

## Module Responsibilities

| Module | File | Responsibility |
|--------|------|----------------|
| **Backtest Engine** | `eqlib/engine.py` | Event loop, scheduling, order matching, portfolio management |
| **Data API** | `eqlib/data.py` | Historical quotes, real-time snapshots, fundamentals, A-share specific data |
| **Trade Execution** | `eqlib/trade.py` | Order placement, T+1 checks, 100-lot rounding, commission calculation |
| **Performance Analysis** | `eqlib/attribution.py` | Sharpe, Alpha/Beta, Brinson attribution, factor analysis |
| **Report Generation** | `eqlib/report.py` | Interactive HTML reports, PNG charts, Markdown, JSON |
| **Stock Selection** | `eqlib/selection.py` | TopNSelector, MultiFactorSelector, periodic rebalancing |
| **Utilities** | `eqlib/utils/` | 40+ technical indicators, statistical analysis, money management |
| **Notifications** | `eqlib/notification.py` | DingTalk / Feishu webhook trade signals |
| **Scientific Validation** | `eqlib/scientific/` | Overfitting detection, statistical confidence, bias detection |

## Data Flow

```text
User-defined strategy → initialize() → run_daily() registers callbacks
                                              │
                                              ▼
Each trading day: before_trading_start → handle_data / market_open → after_trading_end
                                              │
                                              ├── Call data API for quotes
                                              ├── Compute signals
                                              ├── Call order*() to place orders (queued)
                                              │
                                              ▼
                              Next trading day open: orders matched (avoids look-ahead bias)
                                              │
                                              ▼
Backtest complete → analyze_returns() → generate_report()
```

## Web Studio Architecture

The Web Strategy Studio adds a web interface layer on top of `eqlib`:

- **Frontend**: React + Vite + TypeScript, using Monaco Editor and Lightweight Charts
- **Backend**: FastAPI, running backtests in **isolated subprocesses** via `isolated_runner.py` to prevent strategy code from affecting the server
- **Communication**: SSE (Server-Sent Events) for real-time backtest log streaming
- **Storage**: SQLite (strategy code and backtest results) + filesystem (report artifacts)
