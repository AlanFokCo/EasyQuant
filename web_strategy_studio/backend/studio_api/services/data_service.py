"""Async data service layer for data management operations.

Wraps the synchronous eqlib.data_cache module with:
- asyncio.to_thread for non-blocking file I/O
- In-memory TTL cache (5 min) to avoid repeated disk reads
- Pagination, search, and sorting on stock listings
- Batch delete with result aggregation
- Data quality checks for local CSV files
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from eqlib import data_cache as dc

# A-share code: strictly 6 digits
_CODE_RE = re.compile(r"^[0-9]{6}$")


class DataService:
    """Async data service for local stock data operations.

    All eqlib.data_cache calls are blocking (disk I/O), so we dispatch
    them via ``asyncio.to_thread`` to keep the event loop responsive.
    Results are cached in-memory with a configurable TTL.
    """

    CACHE_TTL = timedelta(minutes=5)

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_stocks(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        sort_by: str = "code",
        sort_order: str = "asc",
        adjust: str = "qfq",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List stocks with local data, supporting pagination/search/sorting.

        Returns:
            Tuple of (list of stock info dicts, total matching count).
        """
        cache_key = self._get_cache_key(
            action="list",
            page=page,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            adjust=adjust,
        )
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Fetch all stock codes (fast — just directory listing)
        codes = await asyncio.to_thread(dc.list_local_stocks, adjust=adjust)

        # Gather file info for each code (blocking I/O)
        all_stocks = await self._gather_stock_info(codes, adjust)

        # Search filter
        if search:
            needle = search.strip().lower()
            all_stocks = [
                s
                for s in all_stocks
                if needle in s["code"].lower() or needle in (s.get("name") or "").lower()
            ]

        total = len(all_stocks)

        # Sorting
        reverse = sort_order == "desc"
        sort_key = (
            sort_by if sort_by in ("code", "start_date", "end_date", "size_bytes") else "code"
        )
        all_stocks.sort(
            key=lambda s: (s.get(sort_key) is None, s.get(sort_key, "")),
            reverse=reverse,
        )

        # Pagination
        start = (page - 1) * per_page
        end = start + per_page
        page_stocks = all_stocks[start:end]

        result = (page_stocks, total)
        self._set_cache(cache_key, result)
        return result

    async def get_stock_detail(self, code: str, adjust: str = "qfq") -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific stock's local data."""
        cache_key = self._get_cache_key(action="detail", code=code, adjust=adjust)
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        info = await asyncio.to_thread(dc.get_local_file_info, code, adjust=adjust)
        if info is not None:
            self._set_cache(cache_key, info)
        return info

    async def batch_delete(self, codes: List[str], adjust: str = "qfq") -> Dict[str, Any]:
        """Delete local CSV data for multiple stocks.

        Returns dict with deleted count and per-code results.
        """
        deleted_codes: list[str] = []
        failed_codes: list[dict[str, str]] = []

        for code in codes:
            ok = await asyncio.to_thread(dc.remove_local_data, code, adjust=adjust)
            if ok:
                deleted_codes.append(code)
            else:
                failed_codes.append({"code": code, "error": "No local data found"})

        # Invalidate all cached entries since the file set has changed
        self.invalidate_cache()

        return {
            "deleted": len(deleted_codes),
            "deleted_codes": deleted_codes,
            "failed": failed_codes,
        }

    async def check_data_quality(self, code: str, adjust: str = "qfq") -> Dict[str, Any]:
        """Run data quality checks on a stock's local CSV data.

        Checks:
        - File exists and is readable
        - Date range coverage
        - Data freshness (days since last update)
        - File size sanity
        """
        info = await asyncio.to_thread(dc.get_local_file_info, code, adjust=adjust)
        if info is None:
            return {
                "code": code,
                "exists": False,
                "checks": [],
                "score": 0,
                "message": "No local data found",
            }

        checks: list[dict[str, Any]] = []
        score = 0

        # Check 1: file exists
        checks.append(
            {
                "name": "file_exists",
                "passed": True,
                "message": "Local CSV file exists",
            }
        )
        score += 25

        # Check 2: has date range
        has_dates = info.get("start_date") and info.get("end_date")
        checks.append(
            {
                "name": "date_range",
                "passed": bool(has_dates),
                "message": (
                    f"Date range: {info['start_date']} ~ {info['end_date']}"
                    if has_dates
                    else "Date range unavailable"
                ),
            }
        )
        if has_dates:
            score += 25

        # Check 3: file size is reasonable (> 0)
        size_ok = info.get("size_bytes", 0) > 0
        checks.append(
            {
                "name": "file_size",
                "passed": size_ok,
                "message": f"File size: {info.get('size_human', 'unknown')}",
            }
        )
        if size_ok:
            score += 25

        # Check 4: data freshness — end_date within last 30 days
        fresh = False
        if info.get("end_date"):
            try:
                end_dt = datetime.strptime(info["end_date"], "%Y-%m-%d")
                days_ago = (datetime.now() - end_dt).days
                fresh = days_ago <= 30
                checks.append(
                    {
                        "name": "freshness",
                        "passed": fresh,
                        "message": f"Last data point {days_ago} days ago",
                    }
                )
            except (ValueError, TypeError):
                checks.append(
                    {
                        "name": "freshness",
                        "passed": False,
                        "message": "Cannot parse end date",
                    }
                )
        else:
            checks.append(
                {
                    "name": "freshness",
                    "passed": False,
                    "message": "No end date available",
                }
            )
        if fresh:
            score += 25

        return {
            "code": code,
            "exists": True,
            "checks": checks,
            "score": score,
            "message": _quality_label(score),
        }

    async def download_stocks(
        self,
        codes: List[str],
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> Dict[str, Any]:
        """Download stock data and save to local CSV, merging with existing data."""
        downloaded: list[str] = []
        merged: list[str] = []
        failed: list[dict[str, str]] = []

        start = start_date or "20000101"
        end = end_date or datetime.now().strftime("%Y%m%d")

        for code in codes:
            had_data = await asyncio.to_thread(dc.has_local_data, code, adjust=adjust)
            path = await asyncio.to_thread(dc.save_stock_local, code, start, end, adjust)
            if path:
                if had_data:
                    merged.append(code)
                else:
                    downloaded.append(code)
            else:
                failed.append({"code": code, "error": "Download failed or no data returned"})

        # Invalidate cache since new data was added
        self.invalidate_cache()

        return {
            "ok": len(downloaded) > 0 or len(merged) > 0,
            "downloaded": downloaded,
            "merged": merged,
            "failed": failed,
        }

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def _get_cache_key(self, **kwargs: Any) -> str:
        return json.dumps(kwargs, sort_keys=True, default=str)

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_timestamps:
            return False
        return datetime.now() - self._cache_timestamps[key] < self.CACHE_TTL

    def _set_cache(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _gather_stock_info(self, codes: list[str], adjust: str) -> list[dict[str, Any]]:
        """Gather file info for a list of codes using concurrent I/O."""
        if not codes:
            return []

        # Use asyncio.gather with to_thread for concurrent file reads
        tasks = [asyncio.to_thread(dc.get_local_file_info, code, adjust=adjust) for code in codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        stocks: list[dict[str, Any]] = []
        for info in results:
            if isinstance(info, dict) and info:
                stocks.append(info)
        return stocks


def _quality_label(score: int) -> str:
    """Human-readable quality label."""
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 25:
        return "Poor"
    return "No data"


def validate_code(code: str) -> str:
    """Validate and normalize a stock code.

    A-share codes are strictly 6 digits. Path separators, URL encoding,
    and exchange suffixes are stripped before validation.
    Raises ValueError for invalid codes.
    """
    raw = code.strip().upper()
    raw = raw.replace(".XSHG", "").replace(".XSHE", "")

    if not _CODE_RE.match(raw):
        raise ValueError(f"Stock code must be 6 digits, got: {code}")
    return raw
