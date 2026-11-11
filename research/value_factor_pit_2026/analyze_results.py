"""Post-run analysis for the PIT value study: frictionless universe reference.

The equal-weight reference answers "did the factor beat its own pool, or did
the pool beat the index?" It is frictionless and daily-rebalanced — a
diagnostic, not an investable portfolio at 1,000,000 CNY.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research" / "regime_momentum_2026"))

from runner import period_metrics  # noqa: E402


def pit_equal_weight_reference(
    frames: dict[str, pd.DataFrame],
    membership: dict[str, set[str]],
    dates: pd.DatetimeIndex,
) -> pd.Series:
    """Daily-rebalanced mean member return over ``dates`` (frictionless).

    Membership applies from its sample date forward; a member contributes on
    a day when its frame has a computable return there (consecutive rows —
    on this dataset BaoStock pads suspensions with flat volume=0 bars, so
    suspended members contribute 0%; a vendor that omitted those rows would
    silently change the caliber). Delisted names stop contributing after
    their last bar.
    """
    member_dates = sorted(
        (pd.Timestamp(d), set(codes)) for d, codes in membership.items()
    )
    returns = {
        code: frame["close"].astype(float).pct_change()
        for code, frame in frames.items()
    }
    out = {}
    for i in range(1, len(dates)):
        day = dates[i]
        members = None
        for md, codes in member_dates:
            if md <= day:
                members = codes
            else:
                break
        if not members:
            continue
        values = []
        for code in members:
            series = returns.get(code)
            if series is None:
                continue
            value = series.get(day)
            if value is not None and math.isfinite(value):
                values.append(float(value))
        if values:
            out[day] = sum(values) / len(values)
    return pd.Series(out).sort_index()


def yearly_attribution(equity_csv: Path, benchmark: pd.DataFrame,
                       years: range, starting_cash: float) -> list[dict]:
    """Yearly slices of a recorded equity curve via the shared metric caliber."""
    import types

    equity = pd.read_csv(equity_csv)
    shim = {
        "recorded_values": equity.to_dict("list"),
        "context": types.SimpleNamespace(
            portfolio=types.SimpleNamespace(starting_cash=starting_cash)
        ),
    }
    rows = []
    for year in years:
        m = period_metrics(shim, benchmark, f"{year}-01-01", f"{year}-12-31")
        if m is not None:
            rows.append({"year": year, **m})
    return rows
