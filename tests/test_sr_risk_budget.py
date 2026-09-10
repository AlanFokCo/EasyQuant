"""Behavioral regressions for risk sizing and the real daily fill lifecycle."""

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eqlib import log
from eqlib.strategies.sr_risk_budget import (
    SRRiskConfig,
    make_sr_risk_budget_strategy,
    market_allows_entry,
    plan_entry,
    size_entry,
    valid_bars,
)
from examples._defaults import DEFAULT_ORDER_COST, INDEX_HS300

spec = importlib.util.spec_from_file_location(
    "sr_example", Path(__file__).parents[1] / "examples/25_sr_risk_budget.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CODE = "601398"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("strategy regression tests must stay offline")

    monkeypatch.setattr("requests.sessions.Session.request", reject)


def frame_from_closes(closes, dates):
    close = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(len(close), 1e7),
        },
        index=dates,
    )


@pytest.fixture
def frames():
    dates = runner.exchange_calendar("2023-01-01", "2024-03-31")[:190]
    closes = np.r_[
        np.linspace(8, 10, 154),
        [10.7, 10.5, 10.4, 10.3, 10.3, 10.4],
        np.linspace(10.4, 13.3, 30),
    ]
    stock = frame_from_closes(closes, dates)
    stock.iloc[154, stock.columns.get_loc("volume")] = 2e7
    stock.iloc[159, stock.columns.get_loc("low")] = 10.18
    benchmark = frame_from_closes(np.linspace(1000, 1400, len(dates)), dates)
    return {CODE: stock, INDEX_HS300: benchmark}


def run(frames, end_idx=189, config=None, codes=None):
    log.set_quiet(True)
    dates = frames[CODE].index
    return runner.run_snapshot(
        frames,
        codes or [CODE],
        str(dates[159].date()),
        str(dates[end_idx].date()),
        1e6,
        config or SRRiskConfig(),
        DEFAULT_ORDER_COST,
    )[0]


def set_bar(frame, i, opening, close, volume=1e7):
    frame.iloc[i] = [
        opening,
        max(opening, close) + 0.01,
        min(opening, close) - 0.01,
        close,
        volume,
    ]


def test_retest_uses_pre_breakout_resistance(frames):
    frame = frames[CODE].iloc[:160]
    plan = plan_entry(frame, SRRiskConfig())
    assert plan is not None and plan.kind == "breakout_retest"
    assert plan.support == pytest.approx(10.2)
    assert plan.reward_risk == pytest.approx(3)
    assert plan.stop < plan.support < plan.limit < plan.target


def test_support_bounce_and_nearby_resistance_rejection(frames):
    frame = frame_from_closes(
        np.r_[np.linspace(8, 10, 139), np.full(20, 10), 10.2], frames[CODE].index[:160]
    )
    frame.iloc[-10, frame.columns.get_loc("high")] = 12
    frame.iloc[-1, frame.columns.get_loc("low")] = 9.9
    config = replace(SRRiskConfig(), level_window=20, trend_window=20)
    assert plan_entry(frame, config).kind == "support_bounce"
    frame.iloc[-10, frame.columns.get_loc("high")] = 10.2
    assert plan_entry(frame, config) is None


@pytest.mark.parametrize(
    "damage", ["nan", "duplicate", "reverse", "bad_ohlc", "zero_price"]
)
def test_invalid_bars_do_not_create_signals(frames, damage):
    frame = frames[CODE].iloc[:160].copy()
    if damage == "nan":
        frame.iloc[-1, 0] = np.nan
    elif damage == "duplicate":
        frame.index = list(frame.index[:-1]) + [frame.index[-2]]
    elif damage == "reverse":
        frame = frame.iloc[::-1]
    elif damage == "bad_ohlc":
        frame.iloc[-1, 1] = 0.1
    else:
        frame.iloc[-1, 3] = 0
    assert not valid_bars(frame, 160)
    assert plan_entry(frame, SRRiskConfig()) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"risk_per_trade": float("nan")},
        {"max_positions": 1.5},
        {"risk_per_trade": 0.5},
        {"min_stop_pct": 0.2},
        {"slippage": 0},
        {"max_exposure": 1},
        {"max_positions": True},
    ],
)
def test_invalid_config_is_rejected(overrides):
    with pytest.raises(ValueError):
        SRRiskConfig(**overrides)


def test_missing_or_weak_market_blocks_new_entries(frames):
    assert not market_allows_entry(pd.DataFrame(), SRRiskConfig())
    frames[INDEX_HS300]["close"] = 2000 - frames[INDEX_HS300].close
    frame = frames[INDEX_HS300]
    frame["open"], frame["high"], frame["low"] = (
        frame.close,
        frame.close + 0.2,
        frame.close - 0.2,
    )
    assert not run(frames)["trade_log"]


def test_fee_inclusive_lot_sizing_and_portfolio_capacity(frames):
    cfg = SRRiskConfig()
    plan = plan_entry(frames[CODE].iloc[:160], cfg)
    shares = size_entry(plan, 1e6, 1e6, 0, 0, cfg, DEFAULT_ORDER_COST)
    assert shares > 0 and shares % 100 == 0
    worst_loss = (
        shares * (plan.limit - plan.stop + plan.limit * (0.0005 + 0.001 + 0.002)) + 10
    )
    assert worst_loss <= 1e6 * cfg.risk_per_trade
    assert shares * plan.limit <= 1e6 * cfg.max_stock_weight
    assert size_entry(plan, 1e6, 500, 0, 0, cfg, DEFAULT_ORDER_COST) == 0
    assert size_entry(plan, 1e6, 1e6, 600_000, 0, cfg, DEFAULT_ORDER_COST) == 0
    assert size_entry(plan, 1e6, 1e6, 0, 20_000, cfg, DEFAULT_ORDER_COST) == 0


def test_real_engine_uses_next_open_and_later_day_sales(frames):
    result = run(frames)
    trades = result["trade_log"]
    assert [trade["type"] for trade in trades[:2]] == ["BUY", "SELL"]
    assert trades[0]["date"] == frames[CODE].index[160].date()
    assert trades[0]["price"] == pytest.approx(frames[CODE].open.iloc[160] * 1.001)
    assert trades[1]["date"] > trades[0]["date"]
    assert all(trade["amount"] % 100 == 0 for trade in trades)
    assert result["context"].portfolio.available_cash >= 0
    assert all(trade["commission"] >= 5 for trade in trades)


def test_future_mutation_cannot_change_earlier_signals_or_fills(frames):
    first = run(frames, end_idx=168)
    modified = {code: frame.copy() for code, frame in frames.items()}
    for frame in modified.values():
        frame.iloc[169:, :4] *= 0.5
    second = run(modified)
    cutoff = frames[CODE].index[168].date()

    def past_trades(result):
        return [
            {k: v for k, v in trade.items() if k != "order_id"}
            for trade in result["trade_log"]
            if trade["date"] <= cutoff
        ]

    assert past_trades(first) == past_trades(second)
    assert first["context"].sr_risk_budget.events == [
        event
        for event in second["context"].sr_risk_budget.events
        if event["date"] <= str(cutoff)
    ]


def test_unfilled_gap_up_entry_expires_without_phantom_holding(frames):
    set_bar(frames[CODE], 160, 11.44, 11.44)
    result = run(frames, end_idx=160)
    assert not result["trade_log"]
    assert not result["context"].sr_risk_budget.holdings
    assert not result["session"]._pending_orders


def test_partial_buy_cancels_remainder_and_tracks_only_actual_holding(frames):
    frames[CODE].iloc[160, frames[CODE].columns.get_loc("volume")] = 1000
    result = run(frames, end_idx=161)
    buys = [trade for trade in result["trade_log"] if trade["type"] == "BUY"]
    assert len(buys) == 1 and buys[0]["amount"] == 100
    assert len(result["context"].sr_risk_budget.holdings) == 1
    assert not result["session"]._pending_orders


def test_gap_below_stop_cannot_be_sold_on_buy_day(frames):
    set_bar(frames[CODE], 160, 9.5, 9.5)
    set_bar(frames[CODE], 161, 9.4, 9.4)
    trades = run(frames, end_idx=161)["trade_log"]
    assert [trade["type"] for trade in trades] == ["BUY", "SELL"]
    assert trades[1]["date"] > trades[0]["date"]
    assert trades[1]["price"] < plan_entry(frames[CODE].iloc[:160], SRRiskConfig()).stop


def test_limit_down_exit_is_retried_until_a_real_fill(frames):
    set_bar(frames[CODE], 160, 10.3, 9.7)
    set_bar(frames[CODE], 161, 8.73, 8.73)
    set_bar(frames[CODE], 162, 8.8, 8.9)
    result = run(frames, end_idx=162)
    sells = [trade for trade in result["trade_log"] if trade["type"] == "SELL"]
    assert len(sells) == 1 and sells[0]["date"] == frames[CODE].index[162].date()
    exits = [
        event
        for event in result["context"].sr_risk_budget.events
        if event["action"] == "exit_order"
    ]
    assert len(exits) == 2
    assert not result["context"].portfolio.positions


def test_simultaneous_signals_reserve_cash_gross_and_total_risk(frames):
    codes = [CODE, "600036", "600519", "600276", "000333", "000651"]
    for code in codes:
        frames[code] = frames[CODE].copy()
    result = run(frames, end_idx=160, codes=codes)
    orders = [
        event
        for event in result["context"].sr_risk_budget.events
        if event["action"] == "entry_order"
    ]
    assert 1 < len(orders) <= 5
    assert (
        sum(event["shares"] * (event["limit"] - event["stop"]) for event in orders)
        < 20_000
    )
    assert sum(event["shares"] * event["limit"] for event in orders) <= 600_000
    assert result["context"].portfolio.available_cash >= 0


def test_halt_liquidates_then_requires_flat_cooldown_and_market_recovery(frames):
    set_bar(frames[CODE], 160, 10.3, 9.7)
    set_bar(frames[CODE], 161, 9.8, 9.8)
    result = run(
        frames,
        end_idx=165,
        config=replace(SRRiskConfig(), halt_drawdown=0.0001, halt_days=3),
    )
    events = result["context"].sr_risk_budget.events
    halt = next(event for event in events if event["action"] == "portfolio_halt")
    resume = next(event for event in events if event["action"] == "portfolio_resume")
    assert halt["date"] == str(frames[CODE].index[160].date())
    assert resume["date"] >= str(frames[CODE].index[163].date())
    assert not any(
        event["action"] == "entry_order"
        and halt["date"] <= event["date"] < resume["date"]
        for event in events
    )


def test_csv_preflight_rejects_truncation_and_missing_benchmark_days(tmp_path, frames):
    dates = frames[CODE].index
    for code, frame in frames.items():
        frame.to_csv(tmp_path / f"{code}_daily_qfq.csv")
    # First 160 bars are warm-up; the request starts after them.
    args = (
        tmp_path,
        list(frames),
        str(dates[160].date()),
        str(dates[-1].date()),
        SRRiskConfig(),
    )
    loaded, manifest = runner.read_inputs(*args)
    assert len(manifest[CODE]["sha256"]) == 64 and len(loaded) == 2
    frames[INDEX_HS300].drop(dates[170]).to_csv(
        tmp_path / f"{INDEX_HS300}_daily_qfq.csv"
    )
    with pytest.raises(ValueError, match="benchmark is missing"):
        runner.read_inputs(*args)
    frames[INDEX_HS300].to_csv(tmp_path / f"{INDEX_HS300}_daily_qfq.csv")
    frames[CODE].iloc[:-1].to_csv(tmp_path / f"{CODE}_daily_qfq.csv")
    with pytest.raises(ValueError, match="history ends"):
        runner.read_inputs(*args)


def test_only_main_board_universe_is_accepted():
    for codes in ([], ["688001"], ["300750"], ["920001"], ["not-a-stock"]):
        with pytest.raises(ValueError):
            make_sr_risk_budget_strategy(codes)


@pytest.mark.parametrize("download", [False, True])
def test_cli_writes_complete_synthetic_and_cost_stress_reports(
    tmp_path, frames, monkeypatch, download
):
    from examples._defaults import STOCKS

    dates = frames[CODE].index
    source_frames = {}
    expected_volumes = {}
    for code in [*STOCKS.values(), INDEX_HS300]:
        frame = frames[INDEX_HS300 if code == INDEX_HS300 else CODE].copy()
        extra = frame.iloc[:1].copy()
        extra.index = pd.DatetimeIndex([pd.Timestamp("2022-12-30")])
        frame = pd.concat([extra, frame])
        expected_volumes[code] = frame.volume.copy()
        if download:
            if code != INDEX_HS300:
                frame["volume"] /= 100.0
            source_frames[code] = frame
        else:
            frame.to_csv(tmp_path / f"{code}_daily_qfq.csv")
    if download:
        monkeypatch.setattr(
            runner, "fetch_stock_data", lambda code, *args, **kwargs: source_frames[code]
        )
    output = tmp_path / "out"
    assert (
        runner.main(
            [
                *(["--download"] if download else []),
                "--data-dir",
                str(tmp_path),
                "--output",
                str(output),
                "--synthetic",
                "--stress",
                "--start",
                str(dates[159].date()),
                "--end",
                str(dates[-1].date()),
            ]
        )
        == 0
    )
    payload = json.loads((output / "summary.json").read_text())
    for code, expected in expected_volumes.items():
        saved = pd.read_csv(
            tmp_path / f"{code}_daily_qfq.csv", index_col=0, parse_dates=True
        )
        pd.testing.assert_series_equal(saved.volume, expected, check_names=False)
        if download:
            multiplier = 1 if code == INDEX_HS300 else 100
            pd.testing.assert_series_equal(
                source_frames[code].volume * multiplier, expected
            )
    assert payload["evidence"] == "synthetic_execution_test"
    assert payload["profitability_proven"] is False
    assert payload["full_period"]["fill_count"] > 0
    assert payload["cost_stress"]["paid_costs"] > payload["full_period"]["paid_costs"]
    assert (
        payload["cost_stress"]["total_return"] < payload["full_period"]["total_return"]
    )
    assert payload["full_period"]["total_return"] == pytest.approx(
        payload["full_period"]["core_total_return"]
    )
    assert {"equity.csv", "trades.csv", "events.csv"} <= {
        path.name for path in output.iterdir()
    }


def test_eligibility_and_daily_only_contract(frames):
    from eqlib import run_backtest

    dates = frames[CODE].index
    initialize = make_sr_risk_budget_strategy([CODE], eligible=lambda code, date: False)
    with runner.local_prices(frames):
        result = run_backtest(
            initialize,
            str(dates[159].date()),
            str(dates[165].date()),
            starting_cash=1e6,
            use_local=True,
        )
        assert not result["trade_log"]
        with pytest.raises(ValueError, match="daily backtests only"):
            run_backtest(
                initialize,
                str(dates[159].date()),
                str(dates[165].date()),
                frequency="minute",
                use_local=True,
            )
