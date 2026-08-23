"""Recorded-value normalization contracts used by portfolio risk checks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eqlib.utils.equity import daily_returns, normalize_recorded_values


def test_normalize_recorded_values_sorts_mapping_dates_and_preserves_values():
    values = {
        "2024-01-03": {"total_value": 110.0},
        "2024-01-02": {"total_value": 100.0},
    }

    result = normalize_recorded_values(values)

    assert result.index.tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
    assert result.tolist() == [100.0, 110.0]
    assert daily_returns(values).tolist() == pytest.approx([0.1])


@pytest.mark.parametrize("value", [0.0, -1.0, np.inf])
def test_normalize_recorded_values_rejects_nonpositive_or_nonfinite_values(value):
    with pytest.raises(ValueError, match="total_value"):
        normalize_recorded_values({"2024-01-02": {"total_value": value}})
