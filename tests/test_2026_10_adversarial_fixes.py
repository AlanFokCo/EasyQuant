"""Regression coverage for the 2026-10-09 adversarial-review fixes.

Covers: WFA recorded_values list crash (P0-1), volume unit canonicalisation
to shares (P0-2), minute-bar date bounds (P1-1), _LazyData.current()/
attribute_history() (P1-2), paper price-limit prev_close fetch (P1-3),
paper trading-day guard (P1-4), scheduled-func per-day dedup (P1-5),
bare/suffixed code resolution in series APIs (P1-6), get_price preloaded
fast path (P1-7), qfq anchor-drift cache guard (P1-8), local CSV coverage
validation (P1-9), DingTalk sign URL-encoding (P1-10), explicit close_tax
precedence, negative-count validation, RSI all-up convention,
LinearRegression feature importances, get_trade_days count semantics,
Tencent single-canonicalisation regression, and legacy lots-unit cache/CSV
refusal on both the read and write paths.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import eqlib._state as st
from eqlib import engine, trade
from eqlib.context import Context

DAY = dt.date(2024, 1, 3)
SEC = "601390.XSHG"

# Captured at import time, before any fixture monkeypatches it; used by the
# paper-trading test to restore the real session lookup (run_paper_trade
# creates and activates its own session).
_REAL_GET_SESSION = st.get_session


@pytest.fixture
def session(monkeypatch):
    sess = st.BacktestSession()
    sess._context = Context(DAY, DAY + dt.timedelta(days=10), starting_cash=1_000_000)
    sess._options["check_price_limit"] = False
    monkeypatch.setattr(st, "get_session", lambda: sess)
    monkeypatch.setattr(engine, "_get_open_fast", lambda *a: 10.0)
    monkeypatch.setattr(engine, "_get_volume_fast", lambda *a: 10_000)
    monkeypatch.setattr(engine, "_get_preloaded", lambda: None)
    return sess


# ── P0-1: walk_forward consumes recorded_values (a list) without crashing ─────

def test_walk_forward_handles_recorded_values_list(monkeypatch):
    import eqlib.wfa as wfa

    def fake_run_backtest(init, start_date=None, end_date=None, **kwargs):
        days = pd.date_range(str(start_date), str(end_date), freq="B")
        return {
            "recorded_values": [
                {"date": d.date(), "total_value": 100_000 + i * 10.0}
                for i, d in enumerate(days)
            ]
        }

    monkeypatch.setattr(engine, "run_backtest", fake_run_backtest)
    monkeypatch.setattr(
        "eqlib.attribution.analyze_returns", lambda result: {"sharpe": 1.0}
    )

    result = wfa.walk_forward(
        lambda: (lambda context: None),
        start_date="2020-01-01",
        end_date="2020-09-01",
        train_months=3,
        test_months=2,
        step_months=2,
    )
    assert result.windows, "expected at least one WFA window"
    assert not result.oos_equity.empty
    assert result.oos_equity.index.is_monotonic_increasing


# ── P0-2: canonical volume unit is shares (股), providers deliver lots (手) ────

def test_canonicalize_converts_volume_lots_to_shares():
    import eqlib.data as data

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.9, 10.0],
            "close": [10.1, 10.2],
            "volume": [161_617.0, 150_000.0],  # lots, as providers deliver
        }
    )
    out = data._canonicalize_ohlcv(frame, "eastmoney")
    assert out is not None
    assert out["volume"].tolist() == [16_161_700.0, 15_000_000.0]


def test_daily_volume_cap_uses_shares(session):
    # 10k-share day, default 10% cap → at most 1000 shares fill per day.
    obj = trade.order(SEC, 2000)
    engine._fill_pending_orders(session, DAY + dt.timedelta(days=1))
    assert obj.filled_amount == 1000
    assert obj.filled_amount < obj.amount


# ── P1-1: bare date end bound keeps intraday minute bars ──────────────────────

def test_fetch_minute_data_date_bound_keeps_intraday_bars(monkeypatch):
    import eqlib.data as data

    idx = pd.to_datetime(
        ["2024-06-03 09:31", "2024-06-03 09:32", "2024-06-03 09:33"]
    )
    fake = pd.DataFrame(
        {
            "时间": idx.strftime("%Y-%m-%d %H:%M:%S"),
            "开盘": [10.0, 10.0, 10.0],
            "收盘": [10.0, 10.0, 10.0],
            "最高": [10.0, 10.0, 10.0],
            "最低": [10.0, 10.0, 10.0],
            "成交量": [100.0, 100.0, 100.0],
            "成交额": [100_000.0, 100_000.0, 100_000.0],
        }
    )
    monkeypatch.setattr(data.ak, "stock_zh_a_hist_min_em", lambda **kw: fake)

    df = data.fetch_minute_data(
        SEC, period="1m", start_date=dt.date(2024, 6, 3), end_date=dt.date(2024, 6, 3)
    )
    assert len(df) == 3, "bare date end bound must keep intraday bars"
    # Minute volume also canonicalised to shares
    assert df["volume"].iloc[0] == 10_000.0


# ── P1-2: _LazyData exposes current()/attribute_history() ─────────────────────

def test_lazy_data_current_and_attribute_history(session, monkeypatch):
    import eqlib.data as data

    lazy = engine._LazyData(session._context)
    assert lazy.current(SEC, "close") is None  # no bar → None, not AttributeError

    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    frame = pd.DataFrame({"close": [10.0, 10.1, 10.2, 10.3, 10.4]}, index=idx)
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **kw: frame)
    # st._context delegates via the thread-local registry (not the patched
    # get_session), so activate the session explicitly.
    st._set_session(session)
    try:
        session._context.current_dt = dt.datetime(2024, 1, 8, 9, 30)
        hist = lazy.attribute_history(SEC, 5, "1d", ["close"])
    finally:
        st._clear_session()
    assert isinstance(hist, pd.DataFrame)
    assert hist["close"].iloc[-1] == pytest.approx(10.4)


# ── P1-3: paper price-limit check actually fetches prev_close ─────────────────

def test_paper_price_limit_blocks_limit_up_buy(session, monkeypatch):
    session._options["_is_paper_trading"] = True
    session._options["check_price_limit"] = True

    prev = pd.DataFrame(
        {"close": [10.0]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    import eqlib.data as data
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **kw: prev)

    obj = trade.order(SEC, 100)  # buy at 11.0 with prev_close 10.0 → limit-up
    engine._fill_pending_orders(
        session, DAY + dt.timedelta(days=1), exec_prices={"601390": 11.0}
    )
    assert obj.status == "cancelled"
    assert obj.filled_amount == 0


# ── P1-4: paper trading-day guard ─────────────────────────────────────────────

def test_paper_trading_day_guard_uses_calendar(monkeypatch):
    import eqlib.data as data
    # Force the offline bundled-calendar path.
    monkeypatch.setattr(
        data.ak, "tool_trade_date_hist_sina",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert engine._paper_is_trading_day(dt.date(2026, 10, 10)) is False  # Saturday
    assert engine._paper_is_trading_day(dt.date(2026, 10, 12)) is True   # Monday


# ── P1-5: scheduled funcs run at most once per day in paper mode ──────────────

def test_paper_scheduled_func_fires_once_per_day(session, monkeypatch):
    import eqlib

    # run_paper_trade creates and activates its own session; the fixture's
    # get_session patch would split registration and dispatch across two
    # different sessions, so restore the real lookup here.
    monkeypatch.setattr(st, "get_session", _REAL_GET_SESSION)
    monkeypatch.setattr(engine, "_paper_is_trading_day", lambda day: True)
    monkeypatch.setattr(engine, "_fetch_live_prices", lambda cache, securities=None: cache)
    monkeypatch.setattr(engine, "_resolve_live_price", lambda cache, sec, default: 10.0)

    calls = {"n": 0}
    sleeps = {"n": 0}

    class _StopLoop(Exception):
        pass

    def counted(context):
        calls["n"] += 1

    def fake_sleep(seconds):
        sleeps["n"] += 1
        if sleeps["n"] >= 3:
            raise _StopLoop

    monkeypatch.setattr(engine.time, "sleep", fake_sleep)

    now = dt.datetime.now()
    hhmm = now.strftime("%H:%M")

    def initialize(context):
        eqlib.run_daily(counted, time=hhmm)

    with pytest.raises(_StopLoop):
        engine.run_paper_trade(initialize, interval=1)
    assert calls["n"] == 1, "scheduled func must not refire inside the ±60s window"


# ── P1-6: bare and suffixed codes resolve to the same preloaded series ────────

def _make_preloaded_with_series(key):
    from eqlib.data_cache import PreloadedData

    preloaded = PreloadedData()
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    preloaded._field_series = {
        key: {"close": pd.Series([10.0, 10.1, 10.2, 10.3, 10.4], index=idx)}
    }
    preloaded.load_stats = {"adjust": "qfq"}
    return preloaded


@pytest.mark.parametrize("stored_key", ["601398.XSHG", "601398"])
def test_attribute_history_resolves_code_variants(session, monkeypatch, stored_key):
    import eqlib.data as data

    preloaded = _make_preloaded_with_series(stored_key)
    monkeypatch.setattr(engine, "_get_preloaded", lambda: preloaded)
    st._set_session(session)
    try:
        # Point-in-time safety excludes bars on/after the current day; place
        # "now" after the synthetic series so all five bars are visible.
        session._context.current_dt = dt.datetime(2024, 1, 8, 9, 30)
        for query in ("601398", "601398.XSHG"):
            frame = data.attribute_history(query, 5, "1d", ["close"])
            assert not frame.empty, f"{query} (stored as {stored_key}) returned empty"
            assert frame["close"].iloc[-1] == pytest.approx(10.4)
    finally:
        st._clear_session()


# ── P1-7: get_price serves preloaded data inside a simulation ─────────────────

def test_get_price_uses_preloaded_without_network(session, monkeypatch):
    import eqlib.data as data

    preloaded = _make_preloaded_with_series(SEC)
    monkeypatch.setattr(engine, "_get_preloaded", lambda: preloaded)

    def fail_fetch(*a, **kw):
        raise AssertionError("network fetch must not be used inside a simulation")

    monkeypatch.setattr(data, "fetch_stock_data", fail_fetch)
    st._set_session(session)
    try:
        frame = data.get_price(SEC, start_date="2024-01-01", end_date="2024-01-02")
        assert not frame.empty
        assert frame["close"].iloc[-1] == pytest.approx(10.1)  # cutoff excludes current day
    finally:
        st._clear_session()


# ── P1-8: qfq anchor drift blocks cache merges ────────────────────────────────

def test_adjustment_anchor_drift_detection():
    from eqlib.data_cache import _adjustment_anchor_drifted

    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    old = pd.DataFrame({"close": np.full(10, 10.0)}, index=idx)
    same = pd.DataFrame({"close": np.full(10, 10.0)}, index=idx)
    drifted = pd.DataFrame({"close": np.full(10, 11.0)}, index=idx)  # +10% anchor shift
    assert _adjustment_anchor_drifted(old, same) is False
    assert _adjustment_anchor_drifted(old, drifted) is True
    # Consistent deviation is provable from just 2 overlapping bars — this is
    # the common incremental-update case and must be caught.
    assert _adjustment_anchor_drifted(old.iloc[:2], drifted.iloc[:2]) is True
    # A single overlapping bar cannot prove drift → allow merge.
    assert _adjustment_anchor_drifted(old.iloc[:1], drifted.iloc[:1]) is False
    # A lone refreshed/corrected bar is not an anchor shift → allow merge.
    corrected = old.iloc[:2].copy()
    corrected.iloc[-1] = 12.0
    assert _adjustment_anchor_drifted(old.iloc[:2], corrected) is False


def test_save_to_disk_drops_drifted_cache(tmp_path, monkeypatch):
    import eqlib.data_cache as cache

    monkeypatch.setattr(cache, "_cache_path", lambda s, a: tmp_path / f"{s}_{a}.pkl")
    monkeypatch.setattr(cache, "_pickle_cache_path", lambda s, a: tmp_path / f"{s}_{a}.pkl")
    monkeypatch.setattr(
        cache, "_metadata_cache_path", lambda s, a: tmp_path / f"{s}_{a}.meta.json"
    )
    monkeypatch.setattr(cache, "_parquet_engine", lambda: None)

    old_idx = pd.date_range("2024-01-01", periods=10, freq="B")
    old = pd.DataFrame(
        {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1e6},
        index=old_idx,
    )
    new_idx = pd.date_range("2024-01-10", periods=8, freq="B")
    new = pd.DataFrame(
        {"open": 11.0, "high": 11.5, "low": 10.5, "close": 11.0, "volume": 1e6},
        index=new_idx,
    )
    cache._save_to_disk(old, "601398", "qfq")
    cache._save_to_disk(new, "601398", "qfq")

    stored = pd.read_pickle(tmp_path / "601398_qfq.pkl")
    # Old anchor (close=10) must be gone entirely — no seam at the join.
    assert (stored["close"] == 11.0).all()
    assert stored.index.min() == new_idx.min()

    meta = json.loads((tmp_path / "601398_qfq.meta.json").read_text())
    assert meta["version"] == 2
    assert meta["volume_unit"] == "shares"


# ── P1-9: load_stock_local validates unit metadata and coverage ───────────────

def _write_local_csv(tmp_path, monkeypatch, meta):
    import eqlib.data_cache as cache

    monkeypatch.setattr(cache, "_local_csv_path", lambda s, a="qfq": tmp_path / f"{s}.csv")
    idx = pd.date_range("2023-01-02", periods=30, freq="B")
    df = pd.DataFrame(
        {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1e6},
        index=idx,
    )
    df.to_csv(tmp_path / "601398.csv")
    if meta is not None:
        (tmp_path / "601398.meta.json").write_text(json.dumps(meta))
    return cache


def test_load_stock_local_rejects_legacy_lot_file(tmp_path, monkeypatch):
    cache = _write_local_csv(tmp_path, monkeypatch, meta=None)
    assert cache.load_stock_local("601398", "2023-01-02", "2023-02-28") is None


def test_load_stock_local_rejects_insufficient_coverage(tmp_path, monkeypatch):
    cache = _write_local_csv(
        tmp_path, monkeypatch,
        meta={
            "version": 2,
            "volume_unit": "shares",
            "covered_start": "20230101",
            "covered_end": "20231231",
        },
    )
    # Requested range exceeds the saved coverage → refuse
    assert cache.load_stock_local("601398", "2020-01-01", "2023-02-28") is None
    # Covered range → OK
    frame = cache.load_stock_local("601398", "2023-01-02", "2023-02-28")
    assert frame is not None and not frame.empty


# ── P1-10: DingTalk signature is URL-encoded ──────────────────────────────────

def test_dingtalk_sign_is_url_encoded(monkeypatch):
    import urllib.parse

    from eqlib.notification import DingTalkSender

    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url

        class Resp:
            status_code = 200

            def json(self):
                return {"errcode": 0}

        return Resp()

    monkeypatch.setattr("eqlib.notification.requests.post", fake_post)
    notifier = DingTalkSender(
        "https://oapi.dingtalk.com/robot/send?access_token=abc", secret="SEC123"
    )
    assert notifier.send("hello") is True

    query = urllib.parse.urlsplit(captured["url"]).query
    raw_sign = [p for p in query.split("&") if p.startswith("sign=")][0][5:]
    assert "+" not in raw_sign and "/" not in raw_sign, "sign must be URL-encoded"
    parsed = urllib.parse.parse_qs(query)
    ts = int(parsed["timestamp"][0])
    assert parsed["sign"][0] == notifier._compute_sign(ts)


# ── P2: explicit close_tax beats the statutory date-based rate ────────────────

def test_explicit_close_tax_overrides_statutory_rate():
    from eqlib.objects import OrderCost

    day = dt.date(2024, 1, 2)  # post-2023-08-28 → statutory 0.05%
    zero = OrderCost(close_tax=0.0)
    # tax waived, only min commission applies
    assert zero.calc_close_cost(10.0, 100, trade_date=day) == pytest.approx(5.0)
    default = OrderCost()
    # statutory 0.05% tax (0.5) + min commission (5)
    assert default.calc_close_cost(10.0, 100, trade_date=day) == pytest.approx(5.5)
    # pre-2023-08-28 → statutory 0.1%
    older = dt.date(2020, 1, 2)
    assert default.calc_close_cost(10.0, 100, trade_date=older) == pytest.approx(6.0)
    assert zero.calc_close_cost(10.0, 100, trade_date=older) == pytest.approx(5.0)


# ── P2: negative/invalid count rejected on series APIs ────────────────────────

def test_attribute_history_rejects_non_positive_count():
    import eqlib.data as data

    with pytest.raises(ValueError, match="positive"):
        data.attribute_history(SEC, -5, "1d", ["close"])
    with pytest.raises(ValueError, match="positive"):
        data.history(-1, "1d", "close", security=SEC)


# ── P2: RSI convention — all-up window is 100, flat is 50 ────────────────────

def test_rsi_all_up_window_is_100():
    from eqlib.utils.indicators import rsi

    up = pd.Series(np.arange(1, 41, dtype=float))  # 39 consecutive up moves
    assert rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    flat = pd.Series(np.full(40, 10.0))
    assert rsi(flat, 14).iloc[-1] == pytest.approx(50.0)


# ── P2: LinearRegression feature importances are per-feature ─────────────────

def test_linear_regression_feature_importances_not_broadcast():
    from eqlib.ml.models import BaseMLModel

    rng = np.random.default_rng(7)
    x = pd.DataFrame(
        {
            "a": rng.normal(size=200),
            "b": rng.normal(size=200),
            "c": rng.normal(size=200),
        }
    )
    y = pd.Series(3.0 * x["a"] - 1.0 * x["b"] + 0.01 * x["c"])
    model = BaseMLModel("logistic_regression", is_classifier=False)
    model.fit(x, y)
    imp = model.feature_importances()
    assert imp["a"] > imp["b"] > imp["c"], "importances must reflect per-feature coefficients"


# ── P2: get_trade_days count applies after the date filter ───────────────────

def test_get_trade_days_count_applies_after_date_filter(monkeypatch):
    import eqlib.data as data

    cal = pd.DataFrame(
        {"trade_date": pd.date_range("2024-01-01", "2024-01-10", freq="B")}
    )
    monkeypatch.setattr(data.ak, "tool_trade_date_hist_sina", lambda: cal)

    days = data.get_trade_days("2024-01-02", "2024-01-05", count=2)
    assert days == [dt.date(2024, 1, 4), dt.date(2024, 1, 5)]


# ── P0 review-followup: Tencent volume canonicalised exactly once ─────────────

def test_tencent_volume_canonicalized_once(monkeypatch):
    """Regression: _fetch_from_tencent must not canonicalise internally.

    fetch_stock_data canonicalises every source once (lots→shares ×100); the
    Tencent fetcher previously canonicalised too, inflating volume 100×.
    """
    import eqlib.data as data

    payload = {
        "data": {
            "sh601398": {
                "day": [
                    ["2024-01-02", "10.0", "10.1", "10.2", "9.9",
                     "161617.0", {}, "0.5", "163.21", ""],
                    ["2024-01-03", "10.1", "10.2", "10.3", "10.0",
                     "150000.0", {}, "0.9", "153.00", ""],
                ]
            }
        }
    }

    class _Resp:
        def json(self):
            return payload

    monkeypatch.setattr(data.requests, "get", lambda *a, **kw: _Resp())
    # Route the fallback chain directly to Tencent.
    monkeypatch.setattr(
        data, "_DATA_FETCHERS", [("tencent", data._fetch_from_tencent)]
    )

    df = data.fetch_stock_data("601398", "20240102", "20240103", "")
    assert not df.empty
    # 161,617 lots → 16,161,700 shares exactly once (not ×100 twice).
    assert df["volume"].iloc[0] == 16_161_700.0
    assert df["volume"].iloc[1] == 15_000_000.0


# ── P1 review-followup: cache/CSV legacy-unit refusal on read AND write ───────

def _patch_cache_paths(cache, tmp_path, monkeypatch):
    monkeypatch.setattr(
        cache, "_cache_path", lambda s, a: tmp_path / f"{s}_{a}.pkl"
    )
    monkeypatch.setattr(
        cache, "_pickle_cache_path", lambda s, a: tmp_path / f"{s}_{a}.pkl"
    )
    monkeypatch.setattr(
        cache, "_metadata_cache_path", lambda s, a: tmp_path / f"{s}_{a}.meta.json"
    )
    monkeypatch.setattr(cache, "_parquet_engine", lambda: None)


def test_load_from_disk_refuses_legacy_lot_cache(tmp_path, monkeypatch):
    import eqlib.data_cache as cache

    _patch_cache_paths(cache, tmp_path, monkeypatch)
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    frame = pd.DataFrame(
        {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1e5},
        index=idx,
    )
    frame.to_pickle(tmp_path / "601398_qfq.pkl")

    # No sidecar metadata at all → legacy (lots) → refused.
    assert cache._load_from_disk("601398", "20240101", "20240115", "qfq") is None
    # Explicit v1 metadata → refused.
    (tmp_path / "601398_qfq.meta.json").write_text(
        json.dumps({"version": 1, "volume_unit": "lots"})
    )
    assert cache._load_from_disk("601398", "20240101", "20240115", "qfq") is None
    # v2 shares metadata with coverage → accepted.
    (tmp_path / "601398_qfq.meta.json").write_text(
        json.dumps(
            {
                "version": 2,
                "volume_unit": "shares",
                "covered_ranges": [{"start": "20240101", "end": "20240115"}],
            }
        )
    )
    loaded = cache._load_from_disk("601398", "20240101", "20240115", "qfq")
    assert loaded is not None and not loaded.empty


def test_save_to_disk_replaces_legacy_lot_cache(tmp_path, monkeypatch):
    """A v1 (lots) cache must never be merged with shares-unit rows."""
    import eqlib.data_cache as cache

    _patch_cache_paths(cache, tmp_path, monkeypatch)
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    legacy = pd.DataFrame(
        {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0,
         "volume": 161_617.0},  # lots
        index=idx,
    )
    legacy.to_pickle(tmp_path / "601398_qfq.pkl")
    # No sidecar → legacy cache.

    new = pd.DataFrame(
        {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.1,
         "volume": 16_161_700.0},  # shares
        index=idx,
    )
    cache._save_to_disk(new, "601398", "qfq")

    stored = pd.read_pickle(tmp_path / "601398_qfq.pkl")
    # Every stored row must be the shares-unit replacement, no lots residue.
    assert (stored["volume"] == 16_161_700.0).all()
    meta = json.loads((tmp_path / "601398_qfq.meta.json").read_text())
    assert meta["version"] == 2 and meta["volume_unit"] == "shares"
