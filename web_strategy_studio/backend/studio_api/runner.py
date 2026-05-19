"""Runner protocol — LocalRunner (subprocess) and DockerRunner (sandboxed).

Selected via ``EQ_STUDIO_RUNNER=local|docker`` (default: ``local``).

.. warning::
    **LocalRunner provides NO sandboxing.**  User strategy code runs with the
    same privileges as the Studio backend process.  Only use LocalRunner on
    a trusted single-user machine where the API is bound to ``127.0.0.1``.

    For team / shared deployments set ``EQ_STUDIO_RUNNER=docker`` so each
    backtest executes inside a Docker container with:
    ``--network none --read-only --tmpfs /tmp --memory=2g --pids-limit=64
    --user 65534:65534 --security-opt no-new-privileges``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from studio_api.config import settings
from studio_api.proc_registry import register as register_proc
from studio_api.proc_registry import unregister as unregister_proc
from studio_api.stream_hub import stream_hub

_PROGRESS_RE = re.compile(r"Backtest progress[:\s]+(\d+)\s*/\s*(\d+)")


def _parse_iso(d: str):
    return datetime.strptime(d[:10], "%Y-%m-%d").date()


def _estimate_trading_fraction(done_days: int, start, end) -> float:
    total = max(len(pd.bdate_range(start=start, end=end)), 1)
    return min(0.95, 0.15 + 0.75 * (done_days / total))


# ── Runner protocol ──────────────────────────────────────────────────────────


class Runner(ABC):
    """Abstract interface for executing a user strategy backtest."""

    @abstractmethod
    async def run(
        self,
        run_id: str,
        source_code: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the backtest and return a result payload."""


# ── Shared helpers ───────────────────────────────────────────────────────────


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


def _build_env(artifact_sub: Path) -> Dict[str, str]:
    """Build a filtered environment dict for subprocess execution."""
    filtered: Dict[str, str] = {}
    for k, v in os.environ.items():
        if k in _ALLOWED_ENV_KEYS or any(k.startswith(p) for p in _ALLOWED_ENV_PREFIXES):
            filtered[k] = v
    return {
        **filtered,
        "PYTHONUNBUFFERED": "1",
        "EQ_ARTIFACT_DIR": str(artifact_sub),
        "EQ_REPO_ROOT": str(settings.repo_root.resolve()),
    }


def _make_run_config(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "start_date": params.get("start_date", "2024-01-01"),
        "end_date": params.get("end_date", "2024-12-31"),
        "starting_cash": float(params.get("starting_cash", 100_000)),
        "benchmark": params.get("benchmark", "000300.XSHG"),
        "use_local": bool(params.get("use_local", True)),
        "securities": params.get("securities"),
        "max_memory_mb": int(params.get("max_memory_mb", 1024)),
        # HIGH-21: pass through @param values to isolated runner
        "strategy_params": params.get("strategy_params"),
    }


async def _pump_and_collect(
    proc: asyncio.subprocess.Process,
    run_id: str,
    start,
    end,
) -> int:
    """Read stdout/stderr, publish log + progress events. Returns log line count."""
    import time as _time

    log_lines = 0
    last_activity_ts = _time.monotonic()

    async def pump_stream(stream, name: str) -> None:
        nonlocal log_lines, last_activity_ts
        while True:
            line_b = await stream.readline()
            if not line_b:
                break
            line = line_b.decode("utf-8", errors="replace").rstrip()
            log_lines += 1
            last_activity_ts = _time.monotonic()  # MED-27: track activity

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
        tick_start = _time.monotonic()
        while proc.returncode is None:
            await asyncio.sleep(2.0)
            # MED-27: use elapsed time as fallback when log_lines is stale
            elapsed = _time.monotonic() - tick_start
            active = _time.monotonic() - last_activity_ts < 30
            try:
                if active:
                    frac = _estimate_trading_fraction(log_lines // 2 + 1, start, end)
                else:
                    # Stale output — estimate progress by elapsed time (cap at 90%)
                    frac = min(0.90, 0.10 + 0.80 * (elapsed / max(settings.run_timeout_sec, 1)))
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

    return log_lines, timeout_payload


def _read_result(artifact_sub: Path, work: Path) -> Dict[str, Any]:
    """Read result.json from artifact dir (preferred) or work dir (fallback)."""
    for candidate in (artifact_sub / "result.json", work / "result.json"):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "error": "Invalid result.json", "error_code": "BAD_RESULT"}
    return {"ok": False, "error": "No result.json", "error_code": "NO_RESULT"}


def _enrich_result(payload: Dict[str, Any], artifact_sub: Path, run_id: str) -> Dict[str, Any]:
    """Add public URL fields to a successful result."""
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
    return payload


# ── LocalRunner (current behaviour, no sandbox) ──────────────────────────────


class LocalRunner(Runner):
    """Run backtest in a local subprocess (NO sandboxing)."""

    async def run(
        self,
        run_id: str,
        source_code: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        work = Path(tempfile.mkdtemp(prefix=f"eqrun_{run_id}_"))
        artifact_sub = settings.artifact_dir / "reports" / run_id
        artifact_sub.mkdir(parents=True, exist_ok=True)

        run_config = _make_run_config(params)
        (work / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
        (work / "user_strategy.py").write_text(source_code, encoding="utf-8")

        cmd = [sys.executable, "-m", "studio_api.isolated_runner", str(work)]

        await stream_hub.publish(
            run_id,
            "progress",
            {"progress": 0.08, "stage": "validate", "message": "Starting isolated runner"},
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(work),
            env=_build_env(artifact_sub),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        register_proc(run_id, proc)

        start = _parse_iso(str(run_config["start_date"]))
        end = _parse_iso(str(run_config["end_date"]))
        _, timeout_payload = await _pump_and_collect(proc, run_id, start, end)
        unregister_proc(run_id)

        if timeout_payload is not None:
            shutil.rmtree(work, ignore_errors=True)
            return timeout_payload

        payload = _read_result(artifact_sub, work)
        payload = _enrich_result(payload, artifact_sub, run_id)
        shutil.rmtree(work, ignore_errors=True)
        return payload


# ── DockerRunner (sandboxed) ─────────────────────────────────────────────────


class DockerRunner(Runner):
    """Run backtest inside a Docker container with resource limits and no network.

    Docker flags:
    ``--rm``              Clean up container after exit
    ``--network none``    No network access (use ``bridge`` if ``enable_network``)
    ``--read-only``       Root filesystem is read-only
    ``--tmpfs /tmp:size=512m`` Writable tmpfs for temp files
    ``--memory=<N>m``     Max RAM (OOM-kill if exceeded)
    ``--pids-limit=64``   Max processes (prevents fork bombs)
    ``--cpus=1``          Max CPU
    ``--user 65534:65534`` Run as nobody:nogroup
    ``--security-opt no-new-privileges``  Prevent privilege escalation
    """

    def _build_cmd(
        self,
        work_dir: str,
        artifact_dir: str,
    ) -> list[str]:
        """Construct the ``docker run`` command."""
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:size=512m",
            "--memory",
            str(settings.max_memory_mb) + "m",
            "--pids-limit",
            "64",
            "--cpus",
            "1",
            "--user",
            "65534:65534",
            "--security-opt",
            "no-new-privileges",
            "--volume",
            f"{work_dir}:/work:ro",
            "--volume",
            f"{artifact_dir}:/out:rw",
            "--workdir",
            "/work",
        ]

        if settings.enable_network:
            net_idx = cmd.index("none")
            cmd[net_idx] = "bridge"

        image = os.environ.get("EQ_STUDIO_RUNNER_IMAGE", "python:3.11-slim")
        cmd.append(image)
        cmd.extend(["python", "-m", "studio_api.isolated_runner", "/work"])
        return cmd

    async def run(
        self,
        run_id: str,
        source_code: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        work = Path(tempfile.mkdtemp(prefix=f"eqrun_{run_id}_"))
        artifact_sub = settings.artifact_dir / "reports" / run_id
        artifact_sub.mkdir(parents=True, exist_ok=True)

        run_config = _make_run_config(params)
        (work / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
        (work / "user_strategy.py").write_text(source_code, encoding="utf-8")

        await stream_hub.publish(
            run_id,
            "progress",
            {"progress": 0.08, "stage": "validate", "message": "Starting Docker sandbox"},
        )

        cmd = self._build_cmd(work_dir=str(work), artifact_dir=str(artifact_sub))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        register_proc(run_id, proc)

        start = _parse_iso(str(run_config["start_date"]))
        end = _parse_iso(str(run_config["end_date"]))
        _, timeout_payload = await _pump_and_collect(proc, run_id, start, end)
        unregister_proc(run_id)

        if timeout_payload is not None:
            shutil.rmtree(work, ignore_errors=True)
            return timeout_payload

        # Result is in artifact_sub (mapped to /out in container)
        payload = _read_result(artifact_sub, work)
        payload = _enrich_result(payload, artifact_sub, run_id)
        shutil.rmtree(work, ignore_errors=True)
        return payload


# ── Factory ──────────────────────────────────────────────────────────────────

_runner: Optional[Runner] = None


def get_runner() -> Runner:
    """Return the active Runner based on ``EQ_STUDIO_RUNNER`` env var.

    Valid values: ``local`` (default), ``docker``.
    Unknown values fall back to ``local``.
    """
    global _runner
    if _runner is not None:
        return _runner

    mode = os.environ.get("EQ_STUDIO_RUNNER", "local").lower().strip()
    if mode == "docker":
        _runner = DockerRunner()
    else:
        if mode != "local":
            warnings.warn(
                f"Unknown EQ_STUDIO_RUNNER={mode!r}; falling back to LocalRunner. "
                "Valid values: local, docker",
                UserWarning,
            )
        _runner = LocalRunner()
    return _runner


def reset_runner() -> None:
    """Reset the runner singleton (useful in tests that change env vars)."""
    global _runner
    _runner = None


async def execute_backtest(
    run_id: str,
    source_code: str,
    params: Dict[str, Any],
    on_log: Any = None,
) -> Dict[str, Any]:
    """Execute a backtest using the active Runner."""
    runner = get_runner()
    return await runner.run(run_id, source_code, params)
