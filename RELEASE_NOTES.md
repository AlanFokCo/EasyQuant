# Release Notes — Unreleased (pending v1.1.0)

**Date:** 2026-10-10 (in progress)

## Overview

Adversarial-review hardening release: fixes from the 2026-10-09 three-way
stability/accuracy/reliability audit of the backtest engine, agent/evaluator
toolchain. Contains **breaking changes** around the
canonical volume unit and disk-cache format — read the migration notes below.

---

## Breaking Changes & Migration

- **Volume unit is now shares (股), not lots (手)**. akshare providers deliver
  daily/minute volume in lots; `_canonicalize_ohlcv` now multiplies by 100 at
  the ingestion boundary so every downstream consumer (volume caps,
  `attribute_history`, strategies) sees shares. **Action required**: any
  user-strategy threshold expressed in lots must be scaled ×100 (e.g.
  `min_avg_volume` 100,000 → 10,000,000).
- **Disk cache format bumped to version 2**. Cache/CSV metadata now records
  `volume_unit: "shares"`; legacy lot-based cache files are refused and will
  be re-downloaded on first use. Local CSVs without the sidecar metadata are
  likewise re-fetched.
- **`OrderCost.close_tax` default changed**: previously hard-coded 0.05%, it
  now defaults to `None`, meaning the statutory date-dependent stamp duty is
  applied (0.1% before 2023-08-28, 0.05% on/after, per MoF Announcement 2023
  No. 33). Explicitly passing `close_tax=` takes precedence.
  Backtests that leave `close_tax` unset and span pre-2023-08-28 sells will
  show higher (correct) tax costs. Note that `examples/_defaults.py`
  explicitly pins `close_tax=0.0005` per the repo's educational-default
  convention (see AGENTS.md), so the bundled examples keep the flat
  contemporary rate; pass `close_tax=None` to opt into the statutory
  date-based rate.

---

## Known Limitations

- **Anchor-drift guard needs overlapping bars**: the qfq drift detector
  compares close-price ratios on ≥2 overlapping dates. All current fetch
  paths request full ranges, so overlaps are always large; a future
  incremental tail-fetcher with <2 overlapping bars would merge a seam
  undetected.
- **Drift reset discards cached history**: when anchor drift is detected the
  legacy cached frame is replaced by the freshly fetched window (coverage
  metadata is reset accordingly, so subsequent wider requests refetch).
- **Index volumes are not unit-canonicalised**: index daily bars
  (`stock_zh_index_daily*`, csindex) keep provider volume units (lots); only
  stock/ETF frames are converted to shares. Do not mix benchmark and stock
  volume figures in strategy logic.

---

## eqlib Core

### Critical Fixes

- **Walk-forward analysis crash**: `walk_forward` no longer crashes on
  `recorded_values` being a list of per-day dicts (P0-1).
- **qfq cache merge price seam**: disk-cache merges now detect adjustment
  anchor drift on overlapping dates (consistent close-ratio deviation >0.5%);
  a drifted legacy frame is dropped and coverage metadata reset instead of
  silently concatenating a fake price jump across an ex-dividend date (P1-8).
- **Tencent fallback double-converted volume**: `_fetch_from_tencent`
  canonicalised internally *and* the fallback chain canonicalised again, so
  whenever EastMoney and Sina both failed, Tencent-sourced volume was inflated
  100×.  Canonicalisation now happens exactly once at the fetch boundary, and
  the write side of both the disk cache and `save_stock_local` refuses to
  merge into legacy lots-unit files (they are replaced, with fresh metadata).
- **`history()`/`get_price()` bypass of preloaded data**: series APIs now
  resolve bare and exchange-suffixed codes against the preloaded snapshot and
  serve a point-in-time-safe fast path when the loaded adjustment matches the
  request (P1-6, P1-7).

### Bug Fixes

- **Minute-bar date bounds**: a bare `end_date` now keeps that day's intraday
  bars instead of truncating at midnight (P1-1).
- **`data.current()` / `data.attribute_history()` in strategies**: `_LazyData`
  exposes both methods and degrades to `None`/empty instead of raising when no
  bar is available (P1-2).
- **Paper trading**: price-limit checks fetch `prev_close` with the correct
  signature (P1-3); the loop idles on weekends/holidays using the exchange
  calendar (P1-4); scheduled functions fire at most once per day instead of
  re-firing inside the ±60s polling window (P1-5).
- **DingTalk notifications**: the HMAC signature is URL-encoded, fixing
  `errcode 310000` verification failures (P1-10).
- **RSI conventions**: all-up days return 100 and flat days 50 instead of
  degenerate values; `LinearRegression.feature_importances_` handles
  single-feature (1-D coefficient) models; `report.py` no longer emits
  invalid `\/` JSON escapes; bundled exchange calendar adds 12 missing dates;
  `get_trade_days(count=…)` applies the count after filtering;
  `attribute_history`/`history` reject non-positive `count`.

---

## Agent / Evaluator / Scripts

- **Live evaluator gate**: the live CI job now runs with `--strict` so P0/P1
  findings block; provider-outage classification matches network markers only
  on pytest exception/summary lines, and contract timeouts always report as
  P1 instead of downgrading to "unavailable".
- **Optimizer NaN hardening**: non-finite metrics (NaN/inf) always fail
  requirement evaluation; aggregates propagate NaN instead of averaging it
  away.
- **Audit log integrity**: JSONL entries sanitize non-finite floats to `null`
  and serialize with `allow_nan=False`; session IDs gain microseconds plus a
  uuid suffix to prevent same-second collisions.
- **Calendar coverage**: an expired bundled calendar escalates to P1.
- **Wheel build**: source copies exclude virtualenvs/caches/reports/data,
  bounding copy time.
- **`check_doc_sync.py`**: doc cost rates are parsed from
  `examples/_defaults.py` at runtime (no stale hard-coded patterns) and orphan
  `.en.md` translations are flagged.
- **Example smoke tests**: `examples/03_run_backtest.py` now has a real
  offline runtime-execution test asserting a BUY+SELL round trip, in addition
  to the compile/import checks.

---

## Removed

- **Web Strategy Studio removed from the repository**: the
  `web_strategy_studio/` FastAPI backend + React frontend has been dropped so
  the project refocuses on the core backtesting library (`eqlib`). The
  studio CI workflow, pre-commit hooks, and user docs went with it. The
  unreleased studio hardening work from this audit cycle is superseded by the
  removal; deployments already running the studio service are unaffected but
  receive no further updates from this repository.

---

# Release Notes — v1.0.3

**Release Date:** 2026-05-23

## Overview

This release focuses on Web Strategy Studio enhancements, security hardening, bug fixes, and documentation improvements. It includes significant UX optimizations for the browser-based strategy development platform, fixes for eqlib financial calculations, and comprehensive documentation updates.

---

## Web Strategy Studio

### New Features

- **Auto-logout on authentication failure**: Users are automatically logged out when JWT token expires or becomes invalid (401 response), with seamless redirect to login page
- **Preset users configuration**: Add support for configuring preset users via `users.yaml` file (recommended) or `EQ_PRESET_USERS` environment variable
- **Smart polling for history panel**: Backtest history list only polls when there are active (running/queued) runs, reducing unnecessary API calls

### UX Improvements

- **Fixed sidebar navigation**: Navigation buttons (history, compare, data) now respond correctly to clicks
- **Removed registration page**: Simplified login flow — users must be pre-configured by server
- **Loading indicators**: Added loading states for login button, stock search, and backtest runs
- **Hover states**: Enhanced button hover effects with visual feedback
- **Translated labels**: Key UI labels translated to Chinese (e.g., "初始资金", "使用本地数据")
- **Accessibility**: Added `aria-live="polite"` for toast notifications, improved keyboard navigation

### Bug Fixes

- **Race condition in run_queue.py**: Fixed semaphore acquisition order to prevent queue corruption
- **Stream hub buffer operations**: Added async lock for concurrent buffer access
- **Stock picker search cancellation**: AbortController cancels previous requests when new search starts
- **Unmount state handling**: Added `mountedRef` to prevent setState on unmounted components
- **JWT leak in URLs**: Fixed JWT token appearing in URLs when opening reports in new tabs

### Security

- **Harden authentication**: Improved JWT handling and token validation
- **Environment variable leak**: Filter sensitive variables (`EQ_JWT_SECRET`, `EQ_ADMIN_PASSWORD`) from subprocess environment
- **Static reports mount removed**: Reports now served through authenticated API endpoint only

---

## eqlib Core

### Bug Fixes

- **NaN handling in financial calculations**: Added `pd.isna()` and `np.isfinite()` checks in:
  - Sharpe ratio calculation (returns 0 when std is NaN or ≤ 0)
  - Sortino ratio calculation
  - Max drawdown calculation
  - Beta calculation
- **Index data fetch alignment**: Fixed alignment between index returns and strategy returns

---

## Documentation

### Updates

- **README (English & Chinese)**: Added Web Studio section, improved Quick Start guidance (PyPI vs source install)
- **User Guide**: Added Web Studio alternative for browser-based users
- **Tutorials**: Added Web Studio as learning path option
- **FAQ**: Added 6 new Web Studio questions (login, deployment, troubleshooting)
- **Web Studio Docs**: Updated authentication section with auto-logout mechanism and preset users configuration

### GitHub Pages Enhancements

- **New hero card**: Added "Web 工作室" (Web Studio) card on homepage
- **Card icons**: Added emoji icons for each hero card (🚀, 📖, 🎓, 🌐, 🔧)
- **Hover effects**: Enhanced card hover with elevation animation and shadow
- **Search shortcut hint**: Shows "⌘K 快捷搜索" when search input focused
- **Focus-visible states**: Improved accessibility for keyboard navigation
- **Back-to-top animation**: Added fade-in-up animation
- **Navigation indicator**: Added blue accent bar for active navigation items
- **Responsive layout**: Optimized for mobile devices
- **Print styles**: Added print-friendly output

---

## CI/CD

- **Studio Tests workflow**: Fixed ruff lint errors, added `@types/node` for frontend TypeScript
- **Backend pytest**: Stabilized asyncio loop handling and queue isolation tests
- **bcrypt compatibility**: Replaced passlib with bcrypt directly for bcrypt 4.x compatibility

---

## Installation

```bash
pip install easyquant-eqlib --upgrade
```

Or from source:

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install .
```

---

## Upgrade Notes

### Web Studio Users

If you're using Web Strategy Studio:

1. **Update preset users**: Create `web_strategy_studio/backend/users.yaml` to configure users:
   ```yaml
   preset_users:
     - username: your_username
       password: your_password
   ```

2. **JWT secret for production**: Set stable JWT secret to prevent logout after restart:
   ```bash
   export EQ_JWT_SECRET="your-secure-random-key"
   ```

3. **Admin password**: Change default admin password:
   ```bash
   export EQ_ADMIN_PASSWORD="your-secure-password"
   ```

### eqlib Users

No breaking changes. NaN handling improvements ensure stable output for edge cases (empty data, zero volatility).

---

## Full Changelog

See [v1.0.2...v1.0.3](https://github.com/AlanFokCo/EasyQuant/compare/v1.0.2...v1.0.3)

---

## Contributors

- @AlanFokCo
- @copilot (GitHub Copilot assisted fixes)
- Claude Opus 4.7 (AI-assisted development)
