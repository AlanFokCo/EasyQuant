"""Freeze extended price history for the pool (network step, run once).

Fetches 2015-01-01 .. 2026-10-27 qfq daily bars for the 44-name pool plus
CSI300 and writes immutable CSV snapshots to ``data/value_pool_prices/`` with
a sha256 manifest. Late-IPO names are allowed — their first date is recorded
and the strategy admits them once history suffices. The prior freeze under
``data/regime_momentum/`` is NOT touched; old evidence hashes stay valid.

    python research/value_sector_cap_2026/prefetch_prices.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "research" / "regime_momentum_2026")):
    if path not in sys.path:
        sys.path.insert(0, path)

from universe import BENCHMARK, UNIVERSE  # noqa: E402

START = "2015-01-01"
END = "2026-10-27"          # same terminal date as the prior freeze
FIELDS = ("open", "high", "low", "close", "volume")
OUT_DIR = Path("data/value_pool_prices")


def main() -> int:
    from eqlib.data import get_price
    from eqlib.data_cache import fetch_cached

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    failures: list[str] = []
    for i, code in enumerate(list(UNIVERSE) + [BENCHMARK], 1):
        try:
            frame = (
                get_price(code, start_date=START, end_date=END)
                if code == BENCHMARK
                else fetch_cached(code, START, END, adjust="qfq")
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{code}: {type(exc).__name__}: {exc}")
            print(f"[{i:2d}/45] {code} FAILED {type(exc).__name__}")
            continue
        if frame is None or frame.empty:
            failures.append(f"{code}: empty frame")
            print(f"[{i:2d}/45] {code} EMPTY")
            continue
        frame = frame.loc[:, list(FIELDS)].astype(float)
        if frame.isna().any().any():
            failures.append(f"{code}: non-finite OHLCV")
            continue
        if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
            failures.append(f"{code}: unordered/duplicate dates")
            continue
        index = pd.DatetimeIndex(frame.index).normalize()
        frame.index = index
        frame.index.name = "date"
        path = OUT_DIR / f"{code}_daily_qfq.csv"
        frame.to_csv(path, float_format="%.6f")
        manifest[code] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": int(len(frame)),
            "first": str(index.min().date()),
            "last": str(index.max().date()),
        }
        print(f"[{i:2d}/45] {code} {len(frame):5d} rows "
              f"{manifest[code]['first']} .. {manifest[code]['last']}")
        time.sleep(0.3)  # politeness; this is the only networked step

    (OUT_DIR / "manifest.json").write_text(
        json.dumps({"start": START, "end": END, "adjust": "qfq",
                    "benchmark": BENCHMARK, "files": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    late = {c: m["first"] for c, m in manifest.items()
            if m["first"] > "2015-06-01"}
    if late:
        print("\nlate-starting names (admitted once history suffices):")
        for code, first in sorted(late.items(), key=lambda x: x[1]):
            print(f"   {code}: {first}")
    if failures:
        print(f"\n!! failures: {failures}")
        return 1
    if any(m["last"] < END for m in manifest.values()):
        print("\n!! some series end before the terminal date")
        return 1
    print(f"\ncoverage gate PASSED: {len(manifest)} snapshots frozen to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
