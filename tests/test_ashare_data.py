# tests/test_ashare_data.py
"""Tests for A-share market specific data functions."""

import pytest
import pandas as pd
import datetime


class TestNorthMoneyFlow:
    """Tests for get_north_money_flow function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_north_money_flow
        assert get_north_money_flow is not None


class TestMarginData:
    """Tests for get_margin_data function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_margin_data
        assert get_margin_data is not None


class TestLimitUpDownStats:
    """Tests for get_limit_up_down_stats function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_limit_up_down_stats
        assert get_limit_up_down_stats is not None


class TestRestrictionRelease:
    """Tests for get_restriction_release function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_restriction_release
        assert get_restriction_release is not None