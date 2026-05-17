"""Tests for BLOCKER-4 (minute mode warning).

BLOCKER-4: In minute mode, orders placed during minute bars are buffered
and only filled at the next trading day's open — not intraday. The fix for
PR-3 is a warning emitted by run_backtest when frequency='minute' is used,
so users are aware of the limitation.
"""

import datetime
import warnings

import pytest


class TestBlocker4MinuteModeWarning:
    """Verify that run_backtest emits a UserWarning when frequency='minute'."""

    def test_minute_mode_emits_warning(self):
        """run_backtest with frequency='minute' should warn about intraday limitation."""
        import eqlib
        from eqlib import g

        def initialize(context):
            g.security = "601390"
            eqlib.set_benchmark("000300.XSHG")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            eqlib.run_backtest(
                initialize,
                start_date=datetime.date(2024, 1, 2),
                end_date=datetime.date(2024, 1, 5),
                starting_cash=100000,
                frequency="minute",
            )
            minute_warnings = [
                x for x in w
                if issubclass(x.category, UserWarning)
                and "minute mode" in str(x.message).lower()
            ]
            assert len(minute_warnings) >= 1, (
                "Expected a UserWarning about minute mode limitation"
            )
            assert "intraday" in str(minute_warnings[0].message).lower(), (
                "Warning should mention 'intraday' limitation"
            )

    def test_daily_mode_no_minute_warning(self):
        """run_backtest with frequency='daily' should NOT emit the minute warning."""
        import eqlib
        from eqlib import g

        def initialize(context):
            g.security = "601390"
            eqlib.set_benchmark("000300.XSHG")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            eqlib.run_backtest(
                initialize,
                start_date=datetime.date(2024, 1, 2),
                end_date=datetime.date(2024, 1, 5),
                starting_cash=100000,
                frequency="daily",
            )
            minute_warnings = [
                x for x in w
                if issubclass(x.category, UserWarning)
                and "minute mode" in str(x.message).lower()
            ]
            assert len(minute_warnings) == 0, (
                "daily mode should not emit the minute mode warning"
            )

    def test_minute_warning_message_content(self):
        """The warning message should mention next-day open and buffered orders."""
        import eqlib
        from eqlib import g

        def initialize(context):
            g.security = "601390"
            eqlib.set_benchmark("000300.XSHG")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            eqlib.run_backtest(
                initialize,
                start_date=datetime.date(2024, 1, 2),
                end_date=datetime.date(2024, 1, 5),
                starting_cash=100000,
                frequency="minute",
            )
            msg = str([x.message for x in w if issubclass(x.category, UserWarning)])
            assert "next-day" in msg.lower() or "next day" in msg.lower(), (
                "Warning should mention next-day fill behavior"
            )
