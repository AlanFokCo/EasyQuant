"""Point-in-time (PIT) contract tests for the data layer.

Covers the audit-confirmed escape channels (QUANT-P1-01/02, GAP-1/2/3)
and the fix-verification follow-ups (FIXGAP-1/2):

- ``fetch_stock_data`` / ``get_money_flow`` / ``get_billboard_list`` /
  ``fetch_minute_data`` must truncate at the simulated clock inside a
  backtest (T-1 during decision-time callbacks, matching ``get_price``),
  and stay unrestricted outside a simulation.
- ``get_fundamentals`` / ``get_financial_abstract`` / ``get_valuation`` /
  ``get_extras`` / ``get_concept_stocks`` / ``get_industry_stocks`` /
  ``scan_market`` / ``get_financial_screen`` / ``get_restriction_release``
  always serve the latest provider snapshot, so inside a backtest they must
  emit a ``FutureWarning`` (or raise with ``set_option('avoid_future_data',
  True)``).
- ``get_current_data`` / ``get_current_data_object`` (FIXGAP-7) share the
  same ``_get_spot_data`` source and the same guard; the object variant
  routes through the check-free impl so each entry point warns exactly
  once under its own name.
- ``check_golden_cross`` fetches full history from the provider directly;
  inside a backtest it must truncate at the simulated clock.
- ``load_stock_local`` must truncate local CSV rows at the simulated clock
  inside a backtest, while engine-internal full-range reads are exempt via
  ``_unrestricted_fetch``.
- ``fetch_cached`` must truncate the disk-hit branch at the simulated clock
  inside a backtest (the network-miss branch is truncated inside
  ``fetch_stock_data`` already).
- ``use_local=True`` network fallback must be visible: WARNING log plus
  ``load_stats["local_fallback"]`` diagnostics.
- Removed Web Studio references must not resurface in ``eqlib/``.
"""

import datetime as dt
import json
import logging
import warnings
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import eqlib.data as data
import eqlib.data_cache as data_cache
import eqlib.stock_query as stock_query
from eqlib import _state


@pytest.fixture(autouse=True)
def isolated_session():
    previous = _state.get_session()
    session = _state.BacktestSession()
    _state._set_session(session)
    data.clear_cache()
    yield session
    data.clear_cache()
    _state._set_session(previous)


def _daily_frame() -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=7)  # 2024-01-02 .. 2024-01-10
    return pd.DataFrame(
        {
            "open": [10.0 + i for i in range(7)],
            "high": [10.5 + i for i in range(7)],
            "low": [9.5 + i for i in range(7)],
            "close": [10.1 + i for i in range(7)],
            "volume": [1000.0] * 7,
            "money": [10100.0] * 7,
        },
        index=idx,
    )


def _set_clock(session, current, recorded=()):
    session._context = SimpleNamespace(current_dt=current)
    session._recorded_values = {d: {"date": d} for d in recorded}


# ── fetch_stock_data truncation ──────────────────────────────────────────────


def test_fetch_stock_data_truncates_to_t_minus_1_in_backtest(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-31")
    assert not result.empty
    assert result.index.max() == pd.Timestamp("2024-01-03")


def test_fetch_stock_data_unrestricted_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-31")
    assert result.index.max() == pd.Timestamp("2024-01-10")


def test_fetch_stock_data_unrestricted_in_paper_session(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-31")
    assert result.index.max() == pd.Timestamp("2024-01-10")


def test_fetch_stock_data_includes_today_after_close(monkeypatch, isolated_session):
    # Post-close callback / post-loop reporting: the day's bar is public.
    _set_clock(
        isolated_session,
        dt.datetime(2024, 1, 4, 15, 0),
        recorded=[dt.date(2024, 1, 4)],
    )
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-31")
    assert result.index.max() == pd.Timestamp("2024-01-04")


def test_fetch_stock_data_post_loop_returns_full_range(monkeypatch, isolated_session):
    # Engine's post-loop benchmark fetch: last day already recorded, so the
    # full backtest window must survive (no report regression).
    days = [dt.date(2024, 1, 2), dt.date(2024, 1, 3), dt.date(2024, 1, 4)]
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30), recorded=days)
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    result = data.fetch_stock_data(
        "000300.XSHG", dt.date(2024, 1, 2), dt.date(2024, 1, 4)
    )
    assert result.index.max() == pd.Timestamp("2024-01-04")


def test_fetch_stock_data_future_only_request_short_circuits(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    def _forbidden(*args, **kwargs):
        raise AssertionError("network/impl must not be touched")

    monkeypatch.setattr(data, "_fetch_stock_data_impl", _forbidden)
    result = data.fetch_stock_data("600536", "2024-01-05", "2024-01-31")
    assert result.empty


def test_fetch_stock_data_cache_hit_still_truncated(isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    cache_key = ("600536", "2024-01-02", "2024-01-10", "qfq")
    with data._cache_lock:
        data._cache[cache_key] = _daily_frame()

    result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-03")


def test_unrestricted_fetch_guard_bypasses_truncation(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data, "_fetch_stock_data_impl", lambda *a, **k: _daily_frame())

    with _state._unrestricted_fetch():
        with _state._unrestricted_fetch():  # nesting must be safe
            result = data.fetch_stock_data("600536", "2024-01-02", "2024-01-31")
    assert result.index.max() == pd.Timestamp("2024-01-10")
    assert isolated_session._full_range_fetch_depth == 0


# ── get_money_flow truncation ────────────────────────────────────────────────


def _fake_fund_flow(stock, market):
    return pd.DataFrame(
        {
            "日期": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "收盘价": [10.0, 10.1, 10.2, 10.3],
            "主力净流入-净额": [1.0, 2.0, 3.0, 4.0],
        }
    )


def test_get_money_flow_truncated_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "stock_individual_fund_flow", _fake_fund_flow)

    result = data.get_money_flow("600536")
    assert list(result["date"]) == ["2024-01-02", "2024-01-03"]
    # count applies after truncation: most recent allowed day wins.
    result = data.get_money_flow("600536", count=1)
    assert list(result["date"]) == ["2024-01-03"]


def test_get_money_flow_unrestricted_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_individual_fund_flow", _fake_fund_flow)

    result = data.get_money_flow("600536")
    assert list(result["date"]) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]


# ── get_billboard_list truncation ────────────────────────────────────────────


def test_get_billboard_list_clamps_range_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    calls = {}

    def _fake_lhb(start_date, end_date):
        calls["start_date"] = start_date
        calls["end_date"] = end_date
        return pd.DataFrame()

    monkeypatch.setattr(data.ak, "stock_lhb_detail_em", _fake_lhb)
    data.get_billboard_list(start_date="2024-01-02", end_date="2024-01-10")
    assert calls == {"start_date": "20240102", "end_date": "20240103"}


def test_get_billboard_list_beyond_cutoff_returns_empty_without_network(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    def _forbidden(**kwargs):
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(data.ak, "stock_lhb_detail_em", _forbidden)
    # Default dates resolve to the real today, which is beyond a 2024 clock.
    result = data.get_billboard_list()
    assert result.empty


def test_get_billboard_list_unrestricted_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    calls = {}

    def _fake_lhb(start_date, end_date):
        calls["start_date"] = start_date
        calls["end_date"] = end_date
        return pd.DataFrame()

    monkeypatch.setattr(data.ak, "stock_lhb_detail_em", _fake_lhb)
    data.get_billboard_list(start_date="2024-01-02", end_date="2024-01-10")
    assert calls == {"start_date": "20240102", "end_date": "20240110"}


# ── fetch_minute_data truncation ─────────────────────────────────────────────


def _fake_minute_em(symbol, period, adjust=""):
    return pd.DataFrame(
        {
            "时间": [
                "2024-01-03 14:55:00",
                "2024-01-04 09:31:00",
                "2024-01-04 14:55:00",
                "2024-01-05 09:31:00",
            ],
            "开盘": [10.0, 10.1, 10.2, 10.3],
            "收盘": [10.0, 10.1, 10.2, 10.3],
            "最高": [10.0, 10.1, 10.2, 10.3],
            "最低": [10.0, 10.1, 10.2, 10.3],
            "成交量": [100.0, 100.0, 100.0, 100.0],
            "成交额": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )


def test_fetch_minute_data_truncated_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "stock_zh_a_hist_min_em", _fake_minute_em)

    result = data.fetch_minute_data("600536", period="5m")
    assert list(result.index) == [pd.Timestamp("2024-01-03 14:55:00")]


def test_fetch_minute_data_unrestricted_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_zh_a_hist_min_em", _fake_minute_em)

    result = data.fetch_minute_data("600536", period="5m")
    assert len(result) == 4


# ── get_fundamentals snapshot warning ────────────────────────────────────────


def _fake_financial_abstract(symbol):
    return pd.DataFrame({"指标": ["营业总收入"], "2024Q1": [1.0]})


def test_get_fundamentals_warns_in_backtest_single_code(
    monkeypatch, isolated_session
):
    import eqlib.stock_query as stock_query

    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "stock_financial_abstract", _fake_financial_abstract)

    with pytest.warns(FutureWarning, match="look-ahead"):
        stock_query.get_fundamentals("601390", date="2020-01-01")
    # The data.py alias delegates to the same implementation (GAP-3).
    with pytest.warns(FutureWarning, match="look-ahead"):
        data.get_fundamentals("601390", date="2020-01-01")


def test_get_fundamentals_warns_in_backtest_query_form(monkeypatch, isolated_session):
    import eqlib.stock_query as stock_query

    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    sentinel = pd.DataFrame({"code": ["601390"]})
    monkeypatch.setattr(stock_query, "_execute_query", lambda q: sentinel)

    with pytest.warns(FutureWarning, match="look-ahead"):
        result = stock_query.get_fundamentals(stock_query.query(stock_query.valuation.code))
    assert result is sentinel


def test_get_fundamentals_raises_with_avoid_future_data(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["avoid_future_data"] = True
    monkeypatch.setattr(data.ak, "stock_financial_abstract", _fake_financial_abstract)

    with pytest.raises(ValueError, match="avoid_future_data"):
        data.get_fundamentals("601390", date="2020-01-01")


def test_get_fundamentals_silent_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_financial_abstract", _fake_financial_abstract)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_fundamentals("601390", date="2020-01-01")
    assert not result.empty


def test_get_fundamentals_silent_in_paper_session(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True
    monkeypatch.setattr(data.ak, "stock_financial_abstract", _fake_financial_abstract)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_fundamentals("601390")
    assert not result.empty


# ── use_local fallback visibility (GAP-2) ────────────────────────────────────


def test_use_local_network_fallback_is_visible(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="eqlib")
    monkeypatch.setattr(data_cache, "load_stock_local", lambda *a, **k: None)
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: _daily_frame())
    monkeypatch.setattr(data_cache, "_save_to_disk", lambda *a, **k: None)
    monkeypatch.setattr(data_cache, "save_stock_local", lambda *a, **k: None)

    preloaded = data_cache.PreloadedData()
    preloaded.load(["600519"], "2024-01-01", "2024-01-10", progress=False, use_local=True)

    assert preloaded.load_stats["sources"]["network"] == 1
    assert preloaded.load_stats["local_fallback"] == ["600519"]
    warnings_seen = [
        record for record in caplog.records if record.levelno >= logging.WARNING
    ]
    assert any("falling back to network" in record.getMessage() for record in warnings_seen)


def test_no_data_error_message_has_no_web_console_reference(monkeypatch):
    monkeypatch.setattr(data_cache, "load_stock_local", lambda *a, **k: None)
    monkeypatch.setattr(data, "fetch_stock_data", lambda *a, **k: pd.DataFrame())

    preloaded = data_cache.PreloadedData()
    with pytest.raises(RuntimeError) as excinfo:
        preloaded.load(["600519"], "2024-01-01", "2024-01-10", progress=False, use_local=True)
    message = str(excinfo.value).lower()
    assert "web console" not in message
    assert "data_diagnostics" in message


# ── Web Studio removal residue (GAP-1) ───────────────────────────────────────


def test_no_web_studio_references_in_eqlib():
    import eqlib

    offenders = []
    for path in Path(eqlib.__file__).parent.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        if "web studio" in text or "web console" in text:
            offenders.append(path.name)
    assert offenders == []


# ── get_index_stocks / get_index_weights survivorship warning (QUANT-P1-03) ──


def _fake_index_cons(symbol):
    return pd.DataFrame(
        {
            "品种代码": ["601398", "601390"],
            "品种名称": ["工商银行", "中国中铁"],
            "纳入日期": ["2020-01-01", "2020-01-01"],
        }
    )


def test_get_index_stocks_warns_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "index_stock_cons", _fake_index_cons)

    with pytest.warns(FutureWarning, match="survivorship"):
        result = data.get_index_stocks("000300")
    assert list(result["code"]) == ["601398", "601390"]


def test_get_index_stocks_raises_with_avoid_future_data(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["avoid_future_data"] = True
    monkeypatch.setattr(data.ak, "index_stock_cons", _fake_index_cons)

    with pytest.raises(ValueError, match="avoid_future_data"):
        data.get_index_stocks("000300")


def test_get_index_stocks_silent_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "index_stock_cons", _fake_index_cons)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_index_stocks("000300")
    assert len(result) == 2


def test_get_index_stocks_silent_in_paper_session(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True
    monkeypatch.setattr(data.ak, "index_stock_cons", _fake_index_cons)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_index_stocks("000300")
    assert len(result) == 2


def test_get_index_weights_warns_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(
        data.ak,
        "index_stock_cons_weight_csindex",
        lambda symbol: pd.DataFrame(
            {"成分券代码": ["601398"], "成分券名称": ["工商银行"], "权重": [3.5]}
        ),
    )

    with pytest.warns(FutureWarning, match="survivorship"):
        result = data.get_index_weights("000300")
    assert list(result["code"]) == ["601398"]


def test_get_index_weights_silent_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(
        data.ak,
        "index_stock_cons_weight_csindex",
        lambda symbol: pd.DataFrame(
            {"成分券代码": ["601398"], "成分券名称": ["工商银行"], "权重": [3.5]}
        ),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_index_weights("000300")
    assert len(result) == 1


# ── get_tick_data snapshot warning ───────────────────────────────────────────


def _fake_tick_tx_js(symbol):
    return pd.DataFrame(
        {
            "时间": ["14:55:00", "14:55:03"],
            "价格": [10.0, 10.01],
            "成交量": [100, 200],
            "成交额": [1000.0, 2002.0],
        }
    )


def test_get_tick_data_warns_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "stock_zh_a_tick_tx_js", _fake_tick_tx_js)

    with pytest.warns(FutureWarning, match="tick snapshot"):
        result = data.get_tick_data("600536", trade_date="2024-01-02")
    assert len(result) == 2


def test_get_tick_data_silent_outside_session(monkeypatch, isolated_session):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_zh_a_tick_tx_js", _fake_tick_tx_js)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = data.get_tick_data("600536")
    assert len(result) == 2


# ── get_north_money_flow clamping ────────────────────────────────────────────


def _fake_hsgt_hist(symbol):
    return pd.DataFrame(
        {
            "日期": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "当日成交净买额": [1.0, 2.0, 3.0, 4.0],
            "买入成交额": [10.0, 11.0, 12.0, 13.0],
            "卖出成交额": [9.0, 9.5, 10.0, 10.5],
        }
    )


def test_get_north_money_flow_clamped_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "stock_hsgt_hist_em", _fake_hsgt_hist)

    result = data.get_north_money_flow(
        start_date="2024-01-02", end_date="2024-01-10"
    )
    assert sorted(result["date"]) == ["2024-01-02", "2024-01-03"]


def test_get_north_money_flow_beyond_cutoff_returns_empty_without_network(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    def _forbidden(**kwargs):
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(data.ak, "stock_hsgt_hist_em", _forbidden)
    result = data.get_north_money_flow(
        start_date="2024-01-10", end_date="2024-01-20"
    )
    assert result.empty


def test_get_north_money_flow_unrestricted_outside_session(
    monkeypatch, isolated_session
):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_hsgt_hist_em", _fake_hsgt_hist)

    result = data.get_north_money_flow(
        start_date="2024-01-02", end_date="2024-01-10"
    )
    assert sorted(result["date"]) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]


# ── get_margin_data clamping ─────────────────────────────────────────────────


def _fake_margin_market():
    return pd.DataFrame(
        {
            "日期": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "融资余额": [1.0e8, 1.1e8, 1.2e8, 1.3e8],
            "融资买入额": [1.0e7, 1.1e7, 1.2e7, 1.3e7],
            "融券余额": [5.0e7, 5.1e7, 5.2e7, 5.3e7],
        }
    )


def test_get_margin_data_clamped_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data.ak, "macro_china_market_margin_sh", _fake_margin_market)
    monkeypatch.setattr(data.ak, "macro_china_market_margin_sz", _fake_margin_market)

    result = data.get_margin_data(start_date="2024-01-02", end_date="2024-01-10")
    assert sorted(result["date"]) == ["2024-01-02", "2024-01-03"]


def test_get_margin_data_beyond_cutoff_returns_empty_without_network(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    def _forbidden():
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(data.ak, "macro_china_market_margin_sh", _forbidden)
    monkeypatch.setattr(data.ak, "macro_china_market_margin_sz", _forbidden)
    result = data.get_margin_data(start_date="2024-01-10", end_date="2024-01-20")
    assert result.empty


def test_get_margin_data_unrestricted_outside_session(
    monkeypatch, isolated_session
):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "macro_china_market_margin_sh", _fake_margin_market)
    monkeypatch.setattr(data.ak, "macro_china_market_margin_sz", _fake_margin_market)

    result = data.get_margin_data(start_date="2024-01-02", end_date="2024-01-10")
    assert sorted(result["date"]) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]


# ── get_limit_up_down_stats clamping ─────────────────────────────────────────


def _patch_limit_up_down_fakes(monkeypatch, fetched):
    def _fake_zt_pool(date):
        fetched.append(date)
        return pd.DataFrame({"代码": ["600001"]})

    monkeypatch.setattr(data.ak, "stock_zt_pool_em", _fake_zt_pool)
    monkeypatch.setattr(
        data.ak, "stock_zt_pool_dtgc_em", lambda date: pd.DataFrame()
    )
    all_days = [
        dt.date(2024, 1, 2),
        dt.date(2024, 1, 3),
        dt.date(2024, 1, 4),
        dt.date(2024, 1, 5),
    ]
    monkeypatch.setattr(
        data,
        "get_trade_days",
        lambda start, end: [d for d in all_days if start <= d <= end],
    )


def test_get_limit_up_down_stats_clamped_in_backtest(monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    fetched: list = []
    _patch_limit_up_down_fakes(monkeypatch, fetched)

    result = data.get_limit_up_down_stats(
        start_date="2024-01-02", end_date="2024-01-10"
    )
    assert list(result["date"]) == ["2024-01-02", "2024-01-03"]
    # Days beyond the simulated clock must never hit the provider.
    assert sorted(fetched) == ["20240102", "20240103"]


def test_get_limit_up_down_stats_beyond_cutoff_returns_empty_without_network(
    monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    def _forbidden(date):
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(data.ak, "stock_zt_pool_em", _forbidden)

    def _no_calendar(start, end):
        raise AssertionError("calendar must not be touched either")

    monkeypatch.setattr(data, "get_trade_days", _no_calendar)
    result = data.get_limit_up_down_stats(
        start_date="2024-01-10", end_date="2024-01-20"
    )
    assert result.empty


def test_get_limit_up_down_stats_unrestricted_outside_session(
    monkeypatch, isolated_session
):
    isolated_session._context = None
    fetched: list = []
    _patch_limit_up_down_fakes(monkeypatch, fetched)

    result = data.get_limit_up_down_stats(
        start_date="2024-01-02", end_date="2024-01-10"
    )
    assert list(result["date"]) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]


# ── Snapshot API warnings (FIXGAP-2): get_valuation / get_extras /
#    get_concept_stocks / get_industry_stocks ─────────────────────────────────


def _fake_spot_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "代码": ["601398", "600536"],
            "名称": ["工商银行", "中国软件"],
            "最新价": [10.0, 20.0],
            "涨跌幅": [1.0, 2.0],
            "成交量": [1e6, 2e6],
            "成交额": [1e7, 4e7],
            "最高": [10.5, 20.5],
            "最低": [9.5, 19.5],
            "今开": [9.9, 19.9],
            "昨收": [9.9, 19.8],
            "市盈率-动态": [5.0, 30.0],
            "市净率": [0.8, 3.0],
            "总市值": [1e12, 2e10],
            "流通市值": [1e12, 2e10],
            "换手率": [0.5, 1.2],
        }
    )


def _fake_board_cons(symbol) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "代码": ["601398", "600536"],
            "名称": ["工商银行", "中国软件"],
            "最新价": [10.0, 20.0],
            "涨跌幅": [1.0, 2.0],
            "成交量": [1e6, 2e6],
            "成交额": [1e7, 4e7],
            "换手率": [0.5, 1.2],
            "市盈率-动态": [5.0, 30.0],
            "市净率": [0.8, 3.0],
            "总市值": [1e12, 2e10],
            "流通市值": [1e12, 2e10],
            "振幅": [2.0, 3.0],
            "最高": [10.5, 20.5],
            "最低": [9.5, 19.5],
            "今开": [9.9, 19.9],
            "昨收": [9.9, 19.8],
        }
    )


_SNAPSHOT_APIS = [
    "get_valuation",
    "get_extras",
    "get_concept_stocks",
    "get_industry_stocks",
    "get_current_data",
    "get_current_data_object",
    "scan_market",
    "get_financial_screen",
    "get_restriction_release",
]


def _install_snapshot_mocks(monkeypatch):
    monkeypatch.setattr(data, "_get_spot_data", lambda: _fake_spot_df())
    monkeypatch.setattr(data.ak, "stock_board_concept_cons_em", _fake_board_cons)
    monkeypatch.setattr(data.ak, "stock_board_industry_cons_em", _fake_board_cons)
    monkeypatch.setattr(
        data.ak,
        "stock_restricted_release_detail_em",
        lambda start_date, end_date: pd.DataFrame(
            {
                "股票代码": ["601398"],
                "股票简称": ["工商银行"],
                "解禁时间": ["2024-02-01"],
                "解禁数量": [1e6],
                "实际解禁市值": [1e7],
                "占解禁前流通市值比例": [0.5],
            }
        ),
    )


def _call_snapshot_api(api_name: str):
    if api_name == "get_valuation":
        return data.get_valuation("601398")
    if api_name == "get_extras":
        return data.get_extras("is_st", ["601398"])
    if api_name == "get_concept_stocks":
        return data.get_concept_stocks("机器人")
    if api_name == "get_industry_stocks":
        return data.get_industry_stocks("酿酒行业")
    if api_name == "get_current_data":
        return data.get_current_data()
    if api_name == "get_current_data_object":
        return stock_query.get_current_data_object()
    if api_name == "scan_market":
        return data.scan_market(
            min_price=5, min_pct_change=0, max_pct_change=10, max_pe=100
        )
    if api_name == "get_financial_screen":
        return data.get_financial_screen()
    if api_name == "get_restriction_release":
        return data.get_restriction_release(days=30)
    raise AssertionError(f"unknown snapshot api {api_name}")


@pytest.mark.parametrize("api_name", _SNAPSHOT_APIS)
def test_snapshot_api_warns_in_backtest(api_name, monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    _install_snapshot_mocks(monkeypatch)

    with pytest.warns(FutureWarning, match="snapshot|survivorship|announcement"):
        result = _call_snapshot_api(api_name)
    assert len(result) > 0  # warning must not swallow the payload


@pytest.mark.parametrize("api_name", _SNAPSHOT_APIS)
def test_snapshot_api_raises_with_avoid_future_data(
    api_name, monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["avoid_future_data"] = True
    _install_snapshot_mocks(monkeypatch)

    with pytest.raises(ValueError, match="avoid_future_data"):
        _call_snapshot_api(api_name)


@pytest.mark.parametrize("api_name", _SNAPSHOT_APIS)
def test_snapshot_api_silent_outside_session(api_name, monkeypatch, isolated_session):
    isolated_session._context = None
    _install_snapshot_mocks(monkeypatch)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = _call_snapshot_api(api_name)
    assert len(result) > 0


@pytest.mark.parametrize("api_name", _SNAPSHOT_APIS)
def test_snapshot_api_silent_in_paper_session(api_name, monkeypatch, isolated_session):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True
    _install_snapshot_mocks(monkeypatch)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = _call_snapshot_api(api_name)
    assert len(result) > 0


def test_get_current_data_object_warns_once_under_its_own_name(
    monkeypatch, isolated_session
):
    """The object entry point routes through the check-free impl: exactly
    one FutureWarning named ``get_current_data_object``, not a duplicate
    from the inner ``get_current_data`` path."""
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    _install_snapshot_mocks(monkeypatch)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = stock_query.get_current_data_object()

    assert len(result) == 2
    pit_warnings = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert len(pit_warnings) == 1
    assert "get_current_data_object" in str(pit_warnings[0].message)


# ── check_golden_cross history truncation (sweep closure) ────────────────────


def _fake_hist_with_cross(symbol, period, adjust):
    # 40 business days 2024-01-02..2024-02-26. Slow decline (fast MA below
    # slow MA throughout), then a single jump to 12.0 on the final day:
    # the fast MA crosses above the slow MA exactly on 2024-02-26 — so the
    # cross is detectable only when that last day is visible.
    idx = pd.bdate_range("2024-01-02", periods=40)
    closes = [10.0 - 0.05 * i for i in range(39)] + [12.0]
    return pd.DataFrame({"日期": idx.strftime("%Y-%m-%d"), "收盘": closes})


def test_check_golden_cross_truncated_in_backtest(monkeypatch, isolated_session):
    # Clock at 2024-02-26 09:30 -> cutoff 02-25; the jump day (02-26) is
    # invisible, so no cross can be detected.
    _set_clock(isolated_session, dt.datetime(2024, 2, 26, 9, 30))
    monkeypatch.setattr(data.ak, "stock_zh_a_hist", _fake_hist_with_cross)

    assert not data.check_golden_cross("601398")


def test_check_golden_cross_unrestricted_outside_session(
    monkeypatch, isolated_session
):
    isolated_session._context = None
    monkeypatch.setattr(data.ak, "stock_zh_a_hist", _fake_hist_with_cross)

    assert data.check_golden_cross("601398")


# ── load_stock_local PIT truncation (FIXGAP-1) ───────────────────────────────


@pytest.fixture()
def local_csv_dir(tmp_path, monkeypatch):
    """A tmp local-data dir holding one valid shares-unit CSV + sidecar."""
    monkeypatch.setattr(data_cache, "_LOCAL_DATA_DIR", str(tmp_path))
    idx = pd.bdate_range("2024-01-02", periods=7)  # 2024-01-02 .. 2024-01-10
    df = pd.DataFrame(
        {
            "open": [10.0] * 7,
            "high": [10.5] * 7,
            "low": [9.5] * 7,
            "close": [10.0] * 7,
            "volume": [1_000_000.0] * 7,  # shares
            "money": [10_000_000.0] * 7,
        },
        index=idx,
    )
    csv_path = tmp_path / "601398_daily_qfq.csv"
    df.to_csv(csv_path)
    csv_path.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "version": 2,
                "volume_unit": "shares",
                "covered_start": "20240102",
                "covered_end": "20240110",
            }
        )
    )
    return tmp_path


def test_load_stock_local_truncates_to_t_minus_1_in_backtest(
    local_csv_dir, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    result = data_cache.load_stock_local("601398", "2024-01-02", "2024-01-10")
    assert result is not None
    assert result.index.max() == pd.Timestamp("2024-01-03")


def test_load_stock_local_includes_today_after_close(local_csv_dir, isolated_session):
    # Post-close callback / post-loop: the day's bar is public.
    _set_clock(
        isolated_session,
        dt.datetime(2024, 1, 4, 15, 0),
        recorded=[dt.date(2024, 1, 4)],
    )

    result = data_cache.load_stock_local("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-04")


def test_load_stock_local_unrestricted_outside_session(
    local_csv_dir, isolated_session
):
    isolated_session._context = None

    result = data_cache.load_stock_local("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-10")


def test_load_stock_local_unrestricted_in_paper_session(
    local_csv_dir, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True

    result = data_cache.load_stock_local("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-10")


def test_load_stock_local_engine_read_exempt_via_unrestricted_fetch(
    local_csv_dir, isolated_session
):
    # Engine preload / post-loop benchmark reads wrap load_stock_local in
    # _unrestricted_fetch and must keep the full requested range.
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    with _state._unrestricted_fetch():
        result = data_cache.load_stock_local("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-10")
    assert isolated_session._full_range_fetch_depth == 0


def test_load_stock_local_pure_future_rows_return_none_in_backtest(
    local_csv_dir, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))

    # Coverage gate passes (request inside saved range), but every row is
    # beyond the simulated clock — same "no data" semantics as an empty
    # requested-range filter.
    assert data_cache.load_stock_local("601398", "2024-01-05", "2024-01-10") is None


# ── fetch_cached disk-hit PIT truncation (FIXGAP-8) ──────────────────────────


@pytest.fixture()
def disk_cache_dir(tmp_path, monkeypatch):
    """A tmp disk cache holding one full-range frame for 601398."""
    monkeypatch.setattr(data_cache, "_CACHE_DIR", str(tmp_path))
    # Force the pickle path so the fixture needs no parquet engine.
    monkeypatch.setattr(data_cache, "_parquet_engine", lambda: None)
    data_cache._save_to_disk(
        _daily_frame(),
        "601398",
        "qfq",
        requested_start="20240102",
        requested_end="20240110",
    )
    return tmp_path


def _network_forbidden(*args, **kwargs):
    raise AssertionError("network must not be touched on a disk hit")


def test_fetch_cached_disk_hit_truncates_to_t_minus_1_in_backtest(
    disk_cache_dir, monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    monkeypatch.setattr(data, "fetch_stock_data", _network_forbidden)

    result = data_cache.fetch_cached("601398", "2024-01-02", "2024-01-10")
    assert not result.empty
    assert result.index.max() == pd.Timestamp("2024-01-03")


def test_fetch_cached_disk_hit_unrestricted_outside_session(
    disk_cache_dir, monkeypatch, isolated_session
):
    isolated_session._context = None
    monkeypatch.setattr(data, "fetch_stock_data", _network_forbidden)

    result = data_cache.fetch_cached("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-10")


def test_fetch_cached_disk_hit_unrestricted_in_paper_session(
    disk_cache_dir, monkeypatch, isolated_session
):
    _set_clock(isolated_session, dt.datetime(2024, 1, 4, 9, 30))
    isolated_session._options["_is_paper_trading"] = True
    monkeypatch.setattr(data, "fetch_stock_data", _network_forbidden)

    result = data_cache.fetch_cached("601398", "2024-01-02", "2024-01-10")
    assert result.index.max() == pd.Timestamp("2024-01-10")
