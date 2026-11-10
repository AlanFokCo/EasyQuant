"""Freeze the research inputs to immutable CSV snapshots.

Reads the eqlib disk cache warmed by ``prefetch.py`` (no new downloads unless
the cache misses) and writes one qfq CSV per name plus the CSI300 benchmark
into ``data/regime_momentum/``. A sha256 manifest is written alongside so every
later run can prove it consumed the same bytes.

Run once, before any evaluation:
    python research/regime_momentum_2026/freeze_inputs.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from universe import BENCHMARK, UNIVERSE  # noqa: E402

START = "2022-01-01"
END = "2026-10-27"
FIELDS = ("open", "high", "low", "close", "volume")
DEFAULT_DIR = Path("data/regime_momentum")


def freeze(directory: Path = DEFAULT_DIR) -> dict:
    """Write frozen snapshots and return the sha256 manifest."""
    from eqlib.data import get_price
    from eqlib.data_cache import fetch_cached

    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    targets = list(UNIVERSE) + [BENCHMARK]

    for code in targets:
        if code == BENCHMARK:
            frame = get_price(code, start_date=START, end_date=END)
        else:
            frame = fetch_cached(code, START, END, adjust="qfq")
        if frame is None or frame.empty:
            raise ValueError(f"no data for {code}; run prefetch.py first")
        frame = frame.loc[:, list(FIELDS)].astype(float)
        if frame.isna().any().any():
            raise ValueError(f"non-finite OHLCV in {code}")
        if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
            raise ValueError(f"unordered or duplicate dates in {code}")
        index = pd.DatetimeIndex(frame.index).normalize()
        frame.index = index
        frame.index.name = "date"
        path = directory / f"{code}_daily_qfq.csv"
        frame.to_csv(path, float_format="%.6f")
        raw = path.read_bytes()
        manifest[code] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": int(len(frame)),
            "first": str(index.min().date()),
            "last": str(index.max().date()),
        }

    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "start": START,
                "end": END,
                "adjust": "qfq",
                "benchmark": BENCHMARK,
                "sources": len(UNIVERSE),
                "files": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    manifest = freeze()
    rows = {code: info["rows"] for code, info in manifest.items()}
    shortest = min(rows.values())
    print(f"froze {len(manifest)} snapshots to data/regime_momentum/")
    print(f"rows: min={shortest} max={max(rows.values())}")
    print(f"benchmark {BENCHMARK}: {rows[BENCHMARK]} rows")
    if len(manifest) != len(UNIVERSE) + 1:
        print("!! snapshot count mismatch")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
