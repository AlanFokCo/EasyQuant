"""Freeze PE(TTM)/PB valuation history for the research pool (network step).

Downloads Baidu sampled valuation series per name, writes raw CSVs to
``data/value_factor/`` and a sha256 manifest. This is the only networked step;
evaluation runs read the frozen snapshots and assert against network access.

    python research/value_factor_2026/prefetch_valuation.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "research" / "regime_momentum_2026")):
    if path not in sys.path:
        sys.path.insert(0, path)

from universe import UNIVERSE  # noqa: E402

OUT_DIR = Path("data/value_factor")
INDICATORS = {"pe_ttm": "市盈率(TTM)", "pb": "市净率"}


def main() -> int:
    import akshare as ak

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "akshare stock_zh_valuation_baidu (Baidu, sampled)",
                "indicators": INDICATORS, "files": {}}
    failures = []
    for code in UNIVERSE:
        entry = {}
        for key, indicator in INDICATORS.items():
            try:
                frame = ak.stock_zh_valuation_baidu(
                    symbol=code, indicator=indicator, period="全部"
                )
            except Exception as exc:  # noqa: BLE001 — record and continue
                print(f"FAIL {code} {key}: {type(exc).__name__} {exc}")
                failures.append((code, key))
                continue
            frame = frame.rename(columns={"date": "date", "value": key})
            frame["date"] = pd.to_datetime(frame["date"])
            frame = frame.set_index("date").sort_index()
            frame = frame[~frame.index.duplicated(keep="last")]
            path = OUT_DIR / f"{code}_{key}.csv"
            frame.to_csv(path)
            entry[key] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": int(len(frame)),
                "first": str(frame.index.min().date()),
                "last": str(frame.index.max().date()),
            }
            print(f"OK   {code} {key}: {entry[key]['rows']} rows "
                  f"{entry[key]['first']}..{entry[key]['last']}")
            time.sleep(0.4)  # politeness; this is the only networked step
        manifest["files"][code] = entry
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        print(f"\n{len(failures)} failures: {failures}")
        return 1
    print(f"\n{len(UNIVERSE)} names × {len(INDICATORS)} indicators frozen to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
