"""Local sample-data contract tests (INFRA-P1-05 / audit Top-9).

``data/`` is gitignored, so git ships no price CSVs; a fresh clone relies on
the on-demand path (``save_stock_local`` / ``examples/06_local_data.py``).
These tests pin the contract that path must satisfy:

- anything written by :func:`save_stock_local` is accepted by
  :func:`load_stock_local` (shares-unit sidecar + coverage metadata);
- legacy lot-unit files (no sidecar) are refused on read and *replaced*
  (not merged) on write;
- every sample CSV present in a developer checkout satisfies the loader
  contract (skipped where no samples exist).
"""

import datetime
import json
from pathlib import Path

import pandas as pd
import pytest

import eqlib.data as data
import eqlib.data_cache as data_cache


@pytest.fixture()
def local_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(data_cache, "_LOCAL_DATA_DIR", str(tmp_path))
    return tmp_path


def _shares_frame() -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=5)
    return pd.DataFrame(
        {
            "open": [10.0] * 5,
            "high": [10.5] * 5,
            "low": [9.5] * 5,
            "close": [10.0] * 5,
            "volume": [1_000_000.0] * 5,  # shares, not lots (手)
            "money": [10_000_000.0] * 5,
        },
        index=idx,
    )


def test_save_then_load_roundtrip(local_data_dir, monkeypatch):
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: _shares_frame())

    path = data_cache.save_stock_local("601398")
    assert path is not None

    meta_path = Path(path).with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["volume_unit"] == "shares"

    loaded = data_cache.load_stock_local(
        "601398", "2000-01-01", datetime.date.today()
    )
    assert loaded is not None and not loaded.empty
    assert loaded["volume"].iloc[0] == 1_000_000.0


def test_legacy_lots_file_refused_then_replaced(local_data_dir, monkeypatch):
    csv_path = local_data_dir / "601398_daily_qfq.csv"
    _shares_frame().to_csv(csv_path)  # no sidecar -> legacy lots file

    assert (
        data_cache.load_stock_local("601398", "2000-01-01", datetime.date.today())
        is None
    )

    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: _shares_frame())
    data_cache.save_stock_local("601398")

    meta = data_cache._read_local_csv_metadata(csv_path)
    assert meta is not None and meta.get("volume_unit") == "shares"
    loaded = data_cache.load_stock_local(
        "601398", "2000-01-01", datetime.date.today()
    )
    assert loaded is not None and not loaded.empty


_REPO_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_repo_sample_csvs_satisfy_loader_contract():
    """Every sample CSV in this checkout must be accepted by the loader.

    ``data/`` is gitignored, so fresh clones have no samples and this test
    skips; where samples do exist (developer/CI nodes), each must carry
    shares-unit sidecar metadata and load for its recorded coverage range.
    """
    samples = sorted(_REPO_DATA_DIR.glob("*_daily_qfq.csv"))
    if not samples:
        pytest.skip("no bundled sample CSVs in this checkout (data/ is gitignored)")
    for csv_path in samples:
        code = csv_path.name.split("_")[0]
        meta = data_cache._read_local_csv_metadata(csv_path)
        assert meta is not None and meta.get("volume_unit") == "shares", (
            f"{csv_path.name}: missing shares-unit sidecar metadata"
        )
        loaded = data_cache.load_stock_local(
            code, meta["covered_start"], meta["covered_end"]
        )
        assert loaded is not None and not loaded.empty, (
            f"{csv_path.name}: refused by load_stock_local"
        )
