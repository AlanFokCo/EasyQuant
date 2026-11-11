# Point-in-Time Value Factor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-test the unchanged value_factor strategy on historical CSI 300 constituents with daily point-in-time valuation, then report the clean 2013–2015 gate result.

**Architecture:** A BaoStock adapter freezes membership and daily stock history to sha256-verified CSVs. A new research strategy consumes membership and daily PE/PB/status frames without changing the original factor economics. The existing offline harness supplies frozen prices and metric calculations; an independent analysis builds the frictionless PIT equal-weight reference and attribution.

**Tech Stack:** Python 3.10, pandas, BaoStock, existing eqlib backtest engine, pytest.

**Spec:** `research/value_factor_pit_2026/DESIGN.md`

## Global Constraints

- Work only on `main`; never create branches or worktrees.
- Do not modify `eqlib/` or previous studies' frozen strategies.
- Use `~/anaconda3/envs/eqlib-py310/bin/python`; system Python 3.9 cannot import eqlib.
- The factor parameters and 2013–2015 gate in DESIGN.md are frozen; no parameter search.
- Existing evidence is never overwritten; every run uses a unique label/output directory.
- Network is allowed only in the prefetch/data-validation step; evaluation asserts against network access.
- Stop rather than substitute current constituents if the historical data gate fails.
- Commit each frozen code state immediately so later evidence can prove code identity.

## Review Focus

- Delisted/removed constituents must remain in frozen data and may be selected only while eligible (Task 1 membership/history tests).
- Daily PE/PB/status values must never be read after the decision date (Tasks 2 and 3 freshness tests).
- Names missing bars or marked ST/suspended must not silently become eligible (Task 2 eligibility tests).
- A failed entry must not be duplicated by the single retry; pending entries must not survive into a later rebalance (Task 2 retry tests).
- An index-only rally must not be misreported as factor alpha: compare against CSI 300 and the frictionless PIT equal-weight reference (Task 4 reference tests).

---

### Task 1: Prove and Freeze the Point-in-Time Dataset

**Files:**
- Create: `research/value_factor_pit_2026/baostock_freeze.py`
- Create: `research/value_factor_pit_2026/tests/test_baostock_freeze.py`
- Create: `data/value_factor_pit/manifest.json` (generated, gitignored)

**Interfaces:**
- Produces: `collect_rows(result) -> pd.DataFrame`, `fetch_membership(date: str) -> pd.DataFrame`, `fetch_stock_history(code: str, start: str, end: str) -> pd.DataFrame`, `load_manifest(directory: Path) -> dict`.
- Frozen membership schema: `date, code` with bare six-digit codes; stock history schema: `date, code, open, high, low, close, volume, pe_ttm, pb_mrq, tradestatus, is_st`.

- [ ] **Step 1: Write failing unit tests**

Test `collect_rows` preserves BaoStock strings and converts no dates implicitly; test code conversion preserves six digits; test manifest validation rejects changed bytes and missing files.

- [ ] **Step 2: Run unit tests and verify failure**

Run: `~/anaconda3/envs/eqlib-py310/bin/python -m pytest research/value_factor_pit_2026/tests/test_baostock_freeze.py -v`
Expected: import failure because `baostock_freeze` does not exist.

- [ ] **Step 3: Implement the adapter and validators**

Normalize BaoStock `sh.600000`/`sz.000001` codes to bare codes, parse dates explicitly, retain empty valuation values as NaN, and write per-name CSVs plus a manifest containing sha256, row counts, first/last dates, and missing trading days.

- [ ] **Step 4: Run the live go/no-go probe**

Query CSI 300 membership for 2010-01-04, 2013-01-04, and 2015-01-05; query a current and a delisted name for 2009–2015. Record member counts and valuation coverage. Compare one overlapping current name and CSI 300 against the akshare freeze up to adjustment-anchor scaling. Stop if DESIGN.md coverage thresholds fail.

- [ ] **Step 5: Run tests and freeze the complete dataset**

Run the unit tests, then freeze monthly membership dates and every unique constituent's daily history for 2009–2015. Commit the adapter/tests immediately; data and manifest remain gitignored.

### Task 2: Implement the Dynamic-Universe Value Strategy

**Files:**
- Create: `research/value_factor_pit_2026/pit_value_strategy.py`
- Create: `research/value_factor_pit_2026/tests/test_pit_value_strategy.py`

**Interfaces:**
- Consumes: frozen history and membership from Task 1.
- Produces: `PITValueConfig`, `make_pit_value_strategy(membership: dict[str, set[str]], histories: dict[str, pd.DataFrame], config: PITValueConfig, benchmark: str, order_cost)`, and pure helpers `eligible_state(frame, as_of, config)`, `select_cheap_names(states: dict, config) -> list[str]`.

- [ ] **Step 1: Write failing signal and state tests**

Cover: PE/PB must be positive; ST and suspended states rejected; missing/short turnover history rejected; no future daily row is visible; cheapest eight selected deterministically; a name removed from CSI 300 exits; kill-switch exit cancellation is resubmitted; an unfilled entry is retried exactly once.

- [ ] **Step 2: Run tests and verify failure**

Run: `~/anaconda3/envs/eqlib-py310/bin/python -m pytest research/value_factor_pit_2026/tests/test_pit_value_strategy.py -v`
Expected: import failure because the strategy module does not exist.

- [ ] **Step 3: Implement the strategy**

Reuse `composite_scores` from the uncapped value_factor study without modifying it. Preserve its monthly cadence, top-eight ranking, order-time caps, rank-out exits and kill switch. Use only daily rows dated on or before the decision date and membership effective on that date. Add the specified entry retry and halt-exit resubmission.

- [ ] **Step 4: Run tests and commit the frozen strategy**

Run the strategy tests, require all to pass, then commit `pit_value_strategy.py`, tests, DESIGN.md and this plan before the first evaluation run.

### Task 3: Offline Runner and Mechanics Validation

**Files:**
- Create: `research/value_factor_pit_2026/run_pit_value.py`
- Create: `research/value_factor_pit_2026/tests/test_run_pit_value.py`

**Interfaces:**
- Consumes: `make_pit_value_strategy` from Task 2 and `frozen_prices`, `period_metrics`, `count_round_trips` from `research/regime_momentum_2026/runner.py`.
- Produces: `load_frozen_inputs(data_dir: Path)`, `run(period: str, cash: float, stress: bool, label: str)`, with periods `smoke`, `development`, `validation` from DESIGN.md.

- [ ] **Step 1: Write failing runner tests**

Cover missing files, sha256 mismatch, benchmark calendar gaps, no-network enforcement, immutable outputs, and exact stress-cost scaling.

- [ ] **Step 2: Run tests and verify failure**

Run: `~/anaconda3/envs/eqlib-py310/bin/python -m pytest research/value_factor_pit_2026/tests/test_run_pit_value.py -v`
Expected: import failure because the runner does not exist.

- [ ] **Step 3: Implement the runner**

Load every historical constituent before the engine starts, patch all fetch paths through the existing offline harness, and emit summary/equity/trades/events/selections with source and data hashes.

- [ ] **Step 4: Run smoke and development**

Run the unit tests, 2012 smoke, then the single 2010–2012 development run. Fix only mechanical defects; if any signal economics change, record it as an explicit design amendment before continuing.

- [ ] **Step 5: Commit the validated runner**

Commit runner and tests with the exact code state used for development evidence.

### Task 4: One-Shot Gate, Reference and Attribution

**Files:**
- Create: `research/value_factor_pit_2026/analyze_results.py`
- Create: `research/value_factor_pit_2026/tests/test_analyze_results.py`
- Create: `research/value_factor_pit_2026/README.md` (after results)

**Interfaces:**
- Consumes: frozen inputs and immutable run artifacts.
- Produces: `pit_equal_weight_reference(frames, membership, dates) -> pd.Series`, `yearly_attribution(summary_path: Path) -> dict`.

- [ ] **Step 1: Write failing analysis tests**

Use three synthetic names with different index-removal dates to verify the reference includes them only while members and never reads prices before listing or after delisting.

- [ ] **Step 2: Run analysis tests, then implement**

Verify the initial import failure, implement the reference and yearly attribution, and rerun until green.

- [ ] **Step 3: Execute validation once and stress once**

Run 2013–2015 validation and stress with unique labels. Do not alter parameters afterward. Compute all gate metrics and the PIT equal-weight reference from the same dates.

- [ ] **Step 4: Write the honest outcome report**

Include the four gate checks, yearly slices, universe reference, membership/removal attribution, coverage, execution anomalies, costs, and limitations. State failure explicitly if any criterion fails.

- [ ] **Step 5: Commit analysis and report**

Commit the exact analysis code and README used for the reported figures.

### Task 5: Independent Adversarial Review and Final Delivery

**Files:**
- Modify only if required: `research/value_factor_pit_2026/README.md`, `research/value_factor_pit_2026/DESIGN.md`
- Create: `research/value_factor_pit_2026/REVIEW.md`

**Interfaces:**
- Consumes: all code, frozen data manifests, and run artifacts.

- [ ] **Step 1: Dispatch a fresh adversarial evaluator**

Require independent recomputation of headline metrics and a sample of rebalances, with specific attention to membership dates, delisted names, valuation timing, entry duplication, and whether development/validation protocol was respected.

- [ ] **Step 2: Triage and correct findings**

Fix documentation directly. Rerun only for execution bugs with a new label and preserved old evidence; never change signal economics after validation.

- [ ] **Step 3: Record review and deliver**

Write REVIEW.md with findings/dispositions, run all research tests, inspect `git diff`, commit, and report the gate result and remaining limitations without overstating robustness.
