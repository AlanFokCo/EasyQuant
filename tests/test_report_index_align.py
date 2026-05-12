"""Tests for HTML benchmark index alignment (no network)."""

import datetime

import pandas as pd
import pytest

from eqlib.report import _align_index_close_to_times, attach_chart_dual_indices


def test_align_index_ffill_before_first_bar():
    """When the index frame starts after the first strategy date, ffill still yields a line."""
    idx = pd.date_range("2023-01-10", periods=5, freq="B")
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
    target = ["2023-01-03", "2023-01-10", "2023-01-12"]
    out = _align_index_close_to_times(target, df)
    assert len(out) == 3
    assert out[0]["time"] == "2023-01-03"
    assert out[0]["value"] == pytest.approx(0.0)
    assert out[1]["value"] == pytest.approx(0.0)
    assert out[2]["value"] == pytest.approx((102.0 / 100.0 - 1.0) * 100.0)


def test_align_index_empty_df():
    assert _align_index_close_to_times(["2023-01-03"], pd.DataFrame()) == []


def test_attach_chart_dual_indices_uses_build_return_series(monkeypatch):
    """attach_chart_dual_indices should align to cumulative-return time keys."""

    class _Pf:
        starting_cash = 100000.0

    class _Ctx:
        start_date = datetime.date(2023, 1, 2)
        end_date = datetime.date(2023, 1, 20)
        portfolio = _Pf()

    idx = pd.date_range("2023-01-02", periods=10, freq="B")
    sample = pd.DataFrame({"close": [4000.0 + i for i in range(10)]}, index=idx)

    def fake_fetch(code, start, end, adjust="qfq"):
        return sample.copy()

    import eqlib.report as rep

    monkeypatch.setattr(rep, "fetch_stock_data", fake_fetch)

    recorded = [
        {"date": datetime.date(2023, 1, 2), "total_value": 100000.0},
        {"date": datetime.date(2023, 1, 5), "total_value": 101000.0},
    ]
    result = {"context": _Ctx(), "recorded_values": recorded}
    attach_chart_dual_indices(result)
    hs = result["chart_index_hs300"]
    sse = result["chart_index_sse"]
    assert len(hs) == 2 and len(sse) == 2
    assert hs[0]["time"] == "2023-01-02" and hs[0]["value"] == pytest.approx(0.0)
    assert sse[1]["time"] == "2023-01-05"
