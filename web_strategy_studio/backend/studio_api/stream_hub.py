"""Per-run SSE / broadcast queues."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


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

    def format_sse(self, event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


stream_hub = StreamHub()
