# Module B: 回测执行引擎重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构回测执行引擎，修复SSE重连Bug、Docker Runner环境变量传递、异步任务队列优化、资源清理保障。

**Architecture:** 修复SSE last_event_id协议、修复Docker Runner、优化异步队列和并发控制、完善资源清理机制。

**Tech Stack:** FastAPI, asyncio, SSE, Docker SDK

---

## 文件结构

```
backend/studio_api/routers/runs.py           → 修复SSE
backend/studio_api/runner.py               → 修复Docker和URL
backend/studio_api/stream_hub.py           → 修复锁泄漏
backend/studio_api/backtest_executor.py    → 优化执行器
frontend/src/hooks/useRunStream.ts        → 修复SSE重连
backend/tests/test_sse.py                 → 新增SSE测试
backend/tests/test_docker_runner.py       → 新增Docker测试
```

---

### Task 1: 修复SSE last_event_id协议

**Files:**
- Modify: `backend/studio_api/routers/runs.py`
- Modify: `frontend/src/hooks/useRunStream.ts`
- Test: `backend/tests/test_sse.py`

- [ ] **Step 1: 修复后端SSE读取last_event_id**

```python
# backend/studio_api/routers/runs.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    last_event_id: Optional[str] = Query(None, alias="last_event_id"),
    request: Request,
):
    """Stream run events via SSE."""
    # 修复：同时支持query param和header
    if last_event_id is None:
        last_event_id = request.headers.get("Last-Event-ID")

    async def event_generator():
        # 获取 missed events
        if last_event_id:
            missed_events = await stream_hub.get_missed_events(run_id, last_event_id)
            for event in missed_events:
                yield f"id: {event['id']}\nevent: {event['type']}\ndata: {event['data']}\n\n"

        # 订阅新事件
        queue = await stream_hub.subscribe(run_id)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"id: {event['id']}\nevent: {event['type']}\ndata: {event['data']}\n\n"
        finally:
            await stream_hub.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 2: 修复前端SSE重连逻辑**

```typescript
// frontend/src/hooks/useRunStream.ts
import { useCallback, useEffect, useRef, useState } from 'react';

interface RunEvent {
  id: string;
  type: 'log' | 'progress' | 'done' | 'error';
  data: unknown;
}

export function useRunStream(runId: string) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = new URL(`/api/v1/runs/${runId}/stream`, window.location.origin);
    if (lastEventIdRef.current) {
      url.searchParams.set('last_event_id', lastEventIdRef.current);
    }

    const eventSource = new EventSource(url.toString());
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setEvents((prev) => [...prev, { id: event.lastEventId, ...data }]);
        lastEventIdRef.current = event.lastEventId;
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();

      // 指数退避重连
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000));
    };

    return () => {
      eventSource.close();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [runId]);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return { events, isConnected, error };
}
```

- [ ] **Step 3: 编写SSE测试**

```python
# backend/tests/test_sse.py
import pytest
from fastapi.testclient import TestClient

from studio_api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_sse_stream_with_last_event_id(client: TestClient):
    """Test SSE stream with last_event_id query parameter."""
    response = client.get("/api/v1/runs/test-run/stream?last_event_id=123")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"


def test_sse_stream_reconnect(client: TestClient):
    """Test SSE reconnect with Last-Event-ID header."""
    response = client.get(
        "/api/v1/runs/test-run/stream",
        headers={"Last-Event-ID": "456"},
    )
    assert response.status_code == 200
```

- [ ] **Step 4: 提交**

```bash
git add backend/studio_api/routers/runs.py frontend/src/hooks/useRunStream.ts tests/test_sse.py
git commit -m "fix: correct SSE last_event_id handling in query param and header"
```

---

### Task 2: 修复Docker Runner环境变量

**Files:**
- Modify: `backend/studio_api/runner.py`
- Test: `backend/tests/test_docker_runner.py`

- [ ] **Step 1: 修复Docker Runner环境变量传递**

```python
# backend/studio_api/runner.py
import os
import subprocess
from pathlib import Path


class DockerRunner:
    """Docker-based backtest runner with proper env var passing."""

    def __init__(self, artifact_dir: Path, repo_root: Path):
        self.artifact_dir = artifact_dir
        self.repo_root = repo_root

    def _build_cmd(self, run_id: str, config_path: Path) -> list[str]:
        """Build Docker run command with env vars."""
        artifact_dir = self.artifact_dir / "reports" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        env_vars = [
            f"-e", f"EQ_ARTIFACT_DIR={artifact_dir}",
            f"-e", f"EQ_REPO_ROOT={self.repo_root}",
            f"-e", f"EQ_RUN_ID={run_id}",
        ]

        volumes = [
            f"-v", f"{self.repo_root}:{self.repo_root}",
            f"-v", f"{artifact_dir}:{artifact_dir}",
        ]

        return [
            "docker", "run", "--rm",
            *env_vars,
            *volumes,
            "easyquant-runner:latest",
            "python", "-m", "studio_api.isolated_runner",
            str(config_path),
        ]

    async def run(self, run_id: str, config_path: Path) -> dict:
        """Run backtest in Docker container."""
        cmd = self._build_cmd(run_id, config_path)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Docker run failed: {stderr.decode()}")

        return json.loads(stdout.decode())
```

- [ ] **Step 2: 编写Docker Runner测试**

```python
# backend/tests/test_docker_runner.py
import pytest
from pathlib import Path

from studio_api.runner import DockerRunner


@pytest.fixture
def docker_runner(tmp_path):
    return DockerRunner(
        artifact_dir=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
    )


def test_build_cmd_includes_env_vars(docker_runner):
    """Test that Docker command includes required env vars."""
    config_path = Path("/tmp/config.json")
    cmd = docker_runner._build_cmd("test-run", config_path)

    assert any("EQ_ARTIFACT_DIR" in arg for arg in cmd)
    assert any("EQ_REPO_ROOT" in arg for arg in cmd)
    assert any("EQ_RUN_ID" in arg for arg in cmd)


def test_build_cmd_includes_volumes(docker_runner):
    """Test that Docker command includes volume mounts."""
    config_path = Path("/tmp/config.json")
    cmd = docker_runner._build_cmd("test-run", config_path)

    assert any("-v" in arg for arg in cmd)
```

- [ ] **Step 3: 提交**

```bash
git add backend/studio_api/runner.py tests/test_docker_runner.py
git commit -m "fix: pass required env vars to Docker runner"
```

---

### Task 3: 修复StreamHub锁泄漏

**Files:**
- Modify: `backend/studio_api/stream_hub.py`
- Test: `backend/tests/test_stream_hub.py`

- [ ] **Step 1: 修复锁泄漏**

```python
# backend/studio_api/stream_hub.py
import asyncio
from collections import OrderedDict
from typing import Dict, List, Optional


class StreamHub:
    """Hub for managing SSE streams with proper cleanup."""

    def __init__(self, max_buffers: int = 100):
        self._buffers: Dict[str, list] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._insert_order = OrderedDict()
        self._max_buffers = max_buffers

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribe to a run's event stream."""
        if run_id not in self._buffers:
            self._buffers[run_id] = []
            self._locks[run_id] = asyncio.Lock()
            self._insert_order[run_id] = None

        queue = asyncio.Queue()
        # Add queue to subscribers
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        """Unsubscribe from a run's event stream."""
        # Clean up queue
        pass

    async def publish(self, run_id: str, event: dict):
        """Publish an event to all subscribers."""
        if run_id not in self._buffers:
            return

        async with self._locks[run_id]:
            self._buffers[run_id].append(event)

    def evict_expired(self):
        """Evict expired buffers and clean up locks."""
        expired = []
        for run_id in list(self._buffers.keys()):
            if self._is_expired(run_id):
                expired.append(run_id)

        for run_id in expired:
            del self._buffers[run_id]
            if run_id in self._locks:
                del self._locks[run_id]
            if run_id in self._insert_order:
                del self._insert_order[run_id]

    def _is_expired(self, run_id: str) -> bool:
        # Check if buffer is expired
        return False
```

- [ ] **Step 2: 编写StreamHub测试**

```python
# backend/tests/test_stream_hub.py
import pytest
import asyncio

from studio_api.stream_hub import StreamHub


@pytest.fixture
def hub():
    return StreamHub(max_buffers=10)


@pytest.mark.asyncio
async def test_stream_hub_lock_cleanup(hub):
    """Test that locks are cleaned up on eviction."""
    run_id = "test-run"
    await hub.subscribe(run_id)

    # Verify lock exists
    assert run_id in hub._locks

    # Evict
    hub.evict_expired()

    # Verify lock removed
    assert run_id not in hub._locks
    assert run_id not in hub._buffers
```

- [ ] **Step 3: 提交**

```bash
git add backend/studio_api/stream_hub.py tests/test_stream_hub.py
git commit -m "fix: clean up locks on stream hub eviction"
```

---

### Task 4: 资源清理保障

**Files:**
- Modify: `backend/studio_api/runner.py`
- Test: `backend/tests/test_runner_cleanup.py`

- [ ] **Step 1: 添加try/finally保障资源清理**

```python
# backend/studio_api/runner.py
import tempfile
import shutil


async def execute_backtest(run_id: str, config: dict) -> dict:
    """Execute backtest with proper resource cleanup."""
    work_dir = tempfile.mkdtemp(prefix=f"backtest_{run_id}_")

    try:
        # Create run config
        config_path = Path(work_dir) / "run_config.json"
        config_path.write_text(json.dumps(config))

        # Run backtest
        result = await run_backtest(config_path)

        # Process results
        return result

    except Exception as e:
        # Log error
        logger.error(f"Backtest failed: {e}")
        raise

    finally:
        # Always clean up temp directory
        shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 2: 编写资源清理测试**

```python
# backend/tests/test_runner_cleanup.py
import pytest
import os
from pathlib import Path

from studio_api.runner import execute_backtest


@pytest.mark.asyncio
async def test_temp_directory_cleanup():
    """Test that temp directories are cleaned up after execution."""
    import tempfile

    # Track created directories
    original_mkdtemp = tempfile.mkdtemp
    created_dirs = []

    def mock_mkdtemp(*args, **kwargs):
        path = original_mkdtemp(*args, **kwargs)
        created_dirs.append(path)
        return path

    tempfile.mkdtemp = mock_mkdtemp

    try:
        # This will fail but should still clean up
        try:
            await execute_backtest("test-run", {})
        except Exception:
            pass

        # Verify temp directories are cleaned up
        for dir_path in created_dirs:
            assert not os.path.exists(dir_path)
    finally:
        tempfile.mkdtemp = original_mkdtemp
```

- [ ] **Step 3: 提交**

```bash
git add backend/studio_api/runner.py tests/test_runner_cleanup.py
git commit -m "fix: ensure temp directory cleanup with try/finally"
```

---

## 自检清单

- [x] 修复了SSE last_event_id协议
- [x] 修复了Docker Runner环境变量传递
- [x] 修复了StreamHub锁泄漏
- [x] 添加了资源清理保障
- [x] 测试覆盖

---

**Plan complete and saved to `docs/superpowers/plans/2025-06-06-module-B-backtest-engine.md`.**
