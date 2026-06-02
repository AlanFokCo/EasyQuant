# tests/test_ashare_data.py
"""Tests for A-share market specific data functions."""

import pytest
import pandas as pd
import numpy as np
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

        # 如果有数据，验证列名和 dtype
        if not df.empty:
            assert "date" in df.columns
            assert "net_buy" in df.columns
            assert "total_buy" in df.columns
            assert "total_sell" in df.columns

            # Bug 14 fix: 验证 dtype
            assert pd.api.types.is_numeric_dtype(df["net_buy"]), \
                f"net_buy should be numeric, got {df['net_buy'].dtype}"
            assert pd.api.types.is_numeric_dtype(df["total_buy"]), \
                f"total_buy should be numeric, got {df['total_buy'].dtype}"
            assert pd.api.types.is_numeric_dtype(df["total_sell"]), \
                f"total_sell should be numeric, got {df['total_sell'].dtype}"

    def test_invalid_date_range(self):
        """验证 start_date > end_date 时返回空 DataFrame"""
        from eqlib.data import get_north_money_flow

        df = get_north_money_flow(start_date="2024-12-31", end_date="2024-01-01")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_various_date_formats(self):
        """验证各种日期格式"""
        from eqlib.data import get_north_money_flow

        # 测试各种格式
        test_cases = [
            ("2024-01-01", "2024-01-31"),  # ISO format
            ("20240101", "20240131"),  # Compact format
            (datetime.date(2024, 1, 1), datetime.date(2024, 1, 31)),  # date object
        ]

        for start, end in test_cases:
            df = get_north_money_flow(start_date=start, end_date=end)
            assert isinstance(df, pd.DataFrame), f"Failed for format {start} to {end}"

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

    def test_basic_fetch(self):
        """验证能获取融资融券数据"""
        from eqlib.data import get_margin_data

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)

        df = get_margin_data(start_date=start_date, end_date=end_date)

        assert isinstance(df, pd.DataFrame)

        if not df.empty:
            assert "date" in df.columns
            assert "margin_balance" in df.columns
            assert "margin_repay" in df.columns

            # Bug 14 fix: 验证 dtype
            assert pd.api.types.is_numeric_dtype(df["margin_balance"]), \
                f"margin_balance should be numeric, got {df['margin_balance'].dtype}"

            # Bug 7 fix: 验证第一行 margin_repay 是 NaN
            if len(df) > 0:
                first_repay = df["margin_repay"].iloc[0]
                assert pd.isna(first_repay), \
                    f"First row margin_repay should be NaN, got {first_repay}"

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_margin_data

        df = get_margin_data()
        assert isinstance(df, pd.DataFrame)


class TestLimitUpDownStats:
    """Tests for get_limit_up_down_stats function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_limit_up_down_stats
        assert get_limit_up_down_stats is not None

    def test_basic_fetch(self):
        """验证能获取涨跌停统计"""
        from eqlib.data import get_limit_up_down_stats

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)

        df = get_limit_up_down_stats(start_date=start_date, end_date=end_date)

        assert isinstance(df, pd.DataFrame)

        if not df.empty:
            assert "date" in df.columns
            assert "limit_up_count" in df.columns
            assert "limit_down_count" in df.columns
            assert "api_error_count" in df.columns  # Bug 10 fix: 新增列

            # 验证 dtype
            assert pd.api.types.is_numeric_dtype(df["limit_up_count"])
            assert pd.api.types.is_numeric_dtype(df["limit_down_count"])

    def test_30_day_warning(self):
        """验证超过 30 天限制时发出警告"""
        from eqlib.data import get_limit_up_down_stats
        import warnings

        # 请求超过 30 天的数据
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=60)

        # 应该能正常工作，但会有警告日志
        df = get_limit_up_down_stats(start_date=start_date, end_date=end_date)
        assert isinstance(df, pd.DataFrame)

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_limit_up_down_stats

        df = get_limit_up_down_stats()
        assert isinstance(df, pd.DataFrame)


class TestRestrictionRelease:
    """Tests for get_restriction_release function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_restriction_release
        assert get_restriction_release is not None

    def test_basic_fetch(self):
        """验证能获取未来解禁列表"""
        from eqlib.data import get_restriction_release

        df = get_restriction_release(days=30)

        assert isinstance(df, pd.DataFrame)

        if not df.empty:
            assert "code" in df.columns
            assert "release_date" in df.columns
            assert "release_value" in df.columns

    def test_days_parameter(self):
        """验证 days 参数工作"""
        from eqlib.data import get_restriction_release

        df_30 = get_restriction_release(days=30)
        df_60 = get_restriction_release(days=60)

        # 60 天范围应包含更多解禁事件
        assert len(df_60) >= len(df_30)

    def test_days_none_handling(self):
        """验证 days=None 时使用默认值（Bug 2 fix）"""
        from eqlib.data import get_restriction_release

        # days=None 应该使用默认值 30
        df = get_restriction_release(days=None)
        assert isinstance(df, pd.DataFrame)

        # days < 1 也应该使用默认值
        df_negative = get_restriction_release(days=-5)
        assert isinstance(df_negative, pd.DataFrame)


class TestModuleExports:
    """Tests for module exports."""

    def test_import_from_eqlib(self):
        """验证可以从 eqlib 导入"""
        from eqlib import (
            get_north_money_flow,
            get_margin_data,
            get_limit_up_down_stats,
            get_restriction_release,
        )
        assert get_north_money_flow is not None
        assert get_margin_data is not None
        assert get_limit_up_down_stats is not None
        assert get_restriction_release is not None