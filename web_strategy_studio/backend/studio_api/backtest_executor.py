"""Subprocess backtest executor + progress estimation."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from studio_api.config import settings
from studio_api.proc_registry import register as register_proc
from studio_api.proc_registry import unregister as unregister_proc
from studio_api.stream_hub import stream_hub


def _parse_iso(d: str) -> date:
    return datetime.strptime(d[:10], "%Y-%m-%d").date()


# Matches "📍 Backtest progress: 47/250 (18.8%)" and "Backtest progress 47/250"
_PROGRESS_RE = re.compile(r"Backtest progress[:\s]+(\d+)\s*/\s*(\d+)")


def _estimate_trading_fraction(done_days: int, start: date, end: date) -> float:
    """Rough progress from trading-day span when bar-level hooks are unavailable."""
    # Use pandas bdate_range (Mon-Fri) as a proxy for trading days (~250/yr)
    # instead of calendar days (~365/yr) to avoid the ~1.46x overestimate.
    total = max(len(pd.bdate_range(start=start, end=end)), 1)
    return min(0.95, 0.15 + 0.75 * (done_days / total))


async def execute_backtest(
    run_id: str,
    source_code: str,
    params: Dict[str, Any],
    on_log: Any = None,
) -> Dict[str, Any]:
    """Run isolated subprocess; stream logs; return artifact paths or error."""
    work = Path(tempfile.mkdtemp(prefix=f"eqrun_{run_id}_"))
    artifact_sub = settings.artifact_dir / "reports" / run_id
    artifact_sub.mkdir(parents=True, exist_ok=True)

    run_config = {
        "start_date": params.get("start_date", "2024-01-01"),
        "end_date": params.get("end_date", "2024-12-31"),
        "starting_cash": float(params.get("starting_cash", 100_000)),
        "benchmark": params.get("benchmark", "000300.XSHG"),
        "use_local": bool(params.get("use_local", False)),
        "securities": params.get("securities"),
        "max_memory_mb": int(params.get("max_memory_mb", 1024)),
    }
    (work / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
    (work / "user_strategy.py").write_text(source_code, encoding="utf-8")

    # S3: Filter environment variables to prevent secret leakage.
    # Only allow an explicit allowlist of safe variables; strip everything else
    # (OPENAI_API_KEY, AWS_*, database connection strings, etc.).
    _ALLOWED_ENV_PREFIXES = ("EQ_", "EQLIB_")
    _ALLOWED_ENV_KEYS = frozenset(
        {
            "PATH",
            "PYTHONPATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TZ",
            "USER",
            "LOGNAME",
            "TMPDIR",
            "TEMP",
            "TMP",
        }
    )

    filtered_env: Dict[str, str] = {}
    for k, v in os.environ.items():
        if k in _ALLOWED_ENV_KEYS or any(k.startswith(p) for p in _ALLOWED_ENV_PREFIXES):
            filtered_env[k] = v

    env = {
        **filtered_env,
        "PYTHONUNBUFFERED": "1",
        "EQ_ARTIFACT_DIR": str(artifact_sub),
        "EQ_REPO_ROOT": str(settings.repo_root.resolve()),
    }

    cmd = [
        sys.executable,
        "-m",
        "studio_api.isolated_runner",
        str(work),
    ]

    await stream_hub.publish(
        run_id,
        "progress",
        {"progress": 0.08, "stage": "validate", "message": "Starting isolated runner"},
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(work),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    register_proc(run_id, proc)

    start = _parse_iso(str(run_config["start_date"]))
    end = _parse_iso(str(run_config["end_date"]))
    log_lines = 0

    async def pump_stream(stream: asyncio.StreamReader, name: str) -> None:
        nonlocal log_lines
        while True:
            line_b = await stream.readline()
            if not line_b:
                break
            line = line_b.decode("utf-8", errors="replace").rstrip()
            log_lines += 1

            # S5: Parse structured progress lines emitted by the engine.
            # Format: "Backtest progress: N/M (pct%)" or "Backtest progress N/M"
            # The regex handles optional emoji prefix, colon, and trailing percentage.
            m = _PROGRESS_RE.search(line)
            if m:
                try:
                    done, total = int(m.group(1)), int(m.group(2))
                    if total > 0:
                        frac = min(0.92, 0.10 + 0.82 * done / total)
                        await stream_hub.publish(
                            run_id,
                            "progress",
                            {
                                "progress": frac,
                                "stage": "simulate",
                                "message": f"Day {done}/{total}",
                            },
                        )
                except (ValueError, IndexError):
                    pass

            await stream_hub.publish(
                run_id,
                "log",
                {
                    "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "stream": name,
                    "line": line,
                },
            )

    async def progress_tick() -> None:
        stage = "fetch_data"
        while proc.returncode is None:
            await asyncio.sleep(2.0)
            try:
                frac = _estimate_trading_fraction(log_lines // 2 + 1, start, end)
            except Exception:
                frac = 0.3
            await stream_hub.publish(
                run_id,
                "progress",
                {"progress": min(0.92, frac), "stage": stage, "message": "backtest running"},
            )
            stage = "simulate"

    t_out = asyncio.create_task(pump_stream(proc.stdout, "stdout"))  # type: ignore[arg-type]
    t_err = asyncio.create_task(pump_stream(proc.stderr, "stderr"))  # type: ignore[arg-type]
    t_prog = asyncio.create_task(progress_tick())

    timeout_payload: Optional[Dict[str, Any]] = None
    try:
        await asyncio.wait_for(proc.wait(), timeout=settings.run_timeout_sec)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        timeout_payload = {"ok": False, "error": "Run timed out", "error_code": "TIMEOUT"}
    finally:
        t_prog.cancel()
        try:
            await t_prog
        except asyncio.CancelledError:
            pass
        await asyncio.gather(t_out, t_err, return_exceptions=True)
        unregister_proc(run_id)

    if timeout_payload is not None:
        shutil.rmtree(work, ignore_errors=True)
        return timeout_payload

    result_path = work / "result.json"
    payload: Dict[str, Any] = {"ok": False, "error": "No result.json", "error_code": "NO_RESULT"}
    if result_path.is_file():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"ok": False, "error": "Invalid result.json", "error_code": "BAD_RESULT"}

    # Public URLs (served by FastAPI StaticFiles). Always use canonical paths so
    # the browser never receives host filesystem paths.
    if payload.get("ok"):
        html_file = artifact_sub / "report.html"
        json_file = artifact_sub / "report.json"
        if html_file.is_file():
            base = f"/static/reports/{run_id}"
            payload["html_report_url"] = f"{base}/report.html"
            payload["json_report_url"] = f"{base}/report.json" if json_file.is_file() else None
        else:
            payload["ok"] = False
            payload["error"] = "report.html not found after run"
            payload["error_code"] = "REPORT_MISSING"
            payload["html_report_url"] = None
            payload["json_report_url"] = None
    else:
        payload.setdefault("html_report_url", None)
        payload.setdefault("json_report_url", None)
    shutil.rmtree(work, ignore_errors=True)
    return payload
