# Robust A-Share Industry-Leader Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dual-channel selection, volatility and portfolio-drawdown risk budgeting, rolling validation, and hard robustness gates while preserving the current `adaptive_composite` baseline behavior.

**Architecture:** Robust behavior is an optional path controlled by `StrategyParams.robust_enabled` in `ashare_sr_leader.py`. The primary channel keeps the current support/resistance logic, while new pure functions implement fallback signals, risk state, and robust weights. The research runner screens full-period candidates before neighborhood and rolling validation, and deterministically retains the A / 71.3 baseline when no robust candidate passes every gate.

**Tech Stack:** Python 3, pandas, NumPy, EasyQuant/eqlib backtest APIs, pytest, and MkDocs.

## Global Constraints

- Full-period annual return must be at least 12%, maximum drawdown must be strictly below 20%, and the grade must remain A with a score of at least 70.
- The 2025 stress period may trail the benchmark by no more than 5%; no other rolling validation period may trail by more than 10%.
- At least 60% of neighboring parameters must retain at least 10% annual return and no more than 22% drawdown.
- Trading decisions may use only bars completed before the callback decision point.
- New behavior defaults off; `robust_enabled=False` must preserve the current `adaptive_composite` path.
- Do not change `grade_strategy`, matching behavior, or shared costs: 0.05% stamp duty, 0.025% commission, CNY 5 minimum.
- Add no dependency, do not expand the universe, and do not introduce broad random search.
- Preserve all existing worktree changes. Stage only files owned by the active task and inspect `git diff --cached` before each commit.
- Keep Chinese and `.en.md` English strategy documentation synchronized.

---

## File Map

- Modify `eqlib/strategies/ashare_sr_leader.py` for fallback signals, risk state, robust candidates, weighting, and runtime integration.
- Modify `scripts/run_ashare_sr_leader_research.py` for robust grids, slicing, hard gates, neighborhood checks, attribution, reporting, and selection.
- Modify `tests/test_ashare_sr_leader_strategy.py` for deterministic unit and integration coverage.
- Modify `docs/explanation/ashare-sr-leader-strategy.md` and `.en.md` for synchronized explanations and actual research results.
- Regenerate all files under `reports/ashare_sr_leader/` that the research runner owns.

### Task 1: Add Fallback Signal Domain Primitives

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:24-84,253-388`
- Test: `tests/test_ashare_sr_leader_strategy.py:8-308`

**Interfaces:**
- Produce `CandidateChannel`, `FallbackSnapshot`, robustness fields on `StrategyParams`, `build_fallback_snapshot()`, and `score_fallback_snapshot()`.
- Consume existing support/resistance, ATR, and relative-strength helpers.

- [ ] Write failing tests that verify robust mode defaults off, default values are 5 / 25% / 10% / 18%, an ascending relative-strength leader qualifies, and a falling or benchmark-lagging stock does not.

Use these exact imports:

```python
from eqlib.strategies.ashare_sr_leader import (
    CandidateChannel,
    build_fallback_snapshot,
    score_fallback_snapshot,
)
```

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_defaults or fallback_snapshot" -q
```

Expected: collection fails because the new symbols do not exist.

- [ ] Add `CandidateChannel.PRIMARY`, `CandidateChannel.FALLBACK`, and this immutable snapshot:

```python
@dataclass(frozen=True)
class FallbackSnapshot:
    close: float
    avg_volume: float
    relative_strength: float
    volatility: float
    medium_trend_change: float
    breakdown: bool
    channel: CandidateChannel = CandidateChannel.FALLBACK
```

- [ ] Add the exact `StrategyParams` fields from the approved design: `robust_enabled`, primary shortage threshold, fallback cap and stop, 120/60/20 trend windows, fallback relative-strength floor, 20-day volatility window, 18% volatility target, 0.55 floor, and 8%/12%/16% drawdown thresholds.

- [ ] Implement `build_fallback_snapshot()` so it requires sufficient completed history, minimum price and volume, close above the long moving average, a non-falling medium moving average, nonnegative configured relative strength, and no ATR-buffered structural breakdown. Implement `score_fallback_snapshot()` as the sum of nonnegative trend, relative-strength, and low-volatility scores.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "snapshot or composite_score or price_filter" -q
```

Expected: all selected new and legacy signal tests pass.

- [ ] Commit:

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust fallback signal primitives"
```

### Task 2: Add Volatility Budget and Portfolio Drawdown State Machine

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:24-84,219-250,454-488`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Produce `PortfolioRiskState`, `PortfolioRiskTracker`, `market_volatility_factor()`, `update_portfolio_risk()`, `drawdown_risk_multiplier()`, and `final_risk_budget()`.

- [ ] Write failing tests for a volatility factor bounded to `[0.55, 1.0]`, immediate state transitions at 8%, 12%, and 16%, weak-market recovery blocking, and one-level recovery after half the episode loss is recovered.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "market_volatility_factor or portfolio_risk" -q
```

Expected: collection fails on the new imports.

- [ ] Add an ordered `IntEnum` with `NORMAL=0`, `CAUTIOUS=1`, `DEFENSIVE=2`, and `PROTECT=3`, plus:

```python
@dataclass(frozen=True)
class PortfolioRiskTracker:
    state: PortfolioRiskState
    high_water: float
    trough: float

    @classmethod
    def initial(cls, total_value: float) -> "PortfolioRiskTracker":
        return cls(PortfolioRiskState.NORMAL, total_value, total_value)
```

- [ ] Implement immediate downgrade from current high-water drawdown. Recovery requires complete data, a non-weak market, at least 50% recovery from the episode trough, and a threshold-implied state below the active state; reduce severity by exactly one level per weekly call.

- [ ] Implement annualized benchmark volatility with `TRADING_DAYS_PER_YEAR`, return `None` for insufficient data, clamp scaling to `[market_volatility_floor, 1.0]`, and calculate final exposure as market exposure times volatility factor times drawdown multiplier.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "volatility_factor or portfolio_risk or final_risk_budget" -q
```

Expected: all selected tests pass, including an exact `0.90 * 0.80 * 0.50 == 0.36` budget assertion.

- [ ] Commit:

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add portfolio risk budget state machine"
```

### Task 3: Add Robust Candidate Composition and Volatility Weights

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:391-451`
- Test: `tests/test_ashare_sr_leader_strategy.py:366-429`

**Interfaces:**
- Produce `RobustCandidate`, `combine_robust_candidates()`, and `robust_target_weights()`.

- [ ] Write failing tests proving that fallback is absent when primary supply meets the threshold, disabled in weak/defensive states, limited to open slots, capped by `fallback_exposure_cap`, and unable to violate stock or industry caps.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_candidates or robust_weights or fallback_is_disabled" -q
```

Expected: collection fails on `RobustCandidate`.

- [ ] Add this normalized immutable candidate:

```python
@dataclass(frozen=True)
class RobustCandidate:
    code: str
    channel: CandidateChannel
    score: float
    volatility: float
    close: float
    avg_volume: float
```

- [ ] Implement primary-first composition. Return only primary candidates when their count meets `min_primary_candidates`, or whenever market state is weak or risk state is defensive/protect. Otherwise append unique fallback candidates until `top_n`.

- [ ] Implement inverse-volatility allocation with `1 / max(volatility, 1e-6)`. Allocate primary against the total exposure first, then allocate fallback against `min(fallback_exposure_cap, remaining exposure)`. Clip each allocation by stock and industry limits and do not redistribute clipped cash.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_candidates or robust_weights or target_weights or industry" -q
```

Expected: all selected tests pass and legacy weights remain unchanged.

- [ ] Commit:

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust channel portfolio weights"
```

### Task 4: Integrate Robust Selection, Runtime Risk, and Order Diagnostics

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:535-705`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Produce `filter_fallback_by_volatility()`, `select_fallback_candidates()`, `risk_data_complete()`, `reduce_portfolio_to_budget()`, and runtime context diagnostics.

- [ ] Write failing tests that keep only fallback candidates at or below cross-sectional median volatility, proportionally reduce a 50% invested portfolio to a 25% budget without any increase, and return false from `risk_data_complete()` when benchmark or volatility data are missing.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "fallback_filter or reduce_portfolio" -q
```

Expected: collection fails on the new helper imports.

- [ ] Implement median-volatility filtering and `select_fallback_candidates()` using the same completed OHLCV fields, exclusions, liquidity checks, and lookback discipline as the primary selector. Exclude codes already selected by the primary channel.

- [ ] Implement order tagging through `context.sr_order_channels[str(order.order_id)]` and persistent `context.sr_code_channels`. Implement proportional risk reduction as `target = current position value * target budget / current invested exposure` and queue only reductions.

- [ ] Implement `rebalance_robust_portfolio()` using Task 3 weights and existing liquidity limits. Existing holdings retain their entry channel. Tag all queued buy, rebalance, and exit orders.

- [ ] Update `_risk_review()` so fallback holdings use `fallback_trailing_drawdown`; primary holdings use existing `max_position_drawdown`. Structural breakdown remains the first exit condition.

- [ ] In robust initialization, create:

```python
context.sr_order_channels = {}
context.sr_code_channels = {}
context.sr_risk_events = []
context.sr_risk_tracker = PortfolioRiskTracker.initial(context.portfolio.total_value)
```

- [ ] Integrate robust monthly and weekly branches. Missing benchmark/volatility data may not increase risk. `PROTECT` permits reductions and exits only. Weekly review may restore at most one state and appends deterministic date/from/to/drawdown events. Leave the existing callback path untouched when robust mode is disabled.

Use `getattr(context, "sr_code_channels", {})` in shared exit code so the legacy path never depends on robust-only context fields.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -q
```

Expected: the entire strategy test file passes without network access.

- [ ] Commit:

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: integrate robust A-share risk controls"
```

### Task 5: Add Research Gates, Neighborhood Checks, and Rolling Validation

**Files:**
- Modify: `scripts/run_ashare_sr_leader_research.py:10-340,869-1080`
- Test: `tests/test_ashare_sr_leader_strategy.py:431-790`

**Interfaces:**
- Produce the exact baseline constant, validation windows, compact robust seeds, parameter neighbors, result slicing, gates, pass rate, and ranking key.

- [ ] Write failing tests for strict 12%/20%/A full gates, a tighter -5% 2025 excess gate, -10% other-period gates, a 60% neighborhood example, and validation-result rebasing.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "full_gate or validation_gate or neighbor_pass or slice_backtest" -q
```

Expected: collection fails on the new research symbols.

- [ ] Define `BASELINE_ADAPTIVE_PARAMS` with the exact current A / 71.3 parameters and define these windows:

```python
VALIDATION_WINDOWS = (
    ("2023", "2020-01-01", "2023-12-31", "2023-01-01", "2023-12-31"),
    ("2024", "2021-01-01", "2024-12-31", "2024-01-01", "2024-12-31"),
    ("2025", "2022-01-01", "2025-12-31", "2025-01-01", "2025-12-31"),
)
```

- [ ] Build ten compact robust seeds around the center: primary threshold 4/5/6, fallback cap 20%/25%/30%, fallback stop 8%/10%, target volatility 16%/18%/20%, and threshold triplets 7/11/15, 8/12/16, 9/13/17. Quick mode includes only the center robust seed.

- [ ] Implement deterministic one-field neighbor generation, `full_gate_failures()`, `validation_gate_failures()`, `neighbor_pass_rate()`, and ranking in this order: neighborhood pass rate, worst validation excess, Sharpe, lower absolute drawdown, monthly win rate, annual return.

Extend `summarize_result()` with the ranking input:

```python
monthly_returns = metrics.get("monthly_returns", {}) or {}
summary["monthly_win_rate"] = (
    sum(value > 0 for value in monthly_returns.values()) / len(monthly_returns)
    if monthly_returns
    else 0.0
)
```

- [ ] Implement `slice_backtest_result()` with a `SimpleNamespace` portfolio rebased to the first and last validation values, validation-only trades and benchmark values, and preserved OHLCV data.

- [ ] Stage research: run all seeds full-period; take at most three robust pre-gate passers; run their full-period neighbors; run their three formation windows and slice each validation year; attach failures and diagnostics; select only all-gate passers. Add `neighbor_pass_rate_below_60pct` below 0.60. When none pass, choose exact `BASELINE_ADAPTIVE_PARAMS` and set `selection_reason="baseline_retained_no_robust_candidate"`.

Mark exactly one full-period row `selected=True`, mark every other row false, and sort that selected row first in every output format.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "gate or neighbor or slice_backtest or best_full_candidate or candidate_param_grid" -q
```

Expected: all selected tests pass, including baseline fallback.

- [ ] Commit:

```bash
git add scripts/run_ashare_sr_leader_research.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust strategy validation gates"
```

### Task 6: Add Channel Attribution, Risk Diagnostics, and Report Sections

**Files:**
- Modify: `scripts/run_ashare_sr_leader_research.py:313-866,921-1001`
- Test: `tests/test_ashare_sr_leader_strategy.py:776-948`

**Interfaces:**
- Produce `channel_diagnostics()` and `risk_state_diagnostics()` and extend report rows.

- [ ] Write a two-security, two-day test where equal 10% weights produce +1% primary and -1% fallback contribution with one average holding in each channel, plus a three-day risk-event test that counts two normal days, one cautious day, one trigger, and one recovery.

- [ ] Extend HTML tests to require `稳健门槛`, `滚动验证`, `风险状态`, and `主/候补通道`.

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "channel_diagnostics or risk_state_diagnostics or render_html_report" -q
```

Expected: collection fails on diagnostic imports.

- [ ] Implement channel reconstruction from filled `trade_log` entries and `context.sr_order_channels`. For each date, multiply prior-close channel weights by next-close security returns. Skip only missing security/date prices, use arithmetic daily contribution, and return numeric defaults for trades, average exposure, and contribution for both channels.

- [ ] Implement risk-state duration from recorded dates and state events. Start in normal, apply same-date transitions before counting that date, count transitions away from normal as triggers, and transitions to a lower numeric risk state as recoveries.

- [ ] Attach diagnostics, gate failures, robust pass, neighborhood pass rate, worst validation excess, average channel holdings, and nested validation rows to summaries. Add scalar columns to CSV and nested data to JSON.

- [ ] Add Markdown and HTML sections for robust gates, rolling validation, risk states, channel diagnostics, and a side-by-side baseline-versus-robust comparison. If no candidate passes, include exactly:

```text
本轮没有找到通过全部稳健门槛的新候选，继续保留当前 A / 71.3 基线。
```

- [ ] Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "diagnostics or report or write_outputs or audit or period_interpretation" -q
```

Expected: all selected tests pass, including HTML escaping.

- [ ] Commit:

```bash
git add scripts/run_ashare_sr_leader_research.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: report robust strategy validation"
```

### Task 7: Run Research, Regenerate Reports, and Update Bilingual Explanation

**Files:**
- Modify both strategy explanation documents.
- Regenerate `summary.json`, `summary.csv`, `final_report.md`, `final_report.html`, and `eqlib_best_backtest_2020_2025.html`.

**Interfaces:**
- Consume the completed runner and produce reproducible artifacts and synchronized documentation.

- [ ] Run quick research:

```bash
MPLCONFIGDIR=/private/tmp/matplotlib-cache python scripts/run_ashare_sr_leader_research.py --quick
```

Expected: exit 0 with baseline and robust report rows.

- [ ] Run full research:

```bash
MPLCONFIGDIR=/private/tmp/matplotlib-cache python - <<'PY'
from eqlib.logger import log

log.set_level("ERROR")

import scripts.run_ashare_sr_leader_research as research

raise SystemExit(research.main())
PY
```

Expected: exit 0 and either an all-gate robust winner or explicit baseline retention.

- [ ] Assert `summary.json` has full rows, a valid selection reason, all hard metrics when a robust candidate wins, and `adaptive_composite` when baseline is retained.

- [ ] Correct stale `pullback_market_gate` winner text in both explanation documents. Document the actual baseline, dual channels, 8/12/16 risk states, volatility scaling, hard gates, rolling validation, neighborhood stability, honest fallback, actual result, and report path. Call 2025 stress validation rather than untouched out-of-sample data.

- [ ] Run:

```bash
python scripts/check_doc_sync.py
python -m pytest tests/test_ashare_sr_leader_strategy.py -q
```

Expected: both commands pass.

- [ ] Commit:

```bash
git add docs/explanation/ashare-sr-leader-strategy.md docs/explanation/ashare-sr-leader-strategy.en.md reports/ashare_sr_leader/summary.json reports/ashare_sr_leader/summary.csv reports/ashare_sr_leader/final_report.md reports/ashare_sr_leader/final_report.html reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html
git diff --cached --check
git commit -m "docs: publish robust A-share strategy research"
```

### Task 8: Complete Repository Verification

**Files:**
- Verify only. A discovered defect reopens the task that owns the failing behavior.

**Interfaces:**
- Consume every prior task and produce final test, example, docs, and report evidence.

- [ ] Run focused regression tests:

```bash
python -m pytest tests/test_data_diagnostics.py tests/test_data_utils.py tests/test_ashare_sr_leader_strategy.py -q
```

Expected: all selected tests pass.

- [ ] Run the complete test suite:

```bash
python -m pytest tests/ -q
```

Expected: all tests pass and no new warning originates from robust strategy files.

- [ ] Run example smoke tests explicitly:

```bash
python -m pytest tests/test_examples_smoke.py -q
```

Expected: all example smoke tests pass.

- [ ] Verify docs:

```bash
python scripts/check_doc_sync.py
mkdocs build --strict
```

Expected: both commands pass. If strict mode fails only on pre-existing Material, navigation, or git-revision warnings, preserve the exact warnings, run `mkdocs build`, and report the limitation.

- [ ] Inspect final repository state:

```bash
git status --short
git diff --check
git log -8 --oneline
```

Expected: no whitespace errors, task commits are visible, and unrelated pre-existing worktree changes remain untouched. Verification itself creates no empty commit; a correction returns to its owning task and repeats that task's tests and commit before Task 8 restarts.
