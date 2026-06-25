"""Tests for grade_strategy(), diagnose_bottleneck(), recommend_params()."""

import pytest
from eqlib.attribution import grade_strategy, diagnose_bottleneck, recommend_params


def _make_analytics(**overrides):
    """Build a minimal analytics dict for grading tests."""
    base = {
        "total_return": 0.15,
        "annual_return": 0.15,
        "annual_volatility": 0.18,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.8,
        "max_drawdown": -0.12,
        "max_drawdown_start": "2024-03-15",
        "max_drawdown_end": "2024-04-02",
        "calmar_ratio": 1.25,
        "alpha": 0.05,
        "beta": 0.8,
        "information_ratio": 0.9,
        "win_rate": 0.55,
        "win_rate_daily": 0.55,
        "win_rate_trade": 0.60,
        "trade_count": 20,
        "win_count": 12,
        "loss_count": 8,
        "profit_loss_ratio": 2.0,
        "annual_turnover": 3.0,
        "total_commission": 200.0,
        "net_return": 0.15,
        "trading_days": 244,
        "num_trades": 40,
        "excess_return": 0.07,
        "benchmark_return": 0.08,
        "excess_return_max_drawdown": -0.05,
        "excess_return_sharpe": 0.9,
        "daily_excess_return": 0.0003,
        "benchmark_volatility": 0.15,
        "monthly_returns": {"2024-01": 0.03, "2024-02": -0.01, "2024-03": 0.04,
                            "2024-04": 0.01, "2024-05": -0.02, "2024-06": 0.06,
                            "2024-07": 0.008, "2024-08": 0.003, "2024-09": 0.02,
                            "2024-10": 0.05, "2024-11": -0.01, "2024-12": 0.03},
        "rolling_sharpe_60d": [],
        "rolling_volatility_60d": [],
        "daily_returns_stats": {},
        "per_stock_pnl": {"000001": 5000.0, "600036": -1000.0},
        "drawdown_periods": [],
    }
    base.update(overrides)
    return base


class TestGradeStrategy:
    def test_returns_none_for_none_input(self):
        result = grade_strategy(None)
        assert result["overall"] == "D"
        assert result["score"] == 0

    def test_six_dimensions_present(self):
        g = grade_strategy(_make_analytics())
        assert len(g["dimensions"]) == 6
        names = [d["name"] for d in g["dimensions"]]
        assert "return_capability" in names
        assert "risk_control" in names
        assert "risk_adjusted" in names
        assert "trade_quality" in names
        assert "excess_capability" in names
        assert "stability" in names

    def test_grade_s_for_excellent_strategy(self):
        g = grade_strategy(_make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70, profit_loss_ratio=3.0,
            excess_return=0.15, information_ratio=1.5,
        ))
        assert g["overall"] in ("S", "A")
        assert g["score"] >= 70

    def test_grade_d_for_poor_strategy(self):
        g = grade_strategy(_make_analytics(
            annual_return=-0.10, sharpe_ratio=-0.5, max_drawdown=-0.40,
            alpha=-0.05, win_rate_trade=0.20, excess_return=-0.15,
        ))
        assert g["overall"] in ("C", "D")

    def test_weakest_and_strongest_identified(self):
        g = grade_strategy(_make_analytics())
        assert g["weakest"] != ""
        assert g["strongest"] != ""
        assert g["weakest"] != g["strongest"]

    def test_summary_text_nonempty(self):
        g = grade_strategy(_make_analytics())
        assert len(g["summary_text"]) > 10

    def test_each_dimension_has_grade(self):
        g = grade_strategy(_make_analytics())
        for d in g["dimensions"]:
            assert "grade" in d
            assert d["grade"] in ("S", "A", "B", "C", "D")

    def test_monthly_win_rate_calculation(self):
        """9 positive months out of 12 = 75%."""
        g = grade_strategy(_make_analytics())
        stability = [d for d in g["dimensions"] if d["name"] == "stability"][0]
        assert stability["key"]["monthly_win_rate"] == pytest.approx(0.75, abs=0.01)


class TestDiagnoseBottleneck:
    def test_empty_for_none_input(self):
        assert diagnose_bottleneck(None, None) == []

    def test_detects_drawdown_violation(self):
        a = _make_analytics(max_drawdown=-0.28)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        metrics = [x["metric"] for x in d]
        assert "max_drawdown" in metrics

    def test_detects_low_sharpe(self):
        a = _make_analytics(sharpe_ratio=0.3)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        metrics = [x["metric"] for x in d]
        assert "sharpe_ratio" in metrics

    def test_no_diagnostics_for_excellent_strategy(self):
        a = _make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70,
        )
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        assert len(d) == 0

    def test_diagnostic_has_required_keys(self):
        a = _make_analytics(max_drawdown=-0.30)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        for item in d:
            assert "metric" in item
            assert "severity" in item
            assert "finding" in item
            assert "root_cause" in item


class TestRecommendParams:
    def test_empty_when_no_params_provided(self):
        assert recommend_params(_make_analytics(), {}, None, None) == []

    def test_recommends_stop_loss_for_drawdown(self):
        a = _make_analytics(max_drawdown=-0.28)
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.08, "position_pct": 0.80}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02), "position_pct": (0.20, 1.00, 0.10)}
        recs = recommend_params(a, g, params, ranges)
        sl_recs = [r for r in recs if r["parameter"] == "stop_loss_pct"]
        assert len(sl_recs) >= 1
        assert sl_recs[0]["suggested"] < sl_recs[0]["current"]

    def test_recommends_vol_confirm_for_low_sharpe(self):
        a = _make_analytics(sharpe_ratio=0.4)
        g = grade_strategy(a)
        params = {"vol_confirm_mul": 1.0}
        ranges = {"vol_confirm_mul": (0.5, 3.0, 0.5)}
        recs = recommend_params(a, g, params, ranges)
        vc_recs = [r for r in recs if r["parameter"] == "vol_confirm_mul"]
        assert len(vc_recs) >= 1
        assert vc_recs[0]["suggested"] > vc_recs[0]["current"]

    def test_recommendation_has_required_keys(self):
        a = _make_analytics(max_drawdown=-0.30)
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.10}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02)}
        recs = recommend_params(a, g, params, ranges)
        for r in recs:
            assert "priority" in r
            assert "parameter" in r
            assert "current" in r
            assert "suggested" in r
            assert "rationale" in r

    def test_no_recommendation_when_all_pass(self):
        a = _make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70,
        )
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.05, "position_pct": 0.50}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02), "position_pct": (0.20, 1.00, 0.10)}
        recs = recommend_params(a, g, params, ranges)
        assert len(recs) == 0
