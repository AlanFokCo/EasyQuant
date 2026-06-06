"""Tests for the data management router endpoints.

Uses httpx.AsyncClient with FastAPI's dependency_overrides to bypass auth.
The DataService is mocked to avoid real file I/O.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Force in-memory DB and temp artifact dir for test isolation
os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault(
    "EQ_STUDIO_ARTIFACT_DIR",
    os.path.join(tempfile.gettempdir(), "eq_studio_data_mgmt_test"),
)


class _FakeUser:
    """Minimal stand-in for studio_api.models.User (avoids SQLAlchemy init)."""

    id = "test-user-id"
    username = "testuser"
    hashed_password = ""
    is_active = True


async def _fake_get_current_user():
    """FastAPI dependency override: always return a valid user."""
    return _FakeUser()


@pytest_asyncio.fixture
async def client():
    """Async test client with auth dependency overridden."""
    from studio_api.app import app
    from studio_api import auth as auth_mod

    app.dependency_overrides[auth_mod.get_current_user] = _fake_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /data/local  — paginated listing
# ---------------------------------------------------------------------------


class TestListLocalData:
    @pytest.mark.asyncio
    async def test_list_default(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.list_stocks",
            new_callable=AsyncMock,
            return_value=(
                [
                    {
                        "code": "600519",
                        "start_date": "2020-01-01",
                        "end_date": "2024-12-31",
                        "size_bytes": 1024,
                        "size_human": "1.0KB",
                    }
                ],
                1,
            ),
        ):
            resp = await client.get("/api/v1/data/local")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["per_page"] == 50

    @pytest.mark.asyncio
    async def test_list_pagination_params(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.list_stocks",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            resp = await client.get("/api/v1/data/local?page=2&per_page=10")
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=2,
                per_page=10,
                search=None,
                sort_by="code",
                sort_order="asc",
                adjust="qfq",
            )

    @pytest.mark.asyncio
    async def test_list_search(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.list_stocks",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            resp = await client.get("/api/v1/data/local?search=600")
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=1,
                per_page=50,
                search="600",
                sort_by="code",
                sort_order="asc",
                adjust="qfq",
            )

    @pytest.mark.asyncio
    async def test_list_sort_params(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.list_stocks",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            resp = await client.get("/api/v1/data/local?sort_by=size_bytes&sort_order=desc")
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=1,
                per_page=50,
                search=None,
                sort_by="size_bytes",
                sort_order="desc",
                adjust="qfq",
            )

    @pytest.mark.asyncio
    async def test_invalid_page(self, client: AsyncClient):
        resp = await client.get("/api/v1/data/local?page=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_sort_order(self, client: AsyncClient):
        resp = await client.get("/api/v1/data/local?sort_order=invalid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /data/local/{code}  — single stock detail
# ---------------------------------------------------------------------------


class TestGetStockDetail:
    @pytest.mark.asyncio
    async def test_found(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.get_stock_detail",
            new_callable=AsyncMock,
            return_value={
                "code": "600519",
                "file": "/data/600519_daily_qfq.csv",
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "size_bytes": 51200,
                "size_human": "50.0KB",
            },
        ):
            resp = await client.get("/api/v1/data/local/600519")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == "600519"

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.get_stock_detail",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.get("/api/v1/data/local/999999")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_code(self, client: AsyncClient):
        resp = await client.get("/api/v1/data/local/ABCDEF")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /data/local/{code}/quality  — data quality report
# ---------------------------------------------------------------------------


class TestDataQuality:
    @pytest.mark.asyncio
    async def test_quality_report(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.check_data_quality",
            new_callable=AsyncMock,
            return_value={
                "code": "600519",
                "exists": True,
                "checks": [
                    {"name": "file_exists", "passed": True, "message": "OK"},
                ],
                "score": 100,
                "message": "Good",
            },
        ):
            resp = await client.get("/api/v1/data/local/600519/quality")
            assert resp.status_code == 200
            data = resp.json()
            assert data["score"] == 100
            assert data["message"] == "Good"

    @pytest.mark.asyncio
    async def test_quality_invalid_code(self, client: AsyncClient):
        resp = await client.get("/api/v1/data/local/INVALID/quality")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /data/local/download  — download stock data
# ---------------------------------------------------------------------------


class TestDownload:
    @pytest.mark.asyncio
    async def test_download_success(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.download_stocks",
            new_callable=AsyncMock,
            return_value={
                "ok": True,
                "downloaded": ["600519"],
                "merged": [],
                "failed": [],
            },
        ):
            resp = await client.post(
                "/api/v1/data/local/download",
                json={"securities": ["600519"]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["downloaded"] == ["600519"]

    @pytest.mark.asyncio
    async def test_download_invalid_code(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/data/local/download",
            json={"securities": ["INVALID"]},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /data/local/batch-delete  — batch delete
# ---------------------------------------------------------------------------


class TestBatchDelete:
    @pytest.mark.asyncio
    async def test_batch_delete_success(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.batch_delete",
            new_callable=AsyncMock,
            return_value={
                "deleted": 2,
                "deleted_codes": ["600519", "000001"],
                "failed": [],
            },
        ):
            resp = await client.post(
                "/api/v1/data/local/batch-delete",
                json={"codes": ["600519", "000001"]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted"] == 2

    @pytest.mark.asyncio
    async def test_batch_delete_empty_codes(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/data/local/batch-delete",
            json={"codes": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_delete_invalid_code(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/data/local/batch-delete",
            json={"codes": ["INVALID"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_delete_partial(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.batch_delete",
            new_callable=AsyncMock,
            return_value={
                "deleted": 1,
                "deleted_codes": ["600519"],
                "failed": [{"code": "999999", "error": "No local data found"}],
            },
        ):
            resp = await client.post(
                "/api/v1/data/local/batch-delete",
                json={"codes": ["600519", "999999"]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted"] == 1
            assert len(data["failed"]) == 1


# ---------------------------------------------------------------------------
# DELETE /data/local/{code}  — single delete (backward compat)
# ---------------------------------------------------------------------------


class TestDeleteSingle:
    @pytest.mark.asyncio
    async def test_delete_success(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.batch_delete",
            new_callable=AsyncMock,
            return_value={
                "deleted": 1,
                "deleted_codes": ["600519"],
                "failed": [],
            },
        ):
            resp = await client.delete("/api/v1/data/local/600519")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient):
        with patch(
            "studio_api.routers.data_mgmt._data_service.batch_delete",
            new_callable=AsyncMock,
            return_value={
                "deleted": 0,
                "deleted_codes": [],
                "failed": [{"code": "999999", "error": "No local data found"}],
            },
        ):
            resp = await client.delete("/api/v1/data/local/999999")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_invalid_code(self, client: AsyncClient):
        resp = await client.delete("/api/v1/data/local/ABCDEF")
        assert resp.status_code == 400
