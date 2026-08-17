# eqlib Dependency Evaluator Design

## Status

- Date: 2026-08-17
- Status: Design approved; written specification awaiting review
- Objective: Build a repeatable, readable evaluator that can gate regressions in CI, then use its first audit to remediate eqlib dependency, data, and numerical risks.

## Background

eqlib is an event-driven A-share backtesting and research library. Its output depends on the Python numerical and ML stack, trading calendars, AkShare, and direct HTTP data sources. A dependency upgrade, installation resolution change, upstream schema change, network fallback, or numerical/indexing semantic change can alter research results without an eqlib source change.

The first read-only adversarial review reproduced the following material defects:

1. Dependencies have no lock/constraints/hash; `requirements.txt`, `pyproject.toml`, runtime imports, and the editable metadata are not fully consistent. `requests` is directly imported but undeclared, and stale editable metadata hides an installed scikit-learn version below the source requirement.
2. The Tencent fallback can scale prices down by 100x, scale money by roughly 10x, and return history outside the requested interval; the existing OHLCV validator accepts it.
3. A statutory-workday calendar is not an exchange trading calendar. The offline fallback treats 2024-02-09 as open and becomes unreliable outside its supported years.
4. Portfolio risk, risk metrics, and ML paths have reproducible errors, including an inactive maximum-drawdown kill switch, equally weighted instead of NAV-weighted VaR, incorrect downside deviation, label misalignment, single-class probability semantics, and prediction-batch dependence.
5. Existing tests mix offline and live network calls; several live tests pass when every provider fails because they only assert a returned DataFrame or check schema only when it is non-empty.

An evaluator cannot honestly guarantee future provider availability, data truth, or investment results. Its guarantee is operational: known high-risk classes become evidenced, thresholded, repeatable, and gateable checks, so those classes cannot enter a protected branch or release without a visible finding.

## Goals

- Verify actual wheel metadata, dependency resolution, and runtime imports in a clean isolated environment instead of trusting editable state.
- Establish frozen adversarial contracts for dependency use: schema, units, dates, completeness, finiteness, index alignment, randomness, error semantics, and fallbacks.
- Verify numerical correctness with independent oracles, golden values, and metamorphic invariants rather than merely absence of exceptions.
- Track controlled performance baselines for cold import, data/cache paths, and scientific computations.
- Produce human-readable Markdown and machine-readable JSON reports with environment evidence, finding IDs, severity, reproduction details, impact, remediation, and gating result.
- Run deterministic offline gates on every pull request and low-frequency, bounded live health probes on scheduled, manual, and release workflows.
- Remediate first-round P0/P1 findings and demonstrate the remediation using the same evaluator.

## Non-Goals

- Do not promise absolute live-provider availability, market-data truth, or future investment outcomes.
- Do not perform high-concurrency, fault-injection, or unbounded-retry testing against third parties on ordinary PRs.
- Do not expose the evaluator as a public eqlib API.
- Do not redesign every data interface or replace every dependency in the first iteration; changes are limited to reviewed risks affecting stability, reliability, accuracy, precision, or performance.

## Selected Approach

Three approaches were compared: static scanning alone, additional pytest tests alone, and a layered evaluator with adversarial contracts and dual CI lanes. The third approach is selected because static scans cannot detect the Tencent or numerical P0s, while tests alone do not provide isolated-wheel evidence, provider-health evidence, or unified reporting.

## Architecture

```text
Source / declarations / lock files / CI configuration
        -> inventory and supply-chain audit -> isolated venv and wheel metadata
        -> offline adversarial contracts ------> unified finding model <------ performance baselines
                                      optional bounded live health probes
                                                      -> report.json + report.md + exit code
                                                      -> PR gate / scheduled alert / release gate
```

The implementation has four bounded layers:

1. **Inventory and isolated environment**: parse declarations, AST-scan third-party imports, build and install a wheel in a temporary venv, then compare source declarations, wheel metadata, installation metadata, locked resolution, and `pip check`.
2. **Offline adversarial contracts**: use frozen raw-provider payloads and synthetic numerical inputs to verify normalization, errors, golden values, and invariants without network access.
3. **Live health**: query a small representative set of symbols/endpoints within strict request, timeout, concurrency, and total-budget limits; record versions, latency, schema fingerprints, provider state, and cross-source magnitude checks.
4. **Reporting and gates**: normalize all evidence into stable P0–P3 findings and select nonzero behavior by profile.

## Command Profiles and Gating

The planned command interface is:

```bash
python scripts/evaluate_eqlib_dependencies.py --profile offline --output artifacts/eqlib-evaluator
python scripts/evaluate_eqlib_dependencies.py --profile live --output artifacts/eqlib-evaluator
python scripts/evaluate_eqlib_dependencies.py --profile offline --strict
```

`offline` is deterministic and runs isolated-wheel validation, declaration/import/extra/lock consistency checks, fixture-driven source contracts, numerical contracts, and controlled subprocess benchmarks. It is the PR gate.

`live` runs `offline` first and adds low-frequency provider probes. Provider failures are recorded as external availability findings; they gate only a release or an explicit strict run. P0 and P1 fail `offline --strict` and `live --strict`; P2/P3 remain visible in reports and can be promoted by configuration.

## Report Model

Each finding has a stable ID such as `DEP-001`, `DATA-101`, `NUM-201`, or `PERF-301`, a severity and status, affected source/dependency/endpoint, audited evidence, expected/actual values and tolerance, reproduction command, impact, remediation, profile, timestamp, OS/Python/dependency environment, wheel hash, and tool versions.

`report.md` provides the risk summary, gate result, domain findings, performance table, and remediation verification. `report.json` carries the identical facts for CI artifacts and automation. An API error or unknown data may never be rendered as zero data, complete data, or a pass.

## Dependency and Supply-Chain Contracts

`pyproject.toml` is the release source of truth. If `requirements.txt` remains, it must be generated from controlled inputs and cover the same primary dependency set; otherwise it is removed with its documentation entry. Every third-party runtime import belongs to a primary dependency, explicit extra, or documented optional provider.

First-round remediation explicitly declares `requests`, aligns scikit-learn/chinese-calendar/primary dependencies and documentation, gives `fastparquet` and `xgboost` explicit extras or tested visible errors, and aligns Python support to `>=3.10`, matching the existing documentation, classifiers, and CI practice.

The evaluator builds a wheel, creates a fresh venv, installs a selected locked resolution, inspects wheel/installed metadata, runs import smoke checks and `pip check`, and records hashes and resolution reports. Hash-pinned, reproducible constraints cover both a current locked resolution and a minimum-compatible resolution; the published package can still publish sensible compatibility ranges.

## Data Contracts

All provider data is canonicalized before backtests, cache, or fallback use. Canonical OHLCV requires a unique, increasing, non-NaT date index; strict requested-range slicing and coverage status; finite positive prices obeying OHLC envelopes; finite nonnegative volume/money; and provenance including units, adjustment, source, schema version, fetch time, and quality state. Incomplete input must be `incomplete`/`unavailable`, with strict mode raising a structured error.

Frozen raw fixtures cover Tencent array reordering, HTML/non-JSON, 429/5xx, timeout, missing fields, duplicate/out-of-order dates, invalid units, tail gaps, negative volume, and OHLC violations. The Tencent fallback is removed from the default accepting path until frozen multi-symbol/multi-date fixtures and cross-source magnitude checks establish its units. All sources then share strict slicing and validation.

The offline calendar becomes a versioned, auditable Shanghai/Shenzhen exchange calendar. `chinese_calendar` may be auxiliary only. Out-of-coverage years must raise or be unavailable; 2024-02-09 is a required regression fixture.

A unified data-source client supplies bounded timeouts, idempotent retries, backoff/jitter, 429/5xx classification, provider concurrency/rate budgets, total deadlines, and visible failure reasons. Cache entries include provenance and only persist validated data. Historic `date`/`trade_date` arguments must constrain as-of data or clearly reject backtest use.

## Numerical and ML Contracts

Independent NumPy/Pandas oracles and frozen golden results test normal, NaN, Inf, zero, negative, out-of-order, duplicate, missing-date, and boundary inputs. First-round P0 contracts are:

| Domain | Required contract | Remediation direction |
|---|---|---|
| Portfolio risk | A synthetic 30% drawdown triggers a kill switch; added risk cannot lower alert level | Calculate portfolio/strategy MDD and aggregate explicit numeric alert priority |
| VaR | Unequal-NAV strategies use same-day NAV weights, not equal strategy counts | Construct weighted portfolio returns and expose/reject insufficient coverage |
| Downside risk | LPM2 uses all observations; VaR/CVaR semantics and confidence validation are consistent | Correct formulas and input semantics across modules |
| Return curves | list/dict, ordering, initial cash, and gap policy have explicit consistent behavior | Establish one normalization path and disable implicit `pct_change` filling |
| ML alignment | Permuting label index matches an explicit reindex reference | Align X/y on common, ordered, unique index |
| ML probabilities | P(class=1) follows `classes_` for all-zero/all-one/nonbinary labels | Select class position explicitly; absent positive class yields zeros |
| ML prediction | Single-row, split-batch, and merged-batch output for a row is invariant | Fit imputation on training data and transform only at prediction |
| Random statistics | Same `random_state` reproduces bootstrap/Monte Carlo results | Expose, record, and test random seeds |

Metamorphic checks include unordered equivalence, list/dict equivalence, alert monotonicity, batch invariance, seed determinism, and diagnosable error on infeasible optimization.

## Performance Contracts

Performance is measured in isolated subprocesses across repeated runs and compared with a versioned controlled-runner median, not an absolute cross-machine time. Initial coverage includes cold `import eqlib` time/RSS, canonical normalization, cache hit/miss, fallback bounds, risk rolling calculations, bootstrap/Monte Carlo, optimizer and common indicators, ML tuning parallelism, and report figure lifetime/concurrency. The initial relative threshold is no more than 2x the same-environment baseline; baseline changes require an explicit reviewed update and record data size, CPU, Python, dependency versions, and peak RSS.

## CI and Release Integration

An evaluator workflow runs Linux offline gates on supported Python 3.10–3.12 and uploads reports. One job uses the current lock and another a minimum-compatible resolution. PRs run `offline --strict` plus the core suite; live tests become explicitly marked. Scheduled/manual runs execute `live`; release candidates execute `live --strict`. Full core tests run on production-like Linux, with macOS retained as additional compatibility coverage. Action SHAs, Docker digests, and dependency hashes are supply-chain findings.

## Scope and Acceptance

Expected implementation areas are `scripts/`, evaluator/fixture/contract/performance tests, `eqlib/data.py`, `eqlib/data_cache.py`, `eqlib/portfolio_risk.py`, `eqlib/utils/stats.py`, `eqlib/ml/models.py`, necessary shared return normalization, dependency metadata/constraints/CI, and bilingual installation/FAQ/security documentation. Public API changes must remain backward compatible or be separately documented.

Completion requires a clean `offline --strict` report with no open P0/P1, deterministic detection of intentionally reintroduced first-round failures, independently verified P0 fixes, bounded live probes that report provider/schema failures explicitly, replayable performance baselines, passing core tests/examples/docs, synchronized bilingual documentation, and a clear statement of residual external uncertainty.
