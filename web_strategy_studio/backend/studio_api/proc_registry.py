"""Track subprocess handles for cooperative cancel."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_procs: dict[str, asyncio.subprocess.Process] = {}


def register(run_id: str, proc: asyncio.subprocess.Process) -> None:
    _procs[run_id] = proc


def unregister(run_id: str) -> None:
    _procs.pop(run_id, None)


def get_proc(run_id: str) -> asyncio.subprocess.Process | None:
    """Public accessor for a live subprocess handle (B21)."""
    return _procs.get(run_id)


def kill(run_id: str) -> bool:
    p = _procs.get(run_id)
    if p is None:
        return False
    try:
        p.kill()
    except ProcessLookupError:
        return False
    return True
