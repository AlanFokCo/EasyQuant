"""Helpers for scientific/reliability diagnostics in reports."""

from __future__ import annotations

from typing import Any


def collect_data_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe data diagnostics payload from a backtest result.

    The result dict may come from older callers, so diagnostics are optional.
    """
    diagnostics = result.get("data_diagnostics") or {}
    if not isinstance(diagnostics, dict):
        return {}

    failed = diagnostics.get("failed", [])
    if not isinstance(failed, list):
        failed = []

    sources = diagnostics.get("sources", {})
    if not isinstance(sources, dict):
        sources = {}

    return {
        "requested": int(diagnostics.get("requested") or 0),
        "loaded": int(diagnostics.get("loaded") or 0),
        "failed": failed,
        "sources": {
            "local": int(sources.get("local") or 0),
            "disk_cache": int(sources.get("disk_cache") or 0),
            "network": int(sources.get("network") or 0),
        },
        "elapsed_seconds": diagnostics.get("elapsed_seconds") or 0.0,
        "memory_mode": diagnostics.get("memory_mode"),
        "memory_estimate_mb": diagnostics.get("memory_estimate_mb"),
        "max_memory_mb": diagnostics.get("max_memory_mb"),
        "use_local": diagnostics.get("use_local"),
        "adjust": diagnostics.get("adjust"),
    }
