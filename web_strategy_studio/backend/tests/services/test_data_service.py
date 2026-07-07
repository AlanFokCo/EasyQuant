"""Tests for DataService — async data service layer.

Uses unittest.mock to patch eqlib.data_cache calls so no real file I/O
is needed. All tests are async (pytest-asyncio).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from studio_api.services.data_service import DataService, validate_code


@pytest.fixture
def svc() -> DataService:
    return DataService()


# ---------------------------------------------------------------------------
# validate_code
# ---------------------------------------------------------------------------


class TestValidateCode:
    def test_valid_code(self):
        assert validate_code("600519") == "600519"

    def test_strips_exchange_suffix(self):
        assert validate_code("600519.XSHG") == "600519"
        assert validate_code("000001.XSHE") == "000001"

    def test_strips_whitespace(self):
        assert validate_code("  600519  ") == "600519"

    def test_rejects_non_digits(self):
        with pytest.raises(ValueError, match="6 digits"):
            validate_code("ABCDEF")

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="6 digits"):
            validate_code("60051")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="6 digits"):
            validate_code("6005199")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="6 digits"):
            validate_code("../../etc/passwd")


# ---------------------------------------------------------------------------
# list_stocks
# ---------------------------------------------------------------------------


class TestListStocks:
    @pytest.mark.asyncio
    async def test_empty_directory(self, svc: DataService):
        with (patch("studio_api.services.data_service.dc.list_local_stocks", return_value=[]),):
            stocks, total = await svc.list_stocks()
            assert stocks == []
            assert total == 0

    @pytest.mark.asyncio
    async def test_pagination(self, svc: DataService):
        codes = [f"{600000 + i}" for i in range(25)]
        with (
            patch("studio_api.services.data_service.dc.list_local_stocks", return_value=codes),
            patch(
                "studio_api.services.data_service.dc.get_local_file_info",
                side_effect=lambda code, adjust="qfq": {
                    "code": code,
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "size_bytes": 1024,
                    "size_human": "1.0KB",
                },
            ),
        ):
            # Page 1 of 10 per page
            stocks, total = await svc.list_stocks(page=1, per_page=10)
            assert total == 25
            assert len(stocks) == 10

            # Clear cache between requests to avoid cache hits
            svc.invalidate_cache()

            # Page 3 should have 5 items (25 - 20)
            stocks, total = await svc.list_stocks(page=3, per_page=10)
            assert total == 25
            assert len(stocks) == 5

    @pytest.mark.asyncio
    async def test_search(self, svc: DataService):
        codes = ["600519", "000001", "601398", "000858"]
        with (
            patch("studio_api.services.data_service.dc.list_local_stocks", return_value=codes),
            patch(
                "studio_api.services.data_service.dc.get_local_file_info",
                side_effect=lambda code, adjust="qfq": {
                    "code": code,
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "size_bytes": 1024,
                    "size_human": "1.0KB",
                },
            ),
        ):
            stocks, total = await svc.list_stocks(search="600")
            assert total == 1
            assert all("600" in s["code"] for s in stocks)

    @pytest.mark.asyncio
    async def test_sorting_desc(self, svc: DataService):
        codes = ["600519", "000001", "601398"]
        with (
            patch("studio_api.services.data_service.dc.list_local_stocks", return_value=codes),
            patch(
                "studio_api.services.data_service.dc.get_local_file_info",
                side_effect=lambda code, adjust="qfq": {
                    "code": code,
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "size_bytes": 1024,
                    "size_human": "1.0KB",
                },
            ),
        ):
            stocks, _ = await svc.list_stocks(sort_by="code", sort_order="desc")
            code_list = [s["code"] for s in stocks]
            assert code_list == sorted(code_list, reverse=True)

    @pytest.mark.asyncio
    async def test_cache_hit(self, svc: DataService):
        """Second call with same params should return cached result."""
        codes = ["600519"]
        with (
            patch(
                "studio_api.services.data_service.dc.list_local_stocks", return_value=codes
            ) as mock_list,
            patch(
                "studio_api.services.data_service.dc.get_local_file_info",
                return_value={
                    "code": "600519",
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "size_bytes": 1024,
                    "size_human": "1.0KB",
                },
            ) as _mock_info,
        ):
            stocks1, total1 = await svc.list_stocks(page=1, per_page=50)
            stocks2, total2 = await svc.list_stocks(page=1, per_page=50)

            assert stocks1 == stocks2
            assert total1 == total2
            # list_local_stocks called only once (second call is cached)
            assert mock_list.call_count == 1


# ---------------------------------------------------------------------------
# get_stock_detail
# ---------------------------------------------------------------------------


class TestGetStockDetail:
    @pytest.mark.asyncio
    async def test_found(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value={
                "code": "600519",
                "file": "/data/600519_daily_qfq.csv",
                "start_date": "2010-01-01",
                "end_date": "2024-12-31",
                "size_bytes": 51200,
                "size_human": "50.0KB",
            },
        ):
            info = await svc.get_stock_detail("600519")
            assert info is not None
            assert info["code"] == "600519"

    @pytest.mark.asyncio
    async def test_not_found(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value=None,
        ):
            info = await svc.get_stock_detail("999999")
            assert info is None

    @pytest.mark.asyncio
    async def test_detail_cache_hit(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value={
                "code": "600519",
                "file": "/data/600519_daily_qfq.csv",
                "start_date": "2010-01-01",
                "end_date": "2024-12-31",
                "size_bytes": 51200,
                "size_human": "50.0KB",
            },
        ) as mock_info:
            assert await svc.get_stock_detail("600519") is not None
            assert await svc.get_stock_detail("600519") is not None
            assert mock_info.call_count == 1


# ---------------------------------------------------------------------------
# batch_delete
# ---------------------------------------------------------------------------


class TestBatchDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.remove_local_data",
            return_value=True,
        ):
            result = await svc.batch_delete(["600519", "000001"])
            assert result["deleted"] == 2
            assert result["deleted_codes"] == ["600519", "000001"]
            assert result["failed"] == []

    @pytest.mark.asyncio
    async def test_delete_missing(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.remove_local_data",
            return_value=False,
        ):
            result = await svc.batch_delete(["999999"])
            assert result["deleted"] == 0
            assert len(result["failed"]) == 1
            assert result["failed"][0]["code"] == "999999"

    @pytest.mark.asyncio
    async def test_mixed_results(self, svc: DataService):
        def _mock_remove(code, adjust="qfq"):
            return code == "600519"

        with patch(
            "studio_api.services.data_service.dc.remove_local_data",
            side_effect=_mock_remove,
        ):
            result = await svc.batch_delete(["600519", "999999"])
            assert result["deleted"] == 1
            assert result["deleted_codes"] == ["600519"]
            assert len(result["failed"]) == 1

    @pytest.mark.asyncio
    async def test_invalidates_cache(self, svc: DataService):
        """Batch delete should clear the cache."""
        # Pre-populate cache
        svc._cache["test_key"] = "test_value"
        svc._cache_timestamps["test_key"] = datetime.now()

        with patch(
            "studio_api.services.data_service.dc.remove_local_data",
            return_value=True,
        ):
            await svc.batch_delete(["600519"])

        assert len(svc._cache) == 0
        assert len(svc._cache_timestamps) == 0


# ---------------------------------------------------------------------------
# check_data_quality
# ---------------------------------------------------------------------------


class TestCheckDataQuality:
    @pytest.mark.asyncio
    async def test_no_data(self, svc: DataService):
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value=None,
        ):
            report = await svc.check_data_quality("999999")
            assert report["exists"] is False
            assert report["score"] == 0

    @pytest.mark.asyncio
    async def test_good_quality(self, svc: DataService):
        today = datetime.now().strftime("%Y-%m-%d")
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value={
                "code": "600519",
                "start_date": "2010-01-01",
                "end_date": today,
                "size_bytes": 51200,
                "size_human": "50.0KB",
            },
        ):
            report = await svc.check_data_quality("600519")
            assert report["exists"] is True
            assert report["score"] == 100
            assert report["message"] == "Good"

    @pytest.mark.asyncio
    async def test_stale_data(self, svc: DataService):
        old_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        with patch(
            "studio_api.services.data_service.dc.get_local_file_info",
            return_value={
                "code": "600519",
                "start_date": "2010-01-01",
                "end_date": old_date,
                "size_bytes": 51200,
                "size_human": "50.0KB",
            },
        ):
            report = await svc.check_data_quality("600519")
            assert report["exists"] is True
            # Stale data loses 25 points (freshness check fails)
            assert report["score"] == 75


# ---------------------------------------------------------------------------
# download_stocks
# ---------------------------------------------------------------------------


class TestDownloadStocks:
    @pytest.mark.asyncio
    async def test_new_download(self, svc: DataService):
        with (
            patch("studio_api.services.data_service.dc.has_local_data", return_value=False),
            patch(
                "studio_api.services.data_service.dc.save_stock_local",
                return_value="/data/600519.csv",
            ),
        ):
            result = await svc.download_stocks(["600519"])
            assert result["ok"] is True
            assert result["downloaded"] == ["600519"]
            assert result["merged"] == []

    @pytest.mark.asyncio
    async def test_merge_existing(self, svc: DataService):
        with (
            patch("studio_api.services.data_service.dc.has_local_data", return_value=True),
            patch(
                "studio_api.services.data_service.dc.save_stock_local",
                return_value="/data/600519.csv",
            ),
        ):
            result = await svc.download_stocks(["600519"])
            assert result["ok"] is True
            assert result["downloaded"] == []
            assert result["merged"] == ["600519"]

    @pytest.mark.asyncio
    async def test_download_failure(self, svc: DataService):
        with (
            patch("studio_api.services.data_service.dc.has_local_data", return_value=False),
            patch("studio_api.services.data_service.dc.save_stock_local", return_value=None),
        ):
            result = await svc.download_stocks(["999999"])
            assert result["ok"] is False
            assert len(result["failed"]) == 1

    @pytest.mark.asyncio
    async def test_download_invalidates_cache(self, svc: DataService):
        svc._cache["stocks"] = "cached"
        svc._cache_timestamps["stocks"] = datetime.now()
        with (
            patch("studio_api.services.data_service.dc.has_local_data", return_value=False),
            patch(
                "studio_api.services.data_service.dc.save_stock_local",
                return_value="/data/600519.csv",
            ),
        ):
            await svc.download_stocks(["600519"])

        assert svc._cache == {}
        assert svc._cache_timestamps == {}


# ---------------------------------------------------------------------------
# cache management
# ---------------------------------------------------------------------------


class TestCacheManagement:
    def test_invalidate_cache(self, svc: DataService):
        svc._cache["key1"] = "value1"
        svc._cache_timestamps["key1"] = datetime.now()
        svc.invalidate_cache()
        assert len(svc._cache) == 0
        assert len(svc._cache_timestamps) == 0

    def test_cache_expiry(self, svc: DataService):
        key = "test_key"
        svc._cache[key] = "value"
        svc._cache_timestamps[key] = datetime.now() - timedelta(minutes=10)
        assert not svc._is_cache_valid(key)

    def test_cache_valid(self, svc: DataService):
        key = "test_key"
        svc._cache[key] = "value"
        svc._cache_timestamps[key] = datetime.now()
        assert svc._is_cache_valid(key)

    def test_cache_key_missing(self, svc: DataService):
        assert not svc._is_cache_valid("nonexistent")
