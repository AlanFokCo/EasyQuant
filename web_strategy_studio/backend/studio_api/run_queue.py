"""Async run queue with concurrency cap (B17/B18).

Replaces FastAPI ``BackgroundTasks`` with a proper ``asyncio.Queue`` + worker
so that:

  - At most ``settings.max_concurrent_runs`` backtests run simultaneously.
  - Excess ``POST /runs`` requests are accepted (202) but wait in queue.
  - Queue position is visible via ``GET /api/v1/queue``.
  - On startup, orphan runs (status=running/queued with no live proc) are
    immediately marked ``failed: SERVER_RESTART`` (B17).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import structlog

from studio_api.config import settings

log = structlog.get_logger(__name__)

# Queue of (run_id, coroutine_factory) pairs.
# A coroutine_factory is a zero-arg async callable that runs the task.
_TaskCoro = Callable[[], Awaitable[None]]

# Module-level state — re-initialised by start_worker() on each lifespan start
# so tests using different event loops work correctly.
_queue: Optional[asyncio.Queue] = None
_worker_task: Optional[asyncio.Task] = None
# Ordered list of run_ids currently sitting in the queue (not yet started).
_pending: List[str] = []
# Set of run_ids currently executing.
_active: Set[str] = set()
# Semaphore limiting simultaneous executions (created in _worker()).
_semaphore: Optional[asyncio.Semaphore] = None


def queue_position(run_id: str) -> Optional[int]:
    """Return 1-based queue position of run_id, or None if not in queue."""
    try:
        return _pending.index(run_id) + 1
    except ValueError:
        return None


def active_run_ids() -> List[str]:
    return list(_active)


def pending_run_ids() -> List[str]:
    return list(_pending)


async def enqueue(run_id: str, coro_factory: _TaskCoro) -> None:
    """Add a run to the processing queue."""
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    _pending.append(run_id)
    await _queue.put((run_id, coro_factory))
    log.info("run.queued", run_id=run_id, queue_depth=len(_pending))


async def _worker() -> None:
    """Consume the queue and run tasks with concurrency cap."""
    global _semaphore, _queue
    _queue = asyncio.Queue()
    _semaphore = asyncio.Semaphore(settings.max_concurrent_runs)
    log.info("run_queue.worker_started", max_concurrent=settings.max_concurrent_runs)
    while True:
        run_id, coro_factory = await _queue.get()
        # Remove from pending list (may already be removed if cancelled).
        try:
            _pending.remove(run_id)
        except ValueError:
            pass
        # Acquire semaphore slot before launching.
        await _semaphore.acquire()
        _active.add(run_id)
        log.info("run.started", run_id=run_id, active=len(_active))

        async def _run(rid: str, factory: _TaskCoro) -> None:
            try:
                await factory()
            except Exception:
                log.exception("run.unhandled_error", run_id=rid)
            finally:
                _active.discard(rid)
                _semaphore.release()
                log.info("run.finished", run_id=rid, active=len(_active))

        asyncio.create_task(_run(run_id, coro_factory))


def start_worker() -> None:
    """Start the background worker (call once from app lifespan).

    Reinitialises the queue and resets module-level state so that each
    lifespan start (including in tests) gets a clean queue bound to the
    current event loop.
    """
    global _worker_task, _queue
    # Create a fresh queue bound to the current running event loop.
    _queue = asyncio.Queue()
    _pending.clear()
    _active.clear()
    current_loop = asyncio.get_running_loop()
    if _worker_task is not None and not _worker_task.done():
        try:
            worker_loop = _worker_task.get_loop()
        except RuntimeError:
            worker_loop = None
        if worker_loop is not current_loop:
            _worker_task.cancel()
            _worker_task = None
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())


async def mark_orphan_runs_failed() -> None:
    """On startup, find runs still in running/queued state and mark them failed.

    These are orphans left over from a prior server process that was killed
    (B17: kill -9 recovery).
    """
    from sqlalchemy import select

    from studio_api.db import SessionLocal
    from studio_api.models import Run

    async with SessionLocal() as session:
        result = await session.execute(select(Run).where(Run.status.in_(["running", "queued"])))
        orphans: List[Run] = result.scalars().all()
        if not orphans:
            return
        now = datetime.now(timezone.utc)
        for run in orphans:
            run.status = "failed"
            run.error_code = "SERVER_RESTART"
            run.error_message = "Server restarted while run was in-flight"
            run.finished_at = now
        await session.commit()
        log.warning(
            "startup.orphan_runs_cleaned",
            count=len(orphans),
            run_ids=[r.id for r in orphans],
        )


# ---------------------------------------------------------------------------
# Rate limiter (per-IP, in-memory sliding-window counter)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple in-process sliding-window rate limiter.

    Not suitable for multi-process deployments; a Redis-backed solution
    should replace this when running behind a load balancer.
    """

    def __init__(self, limit: int, window_sec: int) -> None:
        self._limit = limit
        self._window = window_sec
        self._hits: Dict[str, List[float]] = {}

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Return (allowed, remaining_hits). Updates the sliding window."""
        import time

        now = time.monotonic()
        window_start = now - self._window
        hits = self._hits.get(key, [])
        # Remove expired hits.
        hits = [t for t in hits if t > window_start]
        allowed = len(hits) < self._limit
        if allowed:
            hits.append(now)
        self._hits[key] = hits
        remaining = max(0, self._limit - len(hits))
        return allowed, remaining


rate_limiter = _RateLimiter(
    limit=settings.rate_limit_runs_per_window,
    window_sec=settings.rate_limit_window_sec,
)
