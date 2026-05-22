"""Per-run SSE / broadcast queues with ring-buffer replay (B6/B13)."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

# Events that signal the end of a run.
_TERMINAL_EVENTS = frozenset({"done", "error"})

# Maximum events stored in the ring buffer per run.
_RING_SIZE = 256


class _RunBuffer:
    """Ring buffer of recent events for a single run.

    Stores up to _RING_SIZE events (each as ``{"id": int, "event": str, "data": dict}``).
    Also caches the last terminal event for immediate replay on reconnect.
    Expires `ttl_sec` seconds after the first terminal event is received.
    """

    __slots__ = ("events", "terminal", "_expires_at", "_seq")

    def __init__(self) -> None:
        self.events: deque[Dict[str, Any]] = deque(maxlen=_RING_SIZE)
        self.terminal: Optional[Dict[str, Any]] = None
        self._expires_at: Optional[float] = None
        self._seq: int = 0

    def push(self, event: str, data: Dict[str, Any], ttl_sec: int) -> Dict[str, Any]:
        self._seq += 1
        entry = {"id": self._seq, "event": event, "data": data}
        self.events.append(entry)
        if event in _TERMINAL_EVENTS and self.terminal is None:
            self.terminal = entry
            self._expires_at = time.monotonic() + ttl_sec
        return entry

    def is_expired(self, now: float) -> bool:
        if self._expires_at is None:
            return False
        return now > self._expires_at

    def missed_since(self, last_event_id: int) -> List[Dict[str, Any]]:
        """Return all buffered events with id > last_event_id."""
        return [e for e in self.events if e["id"] > last_event_id]


class StreamHub:
    """Fan-out hub with per-run ring buffers and Last-Event-ID replay."""

    def __init__(
        self,
        max_queued: int = 2000,
        buffer_ttl_sec: int = 1800,
        max_buffers: int = 1000,
    ) -> None:
        self._queues: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._buffers: Dict[str, _RunBuffer] = {}
        self._max = max_queued
        self._ttl = buffer_ttl_sec
        self._max_buffers = max_buffers
        self._locks: Dict[str, asyncio.Lock] = {}
        self._insert_order: List[str] = []  # LRU eviction tracking

    def _get_lock(self, run_id: str) -> asyncio.Lock:
        """Lazily create a lock for run_id, bound to the current event loop."""
        if run_id not in self._locks:
            self._locks[run_id] = asyncio.Lock()
        return self._locks[run_id]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max)
        self._queues[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        if run_id in self._queues:
            try:
                self._queues[run_id].remove(q)
            except ValueError:
                pass
            if not self._queues[run_id]:
                del self._queues[run_id]
                self._locks.pop(run_id, None)

    def get_buffer(self, run_id: str) -> Optional[_RunBuffer]:
        """Return the ring buffer for `run_id` if it exists and hasn't expired."""
        buf = self._buffers.get(run_id)
        if buf is None:
            return None
        if buf.is_expired(time.monotonic()):
            self._buffers.pop(run_id, None)
            return None
        return buf

    async def publish(self, run_id: str, event: str, data: Dict[str, Any]) -> None:
        # Store in ring buffer first (so late subscribers can replay).
        if run_id not in self._buffers:
            self._buffers[run_id] = _RunBuffer()
            self._insert_order.append(run_id)
        buf = self._buffers[run_id]
        entry = buf.push(event, data, self._ttl)
        line = {"id": entry["id"], "event": event, "data": data}

        # MED-26: evict oldest non-terminal buffers when cap exceeded
        if len(self._buffers) > self._max_buffers:
            self._evict_oldest()

        dead: List[asyncio.Queue] = []
        for q in list(self._queues.get(run_id, [])):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                try:
                    _ = q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    dead.append(q)
        for q in dead:
            self.unsubscribe(run_id, q)
        if event in _TERMINAL_EVENTS:
            self._queues.pop(run_id, None)
            self._locks.pop(run_id, None)

    def _evict_oldest(self) -> None:
        """Remove oldest non-terminal buffers to stay under max_buffers."""
        while len(self._buffers) > self._max_buffers and self._insert_order:
            oldest = self._insert_order.pop(0)
            buf = self._buffers.get(oldest)
            if buf is not None and buf.terminal is None:
                self._buffers.pop(oldest, None)
                log.debug("stream_hub.evict_oldest", run_id=oldest)

    def format_sse(self, event_id: int, event: str, data: Dict[str, Any]) -> str:
        return (
            f"id: {event_id}\n"
            f"event: {event}\n"
            f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def evict_expired(self) -> None:
        """Remove expired ring buffers. Call periodically."""
        now = time.monotonic()
        expired = [rid for rid, buf in list(self._buffers.items()) if buf.is_expired(now)]
        for rid in expired:
            self._buffers.pop(rid, None)
            log.debug("stream_hub.evict", run_id=rid)


stream_hub = StreamHub()
