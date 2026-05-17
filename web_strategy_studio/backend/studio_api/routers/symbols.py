"""Stock symbol search endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from studio_api.symbol_search import search_symbols

router = APIRouter(prefix="/api/v1", tags=["symbols"])


@router.get("/symbols/search")
def symbols_search(q: str = "", limit: int = 20):
    """Search stocks by code or name. Returns list of {code, name}."""
    return search_symbols(q, limit)
