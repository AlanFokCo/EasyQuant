"""Reports router — serves report files, comparison, and export endpoints.

All endpoints are auth-gated (HIGH-15) and return CSP headers (HIGH-14).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api import auth as auth_mod
from studio_api.config import settings
from studio_api.db import get_session
from studio_api.models import Run, Strategy, User
from studio_api.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# Shared service instance
_report_service = ReportService(artifact_dir=settings.artifact_dir)

# CSP applied to all report content responses (HIGH-14)
_REPORT_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; sandbox allow-scripts"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_ownership(
    run_id: str,
    current_user: User,
    session: AsyncSession,
) -> None:
    """Raise 404 if *run_id* does not exist or does not belong to *current_user*."""
    result = await session.execute(
        select(Run, Strategy.owner_id)
        .join(Strategy, Run.strategy_id == Strategy.id)
        .where(Run.id == run_id)
    )
    row = result.first()
    if row is None or row.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Report not found")


def _file_response(path, media_type: str) -> FileResponse:
    """Build a FileResponse with the report CSP header."""
    resp = FileResponse(str(path), media_type=media_type)
    resp.headers["Content-Security-Policy"] = _REPORT_CSP
    return resp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{run_id}/report.html")
async def get_html_report(
    run_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve the HTML report for *run_id* (auth-gated, HIGH-15)."""
    await _verify_ownership(run_id, current_user, session)
    path = _report_service.get_report_path(run_id, "report.html")
    if path is None:
        return Response(status_code=404)
    return _file_response(path, "text/html")


@router.get("/{run_id}/report.json")
async def get_json_report(
    run_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve the JSON report for *run_id* (auth-gated, HIGH-15)."""
    await _verify_ownership(run_id, current_user, session)
    path = _report_service.get_report_path(run_id, "report.json")
    if path is None:
        return Response(status_code=404)
    return _file_response(path, "application/json")


@router.get("/{run_id}/metrics")
async def get_report_metrics(
    run_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return parsed report metrics as JSON (auth-gated)."""
    await _verify_ownership(run_id, current_user, session)
    data = _report_service.load_report_json(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return data


class CompareRequest(BaseModel):
    run_ids: List[str]


@router.post("/compare")
async def compare_reports(
    body: CompareRequest,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compare metrics across multiple reports (auth-gated).

    Only reports owned by the current user are included.
    """
    if len(body.run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 reports required")

    # Verify ownership for every requested run
    for run_id in body.run_ids:
        await _verify_ownership(run_id, current_user, session)

    return _report_service.compare_reports(body.run_ids)


@router.get("/{run_id}/export/{fmt}")
async def export_report(
    run_id: str,
    fmt: str,
    current_user: User = Depends(auth_mod.get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Export a report file as a download (auth-gated).

    Supported formats: ``html``, ``json``, ``pdf``, ``png``.
    """
    if fmt not in ("html", "json", "pdf", "png"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    await _verify_ownership(run_id, current_user, session)

    path = _report_service.get_export_path(run_id, fmt)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")

    media_map = {
        "html": "text/html",
        "json": "application/json",
        "pdf": "application/pdf",
        "png": "image/png",
    }
    resp = FileResponse(
        str(path),
        media_type=media_map[fmt],
        filename=f"report_{run_id}.{fmt}",
    )
    resp.headers["Content-Security-Policy"] = _REPORT_CSP
    return resp


@router.get("")
async def list_reports(
    current_user: User = Depends(auth_mod.get_current_user),
):
    """List run IDs that have generated reports."""
    return {"runs": _report_service.list_available_runs()}
