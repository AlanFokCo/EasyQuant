"""FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from studio_api.config import settings
from studio_api.db import init_db
from studio_api.routers import completion, health, runs, strategies
from studio_api.routers import format as fmt
from studio_api.routers import lint as lint_r

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
app.mount("/static/reports", StaticFiles(directory=str(reports_root)), name="reports")

app.include_router(strategies.router)
app.include_router(runs.router)
app.include_router(lint_r.router)
app.include_router(fmt.router)
app.include_router(completion.router)
app.include_router(health.router)
