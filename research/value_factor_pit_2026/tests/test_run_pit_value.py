"""Unit tests for the PIT value runner's pure helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "value_factor_2026"))

from run_pit_value import (  # noqa: E402
    apply_stress,
    ensure_new_destination,
    extract_ohlcv,
)


def test_ensure_new_destination_rejects_existing(tmp_path):
    target = ensure_new_destination(tmp_path, "run_a")
    assert not target.exists()
    target.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="never overwrite"):
        ensure_new_destination(tmp_path, "run_a")


def test_ensure_new_destination_allows_sibling_label_in_same_period(tmp_path):
    used = ensure_new_destination(tmp_path, "validation/pit_value")
    used.mkdir(parents=True)

    free = ensure_new_destination(tmp_path, "validation/pit_value_stress")

    assert not free.exists()


def test_apply_stress_doubles_commission_and_triples_slippage():
    from examples._defaults import DEFAULT_ORDER_COST
    from pit_value_strategy import PITValueConfig

    config, cost = apply_stress(PITValueConfig(), DEFAULT_ORDER_COST)

    assert config.slippage == pytest.approx(0.003)
    assert cost.open_commission == DEFAULT_ORDER_COST.open_commission * 2
    assert cost.close_commission == DEFAULT_ORDER_COST.close_commission * 2
    assert cost.min_commission == DEFAULT_ORDER_COST.min_commission * 2
    assert cost.close_tax == DEFAULT_ORDER_COST.close_tax  # stamp duty untouched


def test_extract_ohlcv_drops_research_only_columns():
    frame = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
         "pe_ttm": 10.0, "pb_mrq": 1.0, "tradestatus": 1, "is_st": 0,
         "code": "600005"},
        index=pd.to_datetime(["2013-01-04"]),
    )

    out = extract_ohlcv(frame)

    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.equals(frame.index)
