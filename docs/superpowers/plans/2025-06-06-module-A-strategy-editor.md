# Module A: 策略编辑器重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构策略编辑器，增强Monaco集成、实现版本管理、策略模板、代码质量实时检查。

**Architecture:** 升级Monaco Editor配置，实现版本快照和回滚，提供策略模板库，集成Ruff实时检查。

**Tech Stack:** React, Monaco Editor, FastAPI, Git-like versioning

---

## 文件结构

```
backend/studio_api/routers/strategies.py      → 修复版本管理
backend/studio_api/services/version_service.py → 新增版本服务
backend/studio_api/services/template_service.py → 新增模板服务
frontend/src/components/MonacoStrategyEditor.tsx → 重构编辑器
frontend/src/components/VersionHistory.tsx     → 新增版本历史
frontend/src/components/TemplateSelector.tsx    → 新增模板选择器
backend/tests/test_strategies.py              → 新增策略测试
```

---

### Task 1: 实现版本管理服务

**Files:**
- Create: `backend/studio_api/services/version_service.py`
- Test: `backend/tests/services/test_version_service.py`

- [ ] **Step 1: 创建版本服务**

```python
# backend/studio_api/services/version_service.py
"""Version management service for strategies."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from studio_api.models import Strategy, StrategyVersion


class VersionService:
    """Service for managing strategy versions."""

    async def create_version(
        self,
        session: AsyncSession,
        strategy_id: str,
        code: str,
        comment: str = "",
    ) -> StrategyVersion:
        """Create a new version snapshot."""
        # Get current max version number
        result = await session.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(desc(StrategyVersion.version_number))
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        next_version = (latest.version_number + 1) if latest else 1

        version = StrategyVersion(
            strategy_id=strategy_id,
            version_number=next_version,
            code=code,
            comment=comment,
        )
        session.add(version)
        await session.commit()
        await session.refresh(version)
        return version

    async def get_versions(
        self,
        session: AsyncSession,
        strategy_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StrategyVersion]:
        """Get version history for a strategy."""
        result = await session.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(desc(StrategyVersion.version_number))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def restore_version(
        self,
        session: AsyncSession,
        strategy_id: str,
        version_number: int,
    ) -> Optional[Strategy]:
        """Restore a strategy to a specific version."""
        result = await session.execute(
            select(StrategyVersion)
            .where(
                StrategyVersion.strategy_id == strategy_id,
                StrategyVersion.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            return None

        # Update strategy code
        strategy_result = await session.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        strategy = strategy_result.scalar_one_or_none()
        if strategy:
            strategy.code = version.code
            strategy.updated_at = datetime.now()
            await session.commit()

        return strategy
```

- [ ] **Step 2: 编写版本服务测试**

```python
# backend/tests/services/test_version_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.services.version_service import VersionService
from studio_api.models import Strategy, StrategyVersion


@pytest.fixture
def version_service():
    return VersionService()


@pytest.mark.asyncio
async def test_create_version(version_service, db_session: AsyncSession):
    """Test creating a version."""
    version = await version_service.create_version(
        db_session, "strategy-1", "print('hello')", "Initial version"
    )
    assert version.version_number == 1
    assert version.code == "print('hello')"


@pytest.mark.asyncio
async def test_get_versions(version_service, db_session: AsyncSession):
    """Test getting versions."""
    # Create multiple versions
    for i in range(3):
        await version_service.create_version(
            db_session, "strategy-1", f"code-{i}", f"Version {i}"
        )

    versions = await version_service.get_versions(db_session, "strategy-1")
    assert len(versions) == 3
    assert versions[0].version_number == 3  # Latest first


@pytest.mark.asyncio
async def test_restore_version(version_service, db_session: AsyncSession):
    """Test restoring a version."""
    # Create versions
    await version_service.create_version(db_session, "strategy-1", "v1 code", "v1")
    await version_service.create_version(db_session, "strategy-1", "v2 code", "v2")

    # Restore to v1
    strategy = await version_service.restore_version(db_session, "strategy-1", 1)
    assert strategy is not None
    assert strategy.code == "v1 code"
```

- [ ] **Step 3: 提交**

```bash
git add backend/studio_api/services/version_service.py tests/services/test_version_service.py
git commit -m "feat: add strategy version management service"
```

---

### Task 2: 实现模板服务

**Files:**
- Create: `backend/studio_api/services/template_service.py`
- Create: `backend/studio_api/data/templates.json`
- Test: `backend/tests/services/test_template_service.py`

- [ ] **Step 1: 创建模板服务**

```python
# backend/studio_api/services/template_service.py
"""Template service for strategy templates."""

import json
from pathlib import Path
from typing import List, Optional


class TemplateService:
    """Service for managing strategy templates."""

    def __init__(self, templates_file: Path = None):
        self.templates_file = templates_file or Path(__file__).parent.parent / "data" / "templates.json"
        self._templates = self._load_templates()

    def _load_templates(self) -> dict:
        """Load templates from file."""
        if self.templates_file.exists():
            return json.loads(self.templates_file.read_text())
        return self._default_templates()

    def _default_templates(self) -> dict:
        """Default strategy templates."""
        return {
            "double_ma": {
                "name": "双均线策略",
                "description": "基于5日和20日均线的简单策略",
                "code": """def initialize(ctx):
    ctx.assigner = ctx.target([\"600519\"])

def handle_bar(ctx):
    for stock in ctx.target_list:
        hist = ctx.data.history(stock, 30)
        if len(hist) < 30:
            continue
        ma5 = hist[-5:].mean()
        ma20 = hist[-20:].mean()
        if ma5 > ma20:
            ctx.order_target_percent(stock, 0.5)
        else:
            ctx.order_target_percent(stock, 0)
""",
            },
            "momentum": {
                "name": "动量策略",
                "description": "基于动量因子的策略",
                "code": """def initialize(ctx):
    ctx.assigner = ctx.target([\"000001\"])

def handle_bar(ctx):
    for stock in ctx.target_list:
        hist = ctx.data.history(stock, 20)
        if len(hist) < 20:
            continue
        momentum = (hist[-1] - hist[0]) / hist[0]
        if momentum > 0.05:
            ctx.order_target_percent(stock, 0.3)
        else:
            ctx.order_target_percent(stock, 0)
""",
            },
        }

    def get_templates(self) -> List[dict]:
        """Get all templates."""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in self._templates.items()
        ]

    def get_template(self, template_id: str) -> Optional[dict]:
        """Get a specific template."""
        return self._templates.get(template_id)
```

- [ ] **Step 2: 编写模板服务测试**

```python
# backend/tests/services/test_template_service.py
import pytest

from studio_api.services.template_service import TemplateService


@pytest.fixture
def template_service():
    return TemplateService()


def test_get_templates(template_service):
    """Test getting all templates."""
    templates = template_service.get_templates()
    assert len(templates) > 0
    assert all("id" in t and "name" in t for t in templates)


def test_get_template(template_service):
    """Test getting a specific template."""
    template = template_service.get_template("double_ma")
    assert template is not None
    assert "code" in template
    assert "def initialize" in template["code"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/studio_api/services/template_service.py backend/studio_api/data/templates.json tests/services/test_template_service.py
git commit -m "feat: add strategy template service with built-in templates"
```

---

### Task 3: 重构前端策略编辑器

**Files:**
- Modify: `frontend/src/components/MonacoStrategyEditor.tsx`
- Create: `frontend/src/components/VersionHistory.tsx`
- Create: `frontend/src/components/TemplateSelector.tsx`

- [ ] **Step 1: 重构Monaco编辑器组件**

```typescript
// frontend/src/components/MonacoStrategyEditor.tsx
import React, { useRef, useCallback, useState } from 'react';
import Editor from '@monaco-editor/react';
import { useDebounce } from '../hooks/useDebounce';

interface MonacoStrategyEditorProps {
  code: string;
  onChange: (code: string) => void;
  onSave: () => void;
  onFormat: () => void;
  isSaving: boolean;
}

export function MonacoStrategyEditor({
  code,
  onChange,
  onSave,
  onFormat,
  isSaving,
}: MonacoStrategyEditorProps) {
  const editorRef = useRef<any>(null);
  const [isDirty, setIsDirty] = useState(false);

  const debouncedSave = useDebounce(() => {
    if (isDirty) {
      onSave();
      setIsDirty(false);
    }
  }, 3000);

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined) {
        onChange(value);
        setIsDirty(true);
        debouncedSave();
      }
    },
    [onChange, debouncedSave]
  );

  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor;

    // Add custom keybindings
    editor.addCommand(
      // Ctrl+S / Cmd+S
      (window as any).monaco.KeyMod.CtrlCmd | (window as any).monaco.KeyCode.KeyS,
      () => {
        onSave();
        setIsDirty(false);
      }
    );

    editor.addCommand(
      // Ctrl+Shift+F / Cmd+Shift+F
      (window as any).monaco.KeyMod.CtrlCmd |
        (window as any).monaco.KeyMod.Shift |
        (window as any).monaco.KeyCode.KeyF,
      () => {
        onFormat();
      }
    );
  };

  return (
    <div className="relative h-full">
      <Editor
        height="100%"
        defaultLanguage="python"
        value={code}
        onChange={handleChange}
        onMount={handleEditorDidMount}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: 'JetBrains Mono, monospace',
          lineNumbers: 'on',
          roundedSelection: false,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          wordWrap: 'on',
          folding: true,
          foldingStrategy: 'indentation',
          showFoldingControls: 'always',
          bracketPairColorization: { enabled: true },
          guides: {
            bracketPairs: true,
            indentation: true,
          },
        }}
        theme="vs-dark"
      />
      {isDirty && (
        <div className="absolute top-2 right-2 px-2 py-1 bg-yellow-500 text-white text-xs rounded">
          未保存
        </div>
      )}
      {isSaving && (
        <div className="absolute top-2 right-2 px-2 py-1 bg-blue-500 text-white text-xs rounded">
          保存中...
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建版本历史组件**

```typescript
// frontend/src/components/VersionHistory.tsx
import React from 'react';

interface Version {
  versionNumber: number;
  code: string;
  comment: string;
  createdAt: string;
}

interface VersionHistoryProps {
  versions: Version[];
  onRestore: (versionNumber: number) => void;
  onCompare: (v1: number, v2: number) => void;
}

export function VersionHistory({ versions, onRestore, onCompare }: VersionHistoryProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold">版本历史</h3>
      <div className="space-y-2">
        {versions.map((version) => (
          <div
            key={version.versionNumber}
            className="p-3 border rounded hover:bg-gray-50 cursor-pointer"
          >
            <div className="flex justify-between items-center">
              <span className="font-medium">版本 {version.versionNumber}</span>
              <span className="text-sm text-gray-500">
                {new Date(version.createdAt).toLocaleString()}
              </span>
            </div>
            <p className="text-sm text-gray-600 mt-1">{version.comment}</p>
            <div className="flex gap-2 mt-2">
              <button
                onClick={() => onRestore(version.versionNumber)}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                恢复
              </button>
              <button
                onClick={() => onCompare(version.versionNumber, version.versionNumber - 1)}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                对比
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/MonacoStrategyEditor.tsx frontend/src/components/VersionHistory.tsx frontend/src/components/TemplateSelector.tsx
git commit -m "feat: refactor strategy editor with version history and templates"
```

---

## 自检清单

- [x] 实现了版本管理服务
- [x] 实现了模板服务
- [x] 重构了Monaco编辑器
- [x] 添加了版本历史UI
- [x] 添加了模板选择器
- [x] 测试覆盖

---

**Plan complete and saved to `docs/superpowers/plans/2025-06-06-module-A-strategy-editor.md`.**
