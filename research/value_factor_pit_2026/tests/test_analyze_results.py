"""Unit tests for the PIT equal-weight reference and attribution."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_results import pit_equal_weight_reference  # noqa: E402


def _closes(closes, start="2013-01-02"):
    return pd.DataFrame(
        {"close": closes}, index=pd.date_range(start, periods=len(closes))
    )


def test_reference_is_member_only_and_delisting_aware():
    frames = {
        # stays a member throughout: +1%/day
        "600001": _closes([10 * (1.01 ** i) for i in range(6)]),
        # member only from day 3: +2%/day
        "600002": _closes([20 * (1.02 ** i) for i in range(6)]),
        # removed member: data stops at day 3 (delisted)
        "600003": _closes([30, 30.6, 29.0]),
    }
    membership = {
        "2013-01-02": {"600001", "600003"},
        "2013-01-04": {"600001", "600002"},
    }
    dates = frames["600001"].index

    ref = pit_equal_weight_reference(frames, membership, dates)

    assert len(ref) == len(dates) - 1  # returns from day 2 onward
    # day 2: 600001 +1%, 600003 +2% -> mean +1.5%
    assert abs(ref.iloc[0] - 0.015) < 1e-12
    # day 4: membership switched to {600001, 600002}; both listed and trading,
    # so the reference is mean(+1%, +2%) = +1.5%; removed 600003 contributes
    # nothing (no longer a member; its data also stops).
    assert abs(ref.iloc[2] - 0.015) < 1e-12


def test_reference_never_uses_prices_after_delisting():
    frames = {
        "600001": _closes([10, 10.1, 10.2, 10.3]),
        "600003": _closes([30, 33.0, 36.3]),  # delisted after day 3
    }
    membership = {"2013-01-02": {"600001", "600003"}}
    dates = frames["600001"].index

    ref = pit_equal_weight_reference(frames, membership, dates)

    # day 4 (index 3 -> return at position 2): 600003 has no bar, excluded
    assert abs(ref.iloc[2] - (10.3 / 10.2 - 1)) < 1e-12
