"""Tests for the A-share industry leader support/resistance strategy."""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from eqlib.strategies.ashare_sr_leader import (
    CandidateChannel,
    DEFAULT_LEADER_UNIVERSE,
    PortfolioRiskState,
    PortfolioRiskTracker,
    RobustCandidate,
    build_fallback_snapshot,
    drawdown_risk_multiplier,
    final_risk_budget,
    filter_fallback_by_volatility,
    industry_for_code,
    liquidity_capped_target_value,
    liquidity_capped_rebalance_target_value,
    MarketState,
    StrategyKind,
    StrategyParams,
    build_signal_snapshot,
    choose_portfolio_candidates,
    classify_market,
    compute_atr,
    combine_robust_candidates,
    get_default_leader_universe,
    is_excluded_board,
    market_exposure,
    market_volatility_factor,
    make_initialize,
    rolling_levels,
    robust_target_weights,
    reduce_portfolio_to_budget,
    rebalance_robust_portfolio,
    risk_data_complete,
    score_snapshot,
    score_fallback_snapshot,
    select_fallback_candidates,
    select_robust_candidates,
    should_exit_trailing_drawdown,
    should_rebalance_position,
    target_weights,
    update_portfolio_risk,
    _risk_review,
)
from scripts.run_ashare_sr_leader_research import (
    _benchmark_total_return,
    audit_rows,
    BENCHMARK,
    candidate_param_grid,
    END_DATE,
    period_interpretation,
    render_html_report,
    START_DATE,
    stability_score,
    SUB_PERIODS,
    _profile_name,
    write_eqlib_html_report,
    write_outputs,
    STARTING_CASH,
)


def _frame(close_values):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1000, 2000, len(close)),
        }
    )


def test_excludes_star_market_and_bse_style_codes():
    assert is_excluded_board("688001")
    assert is_excluded_board("830799")
    assert is_excluded_board("430047")
    assert is_excluded_board("920002")
    assert not is_excluded_board("600519")
    assert not is_excluded_board("300750")


def test_default_universe_has_industry_leaders_without_excluded_boards():
    codes = get_default_leader_universe()
    assert len(codes) >= 60
    assert len(codes) == len(set(codes))
    assert "600519" in codes
    assert "300750" in codes
    assert all(not is_excluded_board(code) for code in codes)
    assert all(leader.industry for leader in DEFAULT_LEADER_UNIVERSE)


def test_compute_atr_uses_true_range_components():
    frame = pd.DataFrame(
        {
            "high": [10.0, 13.0, 12.0],
            "low": [9.0, 11.0, 8.0],
            "close": [9.5, 12.0, 9.0],
        }
    )
    result = compute_atr(frame, period=2)
    # TR values: 1.0, max(2, 3.5, 1.5)=3.5, max(4, 0, 4)=4.0
    assert result.iloc[0] == 1.0
    assert result.iloc[1] == 2.25
    assert result.iloc[2] == 3.75


def test_rolling_levels_use_previous_completed_window():
    frame = _frame([10, 11, 12, 9, 14, 8, 13])
    resistance, support = rolling_levels(frame, window=5)
    assert resistance == frame["high"].iloc[-6:-1].max()
    assert support == frame["low"].iloc[-6:-1].min()


def _ohlcv_from_close(close_values, volume_start=1_000_000, volume_end=2_000_000):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.linspace(volume_start, volume_end, len(close)),
        }
    )


def test_robust_defaults_leave_baseline_disabled():
    params = StrategyParams()

    assert not params.robust_enabled
    assert params.min_primary_candidates == 5
    assert params.fallback_exposure_cap == 0.25
    assert params.fallback_trailing_drawdown == 0.10
    assert params.target_annual_volatility == 0.18


def test_market_volatility_factor_is_bounded_and_never_leverages():
    params = StrategyParams(
        market_volatility_window=20,
        target_annual_volatility=0.18,
        market_volatility_floor=0.55,
    )
    quiet = _ohlcv_from_close(list(np.linspace(100, 103, 40)))
    noisy_returns = np.tile([0.04, -0.035], 20)
    noisy_close = 100 * np.cumprod(1 + noisy_returns)
    noisy = _ohlcv_from_close(noisy_close)

    assert market_volatility_factor(quiet, params) == 1.0
    assert 0.55 <= market_volatility_factor(noisy, params) < 1.0
    assert market_volatility_factor(noisy.iloc[:10], params) is None
    budget = final_risk_budget(
        MarketState.STRONG,
        volatility_factor=0.80,
        risk_state=PortfolioRiskState.DEFENSIVE,
        params=StrategyParams(strong_market_exposure=0.90),
    )
    assert budget == pytest.approx(0.36)


def test_final_risk_budget_preserves_clamped_product_precision():
    params = StrategyParams(strong_market_exposure=0.90)
    volatility_factor = 0.8123456789012345
    expected = params.strong_market_exposure * volatility_factor

    budget = final_risk_budget(
        MarketState.STRONG,
        volatility_factor=volatility_factor,
        risk_state=PortfolioRiskState.NORMAL,
        params=params,
    )

    assert budget == expected


@pytest.mark.parametrize(
    ("total_value", "expected_state"),
    [
        (920_000, PortfolioRiskState.CAUTIOUS),
        (880_000, PortfolioRiskState.DEFENSIVE),
        (840_000, PortfolioRiskState.PROTECT),
    ],
)
def test_portfolio_risk_downgrades_at_exact_threshold(
    total_value, expected_state
):
    tracker = PortfolioRiskTracker.initial(1_000_000)

    updated = update_portfolio_risk(
        tracker,
        total_value,
        MarketState.NEUTRAL,
        StrategyParams(),
        allow_recovery=False,
    )

    assert updated.state is expected_state


def test_portfolio_risk_downgrades_immediately_at_each_threshold():
    params = StrategyParams()
    tracker = PortfolioRiskTracker.initial(1_000_000)

    cautious = update_portfolio_risk(
        tracker, 915_000, MarketState.NEUTRAL, params, allow_recovery=False
    )
    defensive = update_portfolio_risk(
        cautious, 875_000, MarketState.NEUTRAL, params, allow_recovery=False
    )
    protect = update_portfolio_risk(
        defensive, 835_000, MarketState.NEUTRAL, params, allow_recovery=False
    )

    assert cautious.state is PortfolioRiskState.CAUTIOUS
    assert defensive.state is PortfolioRiskState.DEFENSIVE
    assert protect.state is PortfolioRiskState.PROTECT
    assert drawdown_risk_multiplier(protect.state) == 0.25


def test_portfolio_risk_recovers_only_one_level_after_half_loss_recovery():
    params = StrategyParams()
    tracker = PortfolioRiskTracker(
        state=PortfolioRiskState.PROTECT,
        high_water=1_000_000,
        trough=830_000,
    )

    blocked = update_portfolio_risk(
        tracker,
        920_000,
        MarketState.WEAK,
        params,
        allow_recovery=True,
    )
    recovered = update_portfolio_risk(
        tracker,
        920_000,
        MarketState.NEUTRAL,
        params,
        allow_recovery=True,
    )

    assert blocked.state is PortfolioRiskState.PROTECT
    assert recovered.state is PortfolioRiskState.DEFENSIVE


def test_portfolio_risk_does_not_recover_with_incomplete_data():
    tracker = PortfolioRiskTracker(
        state=PortfolioRiskState.PROTECT,
        high_water=1_000_000,
        trough=830_000,
    )

    updated = update_portfolio_risk(
        tracker,
        920_000,
        MarketState.NEUTRAL,
        StrategyParams(),
        allow_recovery=True,
        data_complete=False,
    )

    assert updated.state is PortfolioRiskState.PROTECT


def test_fallback_snapshot_requires_intact_positive_trend():
    params = StrategyParams(
        robust_enabled=True,
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        fallback_trend_window=30,
        fallback_medium_window=15,
        fallback_trend_lookback=5,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close(list(np.linspace(10, 14, 70)))
    benchmark = _ohlcv_from_close(list(np.linspace(10, 11, 70)))

    snapshot = build_fallback_snapshot(stock, benchmark, params)

    assert snapshot is not None
    assert snapshot.relative_strength > 0
    assert snapshot.medium_trend_change >= 0
    assert snapshot.channel is CandidateChannel.FALLBACK
    assert score_fallback_snapshot(snapshot) > 0


def test_fallback_snapshot_rejects_falling_or_benchmark_lagging_stock():
    params = StrategyParams(
        robust_enabled=True,
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        fallback_trend_window=30,
        fallback_medium_window=15,
        fallback_trend_lookback=5,
        min_avg_volume=1,
    )
    falling = _ohlcv_from_close(list(np.linspace(14, 10, 70)))
    lagging = _ohlcv_from_close(list(np.linspace(10, 10.5, 70)))
    benchmark = _ohlcv_from_close(list(np.linspace(10, 12, 70)))

    assert build_fallback_snapshot(falling, benchmark, params) is None
    assert build_fallback_snapshot(lagging, benchmark, params) is None


def _robust_candidate(
    code: str,
    channel: CandidateChannel,
    score: float,
    volatility: float,
) -> RobustCandidate:
    return RobustCandidate(
        code=code,
        channel=channel,
        score=score,
        volatility=volatility,
        close=10.0,
        avg_volume=1_000_000.0,
    )


def test_fallback_filter_keeps_only_candidates_at_or_below_median_volatility():
    candidates = [
        _robust_candidate("600519", CandidateChannel.FALLBACK, 10.0, 0.01),
        _robust_candidate("300750", CandidateChannel.FALLBACK, 9.0, 0.02),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.04),
    ]

    filtered = filter_fallback_by_volatility(candidates)

    assert [item.code for item in filtered] == ["600519", "300750"]


def test_reduce_portfolio_to_budget_only_queues_smaller_targets(monkeypatch):
    queued = []
    monkeypatch.setattr(
        "eqlib.order_target_value",
        lambda code, value: queued.append((code, value)) or None,
    )
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={
                "600519": SimpleNamespace(total_value=300_000),
                "600036": SimpleNamespace(total_value=200_000),
            },
        ),
        sr_order_channels={},
        sr_code_channels={
            "600519": CandidateChannel.PRIMARY.value,
            "600036": CandidateChannel.FALLBACK.value,
        },
    )

    reduce_portfolio_to_budget(context, exposure_budget=0.25)

    assert queued == [("600519", 150_000), ("600036", 100_000)]


def test_missing_benchmark_or_volatility_data_blocks_risk_increase():
    assert not risk_data_complete(pd.DataFrame(), None)
    assert not risk_data_complete(_ohlcv_from_close([10, 11]), None)
    assert risk_data_complete(_ohlcv_from_close([10, 11]), 0.80)


def test_fallback_selection_uses_completed_ohlcv_and_skips_primary_codes(
    monkeypatch,
):
    history_calls = []
    snapshot = SimpleNamespace(
        volatility=0.02,
        close=12.0,
        avg_volume=2_000_000.0,
        medium_trend_change=0.03,
        relative_strength=0.04,
    )

    def fake_history(code, count, unit, fields):
        history_calls.append((code, count, unit, fields))
        return _ohlcv_from_close(np.linspace(10, 12, count))

    monkeypatch.setattr("eqlib.attribute_history", fake_history)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.build_fallback_snapshot",
        lambda frame, benchmark, params: snapshot,
    )
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        rs_window=15,
        volume_window=5,
        atr_period=5,
        fallback_trend_window=30,
        fallback_medium_window=12,
        fallback_trend_lookback=4,
    )

    selected = select_fallback_candidates(
        SimpleNamespace(),
        params,
        ["600519", "600036", "688001"],
        _ohlcv_from_close(np.linspace(10, 11, 40)),
        excluded_codes={"600519"},
    )

    assert [candidate.code for candidate in selected] == ["600036"]
    assert history_calls == [
        (
            "600036",
            35,
            "1d",
            ["open", "high", "low", "close", "volume"],
        )
    ]


def test_robust_selection_normalizes_primary_and_excludes_it_from_fallback(
    monkeypatch,
):
    primary_snapshot = _make_snapshot(volatility=0.03, close=15.0, avg_volume=3_000_000)
    fallback = [_robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.02)]
    seen_exclusions = []
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_candidates",
        lambda *args: [("600519", primary_snapshot, 10.0)],
    )

    def fake_fallback(context, params, universe, benchmark, excluded_codes):
        seen_exclusions.append(excluded_codes)
        return fallback

    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_fallback_candidates",
        fake_fallback,
    )
    params = StrategyParams(
        robust_enabled=True,
        min_primary_candidates=2,
        top_n=2,
    )

    selected = select_robust_candidates(
        SimpleNamespace(),
        StrategyKind.ADAPTIVE_COMPOSITE,
        params,
        ["600519", "600036"],
        _ohlcv_from_close([10, 11]),
        MarketState.NEUTRAL,
        PortfolioRiskState.NORMAL,
    )

    assert seen_exclusions == [{"600519"}]
    assert selected == [
        RobustCandidate(
            code="600519",
            channel=CandidateChannel.PRIMARY,
            score=10.0,
            volatility=0.03,
            close=15.0,
            avg_volume=3_000_000,
        ),
        fallback[0],
    ]


def test_robust_selection_skips_fallback_when_primary_supply_is_sufficient(
    monkeypatch,
):
    primary_snapshot = _make_snapshot()
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_candidates",
        lambda *args: [
            ("600519", primary_snapshot, 10.0),
            ("300750", primary_snapshot, 9.0),
        ],
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_fallback_candidates",
        lambda *args: pytest.fail("sufficient primary supply evaluated fallback"),
    )
    params = StrategyParams(min_primary_candidates=2, top_n=2)

    selected = select_robust_candidates(
        SimpleNamespace(),
        StrategyKind.ADAPTIVE_COMPOSITE,
        params,
        ["600519", "300750"],
        _ohlcv_from_close([10, 11]),
        MarketState.NEUTRAL,
        PortfolioRiskState.NORMAL,
    )

    assert [candidate.code for candidate in selected] == ["600519", "300750"]


def test_robust_rebalance_allocates_existing_fallback_through_fallback_sleeve(
    monkeypatch,
):
    queued = []
    monkeypatch.setattr("eqlib.order_target", lambda *args: None)
    monkeypatch.setattr(
        "eqlib.order_target_value",
        lambda code, value: queued.append((code, value))
        or SimpleNamespace(order_id=f"value-{code}"),
    )
    monkeypatch.setattr("eqlib.record", lambda **values: None)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={"600519": SimpleNamespace(total_value=50_000)},
        ),
        sr_order_channels={},
        sr_code_channels={"600519": CandidateChannel.FALLBACK.value},
        sr_risk_tracker=PortfolioRiskTracker.initial(1_000_000),
    )
    candidates = [
        RobustCandidate(
            "600519",
            CandidateChannel.PRIMARY,
            10.0,
            0.02,
            100.0,
            10_000_000.0,
        )
    ]
    params = StrategyParams(
        top_n=1,
        max_stock_weight=1.0,
        max_industry_weight=1.0,
        fallback_exposure_cap=0.10,
        rebalance_threshold=0.001,
        liquidity_volume_pct=1.0,
    )

    rebalance_robust_portfolio(context, candidates, exposure=0.80, params=params)

    assert queued == [("600519", pytest.approx(100_000))]
    assert context.sr_order_channels == {
        "value-600519": CandidateChannel.FALLBACK.value
    }


def test_robust_rebalance_never_increases_existing_fallback_in_defensive(
    monkeypatch,
):
    queued = []
    monkeypatch.setattr("eqlib.order_target", lambda *args: None)
    monkeypatch.setattr(
        "eqlib.order_target_value",
        lambda code, value: queued.append((code, value))
        or SimpleNamespace(order_id=f"value-{code}"),
    )
    monkeypatch.setattr("eqlib.record", lambda **values: None)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={"600519": SimpleNamespace(total_value=50_000)},
        ),
        sr_order_channels={},
        sr_code_channels={"600519": CandidateChannel.FALLBACK.value},
        sr_risk_tracker=PortfolioRiskTracker(
            PortfolioRiskState.DEFENSIVE,
            high_water=1_000_000,
            trough=880_000,
        ),
    )
    candidates = [
        RobustCandidate(
            "600519",
            CandidateChannel.PRIMARY,
            10.0,
            0.02,
            100.0,
            10_000_000.0,
        )
    ]
    params = StrategyParams(
        top_n=1,
        max_stock_weight=1.0,
        max_industry_weight=1.0,
        fallback_exposure_cap=0.10,
        rebalance_threshold=0.001,
        liquidity_volume_pct=1.0,
    )

    rebalance_robust_portfolio(context, candidates, exposure=0.50, params=params)

    assert queued == []
    assert context.sr_code_channels["600519"] == CandidateChannel.FALLBACK.value


def test_confirmed_exit_reentry_retires_stale_channel_and_primary_stop_applies(
    monkeypatch,
):
    queued = []

    def fake_order_target(code, amount):
        queued.append(("target", code, amount))
        return SimpleNamespace(order_id=f"exit-{len(queued)}")

    def fake_order_target_value(code, value):
        queued.append(("value", code, value))
        return SimpleNamespace(order_id=f"entry-{len(queued)}")

    monkeypatch.setattr("eqlib.order_target", fake_order_target)
    monkeypatch.setattr("eqlib.order_target_value", fake_order_target_value)
    monkeypatch.setattr("eqlib.record", lambda **values: None)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={"600519": SimpleNamespace(total_value=100_000)},
        ),
        current_dt=pd.Timestamp("2026-07-01 09:30").to_pydatetime(),
        sr_order_channels={},
        sr_code_channels={"600519": CandidateChannel.FALLBACK.value},
        sr_risk_tracker=PortfolioRiskTracker.initial(1_000_000),
    )
    params = StrategyParams(
        robust_enabled=True,
        top_n=1,
        level_window=3,
        short_level_window=3,
        atr_period=2,
        max_stock_weight=1.0,
        max_industry_weight=1.0,
        rebalance_threshold=0.001,
        liquidity_volume_pct=1.0,
        max_position_drawdown=0.0,
        fallback_trailing_drawdown=0.10,
    )

    rebalance_robust_portfolio(context, [], exposure=0.50, params=params)
    assert context.sr_code_channels["600519"] == CandidateChannel.FALLBACK.value

    context.current_dt = pd.Timestamp("2026-07-02 09:30").to_pydatetime()
    context.portfolio.positions = {}
    primary = RobustCandidate(
        "600519",
        CandidateChannel.PRIMARY,
        10.0,
        0.02,
        100.0,
        10_000_000.0,
    )
    rebalance_robust_portfolio(context, [primary], exposure=0.10, params=params)

    assert queued[-1] == ("value", "600519", pytest.approx(100_000))
    assert context.sr_code_channels["600519"] == CandidateChannel.PRIMARY.value
    assert context.sr_order_channels[str("entry-2")] == CandidateChannel.PRIMARY.value

    queued_before_review = list(queued)
    _risk_review(context, params)
    assert queued == queued_before_review
    assert context.sr_code_channels["600519"] == CandidateChannel.PRIMARY.value

    context.current_dt = pd.Timestamp("2026-07-03 09:30").to_pydatetime()
    context.portfolio.positions = {"600519": SimpleNamespace(total_value=100_000)}
    trailing_frame = _ohlcv_from_close([10.0, 11.0, 12.0, 12.0, 10.7])
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: trailing_frame)
    queued.clear()

    _risk_review(context, params)

    assert queued == []
    assert context.sr_code_channels["600519"] == CandidateChannel.PRIMARY.value


def test_unfilled_exit_remains_protected_across_callback_dates(monkeypatch):
    queued = []
    monkeypatch.setattr(
        "eqlib.order_target",
        lambda code, amount: queued.append(("target", code, amount))
        or SimpleNamespace(order_id=f"exit-{code}"),
    )
    monkeypatch.setattr(
        "eqlib.order_target_value",
        lambda code, value: queued.append(("value", code, value))
        or SimpleNamespace(order_id=f"value-{code}"),
    )
    monkeypatch.setattr("eqlib.record", lambda **values: None)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={"600519": SimpleNamespace(total_value=500_000)},
        ),
        current_dt=pd.Timestamp("2026-07-01 09:30").to_pydatetime(),
        sr_order_channels={},
        sr_code_channels={"600519": CandidateChannel.FALLBACK.value},
        sr_risk_tracker=PortfolioRiskTracker.initial(1_000_000),
    )
    params = StrategyParams(robust_enabled=True)

    rebalance_robust_portfolio(context, [], exposure=0.50, params=params)
    context.current_dt = pd.Timestamp("2026-07-02 09:30").to_pydatetime()
    reduce_portfolio_to_budget(context, exposure_budget=0.25)
    renewed_primary = RobustCandidate(
        "600519",
        CandidateChannel.PRIMARY,
        10.0,
        0.02,
        100.0,
        10_000_000.0,
    )
    rebalance_robust_portfolio(
        context,
        [renewed_primary],
        exposure=0.90,
        params=params,
    )

    assert queued == [("target", "600519", 0)]
    assert context._sr_pending_exit_codes == {"600519"}
    assert context.sr_code_channels["600519"] == CandidateChannel.FALLBACK.value


def test_robust_candidates_use_fallback_only_when_primary_is_short():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=2, top_n=3)
    primary = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.03),
    ]
    fallback = [_robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.01)]

    enough = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )
    short = combine_robust_candidates(
        primary[:1], fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )

    assert all(item.channel is CandidateChannel.PRIMARY for item in enough)
    assert [item.channel for item in short] == [
        CandidateChannel.PRIMARY,
        CandidateChannel.FALLBACK,
    ]


def test_robust_candidates_sort_each_channel_by_score_with_stable_ties():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=4, top_n=7)
    primary = [
        _robust_candidate("600036", CandidateChannel.PRIMARY, 5.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
    ]
    fallback = [
        _robust_candidate("601318", CandidateChannel.FALLBACK, 1.0, 0.02),
        _robust_candidate("000858", CandidateChannel.FALLBACK, 8.0, 0.02),
        _robust_candidate("600030", CandidateChannel.FALLBACK, 9.0, 0.02),
        _robust_candidate("600887", CandidateChannel.FALLBACK, 8.0, 0.02),
    ]

    result = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )

    assert [item.code for item in result] == [
        "300750",
        "600519",
        "600036",
        "600030",
        "000858",
        "600887",
        "601318",
    ]


def test_robust_candidates_suppress_fallback_code_already_emitted_as_primary():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=2, top_n=3)
    primary = [_robust_candidate("600519", CandidateChannel.PRIMARY, 5.0, 0.02)]
    fallback = [
        _robust_candidate("600519", CandidateChannel.FALLBACK, 10.0, 0.01),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 9.0, 0.02),
    ]

    result = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )

    assert [item.code for item in result] == ["600519", "600036"]
    assert [item.channel for item in result] == [
        CandidateChannel.PRIMARY,
        CandidateChannel.FALLBACK,
    ]


def test_fallback_is_disabled_in_weak_or_defensive_state():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=2, top_n=3)
    primary = [_robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02)]
    fallback = [_robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.01)]

    weak = combine_robust_candidates(
        primary, fallback, MarketState.WEAK, PortfolioRiskState.NORMAL, params
    )
    defensive = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.DEFENSIVE, params
    )

    assert weak == primary
    assert defensive == primary


def test_robust_weights_prioritize_primary_and_cap_fallback_and_industry():
    params = StrategyParams(
        robust_enabled=True,
        top_n=4,
        max_stock_weight=0.30,
        max_industry_weight=0.35,
        fallback_exposure_cap=0.20,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.04),
        _robust_candidate("000858", CandidateChannel.FALLBACK, 8.0, 0.01),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 7.0, 0.02),
    ]

    weights = robust_target_weights(candidates, exposure=0.70, params=params)

    fallback_weight = weights["000858"] + weights["600036"]
    assert fallback_weight <= 0.20
    assert weights["600519"] > weights["300750"]
    assert weights["600519"] + weights["000858"] <= 0.35
    assert sum(weights.values()) <= 0.70


def test_robust_weights_apply_exact_per_stock_cap():
    params = StrategyParams(
        robust_enabled=True,
        top_n=2,
        max_stock_weight=0.12,
        max_industry_weight=0.90,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.01),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.02),
    ]

    weights = robust_target_weights(candidates, exposure=0.90, params=params)

    assert weights == {"600519": pytest.approx(0.12), "300750": pytest.approx(0.12)}


def test_robust_weights_limit_fallback_to_residual_primary_exposure():
    params = StrategyParams(
        robust_enabled=True,
        top_n=3,
        max_stock_weight=0.30,
        max_industry_weight=0.90,
        fallback_exposure_cap=0.20,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.02),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.01),
    ]

    weights = robust_target_weights(candidates, exposure=0.70, params=params)

    assert weights["600519"] == pytest.approx(0.30)
    assert weights["300750"] == pytest.approx(0.30)
    assert weights["600036"] == pytest.approx(0.10)
    assert sum(weights.values()) == pytest.approx(0.70)


def test_robust_weights_leave_cap_induced_unused_exposure_as_cash():
    params = StrategyParams(
        robust_enabled=True,
        top_n=3,
        max_stock_weight=0.90,
        max_industry_weight=0.40,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("000858", CandidateChannel.PRIMARY, 9.0, 0.02),
        _robust_candidate("600036", CandidateChannel.PRIMARY, 8.0, 0.02),
    ]

    weights = robust_target_weights(candidates, exposure=0.90, params=params)

    assert weights["600519"] == pytest.approx(0.30)
    assert weights["000858"] == pytest.approx(0.10)
    assert weights["600036"] == pytest.approx(0.30)
    assert sum(weights.values()) == pytest.approx(0.70)


@pytest.mark.parametrize(
    "volatility",
    [float("nan"), float("inf"), float("-inf"), 0.0, -0.02],
    ids=["nan", "positive-infinity", "negative-infinity", "zero", "negative"],
)
def test_robust_weights_floor_zero_or_invalid_volatility(volatility):
    params = StrategyParams(
        robust_enabled=True,
        top_n=2,
        max_stock_weight=1.0,
        max_industry_weight=1.0,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, volatility),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.02),
    ]

    weights = robust_target_weights(candidates, exposure=0.60, params=params)

    expected_floor_weight = 0.60 * 1_000_000 / 1_000_050
    expected_valid_weight = 0.60 * 50 / 1_000_050
    assert set(weights) == {"600519", "300750"}
    assert weights["600519"] == pytest.approx(expected_floor_weight)
    assert weights["300750"] == pytest.approx(expected_valid_weight)


def _make_snapshot(**overrides):
    values = {
        "close": 10.0,
        "resistance": 10.5,
        "support": 9.7,
        "atr": 0.2,
        "avg_volume": 1_000_000.0,
        "volume_ratio": 1.2,
        "relative_strength": 0.02,
        "volatility": 0.02,
        "support_distance": 0.03,
        "resistance_distance": 0.05,
        "breakout": False,
        "pullback": True,
        "breakdown": False,
    }
    values.update(overrides)
    from eqlib.strategies.ashare_sr_leader import SignalSnapshot
    return SignalSnapshot(**values)


def test_market_gate_uses_completed_index_structure():
    params = StrategyParams(level_window=20, atr_period=5)
    strong = _ohlcv_from_close(list(np.linspace(10, 15, 80)) + [15.5])
    weak = _ohlcv_from_close(list(np.linspace(15, 10, 80)) + [8.0])
    assert classify_market(strong, params) is MarketState.STRONG
    assert classify_market(weak, params) is MarketState.WEAK
    assert market_exposure(MarketState.STRONG, params) == params.strong_market_exposure
    assert market_exposure(MarketState.WEAK, params) == params.weak_market_exposure


def test_breakout_snapshot_requires_atr_buffer_and_relative_strength():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.3,
        volume_window=5,
        rs_window=20,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close(list(np.linspace(10, 12, 50)) + [13.5], 2_000_000, 4_000_000)
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.5, 51)), 2_000_000, 2_500_000)
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert snapshot.breakout
    assert snapshot.relative_strength > 0
    assert score_snapshot(snapshot, StrategyKind.RESISTANCE_BREAKOUT) > 0


def test_composite_score_rewards_support_and_breakout_components():
    support_snapshot = _make_snapshot(
        support_distance=0.03,
        relative_strength=0.02,
        volatility=0.02,
        breakout=False,
        pullback=True,
    )
    breakout_snapshot = _make_snapshot(
        support_distance=0.12,
        relative_strength=0.08,
        volatility=0.025,
        breakout=True,
        pullback=False,
    )

    assert score_snapshot(support_snapshot, StrategyKind.ADAPTIVE_COMPOSITE) > 0
    assert score_snapshot(breakout_snapshot, StrategyKind.ADAPTIVE_COMPOSITE) > 0


def test_default_liquidity_threshold_keeps_high_price_leaders():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
    )
    stock = _ohlcv_from_close(
        list(np.linspace(100, 115, 50)) + [116],
        volume_start=150_000,
        volume_end=180_000,
    )
    benchmark = _ohlcv_from_close(
        list(np.linspace(100, 105, 51)),
        volume_start=200_000,
        volume_end=220_000,
    )
    assert build_signal_snapshot(stock, benchmark, params) is not None


def test_default_price_filter_accepts_qfq_scaled_leader_prices():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
    )
    stock = _ohlcv_from_close(
        list(np.linspace(0.6, 0.8, 50)) + [0.82],
        volume_start=200_000,
        volume_end=250_000,
    )
    benchmark = _ohlcv_from_close(list(np.linspace(100, 105, 51)))
    assert build_signal_snapshot(stock, benchmark, params) is not None


def test_default_price_filter_rejects_extreme_qfq_execution_artifacts():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
    )
    stock = _ohlcv_from_close(
        list(np.linspace(0.02, 0.03, 50)) + [0.031],
        volume_start=2_000_000,
        volume_end=2_500_000,
    )
    benchmark = _ohlcv_from_close(list(np.linspace(100, 105, 51)))
    assert build_signal_snapshot(stock, benchmark, params) is None


def test_defensive_score_prefers_near_support_without_breakdown():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.5,
        volume_window=5,
        rs_window=20,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close([10, 10.5, 11, 11.5, 11, 10.8, 10.6, 10.4, 10.3, 10.2] * 4 + [10.35])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.1, len(stock))))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert not snapshot.breakdown
    assert snapshot.support_distance < 0.15
    assert score_snapshot(snapshot, StrategyKind.DEFENSIVE_SUPPORT) > 0


def test_signal_snapshot_respects_min_relative_strength_filter():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.5,
        volume_window=5,
        rs_window=20,
        min_avg_volume=1,
        min_relative_strength=0.0,
    )
    stock = _ohlcv_from_close(list(np.linspace(10, 10.5, 50)) + [10.55])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 12.0, 51)))

    assert build_signal_snapshot(stock, benchmark, params) is None


def test_signal_snapshot_respects_max_support_distance_filter():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.5,
        volume_window=5,
        volume_ratio_min=5.0,
        rs_window=20,
        min_avg_volume=1,
        max_support_distance=0.04,
    )
    stock = _ohlcv_from_close([10, 10.2, 10.4, 10.6, 10.8] * 10 + [11.4])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.3, 51)))

    assert build_signal_snapshot(stock, benchmark, params) is None


def test_breakdown_snapshot_has_negative_scores():
    params = StrategyParams(level_window=20, atr_period=5, volume_window=5, rs_window=20, min_avg_volume=1)
    stock = _ohlcv_from_close(list(np.linspace(12, 10, 50)) + [7.0])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.2, 51)))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert snapshot.breakdown
    assert score_snapshot(snapshot, StrategyKind.PULLBACK_MARKET_GATE) < 0


def test_trailing_drawdown_exit_uses_recent_peak_when_enabled():
    frame = _ohlcv_from_close([10, 11, 12, 13, 14, 12.1])

    assert should_exit_trailing_drawdown(frame, stop_pct=0.12, window=5)
    assert not should_exit_trailing_drawdown(frame, stop_pct=0.20, window=5)
    assert not should_exit_trailing_drawdown(frame, stop_pct=0.0, window=5)


def test_risk_review_uses_fallback_stop_and_tags_the_exit(monkeypatch):
    queued = []
    frame = _ohlcv_from_close([10.0, 11.0, 12.0, 12.0, 10.7])
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: frame)

    def fake_order_target(code, amount):
        queued.append((code, amount))
        return SimpleNamespace(order_id=f"exit-{code}")

    monkeypatch.setattr("eqlib.order_target", fake_order_target)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            positions={
                "600519": SimpleNamespace(total_value=100_000),
                "600036": SimpleNamespace(total_value=100_000),
            }
        ),
        sr_order_channels={},
        sr_code_channels={
            "600519": CandidateChannel.PRIMARY.value,
            "600036": CandidateChannel.FALLBACK.value,
        },
    )
    params = StrategyParams(
        robust_enabled=True,
        level_window=3,
        short_level_window=3,
        atr_period=2,
        max_position_drawdown=0.0,
        fallback_trailing_drawdown=0.10,
    )

    _risk_review(context, params)

    assert queued == [("600036", 0)]
    assert context.sr_order_channels == {
        "exit-600036": CandidateChannel.FALLBACK.value
    }


def _capture_strategy_callbacks(monkeypatch, params, total_value=1_000_000):
    callbacks = {}
    monkeypatch.setattr(
        "eqlib.run_monthly",
        lambda func, **kwargs: callbacks.setdefault("monthly", (func, kwargs)),
    )
    monkeypatch.setattr(
        "eqlib.run_weekly",
        lambda func, **kwargs: callbacks.setdefault("weekly", (func, kwargs)),
    )
    monkeypatch.setattr("eqlib.set_benchmark", lambda benchmark: None)
    monkeypatch.setattr("eqlib.strategies.ashare_sr_leader._set_costs", lambda: None)
    context = SimpleNamespace(
        portfolio=SimpleNamespace(total_value=total_value, positions={}),
        current_dt=pd.Timestamp("2026-07-21 09:30").to_pydatetime(),
    )

    make_initialize(
        StrategyKind.ADAPTIVE_COMPOSITE,
        params=params,
        universe=["600519", "600036"],
    )(context)
    return context, callbacks


def test_robust_initialize_and_monthly_scan_use_complete_risk_data(monkeypatch):
    params = StrategyParams(
        robust_enabled=True,
        level_window=4,
        short_level_window=3,
        rs_window=3,
        atr_period=2,
        market_volatility_window=3,
    )
    benchmark = _ohlcv_from_close([10.0, 10.2, 10.1, 10.3, 10.4, 10.5])
    history_calls = []
    selected = [_robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02)]
    robust_calls = []

    def fake_history(code, count, unit, fields):
        history_calls.append((code, count, unit, fields))
        return benchmark

    monkeypatch.setattr("eqlib.attribute_history", fake_history)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_robust_candidates",
        lambda *args: robust_calls.append(("select", args)) or selected,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.rebalance_robust_portfolio",
        lambda *args: robust_calls.append(("rebalance", args)),
    )
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)

    assert context.sr_order_channels == {}
    assert context.sr_code_channels == {}
    assert context.sr_risk_events == []
    assert context.sr_risk_tracker == PortfolioRiskTracker.initial(1_000_000)

    callbacks["monthly"][0](context)

    assert history_calls == [
        (
            "000300.XSHG",
            9,
            "1d",
            ["open", "high", "low", "close", "volume"],
        )
    ]
    assert [call[0] for call in robust_calls] == ["select", "rebalance"]
    assert context.sr_risk_tracker.state is PortfolioRiskState.NORMAL


def test_monthly_protect_reduces_with_missing_volatility_and_never_selects(
    monkeypatch,
):
    params = StrategyParams(
        robust_enabled=True,
        neutral_market_exposure=0.60,
        protect_drawdown=0.16,
        market_volatility_floor=0.55,
    )
    benchmark = _ohlcv_from_close([10.0, 10.1])
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: benchmark)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.classify_market",
        lambda frame, runtime_params: MarketState.NEUTRAL,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_robust_candidates",
        lambda *args: pytest.fail("PROTECT must not select entry candidates"),
    )
    queued = []

    def fake_order_target_value(code, value):
        queued.append((code, value))
        return SimpleNamespace(order_id=f"protect-{code}")

    monkeypatch.setattr("eqlib.order_target_value", fake_order_target_value)
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)
    context.portfolio.total_value = 800_000
    context.portfolio.positions = {
        "600519": SimpleNamespace(total_value=500_000),
    }
    context.sr_code_channels = {"600519": CandidateChannel.FALLBACK.value}

    callbacks["monthly"][0](context)

    assert context.sr_risk_tracker.state is PortfolioRiskState.PROTECT
    assert queued == [("600519", pytest.approx(800_000 * 0.60 * 0.55 * 0.25))]
    assert context.sr_order_channels == {
        "protect-600519": CandidateChannel.FALLBACK.value
    }


@pytest.mark.parametrize(
    ("risk_state", "risk_multiplier"),
    [
        (PortfolioRiskState.CAUTIOUS, 0.75),
        (PortfolioRiskState.DEFENSIVE, 0.50),
    ],
)
def test_monthly_incomplete_data_still_reduces_existing_exposure(
    monkeypatch,
    risk_state,
    risk_multiplier,
):
    params = StrategyParams(
        robust_enabled=True,
        neutral_market_exposure=0.60,
        market_volatility_floor=0.55,
    )
    benchmark = _ohlcv_from_close([10.0, 10.1])
    queued = []
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: benchmark)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.classify_market",
        lambda frame, runtime_params: MarketState.NEUTRAL,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_robust_candidates",
        lambda *args: pytest.fail("incomplete data must not select entry candidates"),
    )

    def fake_order_target_value(code, value):
        queued.append((code, value))
        return SimpleNamespace(order_id=f"reduce-{code}")

    monkeypatch.setattr("eqlib.order_target_value", fake_order_target_value)
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)
    context.portfolio.positions = {
        "600519": SimpleNamespace(total_value=500_000),
    }
    context.sr_code_channels = {"600519": CandidateChannel.PRIMARY.value}
    context.sr_risk_tracker = PortfolioRiskTracker(
        risk_state,
        high_water=1_000_000,
        trough=900_000,
    )

    callbacks["monthly"][0](context)

    expected_budget = 0.60 * 0.55 * risk_multiplier
    assert context.sr_risk_tracker.state is risk_state
    assert queued == [("600519", pytest.approx(1_000_000 * expected_budget))]
    assert context.sr_order_channels == {
        "reduce-600519": CandidateChannel.PRIMARY.value
    }


def test_weekly_review_records_recovery_with_real_risk_operations(monkeypatch):
    params = StrategyParams(
        robust_enabled=True,
        level_window=4,
        rs_window=3,
        atr_period=2,
        market_volatility_window=3,
    )
    benchmark = _ohlcv_from_close([10.0, 10.1, 10.2, 10.3, 10.4, 10.5])
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: benchmark)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.classify_market",
        lambda frame, runtime_params: MarketState.NEUTRAL,
    )
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)
    context.portfolio.total_value = 950_000
    context.sr_risk_tracker = PortfolioRiskTracker(
        PortfolioRiskState.CAUTIOUS,
        high_water=1_000_000,
        trough=900_000,
    )

    callbacks["weekly"][0](context)

    assert context.sr_risk_tracker.state is PortfolioRiskState.NORMAL
    assert context.sr_risk_events == [
        {
            "date": "2026-07-21",
            "from": "cautious",
            "to": "normal",
            "drawdown": 0.05,
        }
    ]


def test_same_day_weekly_reduction_cannot_supersede_monthly_exit(monkeypatch):
    params = StrategyParams(
        robust_enabled=True,
        level_window=3,
        short_level_window=3,
        rs_window=3,
        atr_period=2,
        market_volatility_window=3,
        max_position_drawdown=0.0,
    )
    completed_frame = _ohlcv_from_close(
        [10.0, 11.0, 12.0, 12.0, 11.0, 8.0]
    )
    queued = []
    monkeypatch.setattr("eqlib.attribute_history", lambda *args: completed_frame)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.classify_market",
        lambda frame, runtime_params: MarketState.NEUTRAL,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.market_volatility_factor",
        lambda frame, runtime_params: 0.55,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_robust_candidates",
        lambda *args: [],
    )

    def fake_order_target(code, amount):
        queued.append(("target", code, amount))
        return SimpleNamespace(order_id=f"exit-{code}")

    def fake_order_target_value(code, value):
        queued.append(("value", code, value))
        return SimpleNamespace(order_id=f"value-{code}")

    monkeypatch.setattr("eqlib.order_target", fake_order_target)
    monkeypatch.setattr("eqlib.order_target_value", fake_order_target_value)
    monkeypatch.setattr("eqlib.record", lambda **values: None)
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)
    context.portfolio.positions = {
        "600519": SimpleNamespace(total_value=900_000),
    }
    context.sr_code_channels = {"600519": CandidateChannel.PRIMARY.value}

    callbacks["monthly"][0](context)
    callbacks["weekly"][0](context)

    assert queued == [("target", "600519", 0)]
    assert context._sr_pending_exit_codes == {"600519"}
    assert context.sr_order_channels == {
        "exit-600519": CandidateChannel.PRIMARY.value
    }


def test_default_off_initialize_preserves_legacy_callbacks(monkeypatch):
    params = StrategyParams(
        robust_enabled=False,
        level_window=20,
        rs_window=10,
        atr_period=5,
    )
    benchmark = _ohlcv_from_close(np.linspace(10, 12, 30))
    calls = []

    def fake_history(code, count, unit, fields):
        calls.append(("history", code, count, unit, fields))
        return benchmark

    monkeypatch.setattr("eqlib.attribute_history", fake_history)
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.classify_market",
        lambda *args: calls.append(("classify",)) or MarketState.NEUTRAL,
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_candidates",
        lambda *args: calls.append(("select",)) or [],
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.rebalance_portfolio",
        lambda *args: calls.append(("rebalance", args[2])),
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader._risk_review",
        lambda *args: calls.append(("review",)),
    )
    monkeypatch.setattr(
        "eqlib.strategies.ashare_sr_leader.select_robust_candidates",
        lambda *args: pytest.fail("default-off path entered robust selection"),
    )
    context, callbacks = _capture_strategy_callbacks(monkeypatch, params)

    assert not hasattr(context, "sr_risk_tracker")
    assert not hasattr(context, "sr_order_channels")
    callbacks["monthly"][0](context)
    callbacks["weekly"][0](context)

    assert calls == [
        (
            "history",
            "000300.XSHG",
            25,
            "1d",
            ["open", "high", "low", "close", "volume"],
        ),
        ("classify",),
        ("select",),
        ("rebalance", params.neutral_market_exposure),
        ("review",),
    ]


def test_liquidity_capped_target_value_limits_new_order_size():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        liquidity_volume_pct=0.08,
    )
    stock = _ohlcv_from_close(
        list(np.linspace(0.3, 0.4, 50)) + [0.42],
        volume_start=2_000_000,
        volume_end=2_500_000,
    )
    benchmark = _ohlcv_from_close(list(np.linspace(100, 105, 51)))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    capped = liquidity_capped_target_value(
        requested_target_value=120_000,
        snapshot=snapshot,
        params=params,
    )
    assert capped < 120_000
    assert capped == snapshot.close * snapshot.avg_volume * params.liquidity_volume_pct


def test_liquidity_capped_rebalance_target_value_limits_additional_buys():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        liquidity_volume_pct=0.08,
    )
    stock = _ohlcv_from_close(
        list(np.linspace(0.3, 0.4, 50)) + [0.42],
        volume_start=2_000_000,
        volume_end=2_500_000,
    )
    benchmark = _ohlcv_from_close(list(np.linspace(100, 105, 51)))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None

    capped = liquidity_capped_rebalance_target_value(
        requested_target_value=120_000,
        current_value=20_000,
        snapshot=snapshot,
        params=params,
    )

    assert capped < 120_000
    assert capped == 20_000 + snapshot.close * snapshot.avg_volume * params.liquidity_volume_pct


def test_industry_for_code_uses_default_universe_metadata():
    assert industry_for_code("600519") == "白酒"
    assert industry_for_code("600519.XSHG") == "白酒"
    assert industry_for_code("123456") == "未知"


def test_target_weights_respect_stock_and_industry_caps():
    params = StrategyParams(top_n=5, max_stock_weight=0.12, max_industry_weight=0.30)
    selections = [
        ("600519", None, 10.0),
        ("000858", None, 9.0),
        ("000568", None, 8.0),
        ("300750", None, 7.0),
        ("600036", None, 6.0),
    ]
    weights = target_weights(selections, exposure=0.9, params=params)
    assert sum(weights.values()) <= 0.9
    assert all(weight <= 0.12 for weight in weights.values())
    liquor_weight = weights["600519"] + weights["000858"] + weights["000568"]
    assert liquor_weight <= 0.30


def test_choose_portfolio_candidates_keeps_existing_positive_holdings():
    selections = [
        ("new_a", None, 10.0),
        ("new_b", None, 9.0),
        ("held_a", None, 3.0),
        ("held_b", None, 2.0),
    ]
    result = choose_portfolio_candidates(
        selections=selections,
        held_codes=["held_a", "held_b"],
        top_n=3,
    )
    assert [code for code, _snapshot, _score in result] == ["held_a", "held_b", "new_a"]


def test_choose_portfolio_candidates_sells_lowest_held_when_over_limit():
    selections = [
        ("held_a", None, 3.0),
        ("held_b", None, 2.0),
        ("held_c", None, 1.0),
        ("new_a", None, 10.0),
    ]
    result = choose_portfolio_candidates(
        selections=selections,
        held_codes=["held_a", "held_b", "held_c"],
        top_n=2,
    )
    assert [code for code, _snapshot, _score in result] == ["held_a", "held_b"]


def test_choose_portfolio_candidates_keeps_held_even_when_not_currently_ranked():
    selections = [
        ("new_a", None, 10.0),
        ("new_b", None, 9.0),
    ]
    result = choose_portfolio_candidates(
        selections=selections,
        held_codes=["held_a"],
        top_n=3,
    )
    assert [code for code, _snapshot, _score in result] == ["held_a", "new_a", "new_b"]


def test_candidate_param_grid_contains_three_strategy_kinds():
    grid = candidate_param_grid(quick=True)
    kinds = {kind for kind, _params in grid}
    assert kinds == {
        StrategyKind.DEFENSIVE_SUPPORT,
        StrategyKind.RESISTANCE_BREAKOUT,
        StrategyKind.PULLBACK_MARKET_GATE,
        StrategyKind.ADAPTIVE_COMPOSITE,
    }


def test_research_defaults_match_reproducible_2020_2025_report_window():
    assert START_DATE == "2020-01-01"
    assert END_DATE == "2025-12-31"
    assert STARTING_CASH == 1_000_000
    assert BENCHMARK == "000300.XSHG"
    assert SUB_PERIODS == (
        ("2020-2021", "2020-01-01", "2021-12-31"),
        ("2022", "2022-01-01", "2022-12-31"),
        ("2023-2024", "2023-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
    )


def test_candidate_param_grid_includes_a_grade_adaptive_composite_candidate():
    grid = candidate_param_grid(quick=False)
    candidates = [
        params
        for kind, params in grid
        if kind is StrategyKind.ADAPTIVE_COMPOSITE
        and params.level_window == 100
        and params.short_level_window == 50
        and params.atr_multiplier == 0.45
        and params.volume_ratio_min == 0.9
        and params.top_n == 10
        and params.max_stock_weight == 0.10
        and params.max_industry_weight == 0.25
        and params.strong_market_exposure == 0.95
        and params.neutral_market_exposure == 0.68
        and params.weak_market_exposure == 0.25
        and params.min_relative_strength == -0.015
        and params.max_support_distance == 0.11
        and params.rebalance_threshold == 0.05
        and params.liquidity_volume_pct == 0.04
    ]

    assert candidates


def test_candidate_param_grid_includes_guarded_risk_controls():
    grid = candidate_param_grid(quick=False)
    guarded = [
        params
        for _kind, params in grid
        if params.strong_market_exposure <= 0.70
        and params.neutral_market_exposure <= 0.45
        and params.max_stock_weight <= 0.07
    ]

    assert guarded


def test_candidate_param_grid_includes_trend_confirmed_risk_controls():
    grid = candidate_param_grid(quick=False)
    trend_confirmed = [
        params
        for kind, params in grid
        if kind in {StrategyKind.DEFENSIVE_SUPPORT, StrategyKind.PULLBACK_MARKET_GATE}
        and params.min_relative_strength >= 0.0
        and params.max_support_distance <= 0.08
        and params.weak_market_exposure <= 0.15
        and params.neutral_market_exposure <= 0.50
        and params.max_stock_weight <= 0.08
    ]

    assert trend_confirmed


def test_candidate_param_grid_includes_adaptive_composite_candidates():
    grid = candidate_param_grid(quick=False)
    adaptive = [
        params
        for kind, params in grid
        if kind is StrategyKind.ADAPTIVE_COMPOSITE
        and params.top_n >= 10
        and params.rebalance_threshold <= 0.06
        and params.strong_market_exposure >= 0.85
        and params.weak_market_exposure <= 0.25
    ]

    assert adaptive


def test_candidate_param_grid_includes_active_balanced_pullback_candidate():
    grid = candidate_param_grid(quick=False)
    active_balanced = [
        params
        for kind, params in grid
        if kind is StrategyKind.PULLBACK_MARKET_GATE
        and params.top_n == 10
        and params.max_stock_weight == 0.08
        and params.strong_market_exposure == 0.84
        and params.neutral_market_exposure == 0.54
        and params.weak_market_exposure == 0.18
        and params.min_relative_strength == -0.005
        and params.max_support_distance == 0.10
        and params.rebalance_threshold == 0.07
    ]

    assert active_balanced


def test_candidate_param_grid_includes_drawdown_controlled_pullback_candidate():
    grid = candidate_param_grid(quick=False)
    drawdown_controlled = [
        params
        for kind, params in grid
        if kind is StrategyKind.PULLBACK_MARKET_GATE
        and params.max_position_drawdown <= 0.12
        and params.weak_market_exposure <= 0.10
        and params.neutral_market_exposure <= 0.45
        and params.max_stock_weight <= 0.07
    ]

    assert drawdown_controlled


def test_profile_name_labels_trend_confirmed_risk_managed_params():
    assert _profile_name(
        {
            "params": {
                "min_relative_strength": 0.0,
                "max_support_distance": 0.08,
                "weak_market_exposure": 0.15,
            }
        }
    ) == "risk-managed"


def test_profile_name_labels_drawdown_controlled_params():
    assert _profile_name(
        {
            "params": {
                "min_relative_strength": 0.01,
                "max_support_distance": 0.06,
                "max_position_drawdown": 0.12,
                "weak_market_exposure": 0.10,
            }
        }
    ) == "drawdown-controlled"


def test_profile_name_labels_active_balanced_params():
    assert _profile_name(
        {
            "params": {
                "min_relative_strength": -0.005,
                "max_support_distance": 0.10,
                "strong_market_exposure": 0.84,
                "neutral_market_exposure": 0.54,
                "rebalance_threshold": 0.07,
            }
        }
    ) == "active-balanced"


def test_stability_score_penalizes_drawdown_and_trade_count():
    good = {
        "annual_return": 0.12,
        "sharpe_ratio": 1.2,
        "max_drawdown": -0.12,
        "trade_count": 40,
        "excess_return": 0.05,
    }
    overtraded = dict(good, trade_count=300)
    deep_drawdown = dict(good, max_drawdown=-0.45)
    assert stability_score(good) > stability_score(overtraded)
    assert stability_score(good) > stability_score(deep_drawdown)


def test_stability_score_softly_penalizes_undertrading():
    reasonable = {
        "annual_return": 0.12,
        "sharpe_ratio": 0.7,
        "max_drawdown": -0.21,
        "trade_count": 20,
        "excess_return": 1.0,
    }
    too_inactive = dict(reasonable, annual_return=0.125, trade_count=14)

    assert stability_score(reasonable) > stability_score(too_inactive)


def test_stability_score_prefers_controlled_drawdown_over_high_excess():
    controlled = {
        "annual_return": 0.05,
        "sharpe_ratio": 0.2,
        "max_drawdown": -0.15,
        "trade_count": 20,
        "excess_return": 0.05,
    }
    risky = {
        "annual_return": 0.07,
        "sharpe_ratio": 0.3,
        "max_drawdown": -0.40,
        "trade_count": 20,
        "excess_return": 0.25,
    }

    assert stability_score(controlled) > stability_score(risky)


def test_audit_rows_flags_missing_benchmark_deep_drawdown_and_bad_subperiod():
    rows = [
        {
            "period_name": "full",
            "kind": "pullback_market_gate",
            "benchmark_return": 0.0,
            "max_drawdown": -0.39,
            "trade_count": 25,
            "excess_return": 0.30,
        },
        {
            "period_name": "2025-2026",
            "kind": "pullback_market_gate",
            "benchmark_return": 0.24,
            "max_drawdown": -0.10,
            "trade_count": 7,
            "raw_trade_count": 180,
            "excess_return": -0.27,
        },
    ]

    issues = audit_rows(rows)

    assert any(issue["code"] == "benchmark_missing" for issue in issues)
    assert any(issue["code"] == "deep_drawdown" for issue in issues)
    assert any(issue["code"] == "subperiod_underperformance" for issue in issues)
    assert any(issue["code"] == "execution_fragmentation" for issue in issues)


def test_write_outputs_keeps_long_full_rows_first(tmp_path, monkeypatch):
    """Short diagnostic periods must not outrank the long 2020-2026 backtest."""
    import scripts.run_ashare_sr_leader_research as research

    monkeypatch.setattr(research, "REPORT_DIR", tmp_path)
    rows = [
        {
            "period_name": "2020-2021",
            "kind": "defensive_support",
            "start": "2020-01-01",
            "end": "2021-12-31",
            "annual_return": 0.66,
            "total_return": 1.75,
            "benchmark_return": 0.19,
            "excess_return": 1.56,
            "max_drawdown": -0.30,
            "sharpe_ratio": 1.6,
            "trade_count": 9,
            "raw_trade_count": 21,
            "stability_score": 2.65,
            "params": {},
        },
        {
            "period_name": "full",
            "kind": "defensive_support",
            "start": "2020-01-01",
            "end": "2026-07-08",
            "annual_return": 0.18,
            "total_return": 2.04,
            "benchmark_return": 0.15,
            "excess_return": 1.89,
            "max_drawdown": -0.31,
            "sharpe_ratio": 0.7,
            "trade_count": 18,
            "raw_trade_count": 44,
            "stability_score": 2.05,
            "params": {},
        },
    ]

    write_outputs(rows)

    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved[0]["period_name"] == "full"


def test_write_outputs_ranks_full_rows_by_grade_before_stability(tmp_path, monkeypatch):
    import scripts.run_ashare_sr_leader_research as research

    monkeypatch.setattr(research, "REPORT_DIR", tmp_path)
    rows = [
        {
            "period_name": "full",
            "kind": "pullback_market_gate",
            "start": "2020-01-01",
            "end": "2025-12-31",
            "annual_return": 0.144,
            "total_return": 1.23,
            "benchmark_return": 0.115,
            "excess_return": 1.115,
            "max_drawdown": -0.244,
            "sharpe_ratio": 0.72,
            "trade_count": 12,
            "raw_trade_count": 32,
            "stability_score": 1.08,
            "grade": "B",
            "grade_score": 69.0,
            "params": {},
        },
        {
            "period_name": "full",
            "kind": "adaptive_composite",
            "start": "2020-01-01",
            "end": "2025-12-31",
            "annual_return": 0.163,
            "total_return": 1.46,
            "benchmark_return": 0.115,
            "excess_return": 1.345,
            "max_drawdown": -0.243,
            "sharpe_ratio": 0.78,
            "trade_count": 32,
            "raw_trade_count": 54,
            "stability_score": 1.01,
            "grade": "A",
            "grade_score": 71.0,
            "params": {},
        },
    ]

    write_outputs(rows)

    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved[0]["kind"] == "adaptive_composite"


def test_best_full_candidate_prefers_grade_before_stability():
    import scripts.run_ashare_sr_leader_research as research

    lower_grade = ({"grade_score": 69.0, "stability_score": 1.08}, StrategyKind.PULLBACK_MARKET_GATE, StrategyParams())
    higher_grade = ({"grade_score": 71.0, "stability_score": 1.01}, StrategyKind.ADAPTIVE_COMPOSITE, StrategyParams())

    assert research._best_full_candidate([lower_grade, higher_grade]) is higher_grade


def test_benchmark_total_return_uses_engine_benchmark_values():
    result = {
        "recorded_values": [
            {"date": "2020-01-02", "total_value": 1_000_000},
            {"date": "2020-01-06", "total_value": 1_010_000},
        ],
        "benchmark_values": [
            {"date": "2019-12-31", "value": 90.0},
            {"date": "2020-01-02", "value": 100.0},
            {"date": "2020-01-03", "value": 105.0},
            {"date": "2020-01-06", "value": 110.0},
        ],
    }

    assert _benchmark_total_return(result) == 0.10


def test_should_rebalance_position_ignores_small_weight_drift():
    params = StrategyParams()
    assert should_rebalance_position(
        current_value=0,
        target_value=100_000,
        total_value=1_000_000,
        params=params,
    )
    assert not should_rebalance_position(
        current_value=101_000,
        target_value=100_000,
        total_value=1_000_000,
        params=params,
    )
    assert not should_rebalance_position(
        current_value=150_000,
        target_value=100_000,
        total_value=1_000_000,
        params=params,
    )
    assert should_rebalance_position(
        current_value=200_000,
        target_value=100_000,
        total_value=1_000_000,
        params=params,
    )


def test_period_interpretation_reports_regime_and_recommendation():
    rows = [
        {
            "period_name": "full",
            "kind": "pullback_market_gate",
            "annual_return": 0.12,
            "max_drawdown": -0.18,
            "sharpe_ratio": 1.1,
            "excess_return": 0.04,
            "trade_count": 70,
            "stability_score": 0.55,
        },
        {
            "period_name": "2022",
            "kind": "defensive_support",
            "annual_return": -0.04,
            "max_drawdown": -0.16,
            "sharpe_ratio": -0.2,
            "excess_return": 0.03,
            "trade_count": 18,
            "stability_score": 0.10,
        },
    ]
    text = period_interpretation(rows)
    assert "最终推荐" in text
    assert "pullback_market_gate" in text
    assert "2022" in text
    assert "长期回测压力诊断" in text
    assert "不作为收益参考" in text
    assert "该长期策略" in text
    assert "最优候选" not in text
    assert "交易次数没有表现出高频" in text


def test_render_html_report_contains_metrics_tables_and_risk_notes():
    rows = [
        {
            "period_name": "full",
            "kind": "defensive_support",
            "start": "2020-01-01",
            "end": "2026-07-08",
            "annual_return": 0.019,
            "total_return": 0.1295,
            "benchmark_return": 0.05,
            "max_drawdown": -0.1799,
            "sharpe_ratio": -0.05,
            "excess_return": 0.0795,
            "trade_count": 9,
            "stability_score": 0.1451,
        },
        {
            "period_name": "2022",
            "kind": "support<script>",
            "start": "2022-01-01",
            "end": "2022-12-31",
            "annual_return": -0.13,
            "total_return": -0.128,
            "benchmark_return": 0.0,
            "max_drawdown": -0.207,
            "sharpe_ratio": -1.24,
            "excess_return": -0.128,
            "trade_count": 5,
            "stability_score": -0.63,
        },
    ]

    html = render_html_report(rows)

    assert html.startswith("<!doctype html>")
    assert "<title>A股行业龙头支撑压力策略研究报告</title>" in html
    assert "defensive_support" in html
    assert "1.90%" in html
    assert "-17.99%" in html
    assert "全周期候选排名" in html
    assert "Benchmark" in html
    assert "Excess" in html
    assert "5.00%" in html
    assert "7.95%" in html
    assert "长期回测压力诊断" in html
    assert "短期或分阶段结果只用于解释策略失效环境" in html
    assert "风险提示" in html
    assert "support&lt;script&gt;" in html
    assert "support<script>" not in html


def test_render_html_report_surfaces_audit_issues():
    rows = [
        {
            "period_name": "full",
            "kind": "risky_strategy",
            "start": "2020-01-01",
            "end": "2026-07-08",
            "annual_return": 0.08,
            "total_return": 0.55,
            "benchmark_return": 0.10,
            "max_drawdown": -0.36,
            "sharpe_ratio": 0.3,
            "excess_return": 0.45,
            "trade_count": 20,
            "stability_score": 0.10,
        }
    ]

    html = render_html_report(rows)

    assert "回测审计" in html
    assert "deep_drawdown" in html
    assert "最大回撤超过 30%" in html
    assert "不建议直接实盘" in html


def test_write_eqlib_html_report_delegates_to_eqlib_generator(tmp_path, monkeypatch):
    calls = []

    def fake_generate_html_report(result, out_path):
        calls.append((result, out_path))
        out_path.write_text("<html>eqlib</html>", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.run_ashare_sr_leader_research.generate_html_report",
        fake_generate_html_report,
    )
    result = {"recorded_values": [], "trade_log": []}
    out_path = tmp_path / "eqlib_best_backtest.html"

    write_eqlib_html_report(result, out_path)

    assert calls == [(result, out_path)]
    assert out_path.read_text(encoding="utf-8") == "<html>eqlib</html>"
