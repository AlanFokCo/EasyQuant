"""Per-run SSE / broadcast queues."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

# Events that signal the end of a run — on these, the hub cleans up the
# entire run_id entry to prevent unbounded memory growth (S4).
_TERMINAL_EVENTS = frozenset({"done", "error"})


class StreamHub:
    def __init__(self, max_queued: int = 2000) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._max = max_queued
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

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
            # S4: Remove the dict key when the list is empty to free memory.
            if not self._queues[run_id]:
                del self._queues[run_id]
                # Also clean up the associated lock if it exists.
                self._locks.pop(run_id, None)

    async def publish(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        line = {"event": event, "data": data}
        dead: list[asyncio.Queue] = []
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

        # S4: On terminal events, clean up the entire run_id entry after all
        # subscribers have received the final message.
        if event in _TERMINAL_EVENTS and run_id in self._queues:
            del self._queues[run_id]
            self._locks.pop(run_id, None)

    def format_sse(self, event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


stream_hub = StreamHub()
