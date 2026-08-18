# eqlib Dependency Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 建立可重复、可读、可在 CI 门禁的 eqlib 依赖对抗性 evaluator，并修复首轮审查证实的依赖、数据、数值与 ML P0 风险。

**Architecture:** 在仓库根目录新增非公开 evaluator 维护包和薄 CLI。它收集依赖清单、wheel 元数据、离线契约和性能证据，输出稳定 Markdown/JSON finding 报告；核心回归仍以 pytest 验证。数据、风控和 ML 修复保持现有公共 API，并以冻结 fixture、独立 oracle 与变形不变量保护。

**Tech Stack:** Python 3.10–3.12、pytest、stdlib ast/venv/zipfile/json、tomli（仅 Python <3.11）、setuptools/build、NumPy、Pandas、scikit-learn、GitHub Actions。

## Global Constraints

- requires-python、classifiers、README 与中英文安装/FAQ 文档统一为 Python >=3.10。
- pyproject.toml 是发布依赖的唯一事实源；直接运行时导入必须属于主依赖或明确 optional extra。
- offline profile 不访问行情/provider endpoint；live profile 才访问网络，并具有总 deadline、每源请求上限与低并发。
- API 失败、数据缺口、schema 漂移不得在严格路径中表示为零值、完整数据或成功。
- 数值修复必须由独立 NumPy/Pandas oracle 或明确 metamorphic invariant 验证。
- 性能门禁比较同一受控环境的中位数和峰值 RSS，初始相对上限为基线的 2 倍。
- 所有 docs 下 Markdown 修改同步对应 English 文件，并运行 python scripts/check_doc_sync.py。
- 交易成本保持 examples/_defaults.py：印花税 0.05%、佣金 0.025%、最低 5 CNY。

---

## File Structure

| 路径 | 职责 |
|---|---|
| evaluator/models.py | finding、严重度、报告的数据模型。 |
| evaluator/report.py | 原子输出稳定 JSON/Markdown 报告。 |
| evaluator/inventory.py | 解析声明、扫描第三方导入、审计 extra/requirements。 |
| evaluator/wheel.py | 构建 wheel、读取实际 METADATA、在 venv 验证安装。 |
| evaluator/contracts.py | 运行指定离线/联网 pytest 契约，保留失败证据。 |
| evaluator/benchmarks.py | 子进程性能基线和相对回归比较。 |
| evaluator/runner.py | 按 profile 编排所有检查。 |
| scripts/evaluate_eqlib_dependencies.py | CLI 入口。 |
| tests/evaluator/ | evaluator 的单元、wheel、CLI、报告、性能测试。 |
| tests/fixtures/data_sources/ | 冻结、可审计的原始 provider payload。 |
| eqlib/utils/equity.py | recorded-values 到有序净值/收益的内部规范化。 |
| eqlib/data.py | canonical OHLCV、腾讯回退、日期区间和日历修复。 |
| eqlib/portfolio_risk.py | NAV 加权 VaR、MDD 和单调 alert 聚合。 |
| eqlib/utils/stats.py | LPM2 下行偏差和 VaR/CVaR 语义。 |
| eqlib/ml/models.py | X/y 对齐、训练期填补、有限性和正类概率。 |
| requirements/ | 由 pyproject.toml 生成、带 hash 的 Python 3.10 约束及其生成说明。 |
| .github/workflows/eqlib-evaluator.yml | 离线 PR 门禁与定时/手动 live 检查。 |

### Task 1: 建立 finding 和报告模型

**Files:**
- Create: evaluator/__init__.py
- Create: evaluator/models.py
- Create: evaluator/report.py
- Test: tests/evaluator/test_report.py

**Interfaces:**
- Produces: Severity, Finding, EvaluationReport, render_markdown(report), write_report(report, output_dir).
- Consumed by: inventory、wheel、contracts、benchmarks、runner。

- [ ] **Step 1: Write the failing report ordering and dual-format test.**

    from evaluator.models import EvaluationReport, Finding, Severity
    from evaluator.report import write_report

    def test_write_report_orders_findings_and_keeps_same_ids(tmp_path):
        report = EvaluationReport.create(
            profile="offline",
            findings=[
                Finding("DEP-002", Severity.P2, "secondary", "details"),
                Finding("DATA-101", Severity.P0, "critical", "details"),
            ],
        )
        json_path, markdown_path = write_report(report, tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert [item["id"] for item in payload["findings"]] == ["DATA-101", "DEP-002"]
        assert "# eqlib Dependency Evaluator Report" in markdown_path.read_text(encoding="utf-8")

- [ ] **Step 2: Run test to verify it fails.**

Run: python -m pytest tests/evaluator/test_report.py -v

Expected: FAIL with ModuleNotFoundError for evaluator.

- [ ] **Step 3: Write minimal model and writer.**

    class Severity(str, Enum):
        P0 = "P0"
        P1 = "P1"
        P2 = "P2"
        P3 = "P3"

        @property
        def rank(self) -> int:
            return {self.P0: 0, self.P1: 1, self.P2: 2, self.P3: 3}[self]

    @dataclass(frozen=True)
    class Finding:
        id: str
        severity: Severity
        title: str
        detail: str
        evidence: dict[str, Any] = field(default_factory=dict)
        remediation: str | None = None
        status: str = "open"

    @dataclass
    class EvaluationReport:
        profile: str
        started_at: str
        environment: dict[str, str]
        findings: list[Finding]

        @classmethod
        def create(cls, profile: str, findings: list[Finding]) -> "EvaluationReport":
            return cls(profile, datetime.now(timezone.utc).isoformat(), environment_snapshot(), findings)

        def ordered_findings(self) -> list[Finding]:
            return sorted(self.findings, key=lambda item: (item.severity.rank, item.id))

    def write_report(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "report.json"
        markdown_path = output_dir / "report.md"
        _atomic_write(json_path, json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        _atomic_write(markdown_path, render_markdown(report))
        return json_path, markdown_path

- [ ] **Step 4: Run test to verify it passes.**

Run: python -m pytest tests/evaluator/test_report.py -v

Expected: PASS.

- [ ] **Step 5: Commit.**

    git add evaluator tests/evaluator/test_report.py
    git commit -m "feat: add evaluator report model"

### Task 2: 实现依赖清单、AST 导入审计和 wheel 证据

**Files:**
- Create: evaluator/inventory.py
- Create: evaluator/wheel.py
- Test: tests/evaluator/test_inventory.py
- Test: tests/evaluator/test_wheel.py
- Modify: pyproject.toml
- Modify: requirements.txt
- Create: requirements/constraints-py310.txt
- Create: requirements/README.md

**Interfaces:**
- Produces: read_project_dependencies(root), scan_runtime_imports(root), evaluate_inventory(root).
- Produces: build_and_audit_wheel(root, work_dir) -> tuple[dict[str, Any], list[Finding]].
- Consumed by: evaluator.runner.run_evaluation().

- [ ] **Step 1: Write failing declaration and wheel tests.**

    def test_inventory_reports_direct_runtime_import_missing_from_metadata(tmp_path):
        _write_project(tmp_path, dependencies=["numpy>=1.23"])
        (tmp_path / "eqlib").mkdir()
        (tmp_path / "eqlib" / "data.py").write_text("import requests\n", encoding="utf-8")
        findings = evaluate_inventory(tmp_path)
        assert any(item.id == "DEP-001" and "requests" in item.detail for item in findings)

    def test_inventory_reports_stale_requirements_file(tmp_path):
        _write_project(tmp_path, dependencies=["numpy>=1.23", "requests>=2.0"])
        (tmp_path / "requirements.txt").write_text("numpy>=1.23\n", encoding="utf-8")
        assert any(item.id == "DEP-002" for item in evaluate_inventory(tmp_path))

    def test_wheel_metadata_contains_declared_runtime_dependencies(tmp_path):
        evidence, findings = build_and_audit_wheel(ROOT, tmp_path)
        names = {requirement_name(item) for item in evidence["requires_dist"]}
        assert {"requests", "scikit-learn"} <= names
        assert not any(item.id == "DEP-003" for item in findings)

- [ ] **Step 2: Run tests to verify they fail.**

Run: python -m pytest tests/evaluator/test_inventory.py tests/evaluator/test_wheel.py -v

Expected: FAIL because evaluator inventory/wheel APIs are absent.

- [ ] **Step 3: Implement AST-only scanning and declaration comparison.**

    _IMPORT_NAME_TO_DISTRIBUTION = {
        "sklearn": "scikit-learn",
        "chinese_calendar": "chinese-calendar",
    }

    def scan_runtime_imports(root: Path) -> set[str]:
        imported = set()
        for path in (root / "eqlib").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".", 1)[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".", 1)[0]]
                else:
                    continue
                for name in names:
                    if name not in _stdlib_module_names():
                        imported.add(_IMPORT_NAME_TO_DISTRIBUTION.get(name, name))
        return imported

    def evaluate_inventory(root: Path) -> list[Finding]:
        declared = read_project_dependencies(root)
        optional = read_optional_dependencies(root)
        missing = sorted(scan_runtime_imports(root) - declared - optional)
        findings = []
        if missing:
            findings.append(Finding("DEP-001", Severity.P1, "Undeclared runtime dependency", ", ".join(missing)))
        if (root / "requirements.txt").exists() and read_requirements(root / "requirements.txt") != declared:
            findings.append(Finding("DEP-002", Severity.P1, "requirements.txt differs from project metadata", "Regenerate or remove requirements.txt"))
        return findings

- [ ] **Step 4: Build a wheel and inspect its actual METADATA, not editable egg-info.**

    def build_and_audit_wheel(root: Path, work_dir: Path) -> tuple[dict[str, Any], list[Finding]]:
        dist_dir = work_dir / "dist"
        _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)], cwd=root)
        wheel_path = next(dist_dir.glob("*.whl"))
        metadata = _read_wheel_metadata(wheel_path)
        venv_dir = work_dir / "venv"
        _run([sys.executable, "-m", "venv", str(venv_dir)])
        venv_python = _venv_python(venv_dir)
        install = _run([str(venv_python), "-m", "pip", "install", str(wheel_path)], check=False)
        pip_check = _run([str(venv_python), "-m", "pip", "check"], check=False)
        findings = []
        if install.returncode != 0 or pip_check.returncode != 0:
            findings.append(Finding("DEP-003", Severity.P0, "Wheel dependency installation is inconsistent", install.stdout + install.stderr + pip_check.stdout + pip_check.stderr))
        return _evidence(wheel_path, metadata, venv_python, pip_check), findings

Use zipfile.ZipFile and email.message_from_bytes to parse the sole dist-info/METADATA. A blocked package index yields DEP-004 with status unavailable, never a pass.

- [ ] **Step 5: Align release metadata and commit a reproducible constraint.**

Add requests>=2.28.0 to project.dependencies. Make requirements.txt contain exactly akshare, chinese_calendar, pandas, numpy, matplotlib, scipy, scikit-learn, and requests with matching lower bounds. Add tomli>=2.0; python_version < "3.11", build>=1.2, and pip-tools>=7.4 to dev. Give fastparquet and xgboost explicit extras, or let inventory report their intentional optional status.

Under a clean Python 3.10 environment, generate `requirements/constraints-py310.txt` from the release metadata with `pip-compile --generate-hashes --extra dev --output-file requirements/constraints-py310.txt pyproject.toml`. `requirements/README.md` records this exact command, Python version, and the two-stage installation used by CI: `pip install --require-hashes -r requirements/constraints-py310.txt` followed by `pip install --no-deps -e ".[dev]"`. The evaluator tests that the lock has hashes and that its direct pins match the release metadata; a missing, malformed, or stale lock is a visible dependency finding rather than an implicit pass.

- [ ] **Step 6: Run focused validation and commit.**

Run: python -m pytest tests/evaluator/test_inventory.py tests/evaluator/test_wheel.py -v

Run: python -c "from evaluator.inventory import evaluate_inventory; from pathlib import Path; assert not [f for f in evaluate_inventory(Path('.')) if f.id in {'DEP-001', 'DEP-002'}]"

Expected: PASS.

    git add evaluator/inventory.py evaluator/wheel.py tests/evaluator/test_inventory.py tests/evaluator/test_wheel.py pyproject.toml requirements.txt requirements/
    git commit -m "fix: align eqlib runtime dependencies"

### Task 3: 实现 CLI、离线契约和退出码

**Files:**
- Create: evaluator/contracts.py
- Create: evaluator/runner.py
- Create: scripts/evaluate_eqlib_dependencies.py
- Test: tests/evaluator/test_runner.py

**Interfaces:**
- Consumes: --profile {offline,live}, --output PATH, --strict.
- Produces: run_evaluation(root, profile, output_dir, strict) -> tuple[EvaluationReport, int].

- [ ] **Step 1: Write failing strict-exit tests.**

    def test_runner_returns_nonzero_for_strict_p0(tmp_path, monkeypatch):
        monkeypatch.setattr("evaluator.runner.collect_findings", lambda *args: [Finding("NUM-201", Severity.P0, "bad", "bad")])
        _, exit_code = run_evaluation(ROOT, "offline", tmp_path, strict=True)
        assert exit_code == 1
        assert (tmp_path / "report.json").exists()

    def test_runner_keeps_p2_visible_without_non_strict_failure(tmp_path, monkeypatch):
        monkeypatch.setattr("evaluator.runner.collect_findings", lambda *args: [Finding("PERF-301", Severity.P2, "slow", "slow")])
        _, exit_code = run_evaluation(ROOT, "offline", tmp_path, strict=False)
        assert exit_code == 0

- [ ] **Step 2: Run test to verify it fails.**

Run: python -m pytest tests/evaluator/test_runner.py -v

Expected: FAIL with import error for run_evaluation.

- [ ] **Step 3: Implement profile routing and CLI.**

    def run_evaluation(root: Path, profile: str, output_dir: Path, strict: bool) -> tuple[EvaluationReport, int]:
        if profile not in {"offline", "live"}:
            raise ValueError(f"Unsupported profile: {profile}")
        findings = collect_findings(root, profile)
        report = EvaluationReport.create(profile=profile, findings=findings)
        write_report(report, output_dir)
        blocking = {Severity.P0, Severity.P1}
        return report, int(strict and any(item.severity in blocking for item in findings))

    parser = argparse.ArgumentParser(description="Audit eqlib dependency contracts")
    parser.add_argument("--profile", choices=("offline", "live"), default="offline")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eqlib-evaluator"))
    parser.add_argument("--strict", action="store_true")

collect_findings runs inventory and wheel first, then run_offline_contracts. It calls run_live_contracts only in the live profile. Contract failure evidence includes pytest node ID, stdout, stderr, and return code.

- [ ] **Step 4: Run CLI and test.**

Run: python -m pytest tests/evaluator/test_runner.py -v

Run: python scripts/evaluate_eqlib_dependencies.py --profile offline --output /tmp/eqlib-evaluator-smoke

Expected: PASS and both report.json and report.md exist.

- [ ] **Step 5: Commit.**

    git add evaluator scripts/evaluate_eqlib_dependencies.py tests/evaluator/test_runner.py
    git commit -m "feat: add eqlib dependency evaluator cli"

### Task 4: 加固 canonical OHLCV 和腾讯回退路径

**Files:**
- Modify: eqlib/data.py:260-670
- Create: tests/fixtures/data_sources/tencent_qfqday.json
- Modify: tests/test_data_utils.py
- Create: tests/test_data_source_contracts.py

**Interfaces:**
- Produces: _canonicalize_ohlcv(df, source_name, start_date, end_date) -> pd.DataFrame | None.
- Preserves: _validate_ohlcv(df, source_name) -> bool and fetch_stock_data(...) -> pd.DataFrame.

- [ ] **Step 1: Write raw Tencent and invalid-frame failure tests.**

    def test_tencent_adapter_keeps_yuan_prices_and_strictly_slices_requested_range(monkeypatch):
        monkeypatch.setattr("eqlib.data.requests.get", lambda *args, **kwargs: FakeResponse(TENCENT_PAYLOAD))
        frame = _fetch_from_tencent("000001", "20240102", "20240110", "qfq")
        assert frame.index.min() >= pd.Timestamp("2024-01-02")
        assert frame.index.max() <= pd.Timestamp("2024-01-10")
        assert frame.loc[pd.Timestamp("2024-01-10"), "open"] == pytest.approx(7.24)
        assert frame.loc[pd.Timestamp("2024-01-10"), "money"] == pytest.approx(783_771_200.0)

    @pytest.mark.parametrize("column,value", [("volume", -1), ("open", 12), ("date", pd.NaT)])
    def test_canonical_ohlcv_rejects_invalid_market_structure(column, value):
        frame = valid_frame()
        frame.loc[frame.index[0], column] = value
        assert not _validate_ohlcv(frame, "fixture")

- [ ] **Step 2: Run test to verify current failures.**

Run: python -m pytest tests/test_data_source_contracts.py -v

Expected: FAIL for Tencent unit/date and invalid structure.

- [ ] **Step 3: Implement common canonicalization.**

    def _canonicalize_ohlcv(df: pd.DataFrame, source_name: str, start_date=None, end_date=None) -> pd.DataFrame | None:
        required = ["open", "high", "low", "close", "volume"]
        if df.empty or not set(required).issubset(df.columns) or not isinstance(df.index, pd.DatetimeIndex):
            return None
        result = df.copy()
        result.index = pd.to_datetime(result.index, errors="coerce").normalize()
        result = result[~result.index.isna()].sort_index()
        if result.index.has_duplicates:
            return None
        for column in [*required, "money"]:
            if column in result:
                result[column] = pd.to_numeric(result[column], errors="coerce")
        if start_date is not None and end_date is not None:
            result = _slice_by_date(result, start_date, end_date)
        if not _validate_ohlcv(result, source_name):
            return None
        result.attrs["eqlib_source"] = source_name
        result.attrs["eqlib_quality"] = "valid"
        return result

_validate_ohlcv additionally requires a unique increasing DatetimeIndex, finite positive OHLC, low <= min(open, close) <= max(open, close) <= high, and finite nonnegative volume/money.

- [ ] **Step 4: Correct Tencent and constrain every cached candidate.**

In _fetch_from_tencent preserve float(k[1]) through float(k[4]) as yuan and convert amount by 10_000, then call _canonicalize_ohlcv. Reorder _DATA_FETCHERS to eastmoney, sina, tencent, baostock. In fetch_stock_data canonicalize before validation/cache/return:

    candidate = _canonicalize_ohlcv(df, source_name, start_str, end_str)
    if candidate is None:
        continue
    if not _covers_requested_start(candidate, start_str):
        fallback_df = _prefer_longer_candidate(fallback_df, candidate)
        continue
    _cache[cache_key] = candidate.copy()
    return candidate.copy()

- [ ] **Step 5: Run offline contracts and commit.**

Run: python -m pytest tests/test_data_source_contracts.py tests/test_data_utils.py -v

Expected: PASS without provider network access.

    git add eqlib/data.py tests/fixtures/data_sources/tencent_qfqday.json tests/test_data_source_contracts.py tests/test_data_utils.py
    git commit -m "fix: validate and bound market-data fallbacks"

### Task 5: 使用可审计交易所日历和明确覆盖范围

**Files:**
- Create: eqlib/static/ashare_trading_days.json
- Create: eqlib/static/__init__.py
- Modify: eqlib/data.py:840-1050
- Modify: pyproject.toml
- Modify: tests/test_calendar.py
- Modify: tests/test_data_source_contracts.py

**Interfaces:**
- Produces: _bundled_ashare_trading_days(start, end) -> tuple[datetime.date, ...].
- Preserves: get_trade_days() list return. Adds keyword-only strict: bool = False.

- [ ] **Step 1: Write failure tests.**

    def test_bundled_calendar_excludes_2024_lunar_new_year_eve_when_provider_fails(monkeypatch):
        monkeypatch.setattr("eqlib.data.ak.tool_trade_date_hist_sina", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
        days = get_trade_days("2024-02-01", "2024-02-16")
        assert datetime.date(2024, 2, 9) not in days

    def test_bundled_calendar_rejects_unknown_year_when_provider_fails(monkeypatch):
        monkeypatch.setattr("eqlib.data.ak.tool_trade_date_hist_sina", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
        with pytest.raises(DataFetchError, match="calendar coverage"):
            get_trade_days("2030-01-01", "2030-01-31", strict=True)

- [ ] **Step 2: Run test to verify present behavior.**

Run: python -m pytest tests/test_calendar.py tests/test_data_source_contracts.py -v

Expected: FAIL for 2024-02-09 and strict unavailable coverage.

- [ ] **Step 3: Add a complete versioned exchange-calendar resource.**

    {
      "schema_version": 1,
      "source": "akshare.tool_trade_date_hist_sina",
      "generated_on": "2026-08-17",
      "coverage": {"start": "2020-01-01", "end": "2026-12-31"},
      "trading_days": ["2024-02-08", "2024-02-16"]
    }

The committed list contains every published exchange trading day from 2020 through the final complete published year, not only the examples. Generation command and AkShare version are report evidence. Add `eqlib/static/__init__.py` and include `static/*.json` in setuptools package data so `importlib.resources.files("eqlib.static")` works from an installed wheel, not merely a source checkout.

- [ ] **Step 4: Read the resource and fail conservatively.**

    def _bundled_ashare_trading_days(start_date, end_date) -> tuple[datetime.date, ...]:
        payload = json.loads(resources.files("eqlib.static").joinpath("ashare_trading_days.json").read_text(encoding="utf-8"))
        start, end = pd.Timestamp(start_date).date(), pd.Timestamp(end_date).date()
        coverage = payload["coverage"]
        if start < pd.Timestamp(coverage["start"]).date() or end > pd.Timestamp(coverage["end"]).date():
            raise DataFetchError("calendar coverage is unavailable for the requested range")
        return tuple(day.date() for day in map(pd.Timestamp, payload["trading_days"]) if start <= day.date() <= end)

get_trade_days uses provider data if valid, then this bundled source. strict=False logs and returns [] when uncovered; strict=True raises DataFetchError. Remove fallback use of chinese_calendar.is_workday.

- [ ] **Step 5: Run regression tests and commit.**

Run: python -m pytest tests/test_calendar.py tests/test_data_diagnostics.py tests/test_data_source_contracts.py -v

Expected: PASS.

    git add eqlib/static/__init__.py eqlib/static/ashare_trading_days.json eqlib/data.py pyproject.toml tests/test_calendar.py tests/test_data_source_contracts.py
    git commit -m "fix: use bundled exchange trading calendar fallback"

### Task 6: 规范化净值/收益并修复组合风控 P0

**Files:**
- Create: eqlib/utils/equity.py
- Modify: eqlib/portfolio_risk.py:18-175,300-415
- Modify: tests/test_portfolio_risk.py
- Create: tests/test_equity_normalization.py

**Interfaces:**
- Produces: normalize_recorded_values(recorded_values) -> pd.Series and daily_returns(recorded_values) -> pd.Series.
- Preserves: PortfolioRiskMonitor.portfolio_var() and daily_check() return types.

- [ ] **Step 1: Write NAV-weighted VaR, drawdown kill, and alert-monotonicity failure tests.**

    def test_portfolio_var_is_nav_weighted_not_strategy_count_weighted():
        monitor = PortfolioRiskMonitor()
        monitor.add_strategy("large", result_from_values([1_000_000, 900_000] * 20))
        monitor.add_strategy("tiny", result_from_values([1, 1] * 20))
        _, var_pct = monitor.portfolio_var(confidence=0.95)
        assert var_pct == pytest.approx(0.10, abs=0.002)

    def test_thirty_percent_drawdown_triggers_kill_switch():
        monitor = PortfolioRiskMonitor()
        monitor.add_strategy("strategy", result_from_values([100] * 30 + [70]))
        report = monitor.daily_check()
        assert report.alert_level is AlertLevel.KILL_SWITCH
        assert any("回撤" in item for item in report.triggers)

    def test_adding_concentration_to_existing_kill_switch_never_reduces_alert(monkeypatch):
        monitor = monitor_with_kill_correlation()
        monkeypatch.setattr(monitor, "concentration_risk", lambda: concentration(max_single_stock=0.15))
        assert monitor.daily_check().alert_level is AlertLevel.KILL_SWITCH

- [ ] **Step 2: Run test to verify current failures.**

Run: python -m pytest tests/test_equity_normalization.py tests/test_portfolio_risk.py -v

Expected: FAIL for equal-weight VaR, inactive drawdown, and string alert comparison.

- [ ] **Step 3: Implement one recorded-values normalizer.**

    def normalize_recorded_values(recorded_values: Mapping | Sequence[Mapping]) -> pd.Series:
        rows = recorded_values.items() if isinstance(recorded_values, Mapping) else ((row["date"], row) for row in recorded_values)
        values = {pd.Timestamp(date): float(payload["total_value"]) for date, payload in rows}
        series = pd.Series(values, dtype=float).sort_index()
        if series.empty or not series.index.is_unique or not np.isfinite(series.to_numpy()).all() or (series <= 0).any():
            raise ValueError("recorded_values must contain unique, finite, positive total_value observations")
        return series

    def daily_returns(recorded_values: Mapping | Sequence[Mapping]) -> pd.Series:
        return normalize_recorded_values(recorded_values).pct_change(fill_method=None).dropna()

- [ ] **Step 4: Use NAV weights and explicit alert rank.**

    _ALERT_RANK = {AlertLevel.YELLOW: 0, AlertLevel.RED: 1, AlertLevel.KILL_SWITCH: 2}

    def _escalate(current: AlertLevel, candidate: AlertLevel) -> AlertLevel:
        return candidate if _ALERT_RANK[candidate] > _ALERT_RANK[current] else current

    def _portfolio_drawdown(self) -> float:
        curves = [normalize_recorded_values(result["recorded_values"]) for result in self._strategy_results.values()]
        combined = pd.concat(curves, axis=1).sum(axis=1, min_count=len(curves)).dropna()
        return float((combined / combined.cummax() - 1.0).min())

portfolio_var inner-joins return series and weights them by each last valid NAV divided by total NAV. daily_check compares drawdown to yellow/red/kill thresholds and uses _escalate for all risk sources.

- [ ] **Step 5: Run risk tests and commit.**

Run: python -m pytest tests/test_equity_normalization.py tests/test_portfolio_risk.py -v

Expected: PASS.

    git add eqlib/utils/equity.py eqlib/portfolio_risk.py tests/test_equity_normalization.py tests/test_portfolio_risk.py
    git commit -m "fix: enforce portfolio risk drawdown and nav weighting"

### Task 7: 修正 LPM2、VaR/CVaR 语义

**Files:**
- Modify: eqlib/utils/stats.py:133-198
- Modify: tests/test_utils_stats.py

**Interfaces:**
- Preserves function names and makes value_at_risk/conditional_var return nonnegative loss values.

- [ ] **Step 1: Write independent formula and boundary tests.**

    def test_downside_deviation_uses_all_observations_for_lpm2():
        returns = pd.Series([-0.01, 0.01])
        expected = np.sqrt(np.mean(np.minimum(returns.to_numpy(), 0.0) ** 2)) * np.sqrt(TRADING_DAYS_PER_YEAR)
        assert downside_deviation(returns) == pytest.approx(expected)

    @pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, 1.1])
    def test_var_rejects_invalid_tail_probability(confidence):
        with pytest.raises(ValueError, match="confidence"):
            value_at_risk(pd.Series([-0.01, 0.02]), confidence=confidence)

    def test_var_and_cvar_are_nonnegative_losses_for_all_positive_returns():
        returns = pd.Series([0.01, 0.02])
        assert value_at_risk(returns) == 0.0
        assert conditional_var(returns) == 0.0

- [ ] **Step 2: Run test to verify failures.**

Run: python -m pytest tests/test_utils_stats.py -v

Expected: FAIL for formula and confidence validation.

- [ ] **Step 3: Implement full-sample LPM2 and validated loss semantics.**

    def _validated_returns(returns: pd.Series) -> pd.Series:
        values = pd.to_numeric(returns, errors="coerce").dropna()
        if values.empty or not np.isfinite(values.to_numpy()).all():
            raise ValueError("returns must contain finite observations")
        return values.astype(float)

    def downside_deviation(returns: pd.Series, target: float = 0.0, annualize: int = TRADING_DAYS_PER_YEAR) -> float:
        values = _validated_returns(returns)
        return float(np.sqrt(np.mean(np.minimum(values.to_numpy() - target, 0.0) ** 2)) * np.sqrt(annualize))

    def value_at_risk(returns: pd.Series, confidence: float = 0.05, method: str = "historical") -> float:
        if not 0.0 < confidence < 1.0:
            raise ValueError("confidence must be between 0 and 1")
        loss_quantile = _quantile_by_method(_validated_returns(returns), confidence, method)
        return float(max(0.0, -loss_quantile))

conditional_var takes validated returns and returns max(0.0, -tail.mean()), with 0.0 for no loss tail.

- [ ] **Step 4: Run test and commit.**

Run: python -m pytest tests/test_utils_stats.py -v

Expected: PASS.

    git add eqlib/utils/stats.py tests/test_utils_stats.py
    git commit -m "fix: make downside risk metrics mathematically consistent"

### Task 8: 修复 ML 对齐、填补和正类概率

**Files:**
- Modify: eqlib/ml/models.py:150-280
- Modify: tests/test_ml_models.py

**Interfaces:**
- Preserves BaseMLModel.fit(X, y), predict(X), predict_proba(X), save(path), load(path).
- Adds internal _imputation_values: pd.Series | None.

- [ ] **Step 1: Write failing alignment, single-class, and batch-invariance tests.**

    def test_fit_aligns_labels_by_index_not_position():
        X = pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=["a", "b", "c"])
        y = pd.Series([7.0, 5.0, 3.0], index=["c", "b", "a"])
        model = BaseMLModel("logistic_regression", is_classifier=False).fit(X, y)
        assert model.predict(pd.DataFrame({"x": [4.0]}))[0] == pytest.approx(9.0)

    def test_classifier_returns_zero_positive_probability_when_class_one_is_absent():
        X = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
        model = BaseMLModel("random_forest", n_estimators=10).fit(X, pd.Series([0, 0, 0, 0]))
        assert np.all(model.predict(X) == 0.0)

    def test_prediction_of_missing_row_is_independent_of_other_prediction_rows():
        X = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "z": [1.0, 2.0, 3.0, 4.0]})
        model = BaseMLModel("logistic_regression").fit(X, pd.Series([0, 0, 1, 1]))
        one = model.predict(pd.DataFrame({"x": [np.nan], "z": [2.0]}))[0]
        together = model.predict(pd.DataFrame({"x": [np.nan, 1000.0], "z": [2.0, 2.0]}))[0]
        assert one == pytest.approx(together)

- [ ] **Step 2: Run tests to verify current failures.**

Run: python -m pytest tests/test_ml_models.py -v

Expected: FAIL for positional labels, first-column probability, and prediction-time median.

- [ ] **Step 3: Persist training-only imputation and align y.**

    def _prepare_fit_data(self, X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        if not X.index.is_unique or not y.index.is_unique:
            raise ValueError("X and y indexes must be unique")
        y_aligned = y.reindex(X.index)
        valid = y_aligned.notna()
        X_clean = X.loc[valid].replace([np.inf, -np.inf], np.nan)
        y_clean = y_aligned.loc[valid]
        if len(X_clean) < 2:
            raise ValueError("Insufficient data to train model (need >= 2 samples).")
        self._imputation_values = X_clean.median(numeric_only=True)
        if self._imputation_values.reindex(X_clean.columns).isna().any():
            raise ValueError("Each feature must have at least one finite training value")
        return X_clean.fillna(self._imputation_values), y_clean

    def _prepare_predict_data(self, X: pd.DataFrame) -> pd.DataFrame:
        if self._imputation_values is None:
            raise RuntimeError("Model imputation statistics are unavailable.")
        aligned = self._align_columns(X).replace([np.inf, -np.inf], np.nan)
        prepared = aligned.fillna(self._imputation_values)
        if not np.isfinite(prepared.to_numpy(dtype=float)).all():
            raise ValueError("Prediction features must be finite after training-data imputation")
        return prepared

fit returns self. predict locates class 1 using np.flatnonzero(np.asarray(self._model.classes_) == 1); absent class 1 returns zeros. save/load persist _imputation_values; old pickle fails with explicit compatibility error.

- [ ] **Step 4: Run related ML tests and commit.**

Run: python -m pytest tests/test_ml_models.py tests/test_ml_integration.py tests/test_ml_selector.py -v

Expected: PASS.

    git add eqlib/ml/models.py tests/test_ml_models.py
    git commit -m "fix: make ml preprocessing and probabilities deterministic"

### Task 9: 加入性能基线、网络 marker 和 CI

**Files:**
- Create: evaluator/benchmarks.py
- Modify: evaluator/contracts.py
- Create: tests/evaluator/test_benchmarks.py
- Create: tests/evaluator/baselines/macos-py310.json
- Create: .github/workflows/eqlib-evaluator.yml
- Modify: .github/workflows/test.yml
- Modify: pyproject.toml

**Interfaces:**
- Produces: measure_benchmark(name, command, repeats=5), evaluate_benchmarks(root, baseline).
- Consumes: pytest marker network declared in pyproject.toml.

- [ ] **Step 1: Write failing 2x-regression test.**

    def test_benchmark_marks_twofold_regression_as_p2(monkeypatch):
        monkeypatch.setattr("evaluator.benchmarks._samples", lambda *args: [2.1, 2.2, 2.3])
        baseline = {"import_eqlib": {"seconds": 1.0, "max_rss_mb": 100.0}}
        findings = evaluate_benchmarks(ROOT, baseline)
        assert any(item.id == "PERF-301" and item.severity is Severity.P2 for item in findings)

- [ ] **Step 2: Run test to verify it fails.**

Run: python -m pytest tests/evaluator/test_benchmarks.py -v

Expected: FAIL with import error for evaluator.benchmarks.

- [ ] **Step 3: Implement measured median and evidence-unavailable behavior.**

    def measure_benchmark(name: str, command: list[str], repeats: int = 5) -> BenchmarkResult:
        samples = _samples(command, repeats)
        return BenchmarkResult(name, statistics.median(item.seconds for item in samples), max(item.max_rss_mb for item in samples))

    def evaluate_benchmarks(root: Path, baseline: dict[str, dict[str, float]]) -> list[Finding]:
        result = measure_benchmark("import_eqlib", [sys.executable, "-c", "import eqlib"], repeats=5)
        expected = baseline["import_eqlib"]
        if result.seconds > expected["seconds"] * 2 or result.max_rss_mb > expected["max_rss_mb"] * 2:
            return [Finding("PERF-301", Severity.P2, "Cold import regression", "import eqlib exceeds approved 2x baseline", result.to_dict())]
        return []

Use /usr/bin/time -l on macOS and /usr/bin/time -v on Linux. Missing time tooling returns PERF-302 status unavailable, never a fabricated memory value.

- [ ] **Step 4: Mark real provider tests and restrict offline contracts.**

Add this pytest marker:

    markers = [
        "network: requires a real external data provider and is excluded from ordinary PR gates",
    ]

Mark true AkShare tests with pytest.mark.network. run_offline_contracts runs data contracts, calendar, portfolio risk, utility stats, and ML models with -m "not network". run_live_contracts uses only -m network, EQLIB_EVALUATOR_LIVE=1, and a 90-second total deadline; timeout becomes DATA-190 unavailable evidence.

- [ ] **Step 5: Add a two-lane GitHub Actions workflow.**

    name: eqlib Dependency Evaluator
    on:
      pull_request:
      push:
        branches: [main]
      schedule:
        - cron: "17 2 * * 1-5"
      workflow_dispatch:
    jobs:
      offline:
        runs-on: ubuntu-24.04
        strategy:
          matrix:
            python-version: ["3.10", "3.12"]
        steps:
          - uses: actions/checkout@v7
          - uses: actions/setup-python@v6
            with:
              python-version: ${{ matrix.python-version }}
          - run: python -m pip install -e ".[dev]"
          - run: python scripts/evaluate_eqlib_dependencies.py --profile offline --strict
          - uses: actions/upload-artifact@v4
            with:
              name: eqlib-evaluator-${{ matrix.python-version }}
              path: artifacts/eqlib-evaluator
      live:
        if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
        needs: offline
        runs-on: ubuntu-24.04
        steps:
          - uses: actions/checkout@v7
          - uses: actions/setup-python@v6
            with:
              python-version: "3.12"
          - run: python -m pip install -e ".[dev]"
          - run: python scripts/evaluate_eqlib_dependencies.py --profile live --output artifacts/eqlib-evaluator-live
          - uses: actions/upload-artifact@v4
            with:
              name: eqlib-evaluator-live
              path: artifacts/eqlib-evaluator-live

- [ ] **Step 6: Run evaluator, baseline, and workflow hygiene validation.**

Run: python -m pytest tests/evaluator tests/test_workflow_hygiene.py -v

Run: python scripts/evaluate_eqlib_dependencies.py --profile offline --strict --output artifacts/eqlib-evaluator

Expected: PASS with report artifacts. If local Python >=3.10 is unavailable, create an isolated Python 3.12 environment before claiming this outcome.

- [ ] **Step 7: Commit.**

    git add evaluator tests/evaluator .github/workflows/eqlib-evaluator.yml .github/workflows/test.yml pyproject.toml
    git commit -m "feat: gate eqlib dependency contracts in ci"

### Task 10: 发布初始报告、文档和完整验证

**Files:**
- Create: docs/how-to/dependency-evaluator.md
- Create: docs/how-to/dependency-evaluator.en.md
- Modify: mkdocs.yml
- Modify: docs/how-to/install.md
- Modify: docs/how-to/install.en.md
- Modify: docs/project/faq.md
- Modify: docs/project/faq.en.md
- Create: reports/evaluator/2026-08-17-initial-audit.md
- Create: reports/evaluator/2026-08-17-initial-audit.json
- Create: tests/evaluator/test_initial_audit.py

**Interfaces:**
- Documents profiles, exit codes, report fields, provider limitations, Python support, direct dependencies, and remediation status.
- Produces a versioned initial audit with fixed/open/unavailable findings.

- [ ] **Step 1: Write failing checked-in report test.**

    def test_checked_in_initial_audit_has_no_open_p0_or_p1():
        payload = json.loads((ROOT / "reports/evaluator/2026-08-17-initial-audit.json").read_text(encoding="utf-8"))
        blocking = [item for item in payload["findings"] if item["severity"] in {"P0", "P1"} and item["status"] == "open"]
        assert blocking == []

- [ ] **Step 2: Run test to verify it fails.**

Run: python -m pytest tests/evaluator/test_initial_audit.py -v

Expected: FAIL with FileNotFoundError.

- [ ] **Step 3: Write bilingual operation documentation.**

Both guides show:

    python scripts/evaluate_eqlib_dependencies.py --profile offline --strict
    python scripts/evaluate_eqlib_dependencies.py --profile live --output artifacts/eqlib-evaluator-live

Explain P0/P1 strict failures, P2/P3 reporting, live limits, report.json/report.md fields, and provider unavailability is not zero data. Update installation/FAQ to all eight primary distributions and Python 3.10+; add guide pages to How-to navigation.

- [ ] **Step 4: Generate and check in reviewed initial audit.**

Run: python scripts/evaluate_eqlib_dependencies.py --profile offline --strict --output reports/evaluator/2026-08-17-initial-audit-artifacts

Normalize machine-specific absolute paths/timestamps in committed JSON/Markdown. Preserve finding ID, severity, status, evidence summary, remediation commit, and residual external risk. A live check unavailable locally remains unavailable, never passed.

- [ ] **Step 5: Run complete quality gates.**

    python -m pytest tests/ -v --tb=short
    python scripts/check_doc_sync.py
    python -m pytest tests/test_examples_smoke.py -v --tb=short
    mkdocs build --strict
    python scripts/evaluate_eqlib_dependencies.py --profile offline --strict --output artifacts/eqlib-evaluator-final

Expected: every command exits 0 and final report has no open P0/P1 finding.

- [ ] **Step 6: Commit.**

    git add docs/how-to/dependency-evaluator.md docs/how-to/dependency-evaluator.en.md mkdocs.yml docs/how-to/install.md docs/how-to/install.en.md docs/project/faq.md docs/project/faq.en.md reports/evaluator tests/evaluator/test_initial_audit.py
    git commit -m "docs: publish eqlib dependency evaluator audit"

## Plan Self-Review

### Spec coverage

- Tasks 1–3 deliver isolated wheel audit, declaration/import consistency, readable JSON/Markdown reports, and strict exit codes.
- Tasks 4–5 deliver Tencent unit/date protection, canonical OHLCV, fixtures, exchange calendar evidence, and conservative coverage behavior.
- Tasks 6–8 deliver NAV-weighted VaR, drawdown kill switching, monotonic alerts, LPM2/VaR/CVaR, and deterministic ML preprocessing/probability semantics.
- Task 9 delivers performance evidence and separate offline/live CI lanes.
- Task 10 delivers bilingual instructions, versioned initial audit, and full verification.

### Placeholder scan

Every task names files, interfaces, a failing test, command, expected outcome, minimal implementation direction, and commit scope. No implementation step relies on an undefined new API.

### Type consistency

Evaluator modules exchange Finding and EvaluationReport. Data-source consumers retain DataFrame return types. Portfolio monitoring retains RiskReport. ML consumers retain BaseMLModel methods. New helper signatures appear before tasks that consume them.
