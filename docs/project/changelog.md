# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Removed

- **移除 Web 策略工作室**（2026-10-10）— `web_strategy_studio/`（FastAPI 后端 + React 前端）已从仓库中移除，项目重新聚焦于核心回测库 `eqlib`。相关文档（使用指南、部署指南、FAQ 条目、首页入口与导航）已同步删除。

### eqlib Core — 正确性（P0）

#### Fixed

- **年化口径统一为 244 个交易日** — `TRADING_DAYS_PER_YEAR`（244，A 股实际值）现在从 `eqlib.constants` 统一导入，替代原先各处硬编码的 252。涉及：`eqlib/scientific/statistics.py`、`eqlib/scientific/risk.py`、`eqlib/scientific/overfitting.py`、`eqlib/utils/stats.py`（`rolling_sharpe`、`downside_deviation`）、`eqlib/attribution.py`（`_calc_alpha_beta` 与 `analyze_returns`）。同一次回测现在各模块算出的夏普比率一致——此前同一段日收益在不同代码路径下会得出不同的年化值。
- **OrderCost 默认费率更新** — `eqlib/objects.py:OrderCost` 佣金默认改为 `open_commission=close_commission=0.00025`，与 `examples/_defaults.py:DEFAULT_ORDER_COST` 及 2023-08-28 印花税下调后的费率对齐。`close_tax` 显式默认仍为 `None`：未配置时按法定印花税率日期感知（2023-08-28 起 0.05%，此前 0.1%）；`examples/_defaults.py` 固定的 0.0005 适用于 2023-08-28 之后的回测区间。
- **MLSelector 诚实命名** — `target='forward_return_5d'` 现在抛出 `NotImplementedError`，不再静默改用过去收益计算。默认 target 仍为 `past_return_5d`（向后兼容），但 docstring 明确警告它用的是历史收益作为标签，不是真正的前向预测。要做真正的前向收益预测，须通过 `label_data` 传入面板 DataFrame。
- **`MLSelector` 构造函数签名补全** — `label_data` 与 `custom_features` 参数进入公开 API（此前只能走内部属性），支持面板标签训练与用户自定义特征函数。
- **`walk_forward_analysis` 改为真滚动窗口** — 替换原先的"单次回测 + 切片"近似：将 `[start_date, end_date]` 划分为多个训练/测试窗口，按 `step` 天向前滑动。每个窗口在训练段（样本内）与测试段（样本外）各跑一次独立回测，逐窗口的夏普 / 收益 / 最大回撤聚合为 `oos_is_ratio` 与 `is_sharpe_decay`。dict 输入路径（切片已有净值曲线）保留以兼容旧代码。
- **Cornish-Fisher VaR** — `eqlib/utils/stats.py:value_at_risk` 与 `eqlib/scientific/risk.py:value_at_risk` 新增 `method='cornish_fisher'`，在参数法（正态）VaR 上按样本偏度与超额峰度修正。更贴合 A 股日收益通常负偏、厚尾的特征——普通 `parametric` 容易低估尾部风险。
- **统计 ddof 一致性** — `eqlib/scientific/risk.py` 现在统一使用 `ddof=1`（样本标准差），与 `eqlib/attribution.py`、`eqlib/scientific/statistics.py` 对齐。此前个别代码路径使用 `ddof=0`，同一输入序列会算出略不同的 Sharpe/Sortino。
- **修复 `examples/18_grid_trading.py`** — 原网格策略在测试区间 0 笔成交（MDD 97.4%）。重写 `market_open` 为价位穿越触发逻辑（价格向下穿越网格线买入、向上穿越卖出），网格层数 10 → 8，区间回看 60 → 30 天，新增 5% 重建阈值在价格区间漂移时刷新网格。新结果：146 笔成交，MDD -19%，胜率 71.9%。
- **示例 21-24 规范化** — ML 示例改用 `examples._defaults` 的交易成本与日期（不再硬编码），移除 `sys.path.insert(0, '.')`（由 `pip install -e .` 提供），补上模块级 docstring（编号 / 标题 / 教学目标 / 运行命令）。示例 21 将 `target='forward_return_5d'` 改为 `past_return_5d`，与上面的诚实命名对齐。

### eqlib Core — 市场规则与数据口径（2026-10 修复轮）

以下变更会让旧回测结果发生变化，均如实标注。

#### Added

- **通知函数提升为顶层 API** — `set_notification_webhook` / `enable_notification` / `notify_signal` 现在可直接 `from eqlib import ...`（此前须从 `eqlib.engine` / `eqlib.notification` 深路径导入）。

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

### eqlib Core — 通知与数据接口修复（2026-10-13）

#### Fixed

- **订单事件通知真正生效** — `enable_notification(["queued", "filled"])` 此前接受配置但引擎从不推送；现在模拟/实盘会话中订单排队、订单成交（含成交价、数量、佣金、是否部分成交）会自动推送到已配置的钉钉/飞书 webhook。回测期间一律静默，无论配置什么事件。通知发送任何失败都只记日志、返回 `False`，不影响交易主流程。
- **`get_financial_screen` 的 `min_roe` / `min_revenue` / `min_profit` 生效** — 这三个参数此前被接受但静默忽略；现在按最近一期披露基本完整的季报（业绩报表）过滤：`min_roe` 单位为 %，`min_revenue` / `min_profit` 单位为元，传入任一者后结果附带 `roe` / `revenue` / `profit` 列。披露期早期（不足 2000 家）自动回退上一报告期；季报完全不可用时按失败关闭返回空 `DataFrame` 并记录警告，不再假装过滤已生效。
- **`AlertLevel` 新增 `NORMAL` 级别** — `daily_check()` 在零触发项时返回 `NORMAL`（旧基线恒为 `YELLOW`，干净报告也显示黄色，长期使用会造成预警疲劳）；有任何触发项时至少为 `YELLOW`，升级规则不变。⚠️ 行为变化：用 `report.alert_level == AlertLevel.YELLOW` 判断"一切正常"的代码应改判 `NORMAL`。

#### Tests

- **`tests/evaluator/test_wheel.py` 离线环境语义** — 隔离安装审计在包索引不可达（DEP-004）时按 `pytest.skip` 处理而非失败；慢网络环境可用 `EQ_WHEEL_COMMAND_TIMEOUT`（秒）放宽单命令超时（默认 600）；只能经镜像访问 PyPI 的主机可用 `EQ_WHEEL_PIP_INDEX_URL` / `EQ_WHEEL_PIP_TRUSTED_HOST` 显式指定隔离安装所用的索引（`--isolated` 本身忽略 pip 配置文件）。

### Web Strategy Studio

#### Security

- **真正的 JWT 鉴权** — `studio_api/auth.py:get_current_user` 现在校验 JWT bearer token（或短期 SSE query token）、查库确认用户、检查 `is_active`，并通过 `UserSession` 校验会话是否已吊销。此前该函数是始终返回演示用户的桩代码，受保护路由形同虚设。
- **`ensure_admin_user` 设置 `role=ROLE_ADMIN`** — 启动时创建的管理员用户现在真正拥有管理员权限；未设置 `EQ_ADMIN_PASSWORD` 时拒绝启动（`EQ_STUDIO_TESTING=1` 除外）。

### 文档

#### Added

- 教程 11（ML 选股）— `docs/tutorials/11-ml-selection.md` 与 `.en.md` 均改用 2024 费率。
- `docs/reference/api-ml.md` — `MLSelector` 构造函数签名补上 `label_data` 与 `custom_features`；新增 `check_feature_drift` 与 `auto_tune_selector` 小节。
- `docs/reference/api-scientific.md` — `walk_forward_analysis` 按真滚动窗口行为重新记录，含返回值（`oos_is_ratio`、`is_sharpe_decay`、逐窗口 `train_start/end` / `test_start/end`）。
- `docs/reference/api-risk.md` — 记录 Cornish-Fisher VaR 方法。
- `docs/tutorials/index.md` 与 `.en.md` — 修复与实际文件名不符的旧 "Example N" 编号。

### CI/CD

#### Fixed

- `doc-sync.yml` 改用 `pip install -e ".[docs]"` 安装文档依赖，替代硬编码包列表——此前缺少 `mkdocs-git-revision-date-localized-plugin`，导致 `mkdocs build --strict` 失败。
- Studio Tests Backend（Python 3.10/3.11）、Studio Tests Frontend 与 Doc Sync Check 工作流全部通过。

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
- Glossary page added to the documentation site (now at `docs/explanation/glossary.md`).
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

- M10: mkdocs nav now points to the split-by-chapter user guide (since
  restructured into `docs/tutorials/` and `docs/how-to/`); the old
  single-page version is still accessible but no longer in the top nav.
- M11: CHANGELOG, CONTRIBUTING, and SECURITY added to the nav under
  "项目动态 / Project Updates".
- E6: utils reference page added to the API reference section of the nav
  (now at `docs/reference/utils.md`).
- E9: Glossary page added (now at `docs/explanation/glossary.md`).

### Risk Disclosures Added

- Strategy examples 14, 15, 16, 17 now include `⚠️ RISK DISCLOSURE` headers
  warning that examples are for teaching purposes only and should not be
  deployed to live trading without thorough out-of-sample validation.

---

## [0.1.1] — 2025-07 (P0 patch)

未正式发布。计划中 0.1.x 线上的 P0 回测正确性修复最终随 [1.0.2] 一起发布（见上文）。

---

## [0.1.0] — 2025-05

Initial release.

> 示例编号后来重组过，下列路径已按当前 `examples/` 目录对应到新编号。

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
