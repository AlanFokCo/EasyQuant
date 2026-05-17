"""Runs: create, poll, cancel, SSE (§4.4, §4.6) — Phase 2 hardened."""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api.backtest_executor import execute_backtest
from studio_api.config import settings
from studio_api.db import SessionLocal, get_session
from studio_api.lint_service import lint_source
from studio_api.models import Run, Strategy
from studio_api.proc_registry import get_proc
from studio_api.proc_registry import kill as kill_proc
from studio_api.run_queue import (
    active_run_ids,
    enqueue,
    pending_run_ids,
    queue_position,
    rate_limiter,
)
from studio_api.schemas import (
    CompareResponse,
    CompareRunItem,
    CreateRunBody,
    CreateRunResponse,
    EquityCurvePoint,
    QueueRunItem,
    QueueStatusResponse,
    RunArtifacts,
    RunListItem,
    RunListResponse,
    RunMetricsResponse,
    RunStatusResponse,
    api_error,
)
from studio_api.stream_hub import stream_hub

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["runs"])


def _artifacts_response(run: Run) -> RunArtifacts:
    """HTTP paths only; never expose host filesystem paths from legacy DB rows."""
    if run.status != "succeeded":
        return RunArtifacts(html_report_url=None, json_report_url=None)
    rid = run.id
    return RunArtifacts(
        html_report_url=f"/static/reports/{rid}/report.html",
        json_report_url=f"/static/reports/{rid}/report.json",
    )


def _rid() -> str:
    return f"run_{secrets.token_hex(8)}"


async def _process_run_task(run_id: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        if run.status == "cancelled":
            await stream_hub.publish(
                run_id,
                "done",
                {
                    "status": "cancelled",
                    "artifacts": {"html_report_url": None, "json_report_url": None},
                },
            )
            return

        res_s = await session.execute(
            select(Strategy)
            .options(selectinload(Strategy.versions))
            .where(Strategy.id == run.strategy_id)
        )
        strat = res_s.scalar_one_or_none()
        if strat is None:
            run.status = "failed"
            run.error_code = "NO_STRATEGY"
            run.error_message = "Strategy missing"
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            await stream_hub.publish(
                run_id,
                "done",
                {
                    "status": "failed",
                    "artifacts": {"html_report_url": None, "json_report_url": None},
                },
            )
            return

        versions = {v.version: v for v in strat.versions}
        sv = versions.get(run.strategy_version)
        if sv is None:
            run.status = "failed"
            run.error_code = "NO_VERSION"
            run.error_message = "Strategy version not found"
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            await stream_hub.publish(run_id, "done", {"status": "failed", "artifacts": {}})
            return

        source = sv.source_code
        params = dict(run.params or {})

    await stream_hub.publish(
        run_id,
        "progress",
        {"progress": 0.05, "stage": "validate", "message": "Running static checks"},
    )

    lint_quick = lint_source(source, "fast")
    if not lint_quick["ok"]:
        async with SessionLocal() as session:
            run = await session.get(Run, run_id)
            if run and run.status != "cancelled":
                run.status = "failed"
                run.error_code = "LINT_FAILED"
                run.error_message = "Lint or security check failed before execution"
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()
        await stream_hub.publish(run_id, "error", {"message": "Lint failed", "lint": lint_quick})
        await stream_hub.publish(
            run_id,
            "done",
            {"status": "failed", "artifacts": {"html_report_url": None, "json_report_url": None}},
        )
        return

    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        if run.status == "cancelled":
            await stream_hub.publish(
                run_id,
                "done",
                {
                    "status": "cancelled",
                    "artifacts": {"html_report_url": None, "json_report_url": None},
                },
            )
            return
        run.status = "running"
        run.stage = "fetch_data"
        run.started_at = datetime.now(timezone.utc)
        await session.commit()

    exec_result = await execute_backtest(run_id, source, params)

    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        # S8: Check cancellation again after execute_backtest returns.
        if run.status == "cancelled":
            await session.commit()
            return

        finished = datetime.now(timezone.utc)
        run.finished_at = finished
        if exec_result.get("ok"):
            run.status = "succeeded"
            run.progress = 1.0
            run.stage = "report"
            run.html_path = exec_result.get("html_report_url")
            run.json_path = exec_result.get("json_report_url")
            run.error_code = None
            run.error_message = None
        else:
            run.status = "failed"
            run.error_code = exec_result.get("error_code", "RUN_FAILED")
            run.error_message = exec_result.get("error", "Unknown error")
            run.progress = 0.0
        await session.commit()

    arts = {
        "html_report_url": exec_result.get("html_report_url"),
        "json_report_url": exec_result.get("json_report_url"),
    }
    await stream_hub.publish(
        run_id,
        "progress",
        {
            "progress": 1.0 if exec_result.get("ok") else 0.0,
            "stage": "report",
            "message": "finished",
        },
    )
    done_payload: Dict[str, Any] = {
        "status": "succeeded" if exec_result.get("ok") else "failed",
        "artifacts": arts,
    }
    if not exec_result.get("ok"):
        done_payload["error_code"] = exec_result.get("error_code")
        done_payload["error_message"] = exec_result.get("error")
    await stream_hub.publish(run_id, "done", done_payload)


@router.post("/runs", status_code=202, response_model=CreateRunResponse)
async def create_run(
    request: Request,
    body: CreateRunBody,
    session: AsyncSession = Depends(get_session),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    # B18: per-IP rate limit
    client_ip = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    allowed, _remaining = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=api_error(
                "RATE_LIMITED",
                f"Too many run requests. Max {settings.rate_limit_runs_per_window} per "
                f"{settings.rate_limit_window_sec // 60} minutes.",
            ),
        )

    if idempotency_key:
        cache = getattr(request.app.state, "idempotency", {})
        entry = cache.get(idempotency_key)
        if entry is not None:
            rid, _exp = entry
            pos = queue_position(rid)
            return CreateRunResponse(
                run_id=rid,
                status="queued",
                poll_url=f"/api/v1/runs/{rid}",
                stream_url=f"/api/v1/runs/{rid}/stream",
                queue_position=pos,
            )

    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == body.strategy_id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))

    # Use the current version's source code.
    current_sv = next(
        (v for v in strat.versions if v.version == strat.current_version),
        max(strat.versions, key=lambda v: v.version),
    )
    _source = body.source_code if body.source_code is not None else current_sv.source_code

    merged_params = body.params.model_dump()
    if strat.default_params:
        for k, v in strat.default_params.items():
            merged_params.setdefault(k, v)

    run_id = _rid()
    run = Run(
        id=run_id,
        strategy_id=body.strategy_id,
        strategy_version=strat.current_version,
        status="queued",
        progress=0.0,
        stage="validate",
        params=merged_params,
    )
    session.add(run)
    await session.commit()

    if idempotency_key:
        expires_at = time.time() + settings.idempotency_ttl_sec
        request.app.state.idempotency[idempotency_key] = (run_id, expires_at)

    # B17: use asyncio queue instead of BackgroundTasks
    await enqueue(run_id, lambda rid=run_id: _process_run_task(rid))
    pos = queue_position(run_id)

    log.info("run.created", run_id=run_id, strategy_id=body.strategy_id, queue_position=pos)
    return CreateRunResponse(
        run_id=run_id,
        status="queued",
        poll_url=f"/api/v1/runs/{run_id}",
        stream_url=f"/api/v1/runs/{run_id}/stream",
        queue_position=pos,
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Run not found"))
    err = None
    if run.error_message:
        err = f"{run.error_code or ''}: {run.error_message}"
    pos = queue_position(run_id)
    return RunStatusResponse(
        run_id=run.id,
        status=run.status,
        progress=run.progress,
        stage=run.stage,
        started_at=run.started_at,
        finished_at=run.finished_at,
        artifacts=_artifacts_response(run),
        error=err,
        queue_position=pos,
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Run not found"))
    if run.status in ("succeeded", "failed", "cancelled"):
        return {"ok": True, "status": run.status}

    # S8: Kill the subprocess first, then wait for it to exit (with a 5 s timeout).
    kill_proc(run_id)
    proc = get_proc(run_id)
    if proc is not None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)
    await session.commit()
    await stream_hub.publish(
        run_id,
        "done",
        {"status": "cancelled", "artifacts": {"html_report_url": None, "json_report_url": None}},
    )
    return {"ok": True, "status": "cancelled"}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str, session: AsyncSession = Depends(get_session)):
    """Delete a run record and its artifacts."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Run not found"))
    if run.status in ("queued", "running"):
        kill_proc(run_id)

    # Defensive: derive the artifact path from run_id (trusted) rather than
    # from html_path (stored in DB and potentially poisoned).  Only delete
    # if the resolved directory is under the expected reports root.
    if run.html_path:
        reports_root = (settings.artifact_dir / "reports").resolve()
        report_dir = (reports_root / run_id).resolve()
        if report_dir.is_relative_to(reports_root) and report_dir.is_dir():
            shutil.rmtree(report_dir, ignore_errors=True)

    await session.delete(run)
    await session.commit()
    return {"ok": True}


@router.get("/runs/{run_id}/stream")
async def run_stream(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """SSE endpoint with Last-Event-ID replay and immediate done for terminal runs (B6/B13)."""
    # Resolve last_event_id to an int (default -1 = send everything).
    resume_from: int = -1
    if last_event_id:
        try:
            resume_from = int(last_event_id)
        except ValueError:
            resume_from = -1

    async def event_gen():
        # B6/B13: Check if the run is already terminal in DB; if so, immediately
        # replay buffered events (from resume_from) and close — no 1-hour wait.
        run = await session.get(Run, run_id)
        terminal_in_db = run is not None and run.status in ("succeeded", "failed", "cancelled")

        buf = stream_hub.get_buffer(run_id)

        if terminal_in_db and buf is not None:
            # Replay missed events from ring buffer.
            missed = buf.missed_since(resume_from)
            for entry in missed:
                yield stream_hub.format_sse(entry["id"], entry["event"], entry["data"])
            # If the terminal event was already in the buffer, we're done.
            if buf.terminal is not None:
                return
        elif terminal_in_db and buf is None:
            # No buffer (expired or server restart). Synthesize a done event.
            status = run.status if run else "unknown"
            arts = {"html_report_url": None, "json_report_url": None}
            if run and run.status == "succeeded":
                arts = {
                    "html_report_url": f"/static/reports/{run_id}/report.html",
                    "json_report_url": f"/static/reports/{run_id}/report.json",
                }
            yield stream_hub.format_sse(0, "done", {"status": status, "artifacts": arts})
            return

        # Live subscription path.
        q = stream_hub.subscribe(run_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                ev = msg["event"]
                eid = msg.get("id", 0)
                yield stream_hub.format_sse(eid, ev, msg["data"])
                if ev in ("done", "error"):
                    break
        finally:
            stream_hub.unsubscribe(run_id, q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Queue status (B17/B18)
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue():
    """Return current queue depth and per-run positions."""
    pending = pending_run_ids()
    return QueueStatusResponse(
        queue_length=len(pending),
        active_count=len(active_run_ids()),
        max_concurrent=settings.max_concurrent_runs,
        queued_runs=[
            QueueRunItem(run_id=rid, queue_position=i + 1) for i, rid in enumerate(pending)
        ],
    )


# ---------------------------------------------------------------------------
# Runs list, metrics, compare (§4.5)
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    session: AsyncSession = Depends(get_session),
    strategy_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Return a paginated list of all backtest runs."""
    q = (
        select(Run)
        .options(selectinload(Run.strategy))
        .order_by(Run.started_at.desc(), Run.id.desc())
    )
    if strategy_id:
        q = q.where(Run.strategy_id == strategy_id)

    from sqlalchemy import func as sa_func

    count_q = select(sa_func.count(Run.id))
    if strategy_id:
        count_q = count_q.where(Run.strategy_id == strategy_id)
    total = (await session.execute(count_q)).scalar_one() or 0

    rows = (await session.execute(q.limit(limit).offset(offset))).scalars().all()
    items: List[RunListItem] = []
    for run in rows:
        items.append(
            RunListItem(
                run_id=run.id,
                strategy_id=run.strategy_id,
                strategy_name=run.strategy.name if run.strategy else None,
                status=run.status,
                progress=run.progress,
                stage=run.stage,
                started_at=run.started_at,
                finished_at=run.finished_at,
                error_message=run.error_message,
                queue_position=queue_position(run.id),
            )
        )
    return RunListResponse(runs=items, total=total)


def _read_metrics_from_json(run: Run) -> Dict[str, Any]:
    """Try to read metrics from the stored report.json artifact."""
    alt = settings.artifact_dir / "reports" / run.id / "report.json"
    if alt.is_file():
        try:
            return json.loads(alt.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    if run.json_path:
        p = Path(run.json_path)
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def _extract_equity_curve(raw: Dict[str, Any]) -> List[EquityCurvePoint]:
    """Extract equity curve from report.json.

    eqlib uses ``cumulative_returns`` as a list of
    ``{"date": "YYYY-MM-DD", "total_value": float, "cumulative_return": float}``.
    We expose it as ``{"date": str, "value": float}`` (portfolio value).
    """
    points = raw.get("cumulative_returns", [])
    result: List[EquityCurvePoint] = []
    for p in points:
        date = p.get("date")
        value = p.get("total_value")
        if date and value is not None:
            try:
                result.append(EquityCurvePoint(date=str(date), value=float(value)))
            except (TypeError, ValueError):
                pass
    return result


_METRIC_KEYS = (
    "total_return",
    "annual_return",
    "annual_volatility",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "calmar_ratio",
    "alpha",
    "beta",
    "information_ratio",
    "win_rate_daily",
    "win_rate_trade",
)


def _extract_metrics(raw: Dict[str, Any]) -> Dict[str, Optional[float]]:
    risk = raw.get("risk_metrics", raw)
    metrics: Dict[str, Optional[float]] = {}
    for key in _METRIC_KEYS:
        val = risk.get(key)
        if val is not None:
            try:
                metrics[key] = float(val)
            except (TypeError, ValueError):
                metrics[key] = None
        else:
            metrics[key] = None
    return metrics


@router.get("/runs/{run_id}/metrics", response_model=RunMetricsResponse)
async def get_run_metrics(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Run not found"))
    raw = _read_metrics_from_json(run)
    return RunMetricsResponse(
        run_id=run.id,
        status=run.status,
        metrics=_extract_metrics(raw),
        raw=raw,
    )


@router.post("/runs/compare", response_model=CompareResponse)
async def compare_runs(
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_session),
):
    """Compare metrics + equity curves across multiple runs (B22)."""
    run_ids: List[str] = body.get("run_ids", [])
    if not run_ids:
        raise HTTPException(
            status_code=400,
            detail=api_error("BAD_REQUEST", "run_ids is required and must be non-empty"),
        )

    # Eager-load strategy to avoid lazy-load in async context.
    stmt = select(Run).options(selectinload(Run.strategy)).where(Run.id.in_(run_ids))
    rows = (await session.execute(stmt)).scalars().all()
    runs_by_id = {r.id: r for r in rows}

    runs_items: List[CompareRunItem] = []
    all_metric_keys: Set[str] = set()

    for rid in run_ids:
        run = runs_by_id.get(rid)
        if run is None:
            continue
        raw = _read_metrics_from_json(run)
        metrics = _extract_metrics(raw)
        all_metric_keys.update(metrics.keys())
        equity_curve = _extract_equity_curve(raw)
        runs_items.append(
            CompareRunItem(
                run_id=run.id,
                strategy_name=run.strategy.name if run.strategy else None,
                status=run.status,
                started_at=run.started_at,
                metrics=metrics,
                equity_curve=equity_curve,
            )
        )
    common = sorted(all_metric_keys)
    return CompareResponse(runs=runs_items, common_keys=common)


@router.get("/runs/{run_id}/report/data")
async def get_run_report_data(run_id: str, session: AsyncSession = Depends(get_session)):
    """Return the full report.json contents for native frontend rendering."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Run not found"))
    if run.status != "succeeded":
        raise HTTPException(
            status_code=400, detail=api_error("RUN_NOT_SUCCEEDED", "Run has not completed")
        )
    raw = _read_metrics_from_json(run)
    if not raw:
        raise HTTPException(
            status_code=404, detail=api_error("REPORT_NOT_FOUND", "Report data not found")
        )
    return JSONResponse(content=raw)
