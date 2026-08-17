# eqlib Dependency Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build a repeatable, readable, CI-gated adversarial dependency evaluator for eqlib and remediate the dependency, data, numerical, and ML P0 findings proven by the initial review.

**Architecture:** Add a non-public evaluator maintenance package at the repository root plus a thin CLI. It collects dependency inventory, wheel metadata, offline-contract, and benchmark evidence into stable Markdown and JSON finding reports. Core regression protection remains pytest; public eqlib APIs keep their current return types.

**Tech Stack:** Python 3.10–3.12, pytest, stdlib ast/venv/zipfile/json, tomli for Python <3.11, setuptools/build, NumPy, Pandas, scikit-learn, GitHub Actions.

## Global Constraints

- Align requires-python, classifiers, README, and bilingual installation/FAQ pages to Python >=3.10.
- pyproject.toml is the release dependency source of truth; every direct runtime import belongs to a primary dependency or explicit optional extra.
- The offline profile does not call market providers. Only live may access providers and it has a total deadline, per-provider request cap, and low concurrency.
- A provider failure, data gap, or schema drift is never rendered as zero data, complete data, or success in a strict path.
- Numerical fixes use independent NumPy/Pandas oracles or explicit metamorphic invariants.
- Benchmark gates compare same-runner medians/RSS with a 2x initial relative threshold.
- Every docs Markdown change includes its matching English/Chinese partner and runs python scripts/check_doc_sync.py.

---

## File Structure

| Path | Responsibility |
|---|---|
| evaluator/models.py, evaluator/report.py | Stable finding/report model and atomic JSON/Markdown writer. |
| evaluator/inventory.py, evaluator/wheel.py | AST metadata audit and isolated-wheel evidence. |
| evaluator/contracts.py, evaluator/runner.py, scripts/evaluate_eqlib_dependencies.py | Profiled contract execution, exit policy, and CLI. |
| evaluator/benchmarks.py | Subprocess timing/RSS benchmarks. |
| tests/evaluator and tests/fixtures/data_sources | Evaluator tests and frozen raw provider fixtures. |
| eqlib/data.py and eqlib/static/ashare_trading_days.json | Canonical OHLCV, Tencent fix, and audited calendar fallback. |
| eqlib/utils/equity.py, eqlib/portfolio_risk.py, eqlib/utils/stats.py | Equity normalization, portfolio-risk, and loss-metric remediation. |
| eqlib/ml/models.py | Deterministic alignment, training-only imputation, and probability semantics. |
| requirements and .github/workflows/eqlib-evaluator.yml | Reproducible dependency constraints and CI lanes. |

### Task 1: Finding and report model

**Files:**
- Create: evaluator/__init__.py
- Create: evaluator/models.py
- Create: evaluator/report.py
- Test: tests/evaluator/test_report.py

**Interfaces:** Severity, Finding, EvaluationReport, render_markdown(report), write_report(report, output_dir).

- [ ] **Step 1: Write the failing ordering/output test.**

    report = EvaluationReport.create(
        "offline",
        [Finding("DEP-002", Severity.P2, "secondary", "details"),
         Finding("DATA-101", Severity.P0, "critical", "details")],
    )
    json_path, markdown_path = write_report(report, tmp_path)
    assert [row["id"] for row in json.loads(json_path.read_text())["findings"]] == ["DATA-101", "DEP-002"]
    assert "# eqlib Dependency Evaluator Report" in markdown_path.read_text()

- [ ] **Step 2: Run python -m pytest tests/evaluator/test_report.py -v.**

Expected: FAIL because evaluator does not yet exist.

- [ ] **Step 3: Implement Severity rank, immutable Finding, EvaluationReport.create, ordered_findings, and atomic JSON/Markdown writing.**

    blocking_order = {Severity.P0: 0, Severity.P1: 1, Severity.P2: 2, Severity.P3: 3}
    ordered = sorted(findings, key=lambda finding: (blocking_order[finding.severity], finding.id))

- [ ] **Step 4: Re-run the test.**

Expected: PASS.

- [ ] **Step 5: Commit with feat: add evaluator report model.**

### Task 2: Inventory, AST import audit, and isolated-wheel evidence

**Files:**
- Create: evaluator/inventory.py
- Create: evaluator/wheel.py
- Test: tests/evaluator/test_inventory.py
- Test: tests/evaluator/test_wheel.py
- Modify: pyproject.toml
- Modify: requirements.txt

**Interfaces:** read_project_dependencies(root), scan_runtime_imports(root), evaluate_inventory(root), build_and_audit_wheel(root, work_dir).

- [ ] **Step 1: Write failing tests for undeclared requests, stale requirements, and wheel METADATA containing requests/scikit-learn.**

    findings = evaluate_inventory(tmp_project_with_import("requests"))
    assert any(item.id == "DEP-001" for item in findings)

    evidence, findings = build_and_audit_wheel(ROOT, tmp_path)
    assert {"requests", "scikit-learn"} <= {requirement_name(item) for item in evidence["requires_dist"]}
    assert not any(item.id == "DEP-003" for item in findings)

- [ ] **Step 2: Run python -m pytest tests/evaluator/test_inventory.py tests/evaluator/test_wheel.py -v.**

Expected: FAIL because the audit APIs are absent.

- [ ] **Step 3: Implement AST-only scanning.**

    mapping = {"sklearn": "scikit-learn", "chinese_calendar": "chinese-calendar"}
    imported = scan_runtime_imports(root)
    missing = sorted(imported - declared_primary_dependencies - declared_optional_dependencies)

The scanner must parse source via ast, never import it.

- [ ] **Step 4: Build a wheel with python -m build, parse exactly one dist-info/METADATA using zipfile and email.message_from_bytes, create a venv, install the wheel, and run pip check.**

Installation/pip-check failure is DEP-003 P0. A blocked index is DEP-004 status unavailable, never success.

- [ ] **Step 5: Declare requests>=2.28.0 and align requirements.txt to these eight primary distributions: akshare, chinese_calendar, pandas, numpy, matplotlib, scipy, scikit-learn, requests. Add tomli for Python <3.11 and build to dev. Make fastparquet/xgboost explicit extras or intentional optional findings.**

- [ ] **Step 6: Re-run focused tests and commit with fix: align eqlib runtime dependencies.**

### Task 3: CLI, offline contracts, and exit policy

**Files:**
- Create: evaluator/contracts.py
- Create: evaluator/runner.py
- Create: scripts/evaluate_eqlib_dependencies.py
- Test: tests/evaluator/test_runner.py

**Interfaces:** run_evaluation(root, profile, output_dir, strict) -> tuple[EvaluationReport, int].

- [ ] **Step 1: Write failing strict P0 and non-strict P2 tests.**

    monkeypatch.setattr("evaluator.runner.collect_findings", lambda *args: [Finding("NUM-201", Severity.P0, "bad", "bad")])
    _, code = run_evaluation(ROOT, "offline", tmp_path, strict=True)
    assert code == 1

    monkeypatch.setattr("evaluator.runner.collect_findings", lambda *args: [Finding("PERF-301", Severity.P2, "slow", "slow")])
    _, code = run_evaluation(ROOT, "offline", tmp_path, strict=False)
    assert code == 0

- [ ] **Step 2: Run python -m pytest tests/evaluator/test_runner.py -v.**

Expected: FAIL because runner is absent.

- [ ] **Step 3: Implement profiles.**

    if profile not in {"offline", "live"}:
        raise ValueError(f"Unsupported profile: {profile}")
    report = EvaluationReport.create(profile, collect_findings(root, profile))
    write_report(report, output_dir)
    return report, int(strict and any(item.severity in {Severity.P0, Severity.P1} for item in report.findings))

Collect inventory/wheel first, offline pytest contracts second, and live contracts only in live. Preserve test node ID, stdout, stderr, and return code in failure evidence.

- [ ] **Step 4: Run tests and the CLI with --profile offline --output /tmp/eqlib-evaluator-smoke.**

Expected: PASS and report.json/report.md exist.

- [ ] **Step 5: Commit with feat: add eqlib dependency evaluator cli.**

### Task 4: Canonical OHLCV and Tencent fallback

**Files:**
- Modify: eqlib/data.py
- Create: tests/fixtures/data_sources/tencent_qfqday.json
- Modify: tests/test_data_utils.py
- Create: tests/test_data_source_contracts.py

**Interfaces:** _canonicalize_ohlcv(df, source_name, start_date, end_date) -> DataFrame | None; retain _validate_ohlcv and fetch_stock_data return types.

- [ ] **Step 1: Write raw-fixture failures.**

    frame = _fetch_from_tencent("000001", "20240102", "20240110", "qfq")
    assert frame.index.min() >= pd.Timestamp("2024-01-02")
    assert frame.index.max() <= pd.Timestamp("2024-01-10")
    assert frame.loc[pd.Timestamp("2024-01-10"), "open"] == pytest.approx(7.24)
    assert frame.loc[pd.Timestamp("2024-01-10"), "money"] == pytest.approx(783_771_200.0)

Also reject negative volume, NaT/duplicate/out-of-order indexes, nonfinite OHLC, and broken OHLC envelopes.

- [ ] **Step 2: Run python -m pytest tests/test_data_source_contracts.py -v.**

Expected: FAIL for current Tencent scaling/date handling.

- [ ] **Step 3: Canonicalize all provider frames before validation/cache/return.**

    result = df.copy()
    result.index = pd.to_datetime(result.index, errors="coerce").normalize()
    result = result[~result.index.isna()].sort_index()
    if result.index.has_duplicates:
        return None
    result = _slice_by_date(result, start_date, end_date)
    if not _validate_ohlcv(result, source_name):
        return None

Require finite positive OHLC, low <= min(open, close) <= max(open, close) <= high, and finite nonnegative volume/money. Add source/quality attrs.

- [ ] **Step 4: Preserve Tencent prices as yuan, use the fixture-confirmed 10_000 money multiplier, slice strictly, and reorder fetchers eastmoney -> sina -> tencent -> baostock. Cache and return copies.**

- [ ] **Step 5: Re-run source/data utility tests and commit with fix: validate and bound market-data fallbacks.**

### Task 5: Audited exchange calendar

**Files:**
- Create: eqlib/static/ashare_trading_days.json
- Modify: eqlib/data.py
- Modify: tests/test_calendar.py
- Modify: tests/test_data_source_contracts.py

**Interfaces:** _bundled_ashare_trading_days(start, end) -> tuple[date, ...]; get_trade_days adds keyword-only strict=False.

- [ ] **Step 1: Write failing fallback tests.**

    days = get_trade_days("2024-02-01", "2024-02-16")
    assert datetime.date(2024, 2, 9) not in days

    with pytest.raises(DataFetchError, match="calendar coverage"):
        get_trade_days("2030-01-01", "2030-01-31", strict=True)

Patch provider access to fail before each assertion.

- [ ] **Step 2: Run the calendar contracts.**

Expected: current fallback incorrectly admits 2024-02-09 and has no strict coverage failure.

- [ ] **Step 3: Commit a complete, versioned trading-days JSON generated from the exchange endpoint, covering every published day from 2020 through the final complete year. Record source, generation date, version, and coverage.**

- [ ] **Step 4: On provider failure, read the resource only within its coverage. strict=False logs and returns []; strict=True raises DataFetchError. Remove statutory-workday inference using chinese_calendar.is_workday.**

- [ ] **Step 5: Re-run calendar/data-cache/source contracts and commit with fix: use bundled exchange trading calendar fallback.**

### Task 6: Equity normalization and portfolio-risk P0s

**Files:**
- Create: eqlib/utils/equity.py
- Modify: eqlib/portfolio_risk.py
- Modify: tests/test_portfolio_risk.py
- Create: tests/test_equity_normalization.py

**Interfaces:** normalize_recorded_values(recorded_values) -> Series, daily_returns(recorded_values) -> Series; retain RiskReport and monitor public APIs.

- [ ] **Step 1: Write failures for unequal-NAV VaR, 30% drawdown kill switch, and adding concentration to a correlation kill never reducing severity.**

    _, var_pct = monitor_with_large_and_tiny_strategy().portfolio_var(confidence=0.95)
    assert var_pct == pytest.approx(0.10, abs=0.002)

    assert monitor_from_values([100] * 30 + [70]).daily_check().alert_level is AlertLevel.KILL_SWITCH

- [ ] **Step 2: Run tests.**

Expected: FAIL because current VaR equals strategy-count average and daily_check ignores MDD.

- [ ] **Step 3: Normalize unique, finite, positive recorded values and compute daily returns with pct_change(fill_method=None).**

    values = pd.Series(values, dtype=float).sort_index()
    if values.empty or not values.index.is_unique or not np.isfinite(values.to_numpy()).all() or (values <= 0).any():
        raise ValueError("recorded_values must contain unique, finite, positive total_value observations")

- [ ] **Step 4: Inner-align return streams, use each strategy's latest valid NAV weights, calculate aggregate MDD, and replace string comparison with explicit rank.**

    _ALERT_RANK = {AlertLevel.YELLOW: 0, AlertLevel.RED: 1, AlertLevel.KILL_SWITCH: 2}

    def _escalate(current, candidate):
        return candidate if _ALERT_RANK[candidate] > _ALERT_RANK[current] else current

- [ ] **Step 5: Re-run tests and commit with fix: enforce portfolio risk drawdown and nav weighting.**

### Task 7: Loss metrics and deterministic ML P0s

**Files:**
- Modify: eqlib/utils/stats.py
- Modify: tests/test_utils_stats.py
- Modify: eqlib/ml/models.py
- Modify: tests/test_ml_models.py

**Interfaces:** retain risk function and BaseMLModel public names.

- [ ] **Step 1: Write independent LPM2, invalid-confidence, all-positive VaR/CVaR tests plus X/y index permutation, all-zero classifier, prediction batch invariance, and Inf rejection tests.**

    expected = np.sqrt(np.mean(np.minimum(np.array([-0.01, 0.01]), 0.0) ** 2)) * np.sqrt(TRADING_DAYS_PER_YEAR)
    assert downside_deviation(pd.Series([-0.01, 0.01])) == pytest.approx(expected)

    with pytest.raises(ValueError):
        value_at_risk(pd.Series([-0.01, 0.02]), confidence=1.0)

- [ ] **Step 2: Run python -m pytest tests/test_utils_stats.py tests/test_ml_models.py -v.**

Expected: FAIL for formula, confidence, label position, first-column probability, and prediction-time median.

- [ ] **Step 3: Implement all-observation LPM2 and nonnegative loss semantics.**

    values = _validated_returns(returns)
    downside = np.sqrt(np.mean(np.minimum(values.to_numpy() - target, 0.0) ** 2)) * np.sqrt(annualize)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return max(0.0, -loss_quantile)

- [ ] **Step 4: Align y with y.reindex(X.index), retain fit-time feature medians, reject remaining nonfinite values, and locate positive class through classes_ rather than column position. Persist imputation state in save/load.**

    y_aligned = y.reindex(X.index)
    X_clean = X.loc[y_aligned.notna()].replace([np.inf, -np.inf], np.nan)
    self._imputation_values = X_clean.median(numeric_only=True)
    positive = np.flatnonzero(np.asarray(self._model.classes_) == 1)
    return np.zeros(len(X)) if not len(positive) else proba[:, positive[0]]

- [ ] **Step 5: Re-run ML and statistics integrations, then commit two focused commits: fix: make downside risk metrics mathematically consistent and fix: make ml preprocessing and probabilities deterministic.**

### Task 8: Benchmarks, network markers, CI, and documentation

**Files:**
- Create: evaluator/benchmarks.py
- Create: tests/evaluator/test_benchmarks.py
- Create: tests/evaluator/baselines/macos-py310.json
- Create: .github/workflows/eqlib-evaluator.yml
- Modify: evaluator/contracts.py
- Modify: pyproject.toml
- Create: docs/how-to/dependency-evaluator.md
- Create: docs/how-to/dependency-evaluator.en.md
- Modify: mkdocs.yml, install/FAQ bilingual pages
- Create: reports/evaluator/2026-08-17-initial-audit.md
- Create: reports/evaluator/2026-08-17-initial-audit.json
- Create: tests/evaluator/test_initial_audit.py

**Interfaces:** measure_benchmark(name, command, repeats=5), evaluate_benchmarks(root, baseline), network marker.

- [ ] **Step 1: Write a failing 2x benchmark regression test and checked-in report no-open-P0/P1 test.**

    monkeypatch.setattr("evaluator.benchmarks._samples", lambda *args: [2.1, 2.2, 2.3])
    assert any(item.id == "PERF-301" for item in evaluate_benchmarks(ROOT, {"import_eqlib": {"seconds": 1.0, "max_rss_mb": 100.0}}))

    blocking = [item for item in audit_payload["findings"] if item["severity"] in {"P0", "P1"} and item["status"] == "open"]
    assert blocking == []

- [ ] **Step 2: Run the new tests to verify both fail.**

- [ ] **Step 3: Measure repeated subprocess medians and platform RSS with /usr/bin/time -l on macOS or -v on Linux. Missing tooling creates PERF-302 unavailable evidence. Register network marker and keep offline contract selection at -m "not network"; live uses EQLIB_EVALUATOR_LIVE=1 and a 90-second deadline, converting timeout to DATA-190 unavailable.**

- [ ] **Step 4: Add workflow with Ubuntu 3.10 and 3.12 offline strict jobs on PR/push and an artifact upload. Add scheduled/workflow_dispatch live job after offline succeeds.**

    python-version: ${{ matrix.python-version }}
    name: eqlib-evaluator-${{ matrix.python-version }}
    path: artifacts/eqlib-evaluator

- [ ] **Step 5: Write bilingual How-to docs showing offline/live commands, severity semantics, report fields, provider limit, Python 3.10+, and all eight primary dependencies. Add both pages to How-to navigation. Generate a reviewed first audit that marks unavailable live evidence unavailable, never passed.**

- [ ] **Step 6: Run all gates.**

    python -m pytest tests/ -v --tb=short
    python scripts/check_doc_sync.py
    python -m pytest tests/test_examples_smoke.py -v --tb=short
    mkdocs build --strict
    python scripts/evaluate_eqlib_dependencies.py --profile offline --strict --output artifacts/eqlib-evaluator-final

Expected: all commands exit 0 and final report has no open P0/P1 finding.

- [ ] **Step 7: Commit with feat: gate eqlib dependency contracts in ci and docs: publish eqlib dependency evaluator audit.**

## Plan Self-Review

### Spec coverage

Tasks 1–3 implement inventory, isolated wheel, reports, strict exits, and profile orchestration. Tasks 4–5 implement data-source unit/date/schema and calendar risk protections. Tasks 6–7 implement portfolio, statistics, and ML P0 fixes. Task 8 provides performance evidence, separate CI lanes, bilingual docs, initial audit, and full verification.

### Placeholder scan

Every task has named files, inputs/outputs, a first failure, minimal implementation behavior, a verification command, and commit scope. No task depends on an undefined interface.

### Type consistency

Evaluator modules exchange Finding and EvaluationReport. Data consumers retain DataFrame returns. Portfolio code retains RiskReport. ML code retains BaseMLModel public methods. Each new helper is defined before its consuming task.

