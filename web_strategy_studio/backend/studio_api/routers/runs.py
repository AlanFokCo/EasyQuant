"""Runs: create, poll, cancel, SSE (§4.4, §4.6)."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api.backtest_executor import execute_backtest
from studio_api.db import SessionLocal, get_session
from studio_api.lint_service import lint_source
from studio_api.models import Run, Strategy
from studio_api.proc_registry import kill as kill_proc
from studio_api.schemas import CreateRunBody, CreateRunResponse, RunArtifacts, RunStatusResponse
from studio_api.stream_hub import stream_hub

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
                {"status": "cancelled", "artifacts": {"html_report_url": None, "json_report_url": None}},
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
                {"status": "failed", "artifacts": {"html_report_url": None, "json_report_url": None}},
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
            await stream_hub.publish(
                run_id,
                "done",
                {"status": "failed", "artifacts": {}},
            )
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
        await stream_hub.publish(
            run_id,
            "error",
            {"message": "Lint failed", "lint": lint_quick},
        )
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
                {"status": "cancelled", "artifacts": {"html_report_url": None, "json_report_url": None}},
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
        # S8: Check cancellation again after execute_backtest returns; the
        # cancel endpoint may have committed "cancelled" while the subprocess
        # was still running.  Early-return here avoids a duplicate done event.
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
        {"progress": 1.0 if exec_result.get("ok") else 0.0, "stage": "report", "message": "finished"},
    )
    await stream_hub.publish(
        run_id,
        "done",
        {"status": "succeeded" if exec_result.get("ok") else "failed", "artifacts": arts},
    )


@router.post("/runs", status_code=202, response_model=CreateRunResponse)
async def create_run(
    request: Request,
    body: CreateRunBody,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if idempotency_key:
        cache = getattr(request.app.state, "idempotency", {})
        entry = cache.get(idempotency_key)
        if entry is not None:
            rid, _exp = entry
            return CreateRunResponse(
                run_id=rid,
                status="queued",
                poll_url=f"/api/v1/runs/{rid}",
                ws_url=f"/api/v1/runs/{rid}/stream",
            )

    res = await session.execute(
        select(Strategy).options(selectinload(Strategy.versions)).where(Strategy.id == body.strategy_id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Strategy not found", "details": None}},
        )

    latest = max(strat.versions, key=lambda v: v.version)
    source = body.source_code if body.source_code is not None else latest.source_code

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
        from studio_api.config import settings
        expires_at = time.time() + settings.idempotency_ttl_sec
        request.app.state.idempotency[idempotency_key] = (run_id, expires_at)

    background_tasks.add_task(_process_run_task, run_id)

    return CreateRunResponse(
        run_id=run_id,
        status="queued",
        poll_url=f"/api/v1/runs/{run_id}",
        ws_url=f"/api/v1/runs/{run_id}/stream",
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Run not found", "details": None}},
        )
    err = None
    if run.error_message:
        err = f"{run.error_code or ''}: {run.error_message}"
    return RunStatusResponse(
        run_id=run.id,
        status=run.status,
        progress=run.progress,
        stage=run.stage,
        started_at=run.started_at,
        finished_at=run.finished_at,
        artifacts=_artifacts_response(run),
        error=err,
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Run not found", "details": None}},
        )
    if run.status in ("succeeded", "failed", "cancelled"):
        return {"ok": True, "status": run.status}

    # S8: Kill the subprocess first, then wait for it to exit (with a 5 s
    # timeout) before committing "cancelled" to the DB.  Without the wait,
    # the subprocess may still be writing artifacts when the DB is already
    # marked "cancelled", causing _process_run_task to emit a duplicate
    # done/error SSE event.
    from studio_api.proc_registry import kill as kill_proc_fn, _procs
    kill_proc_fn(run_id)
    proc = _procs.get(run_id)
    if proc is not None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass  # process didn't exit cleanly; proceed with DB update anyway

    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)
    await session.commit()
    await stream_hub.publish(
        run_id,
        "done",
        {"status": "cancelled", "artifacts": {"html_report_url": None, "json_report_url": None}},
    )
    return {"ok": True, "status": "cancelled"}


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str):
    from fastapi.responses import StreamingResponse

    async def event_gen():
        q = stream_hub.subscribe(run_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=3600.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                ev = msg["event"]
                payload = json.dumps(msg["data"], ensure_ascii=False)
                yield f"event: {ev}\ndata: {payload}\n\n"
                if ev in ("done", "error"):
                    break
        finally:
            stream_hub.unsubscribe(run_id, q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
