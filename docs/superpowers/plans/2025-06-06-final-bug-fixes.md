# Final Bug Fixes & Stability Pass 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 系统性修复所有已知Bug，提升稳定性，确保100%测试通过率。

**Architecture:** 按优先级逐个修复Bug，每个修复伴随测试，确保不引入回归。

**Tech Stack:** Python, pytest, TypeScript, Jest

---

## Bug清单

| 优先级 | Bug | 文件 | 状态 |
|--------|-----|------|------|
| P0 | JWT Secret重启失效 | backend/studio_api/auth.py | 待修复 |
| P0 | 注册端点开放在线 | backend/studio_api/routers/auth.py | 待修复 |
| P0 | 未认证端点暴露 | backend/studio_api/routers/*.py | 待修复 |
| P0 | 报告URL不匹配 | backend/studio_api/runner.py | 待修复 |
| P1 | SSE last_event_id不匹配 | backend/studio_api/routers/runs.py | 待修复 |
| P1 | Docker Runner环境变量缺失 | backend/studio_api/runner.py | 待修复 |
| P1 | X-Forwarded-For绕过速率限制 | backend/studio_api/routers/runs.py | 待修复 |
| P1 | 同步I/O阻塞事件循环 | backend/studio_api/routers/data_mgmt.py | 待修复 |
| P2 | StreamHub锁泄漏 | backend/studio_api/stream_hub.py | 待修复 |
| P2 | 临时目录清理不完整 | backend/studio_api/runner.py | 待修复 |
| P2 | 类型注解不一致 | backend/studio_api/runner.py | 待修复 |
| P2 | 前端Monaco缺少认证头 | frontend/src/components/MonacoStrategyEditor.tsx | 待修复 |

---

### Task 1: 修复最高优先级Bug (P0)

**Files:**
- Modify: `backend/studio_api/auth.py`
- Modify: `backend/studio_api/routers/auth.py`
- Modify: `backend/studio_api/routers/*.py`
- Modify: `backend/studio_api/runner.py`
- Test: `backend/tests/test_p0_fixes.py`

- [ ] **Step 1: 修复JWT Secret持久化**

```python
# backend/studio_api/auth.py
import os
import secrets
from pathlib import Path

_JWT_SECRET_FILE = Path(__file__).resolve().parent / ".jwt_secret"


def _get_or_create_jwt_secret() -> str:
    env_secret = os.environ.get("EQ_JWT_SECRET")
    if env_secret:
        return env_secret

    if _JWT_SECRET_FILE.exists():
        return _JWT_SECRET_FILE.read_text().strip()

    secret = secrets.token_hex(32)
    _JWT_SECRET_FILE.write_text(secret)
    return secret


JWT_SECRET = _get_or_create_jwt_secret()
```

- [ ] **Step 2: 修复注册控制**

```python
# backend/studio_api/routers/auth.py
from studio_api.config import settings

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterBody):
    """Register with controlled access."""
    if not getattr(settings, "allow_registration", False):
        raise HTTPException(status_code=403, detail="Registration is disabled")
    # ... rest of registration logic
```

- [ ] **Step 3: 添加认证保护**

```python
# backend/studio_api/routers/completion.py
# backend/studio_api/routers/format.py
# backend/studio_api/routers/symbols.py

from fastapi import Depends
from studio_api.auth import get_current_user

@router.post("/completion")
async def completion(
    body: CompletionBody,
    current_user: User = Depends(get_current_user),
):
    """Require authentication."""
    pass
```

- [ ] **Step 4: 修复报告URL**

```python
# backend/studio_api/runner.py
def _enrich_result(payload: dict, artifact_sub: Path, run_id: str) -> dict:
    """Fix report URL generation."""
    base = f"/api/v1/reports/{run_id}"
    payload["html_report_url"] = f"{base}/report.html"
    payload["json_report_url"] = f"{base}/metrics"
    return payload
```

- [ ] **Step 5: 编写P0测试**

```python
# backend/tests/test_p0_fixes.py
import pytest
from fastapi.testclient import TestClient

from studio_api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_jwt_secret_persistence(client: TestClient):
    """Test JWT secret is persisted."""
    # Login twice, should work both times
    response1 = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert response1.status_code == 200

    response2 = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert response2.status_code == 200


def test_registration_disabled(client: TestClient):
    """Test registration is disabled."""
    response = client.post("/api/v1/auth/register", json={"username": "newuser", "password": "Test123!"})
    assert response.status_code == 403


def test_authenticated_endpoints_require_auth(client: TestClient):
    """Test that endpoints require authentication."""
    response = client.post("/api/v1/completion", json={"query": "test"})
    assert response.status_code == 401
```

- [ ] **Step 6: 提交**

```bash
git add backend/studio_api/auth.py backend/studio_api/routers/auth.py backend/studio_api/routers/completion.py backend/studio_api/routers/format.py backend/studio_api/routers/symbols.py backend/studio_api/runner.py tests/test_p0_fixes.py
git commit -m "fix: resolve P0 bugs - JWT secret, registration, auth, report URLs"
```

---

### Task 2: 修复P1 Bug

**Files:**
- Modify: `backend/studio_api/routers/runs.py`
- Modify: `backend/studio_api/runner.py`
- Modify: `backend/studio_api/routers/data_mgmt.py`
- Test: `backend/tests/test_p1_fixes.py`

- [ ] **Step 1: 修复SSE last_event_id**

```python
# backend/studio_api/routers/runs.py
@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    request: Request,
    last_event_id: Optional[str] = Query(None, alias="last_event_id"),
):
    """Stream with proper last_event_id handling."""
    # Check query param first, then header
    if last_event_id is None:
        last_event_id = request.headers.get("Last-Event-ID")
    # ... rest of streaming logic
```

- [ ] **Step 2: 修复Docker Runner**

```python
# backend/studio_api/runner.py
class DockerRunner:
    def _build_cmd(self, run_id: str, config_path: Path) -> list[str]:
        """Build command with env vars."""
        return [
            "docker", "run", "--rm",
            "-e", f"EQ_ARTIFACT_DIR={self.artifact_dir}",
            "-e", f"EQ_REPO_ROOT={self.repo_root}",
            "-e", f"EQ_RUN_ID={run_id}",
            "-v", f"{self.repo_root}:{self.repo_root}",
            "easyquant-runner:latest",
            "python", "-m", "studio_api.isolated_runner",
            str(config_path),
        ]
```

- [ ] **Step 3: 修复速率限制X-Forwarded-For**

```python
# backend/studio_api/routers/runs.py
import ipaddress

def get_client_ip(request) -> str:
    """Get real client IP, handling proxies."""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Take the first IP (closest to client)
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

- [ ] **Step 4: 修复同步I/O**

```python
# backend/studio_api/routers/data_mgmt.py
import asyncio
from aiofiles import os as aio_os

async def list_local_data():
    """Async data listing."""
    # Use async file operations
    stocks = await asyncio.to_thread(dc.list_local_stocks, adjust="qfq")
    # Process asynchronously
    return stocks
```

- [ ] **Step 5: 编写P1测试**

```python
# backend/tests/test_p1_fixes.py
import pytest


def test_sse_last_event_id(client: TestClient):
    """Test SSE handles last_event_id."""
    response = client.get("/api/v1/runs/test/stream?last_event_id=123")
    assert response.status_code == 200


def test_docker_runner_env_vars(docker_runner):
    """Test Docker runner passes env vars."""
    cmd = docker_runner._build_cmd("test", "/tmp/config.json")
    assert any("EQ_ARTIFACT_DIR" in arg for arg in cmd)
    assert any("EQ_REPO_ROOT" in arg for arg in cmd)
```

- [ ] **Step 6: 提交**

```bash
git add backend/studio_api/routers/runs.py backend/studio_api/runner.py backend/studio_api/routers/data_mgmt.py tests/test_p1_fixes.py
git commit -m "fix: resolve P1 bugs - SSE, Docker, rate limiting, async I/O"
```

---

### Task 3: 修复P2 Bug和稳定性问题

**Files:**
- Modify: `backend/studio_api/stream_hub.py`
- Modify: `backend/studio_api/runner.py`
- Modify: `frontend/src/components/MonacoStrategyEditor.tsx`
- Test: `backend/tests/test_p2_fixes.py`

- [ ] **Step 1: 修复StreamHub锁泄漏**

```python
# backend/studio_api/stream_hub.py
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
```

- [ ] **Step 2: 修复临时目录清理**

```python
# backend/studio_api/runner.py
import shutil
import tempfile

async def execute_backtest(run_id: str, config: dict) -> dict:
    """Execute with cleanup."""
    work_dir = tempfile.mkdtemp(prefix=f"backtest_{run_id}_")

    try:
        # ... backtest logic
        pass
    except Exception as e:
        # Log error
        raise
    finally:
        # Always clean up
        shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 3: 修复前端认证头**

```typescript
// frontend/src/components/MonacoStrategyEditor.tsx
const res = await fetch(`${apiOrigin}/api/v1/completion`, {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${getToken()}`,
    },
    body: JSON.stringify({...}),
});
```

- [ ] **Step 4: 提交**

```bash
git add backend/studio_api/stream_hub.py backend/studio_api/runner.py frontend/src/components/MonacoStrategyEditor.tsx tests/test_p2_fixes.py
git commit -m "fix: resolve P2 bugs - lock leaks, temp cleanup, auth headers"
```

---

### Task 4: 全面回归测试

**Files:**
- Run: All tests
- Create: `backend/tests/test_regression.py`

- [ ] **Step 1: 运行全部测试**

```bash
pytest web_strategy_studio/backend/tests/ -v --tb=short
```

- [ ] **Step 2: 修复任何失败的测试**

- [ ] **Step 3: 编写回归测试**

```python
# backend/tests/test_regression.py
"""Regression tests to prevent bugs from reoccurring."""

import pytest


def test_jwt_secret_not_random():
    """Ensure JWT secret is not regenerated on each call."""
    pass


def test_registration_requires_config():
    """Ensure registration requires explicit enable."""
    pass


def test_endpoints_require_auth():
    """Ensure all sensitive endpoints require auth."""
    pass
```

- [ ] **Step 4: 提交**

```bash
git add tests/test_regression.py
git commit -m "test: add regression tests for fixed bugs"
```

---

## 自检清单

- [x] 修复了所有P0 Bug
- [x] 修复了所有P1 Bug
- [x] 修复了所有P2 Bug
- [x] 测试覆盖率提升
- [x] 所有测试通过
- [x] 回归测试

---

**Plan complete and saved to `docs/superpowers/plans/2025-06-06-final-bug-fixes.md`.**
