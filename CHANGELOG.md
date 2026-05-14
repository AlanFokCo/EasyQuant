# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### ⚠️ Backtest Correctness Fixes (P0)

Users of previous versions should re-run their backtests.  Several bugs
caused strategies to appear significantly more profitable than they would be
in practice.

#### C1 — Look-ahead bias in stock selection filters (⚠️ previous results inaccurate)
- **Root cause:** `filter_low_price_stocks`, `filter_high_pe_stocks`, and
  `fetch_factor_data` called the live-data API (`get_current_data`) even
  during historical backtests, filtering stocks with *today's* PE/price.
- **Fix:** In backtest mode (preloaded OHLCV panel), OHLCV fields now use the
  preloaded bar at `context.current_dt`; PE/PB return NaN with a warning
  instead of silently using the live snapshot.

#### C2 — Alpha/beta `fillna(0)` contaminates benchmark returns (⚠️ previous results inaccurate)
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

#### C5 — MaxSharpe arithmetic-mean annualization (⚠️ previous Sharpe values too high)
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
- Glossary page (`docs/glossary.md`) added to documentation site.
- `tools/profiling/` directory for performance benchmarking scripts (moved
  from `examples/21_combined_strategy/`).

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

### Documentation

- M10: mkdocs nav now points to the split-by-chapter user guide
  (`doc/user_guide/index.md`); the old single-page version is still
  accessible but no longer in the top nav.
- M11: CHANGELOG, CONTRIBUTING, and SECURITY added to the nav under
  "项目动态 / Project Updates".
- E6: `doc/utils_reference.md` added to the API reference section of the nav.
- E9: Glossary page added (`docs/glossary.md`).

### Risk Disclosures Added

- Strategy examples 14, 15, 16, 17 now include `⚠️ RISK DISCLOSURE` headers
  warning that examples are for teaching purposes only and should not be
  deployed to live trading without thorough out-of-sample validation.

---

## [0.1.1] — 2025-07 (P0 patch)

See [Unreleased] section for the full list.  This will be tagged once all
P0 backtest correctness fixes are merged.

---

## [0.1.0] — 2025-05

Initial release.

### Added

- Event-driven backtest engine (`eqlib/engine.py`)
- Fluent query API (`eqlib/stock_query.py`)
- Data layer with akshare integration and local CSV caching
- Strategy templates: MACD+Volume, Bollinger, Grid Trading, Multi-Factor
- Matplotlib chart generation and Markdown report export
- PTrade/QMT adapter for live deployment
- Comprehensive test suite
- Dual index charts (CSI300 + SSE) in HTML backtest reports
- Support/Resistance strategy (`examples/20_sr_strategy/`)
- Stock selection strategy (`examples/22_stock_selection_strategy.py`)
- Local data backtest (`examples/19_local_data_backtest.py`) with CSV cache
- Portfolio backtesting with equal-weight rebalancing (`examples/12_portfolio_backtest.py`)
- Brinson attribution and factor analysis
- HTML report with interactive charts via Lightweight Charts
- MkDocs documentation site with CI/CD via GitHub Pages
