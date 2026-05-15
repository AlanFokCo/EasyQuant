"""
Isolated backtest runner (subprocess entrypoint).

Invoked as: python -m studio_api.isolated_runner <workdir>
"""

from __future__ import annotations

import json
import os
import runpy
import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: isolated_runner WORKDIR", file=sys.stderr)
        return 1
    work = Path(sys.argv[1])
    cfg_path = work / "run_config.json"
    if not cfg_path.is_file():
        print("EQ_ERROR: missing run_config.json", file=sys.stderr)
        return 2

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = Path(os.environ.get("EQ_ARTIFACT_DIR", work / "out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(os.environ.get("EQ_REPO_ROOT", ".")).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    user_path = work / "user_strategy.py"
    try:
        ns = runpy.run_path(str(user_path), run_name="__user_strategy__")
    except Exception as e:
        print(f"EQ_ERROR: load strategy: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _write_result(out_dir, work, ok=False, error=str(e), error_code="LOAD_FAIL")
        return 2

    initialize = ns.get("initialize")
    if not callable(initialize):
        print("EQ_ERROR: missing initialize()", file=sys.stderr)
        _write_result(out_dir, work, ok=False, error="missing initialize()", error_code="NO_INIT")
        return 2

    try:
        from eqlib import run_backtest
        from eqlib.report import generate_html_report, generate_report_json
    except ImportError as e:
        print(f"EQ_ERROR: eqlib import: {e}", file=sys.stderr)
        _write_result(out_dir, work, ok=False, error=str(e), error_code="NO_EQLIB")
        return 3

    securities = cfg.get("securities")
    if isinstance(securities, list) and not securities:
        securities = None

    try:
        result = run_backtest(
            initialize,
            cfg["start_date"],
            cfg["end_date"],
            starting_cash=float(cfg.get("starting_cash", 100_000)),
            benchmark=str(cfg.get("benchmark", "000300.XSHG")),
            securities=securities,
            use_local=bool(cfg.get("use_local", False)),
            max_memory_mb=int(cfg.get("max_memory_mb", 1024)),
        )
    except Exception as e:
        print(f"EQ_ERROR: backtest: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _write_result(out_dir, work, ok=False, error=str(e), error_code="BACKTEST_FAIL")
        return 4

    if result is None:
        print("EQ_ERROR: run_backtest returned None", file=sys.stderr)
        _write_result(out_dir, work, ok=False, error="no result", error_code="NO_RESULT")
        return 5

    html_path = out_dir / "report.html"
    json_path = out_dir / "report.json"
    reports_ok = True
    report_err = None

    # Generate HTML report (graceful degradation — if it fails, still return success)
    try:
        generate_html_report(result, str(html_path))
    except Exception as e:
        print(f"EQ_WARN: HTML report: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        reports_ok = False
        report_err = str(e)

    # Generate JSON report (needed for metrics API)
    try:
        generate_report_json(result, str(json_path))
    except Exception as e:
        print(f"EQ_WARN: JSON report: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        reports_ok = False
        report_err = report_err or str(e)

    _write_result(
        out_dir,
        work,
        ok=True,
        html=str(html_path.resolve()) if html_path.is_file() else None,
        report_json=str(json_path.resolve()) if json_path.is_file() else None,
        error=None,
        error_code=None,
    )
    if not reports_ok:
        print(json.dumps({"ok": True, "reports_warning": report_err}))
    else:
        print(json.dumps({"ok": True}))
    return 0


def _write_result(
    out_dir: Path,
    work: Path,
    *,
    ok: bool,
    html: str | None = None,
    report_json: str | None = None,
    error: str | None = None,
    error_code: str | None = None,
) -> None:
    # Local import: avoid any accidental shadowing of the stdlib `json` module.
    import json as json_stdlib

    body = {
        "ok": ok,
        "html": html,
        "json": report_json,
        "error": error,
        "error_code": error_code,
    }
    (work / "result.json").write_text(json_stdlib.dumps(body), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
