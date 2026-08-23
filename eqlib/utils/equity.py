"""Validated equity-curve helpers shared by portfolio risk calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


def normalize_recorded_values(
    recorded_values: Mapping | Sequence[Mapping],
) -> pd.Series:
    """Return a sorted, finite, positive total-value series from recorded values."""
    if isinstance(recorded_values, Mapping):
        rows = recorded_values.items()
    else:
        rows = ((row["date"], row) for row in recorded_values)

    values: dict[pd.Timestamp, float] = {}
    for date, payload in rows:
        timestamp = pd.Timestamp(date)
        if timestamp in values:
            raise ValueError("recorded_values must contain unique dates")
        try:
            value = float(payload["total_value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("recorded_values must contain total_value") from exc
        values[timestamp] = value

    series = pd.Series(values, dtype=float).sort_index()
    if (
        series.empty
        or not series.index.is_unique
        or not np.isfinite(series.to_numpy()).all()
        or (series <= 0).any()
    ):
        raise ValueError(
            "recorded_values must contain unique, finite, positive total_value observations"
        )
    return series


def daily_returns(recorded_values: Mapping | Sequence[Mapping]) -> pd.Series:
    """Return finite daily returns without silently filling missing observations."""
    return (
        normalize_recorded_values(recorded_values).pct_change(fill_method=None).dropna()
    )
