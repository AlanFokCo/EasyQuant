# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

EasyQuant is an event-driven quantitative backtesting framework for the **China A-share market**.

- **Core library**: `eqlib` (Python package under `eqlib/`)
- **Data source**: `akshare` (free China stock market data)
- **Web Studio**: FastAPI backend + React frontend at `web_strategy_studio/`

---

## Common Commands

### eqlib Core Library

```bash
# Install (editable, for development)
pip install -e ".[dev]"

# Run tests
python -m pytest tests/

# Run single test file
python -m pytest tests/test_imports.py -v

# Run single backtest (smoke test)
python examples/03_run_backtest.py

# Verify installation
python -c "from eqlib import *; print('eqlib OK')"

# Build docs locally
mkdocs serve
```

### Web Strategy Studio

```bash
cd web_strategy_studio

# Install all dependencies + build symbol manifest
npm run install:all

# Run backend + frontend in dev mode
npm run dev:all        # API on :8080, frontend on :5173

# Or with Docker
docker compose up --build

# Backend tests only
cd backend && pip install -e ".[dev]" && pytest tests/ -v
```

### Linting & Pre-commit

Pre-commit hooks run automatically on `git commit`. They include:

- **General**: trailing-whitespace, end-of-file-fixer, check-yaml/toml, mixed-line-ending (LF)
- **Backend (`web_strategy_studio/backend/`)**: ruff (lint + import sort), black (format), mypy (type check)
- **Frontend (`web_strategy_studio/frontend/src/`)**: ESLint + Prettier

Note: pre-commit hooks do NOT cover `eqlib/` core — use `ruff` manually if needed.

---

## Architecture

### eqlib Core (`eqlib/`)

Event-driven backtest engine with JoinQuant/Zipline-compatible API.

**Key files:**
- `engine.py` — Backtest engine: `run_backtest`, `run_daily`, `run_paper_trade`
- `data.py` — Data API: `get_price`, `attribute_history`, `fetch_stock_data`, fundamentals, indices
- `trade.py` — Order execution: `order`, `order_target`, `order_value`
- `attribution.py` — Performance analysis: `analyze_returns`, `brinson_attribution`, `simple_factor_analysis`, `grade_strategy`, `diagnose_bottleneck`, `recommend_params`
- `report.py` — HTML/PNG/Markdown/JSON report generation (dark theme, Agent-First JSON)
- `notification.py` — DingTalk/Feishu webhook alerts for paper trading
- `stock_query.py` — Fluent query API: `query()`, `valuation()`, `get_fundamentals()`
- `selection.py` — Periodic stock selection with factor screening
- `data_cache.py` — Disk caching + local CSV data store
- `constants.py` — Single source of truth for `RISK_FREE_RATE` (0.03) and `TRADING_DAYS_PER_YEAR` (244)
- `portfolio_risk.py` — VaR, correlation, concentration risk, Kill Switch
- `portfolio.py` — Multi-strategy portfolio backtest mode
- `wfa.py` — Walk-forward analysis
- `ptrade_adapter.py` — PTrade/QMT broker platform export

**Subpackages:**
- `eqlib/scientific/` — Scientific validation layer (overfitting detection, statistical confidence, bias detection, extended risk metrics, platform comparison, unified `validate_backtest()` orchestration)
- `eqlib/utils/` — Four submodules: `indicators` (MA, MACD, RSI, KDJ, Bollinger, ATR, etc.), `stats` (rolling metrics, regression, VaR, drawdown), `money` (Kelly, ATR sizing, risk parity, volatility normalize), `levels` (pivot points, support/resistance, Fibonacci, trailing stop)

**Strategy lifecycle:**
```
initialize(context) → run_daily(handle_data, time='every_bar') → handle_data(context, bar)
```

Orders are filled at the **next trading day's open** to avoid look-ahead bias.

### API Stability Legend

Every export in `eqlib/__init__.py` carries one of three stability markers (visible in the source comments):

| Label | Meaning |
|-------|---------|
| `STABLE` | Name and signature won't change in minor/patch releases. Breaking changes require a major bump + deprecation notice. |
| `EXPERIMENTAL` | API may change in any release. Don't build production code against it. |
| `DEPRECATED` | Will be removed. A `DeprecationWarning` is emitted. Use the suggested replacement. |

When adding or changing a public API, add the appropriate marker comment. Example:
```python
# Data  [STABLE]
from eqlib.data import get_price, ...
# Financial data  [EXPERIMENTAL]
from eqlib.data import get_financial_abstract, ...
```

### The `g` Proxy (Concurrent Backtests)

`eqlib.g` is a `_GProxy` instance (not a plain `GlobalObject`) that delegates attribute access to the active `BacktestSession._g`. This makes concurrent backtests thread-safe — each session has its own `GlobalObject`, and `g.security = '601398'` routes to the current thread's session.

User code treats `g` as a normal object: `g.security`, `g.lookback = 20`. Internally, `__getattr__`/`__setattr__` delegate through `_state.get_session()`. Don't instantiate `_GProxy` or bypass it — always use the module-level `g`.

### Bare vs Suffixed Stock Codes

A critical convention used throughout the codebase:

| Context | Format | Example |
|---------|--------|---------|
| Data APIs (`get_price`, `attribute_history`, `fetch_stock_data`) | Bare code | `"601398"` |
| Trading APIs (`order`, `order_target`, `order_value`) | Suffixed code | `"601398.XSHG"` |

The suffixes are `.XSHG` (Shanghai) and `.XSHE` (Shenzhen). See `examples/_defaults.py` for both forms (`STOCKS` dict = bare, `STOCKS_TRADE` dict = suffixed). Mixing them up causes silent data misses or trade failures.

### Web Strategy Studio (`web_strategy_studio/`)

FastAPI + React web interface for browser-based strategy development.

**Backend (`studio_api/`):**
- `app.py` — ASGI app with CORS, auth, lifespan
- `config.py` — Pydantic settings (env-vars)
- `db.py` — Async SQLAlchemy engine + session factory
- `models.py` — ORM models: Strategy, Run, User
- `routers/` — Domain routes: strategies, runs, auth, data_mgmt, lint, symbols
- `backtest_executor.py` — Subprocess driver for isolated backtest execution
- `run_queue.py` — Asyncio run queue with progress streaming

**Frontend (`frontend/src/`):**
- React + Vite + TypeScript
- Zustand for global state
- SSE for real-time run progress

**Key pattern:** Backtests run in isolated subprocesses (`isolated_runner.py`) to prevent strategy code from affecting the server process.

### Agent Utilities (`agent/`)

Support utilities for AI-driven optimization (Claude Code orchestrates, not standalone scripts):

- `optimizer.py` — Reference utility showing rule-based parameter search (not the primary driver)
- `audit_log.py` — Structured JSONL + Markdown audit logging (use directly)
- `strategy_template.py` — Parameterized strategy template with `PARAMS` and `PARAM_RANGES`

---

## Strategy Format for AI Optimization

Strategies must define two module-level dicts:

```python
PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    'stop_loss_pct': 0.08,
    # ...
}

PARAM_RANGES = {
    'fast_period': (2, 20, 1),      # (min, max, step)
    'slow_period': (10, 60, 5),
    # ...
}
```

`initialize` and `handle_data` must read from `PARAMS`:

```python
def initialize(context):
    g.fast_period = PARAMS['fast_period']
```

---

## AI-Driven Optimization Workflow

Claude Code orchestrates the optimization loop directly (not via `agent/optimizer.py`).

### Workflow Steps

1. **Baseline backtest** — Run strategy via `run_backtest()`, capture metrics with `analyze_returns()`
2. **Evaluate** — Compare against requirements (Sharpe ≥ 1.0, max drawdown ≤ 20%, etc.)
3. **Diagnose** — Identify failing metrics and root causes using decision table
4. **Propose adjustments** — Change at most 2 parameters per iteration, step-by-step from `PARAM_RANGES`
5. **Apply changes** — Edit `PARAMS` in strategy source file directly (visible in `git diff`)
6. **Code review** — Spawn sub-agent to verify: values in range, cross-param constraints, params used in code
7. **Audit log** — Write structured entry via `agent/audit_log.py`
8. **Repeat** until requirements met or max iterations

### Parameter Adjustment Rules

| Failing metric | Action |
|---------------|--------|
| Sharpe too low | Increase `vol_confirm_mul` or `slow_period`; or decrease `position_pct` |
| Max drawdown too large | Decrease `stop_loss_pct` or `position_pct` |
| Win rate too low | Increase `vol_confirm_mul` or `rsi_oversold` |
| Too few trades | Decrease `vol_confirm_mul` or widen RSI bands |
| Alpha negative | Review entry signals; increase `fast_period` |

### Constraints

- `fast_period` < `slow_period`
- `rsi_oversold` < `rsi_overbought`
- `stop_loss_pct` in (0, 0.30)

---

## Key APIs

```python
from eqlib import *

# Run backtest
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000
)

# Analyze returns
metrics = analyze_returns(result, risk_free_rate=0.03)
# Returns: sharpe_ratio, max_drawdown, annual_return, alpha, beta, win_rate_trade,
#          monthly_returns, rolling_sharpe_60d, per_stock_pnl, drawdown_periods, etc.

# Grade strategy (6-dimension scoring)
grade_info = grade_strategy(metrics)
# Returns: overall (S/A/B/C/D), score, dimensions, weakest, strongest, summary_text

# Diagnostics and parameter recommendations
diagnostics = diagnose_bottleneck(metrics, grade_info)
recommendations = recommend_params(metrics, grade_info, current_params, param_ranges)

# Paper trading with notifications
run_paper_trade(initialize, webhook_url="...")

# Factor analysis
brinson_attribution(result)      # Allocation/selection/interaction
simple_factor_analysis(result)   # Market beta, alpha, momentum proxy
# Note: fama_french_analysis(result) is deprecated — use simple_factor_analysis

# Stock screening
query('000001.XSHE').valuation().pe.lt(20).cap.gt(50e9).get_fundamentals()
```

---

## Metrics Reference

| Metric | Target | Source |
|--------|--------|--------|
| `sharpe_ratio` | > 1.0 | `analyze_returns()` |
| `sortino_ratio` | > 1.5 | `analyze_returns()` |
| `max_drawdown` | < 20% (i.e., > -0.20) | `analyze_returns()` |
| `annual_return` | > 0 (beat cash) | `analyze_returns()` |
| `win_rate_trade` | > 40% | `analyze_returns()` |
| `alpha` | > 0 | `simple_factor_analysis()` |
| `beta` | 0.3–1.3 | `simple_factor_analysis()` |
| `trade_count` | ≥ 3 per year | `analyze_returns()` |

---

## Test Structure

The test suite in `tests/` has several organizational patterns:

- **`test_examples_smoke.py`** — Syntax, import, and standard checks for every example file (no star imports, no private API usage, `__main__` guards, `_defaults` usage)
- **`test_dim1_credibility.py`, `test_dim2_credibility.py`, `test_dim3_credibility.py`** — Backtest credibility fixes organized by dimension (e.g., price-limit caching, Sortino formula, Calmar ratio guard)
- **`test_p0_fixes.py`, `test_p1_p2_p3_p4_fixes.py`** — Priority-tiered bug fixes (P0 = critical, P1-P4 = lower priority)
- **`test_scientific_*.py`** — Scientific validation layer tests (overfitting, bias, statistics, risk, comparison, validation runner)
- **`test_utils_*.py`** — Utility submodule tests (indicators, levels, money, stats)
- **`conftest.py`** — Adds `web_strategy_studio/backend` to `sys.path` so `studio_api` is importable

Run specific dimensions or tiers:
```bash
python -m pytest tests/test_dim2_credibility.py -v     # Sortino/ddof fixes
python -m pytest tests/test_p0_fixes.py -v              # Critical fixes
python -m pytest tests/test_scientific_overfitting.py -v  # Overfitting detection
python -m pytest tests/ -k "sortino" -v                 # All Sortino-related tests
```

---

## Agent Behavior Guidelines

When optimizing strategies:

1. **Never skip audit logging** — Every iteration must produce a complete audit entry
2. **Never change more than 2 parameters per iteration** — Maintain interpretability
3. **Never modify `eqlib/`** — Core library is not part of optimization
4. **Edit strategy files directly** — Use Edit tool on `PARAMS` in source, not in-memory mutation
5. **Spawn sub-agent for code review** — Don't self-review parameter changes
6. **Stop if data download fails** — Don't proceed with incomplete data
7. **Prefer robustness over peak performance** — Consistent Sharpe 1.1 across 3 years beats 2.5 in one year and -0.3 in another

---

## Workflow Rules

These rules govern how changes cascade across the project. Follow them for every modification.

### 1. Documentation Translation Sync

When editing **any** `docs/**/*.md` that has a `.en.md` counterpart, you **MUST** update the English version in the same session.

```
docs/foo.md  →  docs/foo.en.md   (always keep in sync)
```

- **If you add a section** to the Chinese doc → add the same section (translated) to `.en.md`
- **If you remove a section** from the Chinese doc → remove it from `.en.md`
- **If you update example file references** in the Chinese doc → update them in `.en.md`
- **If you create a new doc** without `.en.md` → create the `.en.md` too (or at minimum add a stub with a `<!-- TODO: translate -->` comment)
- **Before committing**: run `python scripts/check_doc_sync.py` to catch any drift

The doc site uses `mkdocs-static-i18n` with `docs_structure: suffix`, so the `.en.md` suffix is what drives the English translation build.

### 2. Example Modification Gate

When modifying **any** file under `examples/`, you MUST:

1. **Run smoke tests**: `python -m pytest tests/test_examples_smoke.py -v -k "<filename>" --tb=short`
2. **If adding/renaming/deleting examples**, also update:
   - `examples/README.md` — example index table
   - `docs/examples/index.md` — detailed index with descriptions
   - Any tutorial docs that reference the changed example
3. **If changing trading costs** in `examples/_defaults.py`, also update:
   - All tutorial docs (both `.md` and `.en.md`) that show `OrderCost` examples
   - `docs/explanation/ashare-market.md` — fee structure table
   - `docs/reference/api-config.md` and `api-trading.md`
4. **If adding a new utility import**, verify it's exported from `eqlib/__init__.py`

### 3. API Change Cascade

When changing a **public API** in `eqlib/` (any function/class listed in `eqlib/__init__.py`):

1. **Update `examples/`** — find and update all example files that use the changed API
2. **Update `docs/tutorials/`** — update tutorial code blocks (both languages)
3. **Update `docs/reference/`** — update the API reference doc
4. **Run full tests**: `python -m pytest tests/ -v --tb=short`
5. **Run smoke tests**: `python -m pytest tests/test_examples_smoke.py -v`
6. **Build docs**: `mkdocs build --strict`

### 4. New Example Checklist

When adding a **new example** to `examples/`:

- [ ] File has module-level docstring with: number, title, description, Teaching Objectives, Expected Output, Run command
- [ ] Uses explicit imports (no `from eqlib import *`)
- [ ] Uses `_defaults` for trading costs, stock codes, and dates
- [ ] Has `if __name__ == "__main__":` guard
- [ ] Passes smoke tests (`tests/test_examples_smoke.py`)
- [ ] Listed in `examples/README.md`
- [ ] Listed in `docs/examples/index.md`
- [ ] Referenced in relevant tutorial docs (if applicable)

### 5. Trading Cost Standards

All trading costs in the project must be consistent:

| Cost | Value | Where defined |
|------|-------|---------------|
| Stamp duty (sell) | 0.05% (`0.0005`) | `examples/_defaults.py` |
| Commission (buy+sell) | 0.025% (`0.00025`) | `examples/_defaults.py` |
| Minimum commission | 5 CNY | `examples/_defaults.py` |

The **single source of truth** is `examples/_defaults.py:DEFAULT_ORDER_COST`. All other references (tutorials, reference docs, how-to guides) must match these values. If rates change, update `_defaults.py` first, then cascade to docs.

### 6. Validation Before Commit

Before committing documentation changes, run:

```bash
# Check doc sync (translations, stale refs, cost consistency)
python scripts/check_doc_sync.py

# Run example smoke tests
python -m pytest tests/test_examples_smoke.py -v

# Build docs (catches broken links, missing pages)
mkdocs build --strict
```

The doc sync script (`scripts/check_doc_sync.py`) validates:
1. Every `docs/*.md` has a corresponding `.en.md` translation
2. No stale example file references (renamed/deleted examples)
3. Trading cost rates in docs match `examples/_defaults.py`
4. No outdated stamp duty (0.001) or commission (0.0003) values

### 7. Commit Message Conventions

| Prefix | Use case | Example |
|--------|----------|---------|
| `docs:` | Documentation changes (always includes .en.md) | `docs: add tutorial 05 (both languages)` |
| `fix:` | Bug fixes | `fix: correct stamp duty rate in examples` |
| `feat:` | New features or examples | `feat: add example 19_sr_portfolio` |
| `chore:` | Cleanup, deletion, reorganization | `chore: remove deprecated examples` |
| `refactor:` | Code restructuring without behavior change | `refactor: extract shared logic in examples` |

Documentation commits should mention both languages when applicable:
- `docs: update tutorial 02 backtesting (zh + en)`
- `docs: fix example references across all tutorials`
