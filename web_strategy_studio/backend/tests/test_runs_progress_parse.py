"""Tests for backtest progress parsing (B5) and estimation (B10) — Phase 0."""

from __future__ import annotations

from datetime import date

from studio_api.backtest_executor import _PROGRESS_RE, _estimate_trading_fraction


class TestProgressRegex:
    """B5 — regex must match the real eqlib log format."""

    def test_matches_emoji_format(self):
        line = "📍 Backtest progress: 47/250 (18.8%)"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 47
        assert int(m.group(2)) == 250

    def test_matches_plain_format(self):
        line = "Backtest progress 47/250"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 47
        assert int(m.group(2)) == 250

    def test_matches_colon_no_emoji(self):
        line = "Backtest progress: 100/200"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 100
        assert int(m.group(2)) == 200

    def test_matches_spaces_around_slash(self):
        line = "Backtest progress: 10 / 250 (4.0%)"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 10
        assert int(m.group(2)) == 250

    def test_no_match_on_unrelated_line(self):
        line = "Loading data for 600000.XSHG..."
        m = _PROGRESS_RE.search(line)
        assert m is None

    def test_no_match_on_empty_line(self):
        assert _PROGRESS_RE.search("") is None

    def test_matches_boundary_zero(self):
        line = "Backtest progress: 0/250"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 0

    def test_matches_boundary_complete(self):
        line = "📍 Backtest progress: 250/250 (100.0%)"
        m = _PROGRESS_RE.search(line)
        assert m is not None
        assert int(m.group(1)) == 250
        assert int(m.group(2)) == 250


class TestEstimateTradingFraction:
    """B10 — should use trading days (~250/yr), not calendar days (~365/yr)."""

    def test_fraction_at_midpoint_is_reasonable(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        # About 261 trading days in 2024; 130 done ≈ halfway
        frac = _estimate_trading_fraction(130, start, end)
        assert 0.4 < frac < 0.8, f"Expected ~0.6, got {frac}"

    def test_fraction_does_not_exceed_0_95(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        frac = _estimate_trading_fraction(9999, start, end)
        assert frac <= 0.95

    def test_fraction_minimum_at_zero_days(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        frac = _estimate_trading_fraction(0, start, end)
        assert frac >= 0.15  # minimum floor from the formula

    def test_trading_days_less_than_calendar_days(self):
        """Verify that bdate_range gives ~250 not ~365 for a full year."""
        import pandas as pd

        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        trading_days = len(pd.bdate_range(start=start, end=end))
        calendar_days = (end - start).days
        # Trading days must be substantially less than calendar days
        assert trading_days < calendar_days * 0.8

    def test_short_range_handles_gracefully(self):
        start = date(2024, 3, 1)
        end = date(2024, 3, 5)  # only a few trading days
        frac = _estimate_trading_fraction(1, start, end)
        assert 0 < frac <= 0.95
