# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Removed

- **移除 Web 策略工作室**（2026-10-10）— `web_strategy_studio/`（FastAPI 后端 + React 前端）已从仓库中移除，项目重新聚焦于核心回测库 `eqlib`。相关文档（使用指南、部署指南、FAQ 条目、首页入口与导航）已同步删除。

### eqlib Core — Correctness (P0)

#### Fixed

- **Annualization basis unified to 244 trading days** — `TRADING_DAYS_PER_YEAR` (244, the A-share correct value) is now imported from `eqlib.constants` everywhere it was previously hardcoded as 252. Affected: `eqlib/scientific/statistics.py`, `eqlib/scientific/risk.py`, `eqlib/scientific/overfitting.py`, `eqlib/utils/stats.py` (`rolling_sharpe`, `downside_deviation`), `eqlib/attribution.py` (`_calc_alpha_beta` and `analyze_returns`). The same backtest now produces matching Sharpe ratios across all modules — previously the same daily returns could yield different annualized values depending on which code path computed them.
- **OrderCost defaults updated to 2024 fee rates** — `eqlib/objects.py:OrderCost` now defaults to `close_tax=0.0005`, `open_commission=close_commission=0.00025`, aligning with `examples/_defaults.py:DEFAULT_ORDER_COST` and the 2023-08-28 stamp-duty cut. Cascaded to `eqlib/engine.py`, `eqlib/strategies/*.py`, `eqlib/examples/multi_factor_momentum.py`, `web_strategy_studio/backend/studio_api/routers/strategies.py`, `web_strategy_studio/backend/studio_api/data/templates.json`, `web_strategy_studio/backend/studio_api/data/eqlib_symbols.json`, `agent/strategy_template.py`. The historical 0.001 stamp duty is still applied automatically for dates before 2023-08-28 via the existing date-branch logic.
- **MLSelector honest naming** — `target='forward_return_5d'` now raises `NotImplementedError` instead of silently computing past returns. The default target remains `past_return_5d` (backward-compatible) but its docstring explicitly warns that it uses historical returns as labels — not a true forward-looking model. For true forward-return prediction, users must supply `label_data` as a panel DataFrame.
- **`MLSelector` constructor signature completed** — `label_data` and `custom_features` parameters are now exposed in the public API (previously only accessible via internals), enabling panel-label training and user-supplied feature functions.
- **`walk_forward_analysis` is now a true rolling window** — Replaced the previous single-backtest-and-slice proxy with a real walk-forward loop: the `[start_date, end_date]` range is divided into multiple train/test windows that slide forward by `step` days. Each window runs a fresh backtest on the train segment (in-sample) and the test segment (out-of-sample), and per-window Sharpe / return / max-drawdown are aggregated into `oos_is_ratio` and `is_sharpe_decay`. The dict-input path (slicing a pre-computed equity curve) is retained for backward compatibility.
- **Cornish-Fisher VaR** — `eqlib/utils/stats.py:value_at_risk` and `eqlib/scientific/risk.py:value_at_risk` now accept `method='cornish_fisher'`, adjusting the parametric (normal) VaR for sample skew and excess kurtosis. Better suited for A-share daily returns, which are typically negatively skewed and heavy-tailed — plain `parametric` tends to underestimate tail risk.
- **Statistical ddof consistency** — `eqlib/scientific/risk.py` now uses `ddof=1` (sample standard deviation) everywhere, matching `eqlib/attribution.py` and `eqlib/scientific/statistics.py`. Previously a few code paths used `ddof=0`, producing slightly different Sharpe/Sortino values for the same input series.
- **`examples/18_grid_trading.py` fixed** — Original grid strategy generated 0 trades over the test period (MDD 97.4%). Rewrote `market_open` with level-crossing trigger logic (buy when price crosses DOWN to a lower grid level, sell when it crosses UP to a higher level), reduced grid levels from 10 to 8, shortened range lookback from 60 to 30 days, and added a 5% rebuild threshold to refresh the grid when the price range drifts. New result: 146 trades, MDD -19%, win rate 71.9%.
- **Examples 21-24 normalized** — ML examples now use `examples._defaults` for trading costs and dates (instead of hardcoded values), removed `sys.path.insert(0, '.')` (provided by `pip install -e .`), and added module-level docstrings with number / title / teaching objectives / run command. Example 21 changed `target='forward_return_5d'` → `past_return_5d` to align with the honest naming above.

### eqlib Core — Market Rules & Data Honesty（2026-10 审查修复轮）

本轮修复源自一次覆盖用法、能力、体验、可靠性、准确性的全面对抗性审查（含独立 evaluator 复核）。以下变更会让旧回测结果发生变化，均如实标注。

#### Changed（⚠️ breaking）

- **⚠️ `check_price_limit` 默认从 `False` 翻转为 `True`** — 涨停价开盘的买单、跌停价开盘的卖单默认不可成交（订单取消并记录 `Order.cancel_reason`）。涨跌幅按板块与日期区分：主板 ±10%、ST ±5%（经 `set_option('st_status_map', ...)` 注入时点状态）、创业板 2020-08-24 注册制改革前 ±10% / 后 ±20%、科创板 ±20%、北交所 ±30%；限价按最近真实收盘价（停牌不更新）计算并精确到分。旧行为（不检查）会系统性抬高动量/打板类策略收益，复现旧行为请显式 `set_option('check_price_limit', False)`。
- **⚠️ 交易日历改为交易所日历权威** — 不再由 universe 数据并集推断（内置 2020–2026 日历，越界回退在线日历）。个别股票缺数据不再让该交易日消失，回测区间不再被退市股静默截断。
- **⚠️ 停牌语义统一为当日取消** — 停牌日订单当日取消并记录 `cancel_reason`（`"no price data"`（缺行情）/ `"suspended"`（零成交）），不再顺延至复牌成交。
- **⚠️ 退市持仓强制清算** — 持仓超过 `delist_gap_days`（默认 30 个交易日）无行情即按最后收盘价强制清算，`trade_log` 记录 `DELIST_LIQUIDATE`；可用 `delisted_position_handling="keep"` 保留持仓、`delisted_liquidation_haircut` 模拟清算折价（如面值退市归零）。
- **⚠️ 交易胜率/盈亏比/个股盈亏改为含双边费用口径** — FIFO 配对时买入佣金摊入成本、卖出费用（佣金+印花税）从收入扣减，与现金账一致；旧口径忽略费用，胜率与盈亏比系统性偏高。
- **⚠️ Brinson 归因重写为真单期 BHB** — 配置/选股/交互三项之和在数学上严格等于超额收益（旧实现三项均分，数值不闭合）；`sector_data` 真正驱动行业分组；新增返回 `portfolio_return`、`benchmark_return`、`benchmark_model` 与分行业明细 `sectors`。
- **⚠️ 基准不可用时 `alpha` / `beta` / `information_ratio` 返回 `NaN`** — 取代旧的静默默认值 0.0/1.0/0.0；HTML/MD 报告渲染为 "N/A" 并附口径提示，JSON 中对应目标记为 `pass: null`。
- **Paper trading 增加交易时段门控** — 09:15 前与 15:00 后（CST）不撮合、不取数、不跑回调；当日首笔成交等集合竞价结束（09:25）；空行情订单保留 pending 而非取消；用户回调增加熔断（连续 3 次失败禁用该回调），异常不再逃逸主循环杀死进程。

#### Fixed

- **底层取数接口在回测会话内的前视泄漏** — `fetch_stock_data` / `get_money_flow` / `get_billboard_list` / `fetch_minute_data` / `check_golden_cross` 在决策期回调统一截断到 T-1（与 `get_price` 一致），纯未来请求短路返回；研究模式与模拟盘不受影响。
- **快照类公共 API 防护铺全** — `get_valuation` / `get_extras` / `get_concept_stocks` / `get_industry_stocks` / `get_current_data` / `get_current_data_object` / `scan_market` / `get_financial_screen` / `get_restriction_release` 接入与 `get_fundamentals` 相同的会话内防护（回测中 `FutureWarning`，`avoid_future_data=True` 时报错）；此前 strict 模式下当前 PE/PB、ST 状态、全市场行情快照、板块成分与解禁日程仍会静默泄漏进历史回测。
- **`load_stock_local` 回测会话内截断** — 本地 CSV 的未来行不再能直达运行中的回测（与 `fetch_stock_data` 同一截止日期语义）；引擎预载与回测结束后的基准读取经 `_unrestricted_fetch` 显式豁免，研究模式与模拟盘不受影响。
- **`get_fundamentals` 非时点安全** — `date` 参数被忽略（数据源无披露日期历史）；回测会话内调用现在发出 `FutureWarning`，`set_option('avoid_future_data', True)` 时升级为 `ValueError`；`eqlib.get_fundamentals` 双定义已统一为单一实现。
- **Paper 集合竞价窗口回调顺序** — 循环在 09:15–09:25 竞价窗口内跨日时，`before_trading_start` 不再晚于当日 `handle_data` 运行；当日首笔成交仍等竞价结束（09:25）后进行。
- **报告基准双口径** — 报告中的基准指标统一使用引擎记录的基准净值序列（与图表同源），仅在其缺失时回退图示口径并明确标注。
- **`use_local=True` 的静默网络回退** — 本地文件被覆盖门禁拒绝后逐证券回退网络时现在发出 WARNING，并在 `result["data_diagnostics"]["local_fallback"]` 中记录证券清单。
- **`Order.cancel_reason`** — 取消/过期订单的取消原因现在落在 Order 对象上，可程序化溯源。

#### Examples

- **回测类示例默认启用滑点** — `examples/_defaults.py` 新增 `DEFAULT_SLIPPAGE = FixedSlippage(0.001)`，回测示例在 `initialize` 中显式 `set_slippage(DEFAULT_SLIPPAGE)`；示例输出因此比旧的零滑点结果更保守。
- **示例打印对 NaN 友好** — 基准不可用时 Alpha/Beta 渲染为 `N/A` 而非 `+nan%`（`examples/_defaults.py` 新增 `format_pct` / `format_num` 助手）。
- **印花税日期敏感性披露** — `_defaults.py` 注释与 README 说明：示例固定的 0.05% 印花税率适用于 2023-08-28 之后，长历史回测请用 `close_tax=None`（日期感知法定税率）。

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
- Translated key UI labels to Chinese (e.g., "初始资金", "使用本地数据")
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

- "Web 工作室" hero card with icon (🌐) on homepage
- Emoji icons for all hero cards (🚀, 📖, 🎓, 🌐, 🔧)
- Search keyboard shortcut hint ("⌘K 快捷搜索")
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

### ⚠️ Backtest Correctness Fixes (P0) (continued from Unreleased)

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
