"""Offline regressions for simulation visibility and data ownership contracts."""
import datetime as dt
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from eqlib import _state
from eqlib import data
from eqlib.data_cache import PreloadedData


@pytest.fixture(autouse=True)
def isolated_session():
    previous = _state.get_session()
    session = _state.BacktestSession()
    _state._set_session(session)
    data.clear_cache()
    yield session
    data.clear_cache()
    _state._set_session(previous)


@pytest.fixture
def bars():
    return pd.DataFrame(
        {"open": [10., 11., 12., 13.], "close": [10., 11., 999., 777.],
         "high": [11., 12., 1000., 800.], "low": [9., 10., 11., 12.],
         "volume": [10000.] * 4},
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
    )


def test_simulation_future_prices_cannot_change_visible_history(
    monkeypatch, isolated_session, bars
):
    isolated_session._context = SimpleNamespace(current_dt=dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: bars.copy())
    before = data.get_price("601390", "2024-01-02", "2024-01-05", count=1)
    bars.loc["2024-01-04":, "close"] = -100000
    after = data.get_price("601390", "2024-01-02", "2024-01-05", count=1)
    pd.testing.assert_frame_equal(before, after)
    assert before.index.tolist() == [pd.Timestamp("2024-01-03")]
    assert before.close.tolist() == [11.]
    assert data.get_price("601390", "2024-01-04", "2024-01-05").empty


def test_research_range_and_string_end_date_count(monkeypatch, bars):
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: bars.copy())
    got = data.get_price("601390", end_date="2024-01-05", count=np.int64(2))
    assert got.index.tolist() == [pd.Timestamp("2024-01-04"), pd.Timestamp("2024-01-05")]
    got = data.get_price("601390", "20240102", "2024-01-04", count=1)
    assert got.close.tolist() == [999.]


def test_exchange_timezone_cutoff_and_multi_security(monkeypatch, isolated_session, bars):
    isolated_session._context = SimpleNamespace(current_dt=pd.Timestamp("2024-01-04T01:30:00Z"))
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: bars.copy())
    result = data.get_price(["601390", "600519"], count=1)
    assert set(result) == {"601390", "600519"}
    assert all(frame.close.tolist() == [11.] for frame in result.values())


@pytest.mark.parametrize("count", [0, -1, 1.5, "1", True, np.nan])
def test_invalid_count_fails_before_fetch(monkeypatch, count):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid arguments must not fetch data")
    monkeypatch.setattr(data, "fetch_stock_data", forbidden)
    with pytest.raises(ValueError, match="positive integer"):
        data.get_price("601390", count=count)


@pytest.mark.parametrize("frequency", ["1m", "5m", "weekly"])
def test_unsupported_frequency_never_returns_daily_data(monkeypatch, frequency):
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: pytest.fail("unexpected daily fetch"))
    with pytest.raises(NotImplementedError, match="daily/1d"):
        data.get_price("601390", frequency=frequency)


def test_invalid_date_range(monkeypatch):
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: pytest.fail("unexpected fetch"))
    with pytest.raises(ValueError, match="start_date"):
        data.get_price("601390", "2024-01-05", "2024-01-02")


@pytest.mark.parametrize("security", ["601390", "000300.XSHG"])
def test_cold_and_warm_fetches_cannot_poison_cached_prices(monkeypatch, bars, security):
    monkeypatch.setattr(data, "_DATA_FETCHERS", [("sina", lambda *a: bars.copy())])
    monkeypatch.setattr(data.ak, "stock_zh_index_daily_em", lambda **k: bars.copy())
    for _ in range(3):
        result = data.fetch_stock_data(security, "2024-01-02", "2024-01-05")
        assert result.loc["2024-01-03", "close"] == 11.
        result.loc["2024-01-03", "close"] = -12345.


def test_spot_cache_returns_owned_frames(monkeypatch):
    monkeypatch.setattr(data.ak, "stock_zh_a_spot_em", lambda: pd.DataFrame({"最新价": [12.]}))
    first = data._get_spot_data()
    first.iloc[0, 0] = -1.
    second = data._get_spot_data()
    assert second.iloc[0, 0] == 12.
    second.iloc[0, 0] = -2.
    assert data._get_spot_data().iloc[0, 0] == 12.


def test_empty_preload_does_not_block_raw_network_history(monkeypatch, isolated_session, bars):
    isolated_session._context = SimpleNamespace(current_dt=dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr("eqlib.engine._get_preloaded", lambda: PreloadedData())
    seen = []
    def fetch(*args, **kwargs):
        seen.append(kwargs["adjust"])
        return bars.copy()
    monkeypatch.setattr(data, "fetch_stock_data", fetch)
    result = data.attribute_history("601390", 1, fq=None)
    assert seen == [""] and result.close.tolist() == [11.]


@pytest.mark.parametrize("panel_only", [False, True])
def test_raw_history_cannot_be_mislabeled_from_qfq_preload(
    monkeypatch, isolated_session, bars, panel_only
):
    isolated_session._context = SimpleNamespace(current_dt=dt.datetime(2024, 1, 4, 9, 30))
    preload = PreloadedData()
    if panel_only:
        preload.panel = pd.concat({"601390": bars}, axis=1)
    else:
        preload._field_series = {"601390": {col: bars[col] for col in bars}}
    monkeypatch.setattr("eqlib.engine._get_preloaded", lambda: preload)
    with pytest.raises(ValueError, match="does not match preloaded"):
        data.attribute_history("601390", 1, fq=None)
    assert data.attribute_history("601390", 1, fq="pre").close.tolist() == [11.]
    # A preload explicitly loaded without adjustment does support raw queries.
    preload.load_stats["adjust"] = ""
    assert data.attribute_history("601390", 1, fq=None).close.tolist() == [11.]
    with pytest.raises(ValueError, match="does not match preloaded"):
        data.attribute_history("601390", 1, fq="pre")


def test_network_history_requests_actual_raw_adjustment(monkeypatch, isolated_session, bars):
    isolated_session._context = SimpleNamespace(current_dt=dt.datetime(2024, 1, 4))
    monkeypatch.setattr("eqlib.engine._get_preloaded", lambda: None)
    requested = []
    def fetch(*args, adjust):
        requested.append(adjust)
        return bars.copy()
    monkeypatch.setattr(data, "fetch_stock_data", fetch)
    assert data.attribute_history("601390", 1, fq=None).close.tolist() == [11.]
    assert requested == [""]


@pytest.mark.parametrize("panel_only", [False, True])
def test_preloaded_results_cannot_modify_future_reads(bars, panel_only):
    preload = PreloadedData()
    preload._indicators = {"601390": pd.DataFrame({"rsi": [40., 50.]}, index=bars.index[:2])}
    preload._close_matrix = pd.DataFrame({"601390": bars.close})
    if panel_only:
        preload.panel = pd.concat({"601390": bars}, axis=1)
    else:
        preload._field_series = {"601390": {col: bars[col] for col in bars}}
    history = preload.get_history("601390", 2, ["close"], None)
    history.iloc[-1, 0] = -12345.
    assert preload.get_history("601390", 2, ["close"], None).iloc[-1, 0] == 777.
    indicators = preload.get_indicators("601390", 1, None)
    indicators.iloc[-1, 0] = -12345.
    assert preload.get_indicators("601390", 1, None).iloc[-1, 0] == 50.
    close = preload.get_close_series("601390")
    close.iloc[-1] = -12345.
    assert preload.get_close_series("601390").iloc[-1] == 777.
