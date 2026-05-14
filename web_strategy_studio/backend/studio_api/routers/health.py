from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/healthz")
async def healthz():
    return {"status": "ok", "database": "sqlite"}


@router.get("/metrics")
async def metrics():
    # Minimal Prometheus-style text (counters stub per spec §8.4)
    body = "# HELP eq_studio_up Studio API process up\neq_studio_up 1\n"
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
