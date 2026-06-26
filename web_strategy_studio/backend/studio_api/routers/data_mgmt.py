"""Data management router -- async, paginated, with batch operations.

Replaces the original synchronous file I/O with the async DataService
layer. All blocking eqlib.data_cache calls run in a thread pool via
asyncio.to_thread (inside DataService).

Endpoints:
  GET  /data/local            -- paginated stock listing with search & sort
  GET  /data/local/{code}     -- single stock detail
  POST /data/local/download   -- download & merge stock data
  POST /data/local/batch-delete -- batch delete local CSV files
  GET  /data/local/{code}/quality -- data quality report
  DEL  /data/local/{code}     -- delete single stock (kept for compat)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from studio_api import auth as auth_mod
from studio_api.models import User
from studio_api.services.data_service import DataService, validate_code

router = APIRouter(prefix="/api/v1", tags=["data"])

# Module-level singleton (stateless across requests, cache is instance-level)
_data_service = DataService()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class StockInfo(BaseModel):
    code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    size_bytes: int = 0
    size_human: str = ""


class PaginatedStocks(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    per_page: int


class DownloadRequestBody(BaseModel):
    securities: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    adjust: str = "qfq"


class DownloadResponse(BaseModel):
    ok: bool
    downloaded: List[str] = []
    merged: List[str] = []
    failed: List[Dict[str, str]] = []


class BatchDeleteRequest(BaseModel):
    codes: List[str]
    adjust: str = "qfq"


class BatchDeleteResponse(BaseModel):
    deleted: int
    deleted_codes: List[str] = []
    failed: List[Dict[str, str]] = []


class QualityReport(BaseModel):
    code: str
    exists: bool
    checks: List[Dict[str, Any]]
    score: int
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/data/local", response_model=PaginatedStocks)
async def list_local_data(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(50, ge=1, le=500, description="Items per page"),
    search: Optional[str] = Query(None, description="Filter by code or name"),
    sort_by: str = Query("code", description="Sort field"),
    sort_order: str = Query("asc", description="Sort direction", pattern="^(asc|desc)$"),
    adjust: str = Query("qfq", description="Adjust type"),
    current_user: User = Depends(auth_mod.get_current_user),
) -> PaginatedStocks:
    """List all stocks with local CSV data (paginated, searchable, sortable)."""
    stocks, total = await _data_service.list_stocks(
        page=page,
        per_page=per_page,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        adjust=adjust,
    )
    return PaginatedStocks(
        items=stocks,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/data/local/{code}")
async def get_local_stock_detail(
    code: str,
    adjust: str = Query("qfq", description="Adjust type"),
    current_user: User = Depends(auth_mod.get_current_user),
) -> Dict[str, Any]:
    """Get detailed info for a single stock's local data."""
    try:
        full_code = validate_code(code)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CODE", "message": str(exc)},
        ) from exc

    info = await _data_service.get_stock_detail(full_code, adjust=adjust)
    if not info:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"No local data for {code}"},
        )
    return info


@router.get("/data/local/{code}/quality", response_model=QualityReport)
async def get_data_quality(
    code: str,
    adjust: str = Query("qfq", description="Adjust type"),
    current_user: User = Depends(auth_mod.get_current_user),
) -> QualityReport:
    """Get a data quality report for a stock's local CSV data."""
    try:
        full_code = validate_code(code)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CODE", "message": str(exc)},
        ) from exc

    report = await _data_service.check_data_quality(full_code, adjust=adjust)
    return QualityReport(**report)


@router.post("/data/local/download", response_model=DownloadResponse)
async def download_local_data(
    body: DownloadRequestBody,
    current_user: User = Depends(auth_mod.get_current_user),
) -> DownloadResponse:
    """Download stock data and save to local CSV (merges with existing data)."""
    # Validate all codes up front
    normalized_codes: list[str] = []
    for code in body.securities:
        try:
            normalized_codes.append(validate_code(code))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_CODE", "message": str(exc)},
            ) from exc

    result = await _data_service.download_stocks(
        normalized_codes,
        start_date=body.start_date,
        end_date=body.end_date,
        adjust=body.adjust,
    )
    return DownloadResponse(**result)


@router.post("/data/local/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_local_data(
    body: BatchDeleteRequest,
    current_user: User = Depends(auth_mod.get_current_user),
) -> BatchDeleteResponse:
    """Delete local CSV data for multiple stocks at once."""
    if not body.codes:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_CODES", "message": "No codes provided"},
        )

    # Validate all codes up front
    normalized_codes: list[str] = []
    for code in body.codes:
        try:
            normalized_codes.append(validate_code(code))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_CODE", "message": str(exc)},
            ) from exc

    result = await _data_service.batch_delete(normalized_codes, adjust=body.adjust)
    return BatchDeleteResponse(**result)


@router.delete("/data/local/{code}")
async def delete_local_stock(
    code: str,
    adjust: str = Query("qfq", description="Adjust type"),
    current_user: User = Depends(auth_mod.get_current_user),
) -> Dict[str, Any]:
    """Delete local CSV data for a single stock (kept for backward compat)."""
    try:
        full_code = validate_code(code)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CODE", "message": str(exc)},
        ) from exc

    result = await _data_service.batch_delete([full_code], adjust=adjust)
    if result["deleted"] > 0:
        return {"ok": True, "message": f"Deleted local data for {full_code}"}
    raise HTTPException(
        status_code=404,
        detail={"code": "NOT_FOUND", "message": f"No local data for {code}"},
    )
