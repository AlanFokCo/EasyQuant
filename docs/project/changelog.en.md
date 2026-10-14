# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Removed

- **Removed Web Strategy Studio** (2026-10-10) — `web_strategy_studio/` (FastAPI backend + React frontend) has been removed from the repository; the project refocuses on the core backtesting library `eqlib`. Related documentation (user guide, deployment guide, FAQ entries, homepage card, and navigation) has been removed as well.

### eqlib Core — Correctness (P0)

#### Fixed

- **Annualization basis unified to 244 trading days** — `TRADING_DAYS_PER_YEAR` (244, the A-share correct value) is now imported from `eqlib.constants` everywhere it was previously hardcoded as 252. Affected: `eqlib/scientific/statistics.py`, `eqlib/scientific/risk.py`, `eqlib/scientific/overfitting.py`, `eqlib/utils/stats.py` (`rolling_sharpe`, `downside_deviation`), `eqlib/attribution.py` (`_calc_alpha_beta` and `analyze_returns`). The same backtest now produces matching Sharpe ratios across all modules — previously the same daily returns could yield different annualized values depending on which code path computed them.
- **OrderCost default commission rates updated** — `eqlib/objects.py:OrderCost` now defaults to `open_commission=close_commission=0.00025`, aligning with `examples/_defaults.py:DEFAULT_ORDER_COST` and the 2023-08-28 stamp-duty cut. The explicit `close_tax` default remains `None`: when unset, the statutory stamp duty applies date-aware (0.05% on/after 2023-08-28, 0.1% before); `examples/_defaults.py` pins 0.0005, suitable for backtests on/after 2023-08-28.
- **MLSelector honest naming** — `target='forward_return_5d'` now raises `NotImplementedError` instead of silently computing past returns. The default target remains `past_return_5d` (backward-compatible) but its docstring explicitly warns that it uses historical returns as labels — not a true forward-looking model. For true forward-return prediction, users must supply `label_data` as a panel DataFrame.
- **`MLSelector` constructor signature completed** — `label_data` and `custom_features` parameters are now exposed in the public API (previously only accessible via internals), enabling panel-label training and user-supplied feature functions.
- **`walk_forward_analysis` is now a true rolling window** — Replaced the previous single-backtest-and-slice proxy with a real walk-forward loop: the `[start_date, end_date]` range is divided into multiple train/test windows that slide forward by `step` days. Each window runs a fresh backtest on the train segment (in-sample) and the test segment (out-of-sample), and per-window Sharpe / return / max-drawdown are aggregated into `oos_is_ratio` and `is_sharpe_decay`. The dict-input path (slicing a pre-computed equity curve) is retained for backward compatibility.
- **Cornish-Fisher VaR** — `eqlib/utils/stats.py:value_at_risk` and `eqlib/scientific/risk.py:value_at_risk` now accept `method='cornish_fisher'`, adjusting the parametric (normal) VaR for sample skew and excess kurtosis. Better suited for A-share daily returns, which are typically negatively skewed and heavy-tailed — plain `parametric` tends to underestimate tail risk.
- **Statistical ddof consistency** — `eqlib/scientific/risk.py` now uses `ddof=1` (sample standard deviation) everywhere, matching `eqlib/attribution.py` and `eqlib/scientific/statistics.py`. Previously a few code paths used `ddof=0`, producing slightly different Sharpe/Sortino values for the same input series.
- **`examples/18_grid_trading.py` fixed** — Original grid strategy generated 0 trades over the test period (MDD 97.4%). Rewrote `market_open` with level-crossing trigger logic (buy when price crosses DOWN to a lower grid level, sell when it crosses UP to a higher level), reduced grid levels from 10 to 8, shortened range lookback from 60 to 30 days, and added a 5% rebuild threshold to refresh the grid when the price range drifts. New result: 146 trades, MDD -19%, win rate 71.9%.
- **Examples 21-24 normalized** — ML examples now use `examples._defaults` for trading costs and dates (instead of hardcoded values), removed `sys.path.insert(0, '.')` (provided by `pip install -e .`), and added module-level docstrings with number / title / teaching objectives / run command. Example 21 changed `target='forward_return_5d'` → `past_return_5d` to align with the honest naming above.

### eqlib Core — Market Rules & Data Honesty (2026-10 audit fixes)

The following changes alter backtest results produced by older versions and are labelled accordingly.

#### Added

- **Notification functions promoted to top-level API** — `set_notification_webhook` / `enable_notification` / `notify_signal` can now be imported directly (`from eqlib import ...`); previously they required deep imports from `eqlib.engine` / `eqlib.notification`.

#### Changed (⚠️ breaking)

- **⚠️ `check_price_limit` default flipped from `False` to `True`** — buys opening at limit-up and sells opening at limit-down are unfillable by default (order cancelled with `Order.cancel_reason` recorded). Limits are board- and date-aware: main board ±10%, ST ±5% (inject point-in-time status via `set_option('st_status_map', ...)`), ChiNext ±10% before / ±20% after the 2020-08-24 registration reform, STAR ±20%, BSE ±30%; limits are computed off the last genuinely traded close (not updated during suspensions) and rounded to the fen. The old behavior (no check) systematically flattered momentum/limit-up-chasing strategies; to reproduce it, set `set_option('check_price_limit', False)` explicitly.
- **⚠️ Trading calendar now follows the exchange calendar** instead of the union of universe data (built-in 2020–2026 calendar, online calendars as fallback outside that range). A single stock's missing data no longer removes that trading day, and backtest windows are no longer silently truncated by delisted stocks.
- **⚠️ Suspension semantics unified to same-day cancellation** — orders on suspension days are cancelled the same day with a recorded `cancel_reason` (`"no price data"` for a missing bar, `"suspended"` for zero volume), never deferred to the resumption day.
- **⚠️ Delisted positions are force-liquidated** — after more than `delist_gap_days` (default 30 trading days) without a bar, at the last close, recorded as `DELIST_LIQUIDATE` in the trade log; `delisted_position_handling="keep"` keeps the position and `delisted_liquidation_haircut` models a liquidation discount (e.g. total loss).
- **⚠️ Trade win rate / profit-loss ratio / per-stock P&L now include both-side fees** — FIFO matching amortizes buy commission into cost and deducts sell fees (commission + stamp duty) from proceeds, consistent with the cash ledger; the old fee-blind accounting systematically overstated win rates and profit factors.
- **⚠️ Brinson attribution rewritten as a true single-period BHB decomposition** — allocation + selection + interaction now equals the active return by construction (the old implementation averaged three pseudo-effects and did not close); `sector_data` genuinely drives sector grouping; new return keys `portfolio_return`, `benchmark_return`, `benchmark_model` and per-sector `sectors` breakdown.
- **⚠️ `alpha` / `beta` / `information_ratio` return `NaN` when the benchmark is unavailable** — replacing the old silent defaults of 0.0/1.0/0.0; HTML/MD reports render "N/A" with a methodology note, and JSON marks the corresponding targets as `pass: null`.
- **Paper trading gains market-session gating** — no matching, data fetching or user callbacks before 09:15 or after 15:00 (CST); the day's first fill waits for the open call auction to complete (09:25); orders with empty quotes stay pending instead of being cancelled; user callbacks get a circuit breaker (disabled after 3 consecutive failures) so exceptions no longer escape the main loop and kill the process.

#### Fixed

- **Look-ahead leaks through low-level data APIs during backtests** — `fetch_stock_data` / `get_money_flow` / `get_billboard_list` / `fetch_minute_data` / `check_golden_cross` are uniformly truncated to T-1 during decision-time callbacks (matching `get_price`), with pure-future requests short-circuited; research mode and paper trading are unaffected.
- **Snapshot API protection rolled out to the remaining public endpoints** — `get_valuation` / `get_extras` / `get_concept_stocks` / `get_industry_stocks` / `get_current_data` / `get_current_data_object` / `scan_market` / `get_financial_screen` / `get_restriction_release` now share the `get_fundamentals` in-session guard (`FutureWarning` inside backtests, `ValueError` with `avoid_future_data=True`); previously even strict mode silently leaked current PE/PB, ST status, full-market spot snapshots, board membership and unlock schedules into historical backtests.
- **`load_stock_local` truncated inside backtest sessions** — future rows in local CSVs can no longer reach a running backtest (same cutoff semantics as `fetch_stock_data`); engine preload and the post-loop benchmark read are explicitly exempt via `_unrestricted_fetch`, and research mode / paper trading are unaffected.
- **`get_fundamentals` is not point-in-time safe** — the `date` parameter is ignored (the sources carry no disclosure-date history); calls inside a backtest now emit a `FutureWarning`, escalated to `ValueError` with `set_option('avoid_future_data', True)`; the duplicate `eqlib.get_fundamentals` definitions have been unified into a single implementation.
- **Paper call-auction callback ordering** — when the loop rolls over to a new day during the 09:15–09:25 auction window, `before_trading_start` no longer runs after the day's first `handle_data`; the day's first fill still waits for the auction to complete (09:25).
- **Dual benchmark sourcing in reports** — benchmark metrics in reports now uniformly use the engine-recorded benchmark NAV series (same source as the charts), falling back to the chart-derived series only when missing and labelling it as such.
- **Silent network fallback with `use_local=True`** — falling back to the network per-security after the overwrite guard rejects a local file now emits a WARNING and records the securities in `result["data_diagnostics"]["local_fallback"]`.
- **`Order.cancel_reason`** — cancellation reasons are now stored on the Order object for cancelled/expired orders, enabling programmatic auditing.

#### Examples

- **Backtest examples now enable slippage by default** — `examples/_defaults.py` adds `DEFAULT_SLIPPAGE = FixedSlippage(0.001)`, wired into each backtest example's `initialize` via `set_slippage(DEFAULT_SLIPPAGE)`; example outputs are therefore more conservative than the old zero-slippage results.
- **NaN-friendly metric printing in examples** — Alpha/Beta render as `N/A` instead of `+nan%` when the benchmark is unavailable (new `format_pct` / `format_num` helpers in `examples/_defaults.py`).
- **Stamp-duty date sensitivity disclosed** — `_defaults.py` comments and the README note that the pinned 0.05% rate applies on/after 2023-08-28; for long-history backtests use `close_tax=None` (date-aware statutory rate).

### eqlib Core — Notification & Data Interface Fixes (2026-10-13)

#### Fixed

- **Order-event notifications actually fire** — `enable_notification(["queued", "filled"])` previously accepted the configuration but the engine never pushed anything; in paper/live sessions, order-queued and order-filled events (with fill price, amount, commission and partial-fill flag) are now pushed automatically to the configured DingTalk/Feishu webhook. Backtests stay completely silent regardless of the configured events. Any notification failure is logged and returns `False` — it never interrupts trading.
- **`get_financial_screen` `min_roe` / `min_revenue` / `min_profit` now effective** — these parameters were accepted but silently ignored; they now filter on the most recent essentially-complete quarterly report: `min_roe` in percent, `min_revenue` / `min_profit` in yuan, and passing any of them adds `roe` / `revenue` / `profit` columns to the result. Early in a disclosure window (fewer than 2000 reporters) the previous period is used instead; when no report is available the function fails closed with an empty `DataFrame` and a warning instead of pretending the filters were applied.
- **New `AlertLevel.NORMAL`** — `daily_check()` returns `NORMAL` when nothing triggered (the old baseline was always `YELLOW`, so even a clean report displayed a warning — a recipe for alert fatigue); any trigger implies at least `YELLOW`, and escalation rules are unchanged. ⚠️ Behavior change: code treating `report.alert_level == AlertLevel.YELLOW` as "all clear" should check `NORMAL` instead.

#### Tests

- **`tests/evaluator/test_wheel.py` offline semantics** — the isolated-install audit now skips via `pytest.skip` when the package index is unavailable (DEP-004) instead of failing; slow networks can raise the per-command timeout (default 600s) via `EQ_WHEEL_COMMAND_TIMEOUT`; hosts that can only reach PyPI through a mirror can set `EQ_WHEEL_PIP_INDEX_URL` / `EQ_WHEEL_PIP_TRUSTED_HOST` to pick the index used for the isolated install explicitly (`--isolated` itself ignores pip config files).

### Web Strategy Studio

#### Security

- **Real JWT authentication** — `studio_api/auth.py:get_current_user` now validates JWT bearer tokens (or short-lived SSE query tokens), looks up the user in the database, checks `is_active`, and verifies session revocation via `UserSession`. Previously the function was a stub that always returned a demo user, defeating the protected routes.
- **`ensure_admin_user` sets `role=ROLE_ADMIN`** — Admin user created on startup now actually has admin privileges. Also refuses to start without `EQ_ADMIN_PASSWORD` unless `EQ_STUDIO_TESTING=1`.

### Documentation

#### Added

- Tutorial 11 (ML Selection) — both `docs/tutorials/11-ml-selection.md` and `.en.md` now use the 2024 fee rates.
- `docs/reference/api-ml.md` — `MLSelector` constructor signature now shows `label_data` and `custom_features`; new sections for `check_feature_drift` and `auto_tune_selector`.
- `docs/reference/api-scientific.md` — `walk_forward_analysis` documented with the new true rolling-window behavior, including return values (`oos_is_ratio`, `is_sharpe_decay`, per-window `train_start/end` / `test_start/end`).
- `docs/reference/api-risk.md` — Cornish-Fisher VaR method documented.
- `docs/tutorials/index.md` and `.en.md` — fixed stale "Example N" numbering that did not match the actual file names.

### CI/CD

#### Fixed

- `doc-sync.yml` now installs docs extras via `pip install -e ".[docs]"` instead of a hardcoded package list — `mkdocs-git-revision-date-localized-plugin` was missing, causing `mkdocs build --strict` to fail.
- Studio Tests Backend (Python 3.10/3.11), Studio Tests Frontend, and Doc Sync Check workflows all pass.

---

## [1.0.3] — 2026-05-23

### Web Strategy Studio

#### Added

- Auto-logout on authentication failure (401 response) with seamless redirect to login page
- Preset users configuration via `users.yaml` file (recommended) or `EQ_PRESET_USERS` environment variable
- Smart polling for history panel — only polls when there are active (running/queued) runs

#### Changed

- Removed registration page — users must be pre-configured by server
- Fixed sidebar navigation buttons not responding to clicks
- Added loading indicators for login button, stock search, and backtest runs
- Enhanced button hover effects with visual feedback
- Translated key UI labels to Chinese (e.g., "Initial Capital", "Use Local Data")
- Added `aria-live="polite"` for toast notifications, improved keyboard navigation

#### Fixed

- Race condition in `run_queue.py` — semaphore acquisition order to prevent queue corruption
- Stream hub buffer operations — added async lock for concurrent buffer access
- Stock picker search cancellation — AbortController cancels previous requests
- Unmount state handling — added `mountedRef` to prevent setState on unmounted components
- JWT leak in URLs — fixed JWT token appearing in URLs when opening reports in new tabs

#### Security

- Hardened JWT handling and token validation
- Filtered sensitive environment variables (`EQ_JWT_SECRET`, `EQ_ADMIN_PASSWORD`) from subprocess
- Removed unauthenticated static reports mount — reports now served through authenticated API only

### eqlib Core

#### Fixed

- NaN handling in Sharpe, Sortino, max_drawdown, and beta calculations — returns stable values for edge cases

### Documentation

#### Added

- Web Studio section in README, user guide, tutorials, and FAQ
- 6 new Web Studio FAQ entries (login, deployment, troubleshooting)

#### Changed

- Improved Quick Start sections with PyPI vs source install guidance
- Updated web_studio.md with auto-logout mechanism and preset users configuration

### GitHub Pages

#### Added

- "Web Studio" hero card with icon on homepage
- Emoji icons for all hero cards
- Search keyboard shortcut hint
- Focus-visible states for keyboard navigation accessibility

#### Changed

- Enhanced hero card hover effects with elevation animation and shadow
- Added back-to-top fade-in animation
- Added navigation active indicator (blue accent bar)
- Optimized responsive layout for mobile devices
- Added print-friendly styles

### CI/CD

#### Fixed

- Studio Tests workflow: ruff lint errors, `@types/node` for frontend TypeScript
- Backend pytest: asyncio loop handling and queue isolation tests
- bcrypt 4.x compatibility: replaced passlib with bcrypt directly

---

## [1.0.2] — 2026-05-15

### Security

- CORS `allow_origins` configurable via `EQ_STUDIO_CORS_ALLOWED_ORIGINS`
- Subprocess environment filtered to prevent host secrets leaking
- `StreamHub` cleans up empty entries to prevent unbounded memory growth

### Web Strategy Studio

- Dockerfile adds non-root `studio` user and `HEALTHCHECK`
- `cancel_run` awaits subprocess exit before committing "cancelled" to DB
- Backtest report modal uses native Lightweight Charts rendering
- Metrics comparison table uses real LTVC mini area charts
- Python 3.9 compatibility with legacy typing syntax

### Backtest Correctness (P0)

- Fixed look-ahead bias in stock selection filters
- Fixed alpha/beta `fillna(0)` contaminating benchmark returns
- Fixed monthly rebalance skipping when month-start is a holiday
- Added optional price-limit enforcement (`set_option('check_price_limit', True)`)
- Fixed MaxSharpe arithmetic-mean annualization (now uses geometric formula)

### HTML Report

- Added RSI(14), MACD(12,26,9), Bollinger Bands(20,2) indicators
- Added indicator toggle panel on K-line chart
- Added crosshair-linked legend for real-time values

### Backtest Correctness Fixes (P0) (continued from Unreleased)

Users of previous versions should re-run their backtests.  Several bugs
caused strategies to appear significantly more profitable than they would be
in practice.

#### C1 — Look-ahead bias in stock selection filters (previous results inaccurate)
- **Root cause:** `filter_low_price_stocks`, `filter_high_pe_stocks`, and
  `fetch_factor_data` called the live-data API (`get_current_data`) even
  during historical backtests, filtering stocks with *today's* PE/price.
- **Fix:** In backtest mode (preloaded OHLCV panel), OHLCV fields now use the
  preloaded bar at `context.current_dt`; PE/PB return NaN with a warning
  instead of silently using the live snapshot.

#### C2 — Alpha/beta `fillna(0)` contaminates benchmark returns (previous results inaccurate)
- **Root cause:** `_calc_alpha_beta` and `fama_french_analysis` treated
  missing benchmark days as "0% return" via `reindex(...).fillna(0)`,
  biasing beta downward and alpha upward.
- **Fix:** Use raw intersection / `dropna` series.

#### C3 — Monthly rebalance skips when month-start is a holiday
- **Root cause:** `_should_run_schedule` checked `day.day == N`; A-share
  January 1 is always a holiday so `monthly:1` never fired.
- **Fix:** New `_is_first_trading_day_ge(day, n)` fires on the first trading
  day ≥ N using the preloaded trading calendar.

#### C4 — No price-limit enforcement
- **Fix:** Added `_get_price_limit_ratio()` (10% main board, 20% ChiNext/STAR)
  and an optional check via `set_option('check_price_limit', True)` (default
  False — existing backtests unaffected).

#### C5 — MaxSharpe arithmetic-mean annualization (previous Sharpe values too high)
- **Root cause:** `_annual_stats` used `mean * 252`, which diverges
  significantly from geometric return at high volatility.
- **Fix:** Geometric formula: `(1 + port_ret).prod() ** (252/n) - 1`.

#### C6 — Paper-trade fills orders before any strategy orders exist
- **Fix:** Added `_warmup_done` flag; skips `_fill_pending_orders` on the
  first calendar-day transition.

### Added

- `simple_factor_analysis()` — renamed from `fama_french_analysis()` to
  accurately reflect that it does **not** implement the Fama-French 3-factor
  model.  The old name is retained as a deprecated alias with a `DeprecationWarning`.
- `walk_forward()` and `WFAResult` in `eqlib.wfa` — walk-forward / rolling
  out-of-sample validation framework.
- `StrategyConfig.use_local` field — promotes `use_local` from a hardcoded
  `True` to a user-configurable parameter in `run_portfolio_backtest`.
- Glossary page added to the documentation site (now at `docs/explanation/glossary.md`).
- `tools/profiling/` directory for performance benchmarking scripts (moved
  from `examples/20_all_weather_alpha/`).

### HTML Report — TradingView-Style Indicators

- **RSI(14)** — Welles Wilder EMA-based RSI oscillator with 70/30/50 reference
  lines and 30/70 overbought/oversold zones.
- **MACD(12,26,9)** — MACD line, signal line, and histogram with zero-line
  reference.
- **Bollinger Bands(20,2)** — Upper/middle/lower bands overlay on the K-line chart.
- **Indicator Toggle Panel** — Floating buttons on the K-line chart to
  show/hide MA, BB, Volume, and Support/Resistance independently.
- **Crosshair-Linked Legend** — Real-time overlay showing OHLC, MA values,
  RSI, MACD/Signal/Hist, BB bands, and volume at the current cursor position.

### Changed

- `attribute_history(..., fq='post')` now raises `ValueError` in backtest mode
  (the preloaded panel only stores `qfq` / forward-adjusted data); use `fq='pre'`.
- `_get_trading_days()` now prefers `ak.tool_trade_date_hist_sina()` over the
  601390 stock history (more complete, no listing-date gaps).
- `data._cache` and `data._spot_cache` are now protected by `threading.Lock`
  for safe use in multi-threaded back-testing scenarios.
- Sortino ratio now uses MAR = 0 (industry standard) and `ddof=0`, consistent
  with the Sharpe ratio implementation.
- `analyze_returns()` excess Sharpe is now the correct Information Ratio
  (`excess.mean() / excess.std() * sqrt(252)`); the prior double-subtraction
  of the risk-free rate has been removed.

### Fixed

- Monthly schedule: `monthly:1` now correctly fires on the first A-share
  trading day of each month (previously missed January and months where
  day 1 falls on a weekend/holiday).
- `fama_french_analysis` / `_calc_alpha_beta` no longer distort beta/alpha
  by treating missing benchmark days as 0% returns.

### Web Strategy Studio

- **S1:** CORS `allow_origins` is now configurable via
  `EQ_STUDIO_CORS_ALLOWED_ORIGINS`; defaults to `localhost:5173` and
  `localhost:8080` only (removes the `["*"]` + `allow_credentials=True`
  violation).
- **S2:** `security_scanner.py` now documents its limitations as a
  "friendly lint" tool, not a security sandbox.
- **S3:** Subprocess environment is now filtered to an allowlist (`PATH`,
  `HOME`, `EQ_*`, etc.) to prevent host secrets from leaking into user
  strategy processes.
- **S4:** `StreamHub` now cleans up empty `run_id` entries after every
  unsubscribe and on terminal events (`done`/`error`), preventing
  unbounded memory growth on long-running instances.
- **S5:** `backtest_executor.py` now parses `"Backtest progress N/M"` lines
  from the engine's stdout for true fractional progress instead of the
  crude `log_lines // 2` heuristic.
- **S6:** Idempotency map entries now expire after 24 h (configurable via
  `EQ_STUDIO_IDEMPOTENCY_TTL_SEC`); a background task purges stale entries.
- **S7:** Dockerfile adds a non-root `studio` user and a `HEALTHCHECK` for
  container orchestrators.
- **S8:** `cancel_run` now awaits subprocess exit (up to 5 s) before
  committing "cancelled" to the DB, eliminating duplicate SSE `done` events.
- **S9:** Backtest report modal now uses **native Lightweight Charts**
  rendering (replacing the iframe approach). The new `ReportViewer` component
  renders all chart types — K-line, cumulative returns, drawdown, daily P&L,
  RSI, MACD — with synchronized time scales and responsive resizing.
- **S10:** Metrics comparison table now uses **real LTVC mini area charts**
  for equity curve sparklines instead of SVG approximations, with green/red
  coloring based on cumulative direction.
- **S11:** New backend endpoint `GET /api/v1/runs/{run_id}/report/data`
  serves the full report.json with all chart data arrays for native rendering.
- **S12:** Python 3.9 compatibility — all `str | None` / `list[T]` / `dict[K, V]`
  type annotations converted to `Optional[T]` / `List[T]` / `Dict[K, V]`
  across the entire backend codebase, with ruff rules adjusted to accept
  the legacy typing syntax.

### Documentation

- M10: mkdocs nav now points to the split-by-chapter user guide (since
  restructured into `docs/tutorials/` and `docs/how-to/`); the old
  single-page version is still accessible but no longer in the top nav.
- M11: CHANGELOG, CONTRIBUTING, and SECURITY added to the nav under
  "Project Updates".
- E6: utils reference page added to the API reference section of the nav
  (now at `docs/reference/utils.md`).
- E9: Glossary page added (now at `docs/explanation/glossary.md`).

### Risk Disclosures Added

- Strategy examples 14, 15, 16, 17 now include `RISK DISCLOSURE` headers
  warning that examples are for teaching purposes only and should not be
  deployed to live trading without thorough out-of-sample validation.

---

## [0.1.1] — 2025-07 (P0 patch)

Never tagged. The P0 backtest-correctness fixes planned for the 0.1.x line
ultimately shipped with [1.0.2] (see above).

---

## [0.1.0] — 2025-05

Initial release.

> Example numbering has since been reorganized; the paths below map to the current `examples/` directory.

### Added

- Event-driven backtest engine (`eqlib/engine.py`)
- Fluent query API (`eqlib/stock_query.py`)
- Data layer with akshare integration and local CSV caching
- Strategy templates: MACD+Volume, Bollinger, Grid Trading, Multi-Factor
- Matplotlib chart generation and Markdown report export
- PTrade/QMT adapter for live deployment
- Comprehensive test suite
- Dual index charts (CSI300 + SSE) in HTML backtest reports
- Support/Resistance strategy (`examples/19_sr_portfolio/`)
- Stock selection strategy (`examples/22_stock_selection_strategy.py`)
- Local data backtest (`examples/06_local_data.py`) with CSV cache
- Portfolio backtesting with equal-weight rebalancing (`examples/11_portfolio_backtest.py`)
- Brinson attribution and factor analysis
- HTML report with interactive charts via Lightweight Charts
- MkDocs documentation site with CI/CD via GitHub Pages
