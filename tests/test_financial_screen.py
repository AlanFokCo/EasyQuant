"""Tests for get_financial_screen ROE / revenue / profit filters.

These parameters were silently ignored before; they must filter on the
latest essentially-complete quarterly report, and the function must fail
closed when that report is unavailable.
"""

from unittest.mock import patch

import pandas as pd
import pytest

import eqlib.data as data_mod


def _spot_df():
    return pd.DataFrame({
        "代码": ["600001", "600002", "600003"],
        "名称": ["甲", "乙", "丙"],
        "最新价": [10.0, 20.0, 30.0],
        "涨跌幅": [1.0, -0.5, 2.0],
        "市盈率-动态": [8.0, 15.0, 30.0],
        "市净率": [0.9, 1.5, 3.0],
        "总市值": [5e10, 8e10, 2e10],
        "换手率": [1.2, 0.8, 3.5],
    })


def _yjbb_df(rows):
    return pd.DataFrame({
        "股票代码": [r[0] for r in rows],
        "净资产收益率": [r[1] for r in rows],
        "营业总收入-营业总收入": [r[2] for r in rows],
        "净利润-净利润": [r[3] for r in rows],
    })


_FULL_REPORT = _yjbb_df(
    [("600001", 12.0, 5e9, 8e8),
     ("600002", 4.0, 2e9, 1e8),
     ("600003", 20.0, 9e9, -3e8)]
    + [(f"9{i:05d}", 8.0, 1e9, 5e7) for i in range(2100)]
)


@pytest.fixture(autouse=True)
def _clear_spot_cache():
    data_mod._spot_cache = None
    yield
    data_mod._spot_cache = None


def test_roe_filter_applies_and_adds_columns():
    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em", return_value=_FULL_REPORT):
        df = data_mod.get_financial_screen(min_roe=10.0)

    assert set(df["code"]) == {"600001", "600003"}
    assert {"roe", "revenue", "profit"} <= set(df.columns)


def test_revenue_and_profit_filters_apply():
    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em", return_value=_FULL_REPORT):
        df = data_mod.get_financial_screen(min_revenue=4e9, min_profit=0)

    # 600003 has negative profit; 600002 revenue below 4e9
    assert list(df["code"]) == ["600001"]


def test_spot_filters_still_combine_with_financial_filters():
    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em", return_value=_FULL_REPORT):
        df = data_mod.get_financial_screen(max_pe=20.0, min_roe=10.0)

    assert list(df["code"]) == ["600001"]


def test_unavailable_report_fails_closed():
    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em", side_effect=RuntimeError("down")):
        df = data_mod.get_financial_screen(min_roe=5.0)

    assert df.empty  # never silently skip requested filters


def test_partial_report_period_falls_back_to_previous():
    partial = _yjbb_df([("600001", 12.0, 5e9, 8e8)])  # mid-disclosure
    calls = []

    def fake_yjbb(date):
        calls.append(date)
        return partial if len(calls) == 1 else _FULL_REPORT

    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em", side_effect=fake_yjbb):
        df = data_mod.get_financial_screen(min_roe=10.0)

    assert len(calls) == 2  # first period rejected as too small
    assert set(df["code"]) == {"600001", "600003"}


def test_no_financial_params_never_touches_report():
    with patch("akshare.stock_zh_a_spot_em", return_value=_spot_df()), \
         patch("akshare.stock_yjbb_em",
               side_effect=AssertionError("should not be called")):
        df = data_mod.get_financial_screen(max_pe=20.0)

    assert set(df["code"]) == {"600001", "600002"}
    assert "roe" not in df.columns
