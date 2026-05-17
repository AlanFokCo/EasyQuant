"""Data management router — list, download, delete local CSV data."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from eqlib import data_cache as dc

router = APIRouter(prefix="/api/v1", tags=["data"])


class LocalStockInfo(BaseModel):
    code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    size_bytes: int = 0
    size_human: str = ""


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


@router.get("/data/local")
async def list_local_data() -> List[LocalStockInfo]:
    """List all stocks that have local CSV data with date range and file size."""
    stocks = dc.list_local_stocks(adjust="qfq")
    result = []
    for code in stocks:
        info = dc.get_local_file_info(code, adjust="qfq")
        if info:
            result.append(
                LocalStockInfo(
                    code=info["code"],
                    start_date=info["start_date"],
                    end_date=info["end_date"],
                    size_bytes=info["size_bytes"],
                    size_human=info["size_human"],
                )
            )
    return result


@router.get("/data/local/{code}")
async def get_local_stock_detail(code: str) -> Dict[str, Any]:
    """Get detailed info for a single stock's local data."""
    full_code = _normalize_code(code)
    info = dc.get_local_file_info(full_code, adjust="qfq")
    if not info:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"No local data for {code}"})
    return info


@router.post("/data/local/download")
async def download_local_data(body: DownloadRequestBody) -> DownloadResponse:
    """Download stock data and save to local CSV (merges with existing data)."""
    result = DownloadResponse(ok=True)

    start = body.start_date or "20000101"
    end = body.end_date or datetime.date.today().isoformat()

    for code in body.securities:
        full_code = _normalize_code(code)
        had_data = dc.has_local_data(full_code, adjust=body.adjust)
        path = dc.save_stock_local(full_code, start, end, body.adjust)
        if path:
            if had_data:
                result.merged.append(full_code)
            else:
                result.downloaded.append(full_code)
        else:
            result.failed.append({"code": full_code, "error": "Download failed or no data returned"})

    result.ok = len(result.downloaded) > 0 or len(result.merged) > 0
    return result


@router.delete("/data/local/{code}")
async def delete_local_stock(code: str) -> Dict[str, Any]:
    """Delete local CSV data for a single stock."""
    full_code = _normalize_code(code)
    removed = dc.remove_local_data(full_code, adjust="qfq")
    if removed:
        return {"ok": True, "message": f"Deleted local data for {full_code}"}
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"No local data for {code}"})


def _normalize_code(code: str) -> str:
    """Ensure code has exchange suffix for internal use, but return without suffix for file naming."""
    code = code.strip().upper()
    # If already has suffix, strip it first for consistency
    code = code.replace(".XSHG", "").replace(".XSHE", "")
    return code
