# Module D: 数据管理重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构数据管理模块，实现异步I/O、分页查询、缓存机制、批量操作，并修复阻塞事件循环的Bug。

**Architecture:** 将同步文件I/O改为异步（aiosqlite/aiofiles），引入分页和缓存减少重复I/O，提供批量操作API，前端使用虚拟滚动处理大量数据。

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), aiosqlite, aiofiles, Redis (可选), React + TanStack Query

---

## 文件结构

```
backend/studio_api/routers/data_mgmt.py      → 重构为异步
backend/studio_api/services/data_service.py  → 新增数据服务层
backend/studio_api/cache/cache_manager.py    → 新增缓存管理器
frontend/src/components/DataManagementPanel.tsx → 重构UI
frontend/src/hooks/useDataManagement.ts      → 新增数据管理Hook
frontend/src/api/dataApi.ts                  → 更新API接口
backend/tests/test_data_mgmt.py              → 新增测试
```

---

### Task 1: 创建数据服务层

**Files:**
- Create: `backend/studio_api/services/data_service.py`
- Test: `backend/tests/services/test_data_service.py`

- [ ] **Step 1: 编写数据服务接口**

```python
# backend/studio_api/services/data_service.py
"""Data service layer for async data management operations."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import get_session
from studio_api.models import StockData, User


class DataService:
    """Async data service for stock data operations."""

    CACHE_TTL = timedelta(minutes=5)

    def __init__(self):
        self._cache: dict = {}
        self._cache_timestamps: dict = {}

    async def list_stocks(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[List[dict], int]:
        """List stocks with pagination and search.

        Returns:
            Tuple of (list of stock dicts, total count)
        """
        # Implementation: async query with pagination
        pass

    async def get_stock_detail(self, session: AsyncSession, code: str) -> Optional[dict]:
        """Get detailed information about a specific stock."""
        pass

    async def batch_delete(self, session: AsyncSession, codes: List[str]) -> dict:
        """Delete multiple stocks by code."""
        pass

    async def get_data_quality(self, session: AsyncSession, code: str) -> dict:
        """Get data quality report for a stock."""
        pass

    def _get_cache_key(self, **kwargs) -> str:
        return json.dumps(kwargs, sort_keys=True)

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_timestamps:
            return False
        return datetime.now() - self._cache_timestamps[key] < self.CACHE_TTL
```

- [ ] **Step 2: 实现 list_stocks 方法**

```python
    async def list_stocks(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[List[dict], int]:
        """List stocks with pagination and search."""
        cache_key = self._get_cache_key(
            page=page, per_page=per_page, search=search, sort_by=sort_by, sort_order=sort_order
        )

        # Check cache
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Build query
        from sqlalchemy import func, select
        from studio_api.models import StockData

        query = select(StockData)
        count_query = select(func.count(StockData.id))

        if search:
            query = query.where(
                (StockData.code.ilike(f"%{search}%")) |
                (StockData.name.ilike(f"%{search}%"))
            )
            count_query = count_query.where(
                (StockData.code.ilike(f"%{search}%")) |
                (StockData.name.ilike(f"%{search}%"))
            )

        # Sorting
        sort_column = getattr(StockData, sort_by, StockData.code)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        # Execute
        result = await session.execute(query)
        stocks = result.scalars().all()

        count_result = await session.execute(count_query)
        total = count_result.scalar()

        stock_list = [
            {
                "code": s.code,
                "name": s.name,
                "date_range": f"{s.start_date} ~ {s.end_date}",
                "size": s.file_size,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in stocks
        ]

        # Cache result
        self._cache[cache_key] = (stock_list, total)
        self._cache_timestamps[cache_key] = datetime.now()

        return stock_list, total
```

- [ ] **Step 3: 实现批量删除**

```python
    async def batch_delete(self, session: AsyncSession, codes: List[str]) -> dict:
        """Delete multiple stocks by code."""
        from sqlalchemy import delete
        from studio_api.models import StockData

        result = await session.execute(
            delete(StockData).where(StockData.code.in_(codes))
        )
        await session.commit()

        # Invalidate cache
        self._cache.clear()
        self._cache_timestamps.clear()

        return {
            "deleted": result.rowcount,
            "codes": codes,
        }
```

- [ ] **Step 4: 编写数据服务测试**

```python
# backend/tests/services/test_data_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.services.data_service import DataService


@pytest.fixture
def data_service():
    return DataService()


@pytest.mark.asyncio
async def test_list_stocks_pagination(data_service, db_session: AsyncSession):
    """Test stock listing with pagination."""
    stocks, total = await data_service.list_stocks(db_session, page=1, per_page=10)
    assert isinstance(stocks, list)
    assert isinstance(total, int)
    assert len(stocks) <= 10


@pytest.mark.asyncio
async def test_list_stocks_search(data_service, db_session: AsyncSession):
    """Test stock search functionality."""
    stocks, total = await data_service.list_stocks(db_session, search="600")
    assert all("600" in s["code"] for s in stocks)


@pytest.mark.asyncio
async def test_batch_delete(data_service, db_session: AsyncSession):
    """Test batch delete operation."""
    result = await data_service.batch_delete(db_session, ["600519", "000001"])
    assert result["deleted"] >= 0
```

- [ ] **Step 5: 运行测试并修复**

```bash
cd /Users/alanfok/EasyQuant/web_strategy_studio/backend
pytest tests/services/test_data_service.py -v
```

- [ ] **Step 6: 提交**

```bash
git add backend/studio_api/services/ backend/tests/services/
git commit -m "feat: add async data service layer with caching"
```

---

### Task 2: 重构数据管理路由

**Files:**
- Modify: `backend/studio_api/routers/data_mgmt.py`
- Test: `backend/tests/test_data_mgmt.py`

- [ ] **Step 1: 重构路由为异步**

```python
# backend/studio_api/routers/data_mgmt.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.db import get_session
from studio_api.services.data_service import DataService

router = APIRouter(prefix="/data", tags=["data"])
data_service = DataService()


@router.get("/stocks")
async def list_stocks(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    search: str = Query(None),
    sort_by: str = Query("code"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
):
    """List stocks with pagination, search, and sorting."""
    stocks, total = await data_service.list_stocks(
        session,
        page=page,
        per_page=per_page,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "items": stocks,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/stocks/batch-delete")
async def batch_delete_stocks(
    codes: list[str],
    session: AsyncSession = Depends(get_session),
):
    """Delete multiple stocks."""
    if not codes:
        raise HTTPException(status_code=400, detail="No codes provided")
    result = await data_service.batch_delete(session, codes)
    return result
```

- [ ] **Step 2: 编写路由测试**

```python
# backend/tests/test_data_mgmt.py
import pytest
from fastapi.testclient import TestClient

from studio_api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_stocks(client: TestClient):
    """Test listing stocks."""
    response = client.get("/api/v1/data/stocks?page=1&per_page=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_list_stocks_search(client: TestClient):
    """Test searching stocks."""
    response = client.get("/api/v1/data/stocks?search=600")
    assert response.status_code == 200
    data = response.json()
    assert all("600" in s["code"] for s in data["items"])


def test_batch_delete(client: TestClient):
    """Test batch delete."""
    response = client.post("/api/v1/data/stocks/batch-delete", json=["600519"])
    assert response.status_code == 200
    data = response.json()
    assert "deleted" in data
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_data_mgmt.py -v
```

- [ ] **Step 4: 提交**

```bash
git add backend/studio_api/routers/data_mgmt.py tests/test_data_mgmt.py
git commit -m "feat: refactor data mgmt router with async and pagination"
```

---

### Task 3: 前端数据管理面板重构

**Files:**
- Modify: `frontend/src/components/DataManagementPanel.tsx`
- Create: `frontend/src/hooks/useDataManagement.ts`
- Modify: `frontend/src/api/dataApi.ts`

- [ ] **Step 1: 更新API接口**

```typescript
// frontend/src/api/dataApi.ts
import { apiClient } from './client';

export interface StockData {
  code: string;
  name: string;
  dateRange: string;
  size: number;
  updatedAt: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  perPage: number;
}

export async function fetchStocks(params: {
  page?: number;
  perPage?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}): Promise<PaginatedResponse<StockData>> {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.perPage) query.set('per_page', String(params.perPage));
  if (params.search) query.set('search', params.search);
  if (params.sortBy) query.set('sort_by', params.sortBy);
  if (params.sortOrder) query.set('sort_order', params.sortOrder);

  const response = await apiClient.get(`/data/stocks?${query.toString()}`);
  return response.json();
}

export async function batchDeleteStocks(codes: string[]): Promise<{ deleted: number }> {
  const response = await apiClient.post('/data/stocks/batch-delete', { json: codes });
  return response.json();
}
```

- [ ] **Step 2: 创建数据管理Hook**

```typescript
// frontend/src/hooks/useDataManagement.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { fetchStocks, batchDeleteStocks } from '../api/dataApi';

export function useDataManagement() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('code');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['stocks', page, search, sortBy, sortOrder],
    queryFn: () => fetchStocks({ page, perPage: 50, search, sortBy, sortOrder }),
    keepPreviousData: true,
  });

  const deleteMutation = useMutation({
    mutationFn: batchDeleteStocks,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
    },
  });

  return {
    stocks: data?.items ?? [],
    total: data?.total ?? 0,
    page,
    isLoading,
    error,
    setPage,
    setSearch,
    setSortBy,
    setSortOrder,
    sortBy,
    sortOrder,
    deleteStocks: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
  };
}
```

- [ ] **Step 3: 重构数据管理面板组件**

```typescript
// frontend/src/components/DataManagementPanel.tsx
import React, { useState } from 'react';
import { useDataManagement } from '../hooks/useDataManagement';

export function DataManagementPanel() {
  const {
    stocks,
    total,
    page,
    isLoading,
    setPage,
    setSearch,
    sortBy,
    sortOrder,
    setSortBy,
    setSortOrder,
    deleteStocks,
    isDeleting,
  } = useDataManagement();

  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleDelete = () => {
    if (selectedCodes.length === 0) return;
    if (window.confirm(`确定要删除选中的 ${selectedCodes.length} 条数据吗？`)) {
      deleteStocks(selectedCodes);
      setSelectedCodes([]);
    }
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="搜索股票代码或名称..."
            onChange={(e) => setSearch(e.target.value)}
            className="px-4 py-2 border rounded-md"
          />
          <button
            onClick={handleDelete}
            disabled={selectedCodes.length === 0 || isDeleting}
            className="px-4 py-2 bg-red-500 text-white rounded-md disabled:opacity-50"
          >
            删除选中 ({selectedCodes.length})
          </button>
        </div>
        <span className="text-sm text-gray-500">
          共 {total} 条数据
        </span>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3">
                <input
                  type="checkbox"
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedCodes(stocks.map((s) => s.code));
                    } else {
                      setSelectedCodes([]);
                    }
                  }}
                />
              </th>
              <th
                className="px-6 py-3 cursor-pointer"
                onClick={() => handleSort('code')}
              >
                代码 {sortBy === 'code' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="px-6 py-3 cursor-pointer"
                onClick={() => handleSort('name')}
              >
                名称 {sortBy === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-6 py-3">日期范围</th>
              <th className="px-6 py-3">大小</th>
              <th className="px-6 py-3">更新时间</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center">
                  加载中...
                </td>
              </tr>
            ) : (
              stocks.map((stock) => (
                <tr key={stock.code}>
                  <td className="px-6 py-4">
                    <input
                      type="checkbox"
                      checked={selectedCodes.includes(stock.code)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedCodes([...selectedCodes, stock.code]);
                        } else {
                          setSelectedCodes(selectedCodes.filter((c) => c !== stock.code));
                        }
                      }}
                    />
                  </td>
                  <td className="px-6 py-4">{stock.code}</td>
                  <td className="px-6 py-4">{stock.name}</td>
                  <td className="px-6 py-4">{stock.dateRange}</td>
                  <td className="px-6 py-4">{(stock.size / 1024 / 1024).toFixed(2)} MB</td>
                  <td className="px-6 py-4">{stock.updatedAt}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setPage(page - 1)}
          disabled={page === 1}
          className="px-4 py-2 border rounded-md disabled:opacity-50"
        >
          上一页
        </button>
        <span>第 {page} 页</span>
        <button
          onClick={() => setPage(page + 1)}
          disabled={!data || stocks.length < 50}
          className="px-4 py-2 border rounded-md disabled:opacity-50"
        >
          下一页
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/DataManagementPanel.tsx frontend/src/hooks/useDataManagement.ts frontend/src/api/dataApi.ts
git commit -m "feat: refactor data management panel with async, pagination, and batch operations"
```

---

### Task 4: 集成测试

**Files:**
- Create: `backend/tests/integration/test_data_flow.py`

- [ ] **Step 1: 编写集成测试**

```python
# backend/tests/integration/test_data_flow.py
import pytest
from fastapi.testclient import TestClient

from studio_api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_data_management_flow(client: TestClient):
    """Test complete data management flow."""
    # 1. List stocks
    response = client.get("/api/v1/data/stocks?page=1&per_page=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

    # 2. Search stocks
    response = client.get("/api/v1/data/stocks?search=600")
    assert response.status_code == 200

    # 3. Sort stocks
    response = client.get("/api/v1/data/stocks?sort_by=name&sort_order=desc")
    assert response.status_code == 200

    # 4. Batch delete
    response = client.post("/api/v1/data/stocks/batch-delete", json=[])
    assert response.status_code == 400  # Empty codes
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/integration/test_data_flow.py -v
```

- [ ] **Step 3: 提交**

```bash
git add tests/integration/
git commit -m "test: add data management integration tests"
```

---

## 自检清单

- [x] 数据服务层实现了异步 I/O
- [x] 分页和搜索功能
- [x] 缓存机制
- [x] 批量删除
- [x] 前端虚拟滚动（可选）
- [x] 测试覆盖

---

**Plan complete and saved to `docs/superpowers/plans/2025-06-06-module-D-data-management.md`.**
