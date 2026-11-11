"""Freeze point-in-time CSI300 membership and daily BaoStock histories.

Network access is confined to this module's fetch/freeze functions. Evaluation
code reads only the resulting CSV snapshots and verifies their sha256 hashes.

    ~/anaconda3/envs/eqlib-py310/bin/python \
        research/value_factor_pit_2026/baostock_freeze.py
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

START = "2009-01-01"
END = "2015-12-31"
OUT_DIR = Path("data/value_factor_pit")
HISTORY_FIELDS = (
    "date,code,open,high,low,close,volume,peTTM,pbMRQ,tradestatus,isST"
)
BENCHMARK = "000300.XSHG"


def bare_code(code: str) -> str:
    """Convert sh.600000/sz.000001/000300.XSHG forms to six digits."""
    parts = str(code).split(".")
    bare = parts[0] if parts[0].isdigit() else parts[-1]
    if len(bare) != 6 or not bare.isdigit():
        raise ValueError(f"not a six-digit A-share/index code: {code}")
    return bare


def bs_code(code: str) -> str:
    """Convert a bare/suffixed code to BaoStock's exchange-prefixed form."""
    if str(code).startswith(("sh.", "sz.")):
        return str(code)
    if str(code).endswith(".XSHG"):
        return f"sh.{bare_code(code)}"
    bare = bare_code(code)
    return ("sh." if bare.startswith("6") else "sz.") + bare


def collect_rows(result) -> pd.DataFrame:
    """Collect a BaoStock result without coercing provider strings."""
    if result.error_code != "0":
        raise ValueError(f"BaoStock error {result.error_code}: {result.error_msg}")
    rows = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def fetch_with_retry(fetch, attempts: int = 4, base_sleep: float = 2.0,
                     on_retry=None):
    """Retry a BaoStock call on transient failures, re-authenticating via callback.

    BaoStock drops long-lived sessions mid-download (error 10002007). The
    on_retry callback rebuilds the session before the next attempt.
    """
    last = None
    for attempt in range(attempts):
        try:
            return fetch()
        except Exception as exc:  # noqa: BLE001 — provider raises mixed types
            last = exc
            if attempt == attempts - 1:
                raise
            if on_retry is not None:
                on_retry()
            else:
                time.sleep(base_sleep * (2 ** attempt))
    raise last


def _relogin():
    """Rebuild the BaoStock session after a dropped connection."""
    import baostock as bs

    try:
        bs.logout()
    except Exception:  # noqa: BLE001 — a dead session need not log out cleanly
        pass
    time.sleep(1.0)
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock re-login failed: {login.error_msg}")


def fetch_membership(date: str) -> pd.DataFrame:
    """Return CSI300 members effective on ``date`` with bare stock codes."""
    import baostock as bs

    frame = fetch_with_retry(
        lambda: collect_rows(bs.query_hs300_stocks(date=date)),
        on_retry=_relogin,
    )
    if frame.empty:
        raise ValueError(f"empty CSI300 membership for {date}")
    out = pd.DataFrame(
        {"date": pd.Timestamp(date), "code": frame["code"].map(bare_code)}
    )
    if len(out) != 300 or out["code"].nunique() != 300:
        raise ValueError(f"expected 300 unique members for {date}, got {len(out)}")
    return out


def fetch_stock_history(code: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily qfq prices, point-in-time valuation and trading status."""
    import baostock as bs

    frame = fetch_with_retry(
        lambda: collect_rows(
            bs.query_history_k_data_plus(
                bs_code(code), HISTORY_FIELDS, start_date=start, end_date=end,
                frequency="d", adjustflag="2",
            )
        ),
        on_retry=_relogin,
    )
    if frame.empty:
        raise ValueError(f"empty daily history for {code}")
    frame = frame.rename(
        columns={"peTTM": "pe_ttm", "pbMRQ": "pb_mrq", "isST": "is_st"}
    )
    frame["code"] = bare_code(code) if code != BENCHMARK else BENCHMARK
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    numeric = ["open", "high", "low", "close", "volume", "pe_ttm", "pb_mrq"]
    for name in numeric:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    for name in ("tradestatus", "is_st"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce").fillna(0).astype(int)
    frame = frame.set_index("date").sort_index()
    if not frame.index.is_unique:
        raise ValueError(f"duplicate dates for {code}")
    return frame[
        ["code", "open", "high", "low", "close", "volume",
         "pe_ttm", "pb_mrq", "tradestatus", "is_st"]
    ]


def rebalance_calendar(calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Union the independent development/smoke/validation rebalance schedules."""
    dates = set()
    for start in ("2010-01-04", "2012-01-04", "2013-01-04"):
        phase = calendar[
            (calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(END))
        ]
        dates.update(phase[::20])
    return pd.DatetimeIndex(sorted(dates))


def read_membership_file(path: Path) -> set[str]:
    """Read a frozen membership CSV, preserving zero-padded codes."""
    frame = pd.read_csv(path, dtype={"code": str})
    codes = set(frame["code"])
    bad = [c for c in codes if len(c) != 6 or not c.isdigit()]
    if bad:
        raise ValueError(f"membership codes must be six-digit strings: {bad[:3]}")
    return codes


def load_manifest(directory: Path) -> dict:
    """Load the freeze manifest and reject missing or changed files."""
    directory = Path(directory)
    path = directory / "manifest.json"
    if not path.is_file():
        raise ValueError(f"missing manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for relative, info in manifest["files"].items():
        target = directory / relative
        if not target.is_file():
            raise ValueError(f"missing frozen file: {target}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != info["sha256"]:
            raise ValueError(f"sha256 mismatch: {target}")
    return manifest


def _write_snapshot(directory: Path, relative: str, frame: pd.DataFrame,
                    files: dict) -> None:
    path = directory / relative
    frame.to_csv(path, float_format="%.10f")
    files[relative] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": int(len(frame)),
        "first": str(frame.index.min().date()),
        "last": str(frame.index.max().date()),
    }


def freeze_dataset(directory: Path = OUT_DIR) -> dict:
    """Fetch and freeze all gate inputs, resuming from existing CSVs."""
    import baostock as bs

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(login.error_msg)
    files: dict = {}
    try:
        benchmark_path = directory / f"{BENCHMARK}_daily_qfq.csv"
        if benchmark_path.exists():
            benchmark = pd.read_csv(benchmark_path, index_col=0, parse_dates=True)
        else:
            benchmark = fetch_stock_history(BENCHMARK, START, END)
        calendar = benchmark.index
        rebalance_dates = rebalance_calendar(calendar)

        membership = {}
        unique_codes = set()
        for i, date in enumerate(rebalance_dates, 1):
            relative = f"membership_{date.date().isoformat()}.csv"
            path = directory / relative
            if path.exists():
                codes = read_membership_file(path)
            else:
                frame = fetch_membership(str(date.date()))
                frame.to_csv(path, index=False)
                codes = set(frame["code"])
                time.sleep(0.15)
            membership[date.date().isoformat()] = sorted(codes)
            unique_codes.update(codes)
            if i % 12 == 0:
                print(f"membership {i}/{len(rebalance_dates)}; names={len(unique_codes)}")

        for i, code in enumerate(sorted(unique_codes | {BENCHMARK}), 1):
            relative = f"{code}_daily_qfq.csv"
            path = directory / relative
            if path.exists():
                frame = pd.read_csv(path, index_col=0, parse_dates=True)
            else:
                frame = fetch_stock_history(code, START, END)
                time.sleep(0.15)
            _write_snapshot(directory, relative, frame, files)
            if i % 25 == 0:
                print(f"history {i}/{len(unique_codes) + 1}")

        for relative in [f"membership_{d}.csv" for d in membership]:
            path = directory / relative
            frame = pd.read_csv(path)
            files[relative] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": int(len(frame)),
            }
        manifest = {
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "BaoStock query_hs300_stocks + query_history_k_data_plus",
            "start": START,
            "end": END,
            "adjust": "BaoStock adjustflag=2 (qfq)",
            "benchmark": BENCHMARK,
            "rebalance_dates": list(membership),
            "members": membership,
            "files": files,
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return manifest
    finally:
        bs.logout()


def main() -> int:
    manifest = freeze_dataset()
    print(f"froze {len(manifest['files'])} files, "
          f"{len(manifest['rebalance_dates'])} rebalance dates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
