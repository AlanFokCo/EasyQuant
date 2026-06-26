"""Tests for StreamHub lock cleanup on eviction (prevents lock leaks)."""

from __future__ import annotations

import asyncio
import time

import pytest

pytest_plugins = ("anyio",)


@pytest.fixture
def hub():
    """Fresh StreamHub for each test."""
    from studio_api.stream_hub import StreamHub

    return StreamHub(max_queued=100, buffer_ttl_sec=5, max_buffers=10)


class TestStreamHubLockCleanupOnEvictExpired:
    """Test that evict_expired properly cleans up locks."""

    def test_evict_expired_removes_lock(self, hub):
        """evict_expired should remove the lock along with the buffer.

        Note: We use non-terminal events because terminal events (done/error)
        already clean up locks via publish(). We need to test the evict_expired
        path which handles expired non-terminal buffers.
        """
        asyncio.run(_test_evict_expired_removes_lock(hub))

    def test_evict_expired_removes_from_insert_order(self, hub):
        """evict_expired should remove run_id from _insert_order."""
        asyncio.run(_test_evict_expired_removes_insert_order(hub))


async def _test_evict_expired_removes_lock(hub):
    """Test that evict_expired cleans up locks for non-terminal buffers.

    To create a buffer with a lock but no terminal event, we:
    1. Subscribe to create a queue entry
    2. Publish non-terminal events (which create lock)
    3. Manually expire the buffer and call evict_expired
    """
    run_id = "run_lock_test_1"

    # Publish non-terminal events (these create lock via _get_lock)
    await hub.publish(run_id, "log", {"line": "test"})

    # Verify lock exists (created by publish via _get_lock)
    assert run_id in hub._locks

    # Force expire by manually setting expires_at
    # (Normally only terminal events set this, but we simulate expiry)
    buf = hub._buffers[run_id]
    buf._expires_at = time.monotonic() - 1

    # Evict
    hub.evict_expired()

    # Verify both buffer and lock are removed
    assert run_id not in hub._buffers
    assert run_id not in hub._locks


async def _test_evict_expired_removes_insert_order(hub):
    """Test that evict_expired cleans up insert_order for non-terminal buffers."""
    run_id = "run_order_test"

    # Publish non-terminal event
    await hub.publish(run_id, "log", {"line": "test"})

    # Verify in insert_order
    assert run_id in hub._insert_order

    # Force expire and evict
    buf = hub._buffers[run_id]
    buf._expires_at = time.monotonic() - 1
    hub.evict_expired()

    # Verify removed from insert_order
    assert run_id not in hub._insert_order


class TestStreamHubLockCleanupOnEvictOldest:
    """Test that _evict_oldest properly cleans up locks."""

    def test_evict_oldest_removes_lock(self):
        """_evict_oldest should remove the lock when evicting a buffer."""
        from studio_api.stream_hub import StreamHub

        hub = StreamHub(max_buffers=3)
        asyncio.run(_test_evict_oldest_removes_lock(hub))

    def test_evict_oldest_cleans_multiple_locks(self):
        """_evict_oldest should clean up locks for all evicted buffers."""
        from studio_api.stream_hub import StreamHub

        hub = StreamHub(max_buffers=2)
        asyncio.run(_test_evict_oldest_cleans_multiple(hub))


async def _test_evict_oldest_removes_lock(hub):
    # Create non-terminal buffers that will be evicted
    for i in range(4):
        await hub.publish(f"run_evict_{i}", "log", {"line": f"test {i}"})

    # The oldest (run_evict_0) should have been evicted
    assert "run_evict_0" not in hub._buffers
    assert "run_evict_0" not in hub._locks


async def _test_evict_oldest_cleans_multiple(hub):
    # Create 5 buffers, expect 3 oldest to be evicted
    for i in range(5):
        await hub.publish(f"run_multi_{i}", "log", {"line": f"test {i}"})

    # Oldest 3 should be evicted with their locks
    for i in range(3):
        rid = f"run_multi_{i}"
        assert rid not in hub._buffers
        assert rid not in hub._locks

    # Newest 2 should remain
    for i in range(3, 5):
        rid = f"run_multi_{i}"
        assert rid in hub._buffers


class TestStreamHubLockConsistency:
    """Test lock consistency across different operations."""

    def test_lock_exists_while_buffer_exists(self, hub):
        """Lock should exist as long as buffer exists."""
        asyncio.run(_test_lock_consistency(hub))

    def test_no_orphan_locks_after_multiple_operations(self, hub):
        """No orphan locks should remain after mixed operations."""
        asyncio.run(_test_no_orphan_locks(hub))


async def _test_lock_consistency(hub):
    run_id = "run_consistency"
    await hub.publish(run_id, "log", {"line": "test"})

    # Both buffer and lock should exist
    assert run_id in hub._buffers
    assert run_id in hub._locks

    # Publish more events
    await hub.publish(run_id, "progress", {"progress": 0.5})
    assert run_id in hub._locks


async def _test_no_orphan_locks(hub):
    # Create several buffers
    for i in range(5):
        run_id = f"run_op_{i}"
        await hub.publish(run_id, "log", {"line": "test"})

    # Expire some of them
    for i in range(3):
        run_id = f"run_op_{i}"
        buf = hub._buffers.get(run_id)
        if buf:
            buf._expires_at = time.monotonic() - 1

    hub.evict_expired()

    # Verify no orphan locks: every lock should have a corresponding buffer
    for rid in hub._locks:
        assert rid in hub._buffers, f"Orphan lock found for {rid}"

    # Verify expired ones are fully cleaned
    for i in range(3):
        rid = f"run_op_{i}"
        assert rid not in hub._buffers
        assert rid not in hub._locks


class TestStreamHubTerminalEventLockCleanup:
    """Test that terminal events properly clean up locks."""

    def test_terminal_event_cleans_lock_via_publish(self, hub):
        """Publishing a terminal event should clean up the queue lock."""
        asyncio.run(_test_terminal_lock_cleanup(hub))


async def _test_terminal_lock_cleanup(hub):
    run_id = "run_terminal_lock"

    # Subscribe to create a queue entry
    hub.subscribe(run_id)
    assert run_id in hub._queues

    # Publish terminal event
    await hub.publish(run_id, "done", {"status": "succeeded"})

    # Queue and lock should be cleaned up
    assert run_id not in hub._queues
    assert run_id not in hub._locks
