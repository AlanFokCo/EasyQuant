"""Tests for preload diagnostics used to assess backtest reliability."""

import datetime as dt
import json
from types import SimpleNamespace

import pandas as pd

from eqlib.data_cache import PreloadedData
from eqlib.report import generate_report_json


def _sample_frame(start="2024-01-02", periods=4):
    idx = pd.date_range(start, periods=periods, freq="B")
    return pd.DataFrame(
        {
            "open": [10.0, 10.2, 10.1, 10.4],
            "high": [10.3, 10.4, 10.5, 10.6],
            "low": [9.9, 10.0, 10.0, 10.2],
            "close": [10.1, 10.3, 10.2, 10.5],
            "volume": [1000, 1100, 1200, 1300],
            "money": [10100, 11330, 12240, 13650],
        },
        index=idx,
    )


def test_preloaded_data_records_sources_and_partial_failures(monkeypatch):
    import eqlib.data as data_mod
    import eqlib.data_cache as dc

    def fake_local(sec, start, end, adjust):
        return _sample_frame() if sec == "600519" else None

    def fake_fetch(sec, start, end, adjust="qfq"):
        return _sample_frame() if sec == "000001" else pd.DataFrame()

    monkeypatch.setattr(dc, "load_stock_local", fake_local)
    monkeypatch.setattr(data_mod, "fetch_stock_data", fake_fetch)
    monkeypatch.setattr(dc, "_save_to_disk", lambda *args, **kwargs: None)
    monkeypatch.setattr(dc, "save_stock_local", lambda *args, **kwargs: "/tmp/fake.csv")

    preloaded = PreloadedData()
    preloaded.load(
        ["600519", "000001", "999999"],
        "2024-01-01",
        "2024-01-10",
        progress=False,
        use_local=True,
    )

    assert preloaded.load_stats["requested"] == 3
    assert preloaded.load_stats["loaded"] == 2
    assert preloaded.load_stats["sources"] == {"local": 1, "disk_cache": 0, "network": 1}
    assert preloaded.load_stats["failed"] == [
        {
            "security": "999999",
            "reason": "local file not found and network fetch failed",
        }
    ]
    assert preloaded.load_stats["memory_mode"] == "dict_cache"
    assert preloaded.load_stats["elapsed_seconds"] >= 0


def test_preloaded_data_records_panel_fallback(monkeypatch):
    import eqlib.data_cache as dc

    monkeypatch.setattr(dc, "_load_from_disk", lambda sec, start, end, adjust: _sample_frame())

    preloaded = PreloadedData()
    preloaded.load(
        ["600519"],
        "2024-01-01",
        "2024-01-10",
        progress=False,
        use_local=False,
        max_memory_mb=-1,
    )

    assert preloaded.load_stats["sources"]["disk_cache"] == 1
    assert preloaded.load_stats["memory_mode"] == "panel_fallback"
    assert preloaded._use_panel_fallback is True


def test_preloaded_data_skips_network_when_cache_starts_after_requested_period(monkeypatch):
    import eqlib.data as data_mod
    import eqlib.data_cache as dc

    network_calls = []

    monkeypatch.setattr(
        dc,
        "_load_from_disk",
        lambda sec, start, end, adjust: _sample_frame() if sec == "000300.XSHG" else None,
    )
    monkeypatch.setattr(
        dc,
        "_cache_starts_after_request_end",
        lambda sec, end, adjust: sec == "600941",
        raising=False,
    )

    def fake_fetch(*args, **kwargs):
        network_calls.append(args)
        return _sample_frame()

    monkeypatch.setattr(data_mod, "fetch_stock_data", fake_fetch)

    preloaded = PreloadedData()
    preloaded.load(
        ["000300.XSHG", "600941"],
        "2020-01-01",
        "2021-12-31",
        progress=False,
        use_local=False,
    )

    assert network_calls == []
    assert preloaded.load_stats["sources"]["disk_cache"] == 1
    assert preloaded.load_stats["sources"]["network"] == 0
    assert preloaded.load_stats["failed"] == [
        {
            "security": "600941",
            "reason": "authoritative listing date is after requested end",
        }
    ]


def test_late_window_cache_does_not_suppress_older_fetch(monkeypatch, tmp_path):
    import eqlib.data as data_mod
    import eqlib.data_cache as dc

    monkeypatch.setattr(dc, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(dc, "_parquet_engine", lambda: None)
    calls = []

    def fake_fetch(sec, start, end, adjust="qfq"):
        calls.append((sec, str(start), str(end), adjust))
        frame_start = "2024-01-02" if str(start).startswith("2024") else "2020-01-02"
        return _sample_frame(frame_start)

    monkeypatch.setattr(data_mod, "fetch_stock_data", fake_fetch)

    late = PreloadedData()
    late.load(
        ["600519"],
        "2024-01-01",
        "2024-01-10",
        progress=False,
        use_local=False,
    )
    older = PreloadedData()
    older.load(
        ["600519"],
        "2020-01-01",
        "2020-01-10",
        progress=False,
        use_local=False,
    )

    assert [call[1:3] for call in calls] == [
        ("2024-01-01", "2024-01-10"),
        ("2020-01-01", "2020-01-10"),
    ]
    assert older.panel.index.min() == pd.Timestamp("2020-01-02")


def test_partial_cache_fetches_uncovered_prefix(monkeypatch, tmp_path):
    import eqlib.data as data_mod
    import eqlib.data_cache as dc

    monkeypatch.setattr(dc, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(dc, "_parquet_engine", lambda: None)
    calls = []

    def fake_fetch(sec, start, end, adjust="qfq"):
        calls.append((str(start), str(end)))
        return _sample_frame("2024-01-02" if len(calls) == 1 else "2023-01-02")

    monkeypatch.setattr(data_mod, "fetch_stock_data", fake_fetch)

    PreloadedData().load(
        ["600519"],
        "2024-01-01",
        "2024-01-10",
        progress=False,
        use_local=False,
    )
    expanded = PreloadedData()
    expanded.load(
        ["600519"],
        "2023-01-01",
        "2024-01-10",
        progress=False,
        use_local=False,
    )
    PreloadedData().load(
        ["600519"],
        "2023-01-01",
        "2024-01-10",
        progress=False,
        use_local=False,
    )

    assert calls == [
        ("2024-01-01", "2024-01-10"),
        ("2023-01-01", "2024-01-10"),
        ("2023-01-01", "2024-01-10"),
    ]
    assert expanded.panel.index.min() == pd.Timestamp("2023-01-02")


def test_authoritative_post_window_listing_skips_network(monkeypatch, tmp_path):
    import eqlib.data as data_mod
    import eqlib.data_cache as dc

    monkeypatch.setattr(dc, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(dc, "_parquet_engine", lambda: None)
    dc._save_to_disk(
        _sample_frame("2024-01-02"),
        "600941",
        "qfq",
        requested_start="2024-01-01",
        requested_end="2024-01-10",
        listing_date="2022-01-05",
        listing_date_authoritative=True,
    )
    dc._save_to_disk(
        _sample_frame("2020-01-02"),
        "000300.XSHG",
        "qfq",
        requested_start="2020-01-01",
        requested_end="2020-01-10",
    )
    network_calls = []
    monkeypatch.setattr(
        data_mod,
        "fetch_stock_data",
        lambda *args, **kwargs: network_calls.append(args) or pd.DataFrame(),
    )

    preloaded = PreloadedData()
    preloaded.load(
        ["000300.XSHG", "600941"],
        "2020-01-01",
        "2020-01-10",
        progress=False,
        use_local=False,
    )

    assert network_calls == []
    assert preloaded.load_stats["failed"] == [
        {
            "security": "600941",
            "reason": "authoritative listing date is after requested end",
        }
    ]


def test_report_json_includes_data_diagnostics(tmp_path, monkeypatch):
    import eqlib.attribution as attribution
    import eqlib.data as data_mod

    analytics = {
        "annual_return": 0.12,
        "sharpe_ratio": 1.1,
        "max_drawdown": -0.08,
        "win_rate_trade": 0.5,
        "alpha": 0.01,
        "beta": 0.8,
        "trade_count": 4,
        "annual_volatility": 0.15,
        "total_return": 0.1,
        "sortino_ratio": 1.2,
        "calmar_ratio": 1.5,
        "win_rate_daily": 0.52,
        "profit_loss_ratio": 1.8,
        "information_ratio": 0.4,
        "excess_return": 0.02,
        "benchmark_return": 0.08,
        "monthly_returns": {},
        "rolling_sharpe_60d": [],
        "rolling_volatility_60d": [],
        "drawdown_periods": [],
        "daily_returns_stats": {},
        "per_stock_pnl": {},
    }
    monkeypatch.setattr(attribution, "analyze_returns", lambda result: analytics)
    monkeypatch.setattr(
        attribution,
        "grade_strategy",
        lambda data: {
            "overall": "A",
            "score": 75,
            "weakest": "risk",
            "summary_text": "stable",
        },
    )
    monkeypatch.setattr(attribution, "diagnose_bottleneck", lambda *_args: [])
    monkeypatch.setattr(attribution, "recommend_params", lambda *_args: [])
    monkeypatch.setattr(attribution, "fama_french_analysis", lambda result: {})
    monkeypatch.setattr(attribution, "brinson_attribution", lambda result: {})
    monkeypatch.setattr(data_mod, "fetch_stock_data", lambda *args, **kwargs: pd.DataFrame())

    portfolio = SimpleNamespace(
        starting_cash=100000.0,
        total_value=110000.0,
        positions={},
    )
    context = SimpleNamespace(
        start_date=dt.date(2024, 1, 1),
        end_date=dt.date(2024, 1, 10),
        portfolio=portfolio,
        universe=[],
    )
    result = {
        "context": context,
        "trade_log": [],
        "recorded_values": [
            {"date": dt.date(2024, 1, 1), "total_value": 100000.0},
            {"date": dt.date(2024, 1, 10), "total_value": 110000.0},
        ],
        "benchmark": "000300.XSHG",
        "ohlcv_data": {},
        "data_diagnostics": {
            "requested": 2,
            "loaded": 1,
            "failed": [{"security": "999999", "reason": "no data"}],
            "sources": {"local": 1},
            "elapsed_seconds": 0.12,
            "memory_mode": "dict_cache",
            "memory_estimate_mb": 1.5,
            "max_memory_mb": 1024,
            "use_local": True,
            "adjust": "qfq",
        },
    }

    out_path = tmp_path / "report.json"
    generate_report_json(result, out_path)
    payload = json.loads(out_path.read_text())

    assert payload["data_diagnostics"]["requested"] == 2
    assert payload["data_diagnostics"]["loaded"] == 1
    assert payload["data_diagnostics"]["failed"][0]["security"] == "999999"
    assert payload["data_diagnostics"]["sources"] == {
        "local": 1,
        "disk_cache": 0,
        "network": 0,
    }
