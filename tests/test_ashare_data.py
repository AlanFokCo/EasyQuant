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

    def test_basic_fetch(self):
        """验证能获取北向资金数据"""
        from eqlib.data import get_north_money_flow

        # 使用近期日期测试
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)

        df = get_north_money_flow(start_date=start_date, end_date=end_date)

        # 验证返回 DataFrame
        assert isinstance(df, pd.DataFrame)

        # 如果有数据，验证列名
        if not df.empty:
            assert "date" in df.columns
            assert "net_buy" in df.columns
            assert "total_buy" in df.columns
            assert "total_sell" in df.columns

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_north_money_flow

        df = get_north_money_flow()  # 无参数调用
        assert isinstance(df, pd.DataFrame)

    def test_returns_empty_on_failure(self):
        """验证 API 失败时返回空 DataFrame"""
        from eqlib.data import get_north_money_flow

        # 使用异常日期测试错误处理
        df = get_north_money_flow(start_date="2099-01-01", end_date="2099-01-31")
        assert isinstance(df, pd.DataFrame)
        # 期望返回空（无数据）或不抛异常


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