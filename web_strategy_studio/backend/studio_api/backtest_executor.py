"""Backtest executor — delegates to the active Runner (LocalRunner or DockerRunner).

The Runner is selected via ``EQ_STUDIO_RUNNER=local|docker`` (default: local).
See ``studio_api/runner.py`` for the protocol and implementations.
"""

from __future__ import annotations

from typing import Any, Dict

from studio_api.runner import (
    _PROGRESS_RE,
    _estimate_trading_fraction,
    execute_backtest as _runner_execute,
)

__all__ = ["execute_backtest", "_PROGRESS_RE", "_estimate_trading_fraction"]

execute_backtest = _runner_execute
"""Execute a backtest using the active Runner.

Args:
    run_id: Unique run identifier.
    source_code: User strategy source code.
    params: Backtest parameters (dates, cash, benchmark, etc.).
    on_log: Optional callback (unused, kept for API compatibility).

Returns:
    Dict with keys: ok, html_report_url, json_report_url, and on failure
    error / error_code.
"""
