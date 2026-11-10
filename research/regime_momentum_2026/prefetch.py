"""Warm the eqlib disk cache for the research universe.

Fetches 2022-01-01 .. today for every name plus the CSI300 benchmark, then
reports coverage so broken/short codes are caught *before* any backtest runs
(CLAUDE.md workflow rule 6: "Stop if data download fails").

Run:
    python research/regime_momentum_2026/prefetch.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from universe import BENCHMARK, UNIVERSE  # noqa: E402

START = "2022-01-01"
END = "2026-10-27"


def main() -> int:
    from eqlib.data_cache import fetch_cached
    from eqlib.data import get_price

    targets = list(UNIVERSE)
    rows = []
    failures = []
    t0 = time.time()

    for i, code in enumerate(targets, 1):
        t = time.time()
        try:
            df = fetch_cached(code, START, END, adjust="qfq")
        except Exception as exc:  # noqa: BLE001
            failures.append((code, f"{type(exc).__name__}: {exc}"))
            print(f"[{i:2d}/{len(targets)}] {code}  FAILED {type(exc).__name__}")
            continue
        if df is None or len(df) == 0:
            failures.append((code, "empty frame"))
            print(f"[{i:2d}/{len(targets)}] {code}  EMPTY")
            continue
        rows.append({
            "code": code,
            "n": len(df),
            "first": str(df.index[0].date()),
            "last": str(df.index[-1].date()),
            "secs": round(time.time() - t, 1),
        })
        print(f"[{i:2d}/{len(targets)}] {code}  {len(df):5d} rows  "
              f"{rows[-1]['first']} .. {rows[-1]['last']}  ({rows[-1]['secs']}s)")

    # Benchmark index
    try:
        idx = get_price(BENCHMARK, start_date=START, end_date=END)
        print(f"\nbenchmark {BENCHMARK}: {len(idx)} rows "
              f"{idx.index[0].date()} .. {idx.index[-1].date()}")
    except Exception as exc:  # noqa: BLE001
        failures.append((BENCHMARK, f"{type(exc).__name__}: {exc}"))
        print(f"\nbenchmark {BENCHMARK} FAILED: {type(exc).__name__}: {exc}")

    print(f"\ntotal {time.time() - t0:.1f}s  ok={len(rows)}  failed={len(failures)}")

    # Coverage gate: every name must start on/before 2022-06-30 (so a 200d MA
    # is available at the 2023-01-01 in-sample start) and end on/after END.
    short = [r for r in rows if r["first"] > "2022-06-30" or r["last"] < END]
    if short:
        print("\n!! insufficient coverage:")
        for r in short:
            print(f"   {r['code']}  {r['first']} .. {r['last']}")
    if failures:
        print("\n!! failures:")
        for code, why in failures:
            print(f"   {code}: {why}")
        return 1
    if short:
        return 1
    print("\ncoverage gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
