"""FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api import auth as auth_mod
from studio_api.config import settings
from studio_api.db import SessionLocal, get_session, init_db
from studio_api.models import User
from studio_api.routers import auth as auth_r
from studio_api.routers import completion, health, runs, strategies
from studio_api.routers import data_mgmt as data_r
from studio_api.routers import format as fmt
from studio_api.routers import lint as lint_r
from studio_api.routers import symbols as symbols_r

# ---------------------------------------------------------------------------
# Structured logging (stdlib JSON + structlog)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        (
            structlog.dev.ConsoleRenderer()
            if settings.api_host == "127.0.0.1"
            else structlog.processors.JSONRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)

_SYMBOLS_FILE = Path(__file__).resolve().parent / "data" / "eqlib_symbols.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    (settings.artifact_dir / "reports").mkdir(parents=True, exist_ok=True)
    await init_db()

    # BLOCKER-7: seed admin user on startup
    from studio_api.auth import ensure_admin_user

    async with SessionLocal() as session:
        admin = await ensure_admin_user(session)
        logger.info("auth_admin_ready", user_id=admin.id, username=admin.username)

    if not _SYMBOLS_FILE.is_file():
        logger.warning(
            "eqlib_symbols_missing",
            path=str(_SYMBOLS_FILE),
            hint="Run: python web_strategy_studio/scripts/build_symbols.py",
        )

    # B17: Mark orphan runs from previous server process as failed.
    from studio_api.run_queue import mark_orphan_runs_failed

    await mark_orphan_runs_failed()

    # B17/B18: Start the asyncio queue worker.
    from studio_api.run_queue import start_worker

    start_worker()

    # S6: idempotency map stores (run_id, expires_at) pairs.
    app.state.idempotency = {}
    cleanup_task = asyncio.create_task(_idempotency_cleanup_task(app))

    # B6: periodically evict expired SSE ring buffers.
    evict_task = asyncio.create_task(_sse_evict_task())

    yield

    cleanup_task.cancel()
    evict_task.cancel()
    for t in (cleanup_task, evict_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


async def _idempotency_cleanup_task(app: FastAPI) -> None:
    """Periodically expire old idempotency entries (S6)."""
    while True:
        await asyncio.sleep(300)
        now = time.time()
        cache: dict = app.state.idempotency
        expired = [k for k, (_, exp) in cache.items() if exp < now]
        for k in expired:
            cache.pop(k, None)


async def _sse_evict_task() -> None:
    """Periodically evict expired SSE ring buffers (B6)."""
    from studio_api.stream_hub import stream_hub

    while True:
        await asyncio.sleep(300)
        stream_hub.evict_expired()


app = FastAPI(title="EasyQuant Web Strategy Studio API", version="0.2.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Request ID middleware (injects X-Request-ID into request & response)
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# S1: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            }
        },
    )


reports_root = settings.artifact_dir / "reports"
reports_root.mkdir(parents=True, exist_ok=True)

# HIGH-14: CSP header applied to all auth-gated report responses.
# 'unsafe-inline' in script-src is required because the backtesting report HTML
# embeds Plotly/chart initialization as inline <script> blocks.
_REPORT_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; sandbox allow-scripts"
)


# HIGH-15: Authenticated report file endpoints (HTML)
@app.get("/api/v1/reports/{run_id}/report.html")
async def get_report_html(
    run_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve report HTML only to the run owner (HIGH-15)."""
    from sqlalchemy import select

    from studio_api.models import Run, Strategy

    result = await session.execute(
        select(Run, Strategy.owner_id)
        .join(Strategy, Run.strategy_id == Strategy.id)
        .where(Run.id == run_id)
    )
    row = result.first()
    if row is None or row.owner_id != current_user.id:
        return Response(status_code=404)

    file_path = reports_root / run_id / "report.html"
    if not file_path.is_file():
        return Response(status_code=404)

    # HIGH-14: CSP header on report content
    resp = FileResponse(str(file_path), media_type="text/html")
    resp.headers["Content-Security-Policy"] = _REPORT_CSP
    return resp


# HIGH-15: Authenticated report file endpoints (JSON)
@app.get("/api/v1/reports/{run_id}/report.json")
async def get_report_json(
    run_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve report JSON only to the run owner (HIGH-15)."""
    from sqlalchemy import select

    from studio_api.models import Run, Strategy

    result = await session.execute(
        select(Run, Strategy.owner_id)
        .join(Strategy, Run.strategy_id == Strategy.id)
        .where(Run.id == run_id)
    )
    row = result.first()
    if row is None or row.owner_id != current_user.id:
        return Response(status_code=404)

    file_path = reports_root / run_id / "report.json"
    if not file_path.is_file():
        return Response(status_code=404)

    resp = FileResponse(str(file_path), media_type="application/json")
    resp.headers["Content-Security-Policy"] = _REPORT_CSP
    return resp


app.include_router(strategies.router)
app.include_router(runs.router)
app.include_router(lint_r.router)
app.include_router(fmt.router)
app.include_router(completion.router)
app.include_router(health.router)
app.include_router(data_r.router)
app.include_router(auth_r.router)
app.include_router(symbols_r.router)
