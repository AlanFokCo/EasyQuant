"""Minute history must not bypass the daily API's simulation boundary."""
from types import SimpleNamespace

import pandas as pd
import pytest

import eqlib.data as data
import eqlib._state as state


@pytest.fixture
def minute_source(monkeypatch):
    old = state.get_session()
    session = state.BacktestSession()
    session._context = SimpleNamespace(current_dt=pd.Timestamp("2024-01-04 09:30"))
    state._set_session(session)
    bars = pd.DataFrame({"时间": ["2024-01-05 15:00", "2024-01-04 09:25",
                                   "2024-01-04 09:30", "2024-01-04 09:20"],
                         "收盘": [777, 11, 999, 10]})
    monkeypatch.setattr(data.ak, "stock_zh_a_hist_min_em", lambda **kw: bars.copy())
    yield session
    state._set_session(old)


@pytest.mark.parametrize("code", ["601390", ["601390", "000001"]])
def test_current_and_future_minute_bars_are_invisible(minute_source, code):
    result = data.get_price_minute(code, count=1, fields=["close"])
    frames = result.values() if isinstance(result, dict) else [result]
    for frame in frames:
        assert len(frame) == 1 and frame.close.iloc[0] == 11
        assert frame.index[0] == pd.Timestamp("2024-01-04 09:25")


def test_minute_research_without_context_can_read_full_range(minute_source):
    minute_source._context = None
    result = data.get_price_minute("601390", count=1)
    assert result.close.iloc[0] == 777


def test_timezone_aware_context_uses_shanghai_time(minute_source):
    minute_source._context.current_dt = pd.Timestamp("2024-01-04 01:30Z")
    result = data.get_price_minute("601390", count=1)
    assert result.close.iloc[0] == 11


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_minute_count_rejects_invalid_values(minute_source, count):
    with pytest.raises(ValueError, match="count"):
        data.get_price_minute("601390", count=count)


def test_minute_period_is_not_silently_substituted(minute_source):
    with pytest.raises(ValueError, match="period"):
        data.get_price_minute("601390", period="2m")
