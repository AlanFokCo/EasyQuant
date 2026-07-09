"""Tests for the A-share industry leader support/resistance strategy."""

import numpy as np
import pandas as pd

from eqlib.strategies.ashare_sr_leader import (
    DEFAULT_LEADER_UNIVERSE,
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
    get_default_leader_universe,
    is_excluded_board,
    market_exposure,
    rolling_levels,
    score_snapshot,
    should_rebalance_position,
    target_weights,
)
from scripts.run_ashare_sr_leader_research import (
    _benchmark_total_return,
    audit_rows,
    candidate_param_grid,
    period_interpretation,
    render_html_report,
    stability_score,
    write_eqlib_html_report,
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


def test_breakdown_snapshot_has_negative_scores():
    params = StrategyParams(level_window=20, atr_period=5, volume_window=5, rs_window=20, min_avg_volume=1)
    stock = _ohlcv_from_close(list(np.linspace(12, 10, 50)) + [7.0])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.2, 51)))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert snapshot.breakdown
    assert score_snapshot(snapshot, StrategyKind.PULLBACK_MARKET_GATE) < 0


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
    }


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
