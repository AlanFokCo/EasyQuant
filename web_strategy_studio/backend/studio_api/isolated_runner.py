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
from typing import Optional

# 设置默认本地数据目录
EQLIB_LOCAL_DATA_DIR = os.environ.get("EQLIB_LOCAL_DATA_DIR", str(Path.home() / "eqlib_data"))
os.environ["EQLIB_LOCAL_DATA_DIR"] = EQLIB_LOCAL_DATA_DIR


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
        from eqlib.data_cache import save_stock_local, has_local_data
    except ImportError as e:
        print(f"EQ_ERROR: eqlib import: {e}", file=sys.stderr)
        _write_result(out_dir, work, ok=False, error=str(e), error_code="NO_EQLIB")
        return 3

    securities = cfg.get("securities")
    if isinstance(securities, list) and not securities:
        securities = None

    # HIGH-21: inject @param values from frontend into strategy's PARAMS dict
    strategy_params = cfg.get("strategy_params")
    if isinstance(strategy_params, dict):
        user_params = ns.get("PARAMS")
        if isinstance(user_params, dict):
            for k, v in strategy_params.items():
                if k in user_params:
                    old = user_params[k]
                    try:
                        user_params[k] = type(old)(v) if v is not None else old
                    except (TypeError, ValueError):
                        user_params[k] = v
                else:
                    user_params[k] = v
            print(f"EQ_INFO: injected {len(strategy_params)} strategy params")

    # 使用本地数据模式（默认 True，但尊重用户配置）
    use_local = bool(cfg.get("use_local", True))
    start_date = cfg["start_date"]
    end_date = cfg["end_date"]

    # 如果有股票列表且使用本地模式，预下载缺失的数据
    download_failures = []
    if use_local and securities and isinstance(securities, list) and len(securities) > 0:
        print(f"EQ_INFO: checking local data for {len(securities)} stocks...")

        for stock in securities:
            # 使用 eqlib 的 has_local_data() 检查，避免路径不一致问题
            if not has_local_data(stock, adjust="qfq"):
                print(f"EQ_INFO: downloading {stock}...")
                try:
                    save_stock_local(stock, start_date, end_date, adjust="qfq")
                    print(f"EQ_INFO: downloaded {stock}")
                except Exception as e:
                    print(f"EQ_ERROR: failed to download {stock}: {e}")
                    download_failures.append(stock)

        # 如果下载失败且使用本地模式，提前报错避免回测时数据缺失
        if download_failures:
            err_msg = f"Failed to download {len(download_failures)} stocks: {download_failures[:5]}"
            if len(download_failures) > 5:
                err_msg += f" ... and {len(download_failures) - 5} more"
            print(f"EQ_ERROR: {err_msg}", file=sys.stderr)
            _write_result(out_dir, work, ok=False, error=err_msg, error_code="DATA_DOWNLOAD_FAIL")
            return 3

    try:
        result = run_backtest(
            initialize,
            cfg["start_date"],
            cfg["end_date"],
            starting_cash=float(cfg.get("starting_cash", 100_000)),
            benchmark=str(cfg.get("benchmark", "000300.XSHG")),
            securities=securities,
            use_local=use_local,
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
    html: Optional[str] = None,
    report_json: Optional[str] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
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
