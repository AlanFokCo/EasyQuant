"""Unit tests for the BaoStock point-in-time data adapter."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baostock_freeze import (
    bare_code,
    collect_rows,
    fetch_with_retry,
    load_manifest,
    read_membership_file,
    rebalance_calendar,
)


class _Result:
    def __init__(self, fields, rows):
        self.fields = fields
        self._rows = iter(rows)
        self.error_code = "0"

    def next(self):
        try:
            self._row = next(self._rows)
            return True
        except StopIteration:
            return False

    def get_row_data(self):
        return self._row


def test_collect_rows_preserves_provider_strings():
    result = _Result(
        ["date", "code", "peTTM", "tradestatus"],
        [["2013-01-04", "sh.600005", "-125.487570", "1"]],
    )

    frame = collect_rows(result)

    assert isinstance(frame, pd.DataFrame)
    assert frame.iloc[0].to_dict() == {
        "date": "2013-01-04",
        "code": "sh.600005",
        "peTTM": "-125.487570",
        "tradestatus": "1",
    }
    assert str(frame["date"].dtype) == "object"


def test_bare_code_preserves_leading_zeroes():
    assert bare_code("sz.000001") == "000001"
    assert bare_code("sh.600005") == "600005"


def test_bare_code_accepts_suffixed_index_code():
    assert bare_code("000300.XSHG") == "000300"


def test_fetch_with_retry_succeeds_after_transient_failures():
    calls = []
    relogins = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("BaoStock error 10002007: network")
        return "ok"

    out = fetch_with_retry(
        flaky, attempts=4, base_sleep=0, on_retry=lambda: relogins.append(1)
    )

    assert out == "ok"
    assert len(calls) == 3
    assert len(relogins) == 2


def test_fetch_with_retry_raises_after_exhaustion():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("BaoStock error 10002007: network")

    with pytest.raises(ValueError, match="10002007"):
        fetch_with_retry(always_fails, attempts=3, base_sleep=0)

    assert len(calls) == 3


def test_read_membership_file_preserves_leading_zero_codes(tmp_path):
    path = tmp_path / "membership_2013-01-04.csv"
    path.write_text(
        "date,code\n2013-01-04,000001\n2013-01-04,600005\n", encoding="utf-8"
    )

    codes = read_membership_file(path)

    assert codes == {"000001", "600005"}


def test_read_membership_file_rejects_malformed_codes(tmp_path):
    path = tmp_path / "membership_2013-01-04.csv"
    path.write_text("date,code\n2013-01-04,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="six-digit"):
        read_membership_file(path)


def test_rebalance_calendar_covers_each_phase_schedule():
    calendar = pd.to_datetime(
        ["2010-01-04", "2012-01-04", "2013-01-04", "2013-02-01", "2015-12-31"]
    )

    dates = rebalance_calendar(calendar)

    assert {"2010-01-04", "2012-01-04", "2013-01-04"} <= {
        str(d.date()) for d in dates
    }
    assert dates.is_unique
    assert dates.is_monotonic_increasing


def test_load_manifest_accepts_matching_file(tmp_path):
    data = tmp_path / "x.csv"
    data.write_text("date,close\n2013-01-04,2.77\n", encoding="utf-8")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"files": {"x.csv": {"sha256": digest}}}), encoding="utf-8"
    )

    manifest = load_manifest(tmp_path)

    assert manifest["files"]["x.csv"]["sha256"] == digest


def test_load_manifest_rejects_changed_bytes(tmp_path):
    data = tmp_path / "x.csv"
    data.write_text("original", encoding="utf-8")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"files": {"x.csv": {"sha256": digest}}}), encoding="utf-8"
    )
    data.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_manifest(tmp_path)


def test_load_manifest_rejects_missing_file(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"files": {"missing.csv": {"sha256": "0" * 64}}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing frozen file"):
        load_manifest(tmp_path)
