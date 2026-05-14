"""FastAPI application."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from studio_api.config import settings
from studio_api.db import init_db
from studio_api.routers import completion, format as fmt, health, lint as lint_r, runs, strategies


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    (settings.artifact_dir / "reports").mkdir(parents=True, exist_ok=True)
    await init_db()
    # S6: idempotency map stores (run_id, expires_at) pairs; expired entries
    # are cleaned up by _idempotency_cleanup_task.
    app.state.idempotency = {}  # {key: (run_id, expires_at)}
    cleanup_task = asyncio.create_task(_idempotency_cleanup_task(app))
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


async def _idempotency_cleanup_task(app: FastAPI) -> None:
    """Periodically expire old idempotency entries (S6)."""
    while True:
        await asyncio.sleep(300)  # run every 5 minutes
        now = time.time()
        cache: dict = app.state.idempotency
        expired = [k for k, (_, exp) in cache.items() if exp < now]
        for k in expired:
            cache.pop(k, None)


app = FastAPI(title="EasyQuant Web Strategy Studio API", version="0.1.0", lifespan=lifespan)

# S1: CORS — allow_origins from settings (defaults to localhost:5173/8080 only).
# allow_credentials=True requires an explicit origin list; ["*"] + credentials
# is disallowed by the browser spec and causes a preflight error.
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
