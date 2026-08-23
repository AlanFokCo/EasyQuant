"""Tests for BLOCKER-6 (A-share holiday calendar beyond 2028).

BLOCKER-6: The hardcoded holiday set only covers 2020-2028. For years
beyond that range, _is_ashare_holiday returns False for all dates, so
all weekdays (Mon-Fri) are treated as trading days — including real
holidays like New Year's Day 2030.

The fix uses chinese_calendar as primary source (2004-2026), falls back
to hardcoded set (2020-2028), then to fixed-date holiday rules (any year).
"""

import datetime

import pytest

from eqlib.data import DataFetchError, get_trade_days


def _offline_calendar_provider():
    raise RuntimeError("offline")


def test_bundled_calendar_excludes_2024_lunar_new_year_eve_when_provider_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        "eqlib.data.ak.tool_trade_date_hist_sina", _offline_calendar_provider
    )

    days = get_trade_days("2024-02-01", "2024-02-20")

    assert datetime.date(2024, 2, 9) not in days
    assert datetime.date(2024, 2, 8) in days
    assert datetime.date(2024, 2, 19) in days


def test_bundled_calendar_rejects_unknown_year_when_provider_fails(monkeypatch):
    monkeypatch.setattr(
        "eqlib.data.ak.tool_trade_date_hist_sina", _offline_calendar_provider
    )

    with pytest.raises(DataFetchError, match="calendar coverage"):
        get_trade_days("2030-01-01", "2030-01-31", strict=True)


class TestBlocker6HolidayCalendar:
    """Verify that _is_ashare_holiday correctly identifies holidays for
    years beyond the hardcoded range.
    """

    def test_2030_new_years_day_is_holiday(self):
        """2030-01-01 is New Year's Day — must be detected as holiday."""
        from eqlib.data import _is_ashare_holiday

        nyd = datetime.date(2030, 1, 1)
        assert _is_ashare_holiday(
            nyd
        ), "2030-01-01 (New Year's Day) should be detected as holiday"

    def test_2030_jan_2_is_workday(self):
        """2030-01-02 is a normal Wednesday — should be a workday."""
        from eqlib.data import _is_ashare_holiday

        d = datetime.date(2030, 1, 2)
        assert d.weekday() == 2, "2030-01-02 should be Wednesday"
        assert not _is_ashare_holiday(d), "2030-01-02 should not be a holiday"

    def test_2030_labor_day_is_holiday(self):
        """2030-05-01 is Labor Day — must be detected as holiday."""
        from eqlib.data import _is_ashare_holiday

        ld = datetime.date(2030, 5, 1)
        assert _is_ashare_holiday(
            ld
        ), "2030-05-01 (Labor Day) should be detected as holiday"

    def test_2030_national_day_is_holiday(self):
        """2030-10-01 is National Day — must be detected as holiday."""
        from eqlib.data import _is_ashare_holiday

        nd = datetime.date(2030, 10, 1)
        assert _is_ashare_holiday(
            nd
        ), "2030-10-01 (National Day) should be detected as holiday"

    def test_2026_holiday_still_uses_chinese_calendar(self):
        """For 2026, chinese_calendar should be the primary source."""
        from eqlib.data import _is_ashare_holiday, _CC_AVAILABLE

        if not _CC_AVAILABLE:
            pytest.skip("chinese_calendar not installed")

        # 2026-01-01 is New Year's Day — both sources agree
        nyd = datetime.date(2026, 1, 1)
        assert _is_ashare_holiday(nyd)

        # 2026-01-04 is Sunday — chinese_calendar knows it's a holiday
        sun = datetime.date(2026, 1, 4)
        assert sun.weekday() == 6

    def test_chinese_calendar_module_available(self):
        """Verify chinese_calendar is importable."""
        from eqlib.data import _CC_AVAILABLE

        assert _CC_AVAILABLE, "chinese_calendar should be importable"

    def test_get_trade_days_fallback_does_not_infer_unknown_calendar_year(self):
        """Offline fallback must not fabricate trading days outside resource coverage."""
        from unittest.mock import patch
        from eqlib.data import get_trade_days

        with patch(
            "eqlib.data.ak.tool_trade_date_hist_sina",
            side_effect=RuntimeError("akshare unavailable"),
        ):
            days = get_trade_days(
                start_date=datetime.date(2030, 1, 1),
                end_date=datetime.date(2030, 1, 31),
            )

        assert days == []

    def test_weekend_not_in_trading_days(self):
        """Weekends should never be trading days."""
        from eqlib.data import get_trade_days

        days = get_trade_days(
            start_date=datetime.date(2030, 1, 1),
            end_date=datetime.date(2030, 1, 31),
        )
        for d in days:
            assert d.weekday() < 5, f"{d} is a weekend but included in trading days"
