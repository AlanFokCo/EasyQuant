"""Frozen provider payload contracts for daily OHLCV fallbacks."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import eqlib.data as data_mod


_FIXTURE = Path(__file__).parent / "fixtures" / "data_sources" / "tencent_qfqday.json"
TENCENT_PAYLOAD = json.loads(_FIXTURE.read_text(encoding="utf-8"))


class _FakeResponse:
    def json(self):
        return TENCENT_PAYLOAD


def _valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [7.24],
            "high": [7.27],
            "low": [7.14],
            "close": [7.17],
            "volume": [1234.0],
            "money": [783_771_200.0],
        },
        index=pd.DatetimeIndex(["2024-01-10"]),
    )


def test_tencent_adapter_keeps_yuan_prices_and_strictly_slices_requested_range(
    monkeypatch,
):
    monkeypatch.setattr(
        data_mod.requests, "get", lambda *args, **kwargs: _FakeResponse()
    )
    # The adapter returns a standardized raw frame; canonicalisation (range
    # slicing, validation, lots→shares volume) happens exactly once in
    # fetch_stock_data, so exercise the contract through the full chain.
    monkeypatch.setattr(
        data_mod, "_DATA_FETCHERS", [("tencent", data_mod._fetch_from_tencent)]
    )
    data_mod._cache.clear()

    frame = data_mod.fetch_stock_data("000001", "20240102", "20240110", "qfq")

    assert frame.index.min() >= pd.Timestamp("2024-01-02")
    assert frame.index.max() <= pd.Timestamp("2024-01-10")
    assert frame.loc[pd.Timestamp("2024-01-10"), "open"] == pytest.approx(7.24)
    assert frame.loc[pd.Timestamp("2024-01-10"), "money"] == pytest.approx(
        783_771_200.0
    )
    # 1234 lots → 123,400 shares, converted exactly once.
    assert frame.loc[pd.Timestamp("2024-01-10"), "volume"] == pytest.approx(123_400.0)


@pytest.mark.parametrize(
    "column,value",
    [
        ("volume", -1.0),
        ("open", 12.0),
        ("money", float("inf")),
    ],
)
def test_validate_ohlcv_rejects_invalid_market_structure(column, value):
    frame = _valid_frame()
    frame.loc[frame.index[0], column] = value

    assert not data_mod._validate_ohlcv(frame, "fixture")
