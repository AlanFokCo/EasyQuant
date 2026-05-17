"""Stock symbol data and search API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_SYMBOLS_FILE = Path(__file__).resolve().parent / "data" / "eqlib_symbols.json"
_cache: List[Dict[str, str]] | None = None


def _load_symbols() -> List[Dict[str, str]]:
    global _cache
    if _cache is not None:
        return _cache
    if not _SYMBOLS_FILE.is_file():
        _cache = []
        return _cache
    data = json.loads(_SYMBOLS_FILE.read_text(encoding="utf-8"))
    # Normalize to list of {code, name}
    if isinstance(data, dict):
        # May be keyed by code: {code: name, ...}
        _cache = [{"code": k, "name": v} for k, v in data.items()]
    elif isinstance(data, list):
        _cache = data
    else:
        _cache = []
    return _cache


def search_symbols(query: str, limit: int = 20) -> List[Dict[str, str]]:
    """Search symbols by code or name (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return []
    symbols = _load_symbols()
    results: List[Dict[str, str]] = []
    for s in symbols:
        code = (s.get("code") or s.get("symbol") or s.get("id", "")).lower()
        name = (s.get("name") or s.get("label") or "").lower()
        if q in code or q in name:
            results.append({"code": s.get("code") or s.get("symbol") or s.get("id"), "name": s.get("name") or s.get("label") or ""})
            if len(results) >= limit:
                break
    return results
