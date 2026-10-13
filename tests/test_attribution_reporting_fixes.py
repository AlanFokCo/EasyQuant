"""Tests for the 2026-10-12 audit fixes in attribution/reporting math.

Covers:
- Fee-aware round-trip statistics: win rate / profit-loss ratio / per-stock
  P&L must include both-side transaction costs (commission + stamp duty),
  matching the engine's cash accounting (QUANT-P2-02).
- Benchmark-unavailable semantics: alpha/beta/information_ratio and the
  excess-return family must be NaN (rendered "N/A"), never plausible-looking
  defaults like alpha=0.0 / beta=1.0 (INFRA-P1-04).
- True single-period BHB Brinson attribution: allocation + selection +
  interaction must close to portfolio_return - benchmark_return, and the
  sector_data parameter must genuinely drive the grouping (QUANT-P1-04).
- Unified benchmark caliber in report metrics (report double-caliber fix).
"""

import datetime as dt
import json
import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(daily_returns, trades=None, positions=None, universe=None,
                 ohlcv_data=None, benchmark_values=None, starting_cash=100000.0):
    """Build a minimal result dict that analyze_returns/brinson can consume."""
    values = (1 + pd.Series(daily_returns)).cumprod() * starting_cash
    dates = pd.bdate_range("2024-01-02", periods=len(values), freq="B")
    entries = [
        {"date": d.date(), "total_value": float(v)}
        for d, v in zip(dates, values)
    ]
    portfolio = SimpleNamespace(
        starting_cash=starting_cash,
        total_value=float(values.iloc[-1]),
        positions=positions or {},
    )
    context = SimpleNamespace(
        portfolio=portfolio,
        universe=universe or [],
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
    )
    result = {
        "context": context,
        "trade_log": trades or [],
        "recorded_values": entries,
        "benchmark": "000300.XSHG",
    }
    if ohlcv_data is not None:
        result["ohlcv_data"] = ohlcv_data
    if benchmark_values is not None:
        result["benchmark_values"] = benchmark_values
    return result


def _ohlcv(closes, start="2024-01-02"):
    dates = pd.bdate_range(start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "open": closes,
            "close": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "volume": [1_000_000.0] * len(closes),
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Fee-aware win rate / P&L (QUANT-P2-02)
# ---------------------------------------------------------------------------

class TestFeeAwareWinRate:
    """Win/loss classification must use fee-adjusted cash flows."""

    def test_net_loss_round_trip_is_not_a_win(self):
        """Evaluator scenario: gross price win but net-of-fees loss.

        Buy 10.00x100 (commission 5.00), sell 10.05x100 (commission 5.50):
        gross +5.00 yuan, fees 10.50 yuan, net -5.50 yuan -> must be a loss.
        """
        from eqlib.attribution import _calc_trade_win_rate, _calc_profit_loss_ratio

        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.00, "amount": 100,
             "commission": 5.0},
            {"type": "SELL", "security": "AAA", "price": 10.05, "amount": 100,
             "commission": 5.5},
        ]
        win_rate, total, wins, losses = _calc_trade_win_rate(trades)
        assert total == 1
        assert wins == 0
        assert losses == 1
        assert win_rate == 0.0

        plr, win_count, loss_count = _calc_profit_loss_ratio(trades)
        assert win_count == 0
        assert loss_count == 1
        assert plr == 0.0

    def test_net_win_round_trip_counts_as_win(self):
        from eqlib.attribution import _calc_trade_win_rate

        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.00, "amount": 100,
             "commission": 5.0},
            {"type": "SELL", "security": "AAA", "price": 11.00, "amount": 100,
             "commission": 5.5},
        ]
        win_rate, total, wins, losses = _calc_trade_win_rate(trades)
        assert (win_rate, total, wins, losses) == (1.0, 1, 1, 0)

    def test_fees_amortized_pro_rata_on_partial_match(self):
        """Buy 200 (comm 10), sell 100: half the buy fee enters the matched cost.

        matched cost  = 10.00*100 + 10*(100/200) = 1005
        net proceeds  = 10.02*100 - 5            = 997
        net pnl       = -8  -> loss
        """
        from eqlib.attribution import _match_round_trips

        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.00, "amount": 200,
             "commission": 10.0},
            {"type": "SELL", "security": "AAA", "price": 10.02, "amount": 100,
             "commission": 5.0},
        ]
        trips = _match_round_trips(trades)
        assert len(trips) == 1
        assert trips[0]["amount"] == 100
        assert trips[0]["buy_cost"] == pytest.approx(1005.0)
        assert trips[0]["sell_proceeds"] == pytest.approx(997.0)
        assert trips[0]["pnl"] == pytest.approx(-8.0)

    def test_zero_commission_keeps_legacy_behavior(self):
        """Trades without commission fall back to the price-only caliber."""
        from eqlib.attribution import _calc_trade_win_rate

        trades = [
            {"type": "BUY", "security": "A", "price": 10.0, "amount": 100},
            {"type": "SELL", "security": "A", "price": 15.0, "amount": 100},
            {"type": "BUY", "security": "B", "price": 20.0, "amount": 100},
            {"type": "SELL", "security": "B", "price": 18.0, "amount": 100},
        ]
        win_rate, total, wins, losses = _calc_trade_win_rate(trades)
        assert (win_rate, total, wins, losses) == (0.5, 2, 1, 1)

    def test_per_stock_pnl_net_of_fees(self, monkeypatch):
        """analyze_returns per-stock P&L must match the engine cash caliber."""
        import eqlib.attribution as attribution
        import eqlib.data as data_mod

        monkeypatch.setattr(data_mod, "fetch_stock_data",
                            lambda *a, **k: pd.DataFrame())

        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.00, "amount": 100,
             "commission": 5.0, "date": dt.date(2024, 1, 3)},
            {"type": "SELL", "security": "AAA", "price": 10.05, "amount": 100,
             "commission": 5.5, "date": dt.date(2024, 1, 10)},
        ]
        result = _make_result([0.001] * 30, trades=trades)
        analytics = attribution.analyze_returns(result)
        assert analytics["per_stock_pnl"]["AAA"] == pytest.approx(-5.5)
        # And the round trip must not show up as a win anywhere.
        assert analytics["win_count"] == 0
        assert analytics["loss_count"] == 1
        assert analytics["win_rate_trade"] == 0.0


# ---------------------------------------------------------------------------
# Benchmark unavailable -> NaN, report renders N/A (INFRA-P1-04)
# ---------------------------------------------------------------------------

class TestBenchmarkUnavailableNaN:
    def test_analyze_returns_nan_when_benchmark_unavailable(self, monkeypatch):
        """No benchmark_values + failing fetch -> NaN family, finite Sharpe."""
        import eqlib.attribution as attribution
        import eqlib.data as data_mod

        monkeypatch.setattr(
            data_mod, "fetch_stock_data",
            lambda *args, **kwargs: pd.DataFrame(),
        )
        result = _make_result([0.001] * 30)
        analytics = attribution.analyze_returns(result)

        assert math.isnan(analytics["alpha"])
        assert math.isnan(analytics["beta"])
        assert math.isnan(analytics["information_ratio"])
        assert math.isnan(analytics["benchmark_return"])
        assert math.isnan(analytics["excess_return"])
        assert math.isnan(analytics["excess_return_max_drawdown"])
        assert math.isnan(analytics["excess_return_sharpe"])
        assert math.isnan(analytics["daily_excess_return"])
        assert math.isnan(analytics["benchmark_volatility"])
        # Benchmark-independent metrics stay real numbers.
        assert math.isfinite(analytics["sharpe_ratio"])
        assert math.isfinite(analytics["total_return"])

    def test_engine_benchmark_values_avoid_fetch(self, monkeypatch):
        """benchmark_values recorded by the engine feed alpha/beta directly."""
        import eqlib.attribution as attribution
        import eqlib.data as data_mod

        def _boom(*args, **kwargs):
            raise AssertionError("fetch must not be called when benchmark_values exist")

        monkeypatch.setattr(data_mod, "fetch_stock_data", _boom)

        n = 40
        dates = pd.bdate_range("2024-01-02", periods=n, freq="B")
        bench_daily = [0.002 if i % 2 == 0 else -0.001 for i in range(n)]
        bench_closes = 4000 * (1 + pd.Series(bench_daily)).cumprod()
        benchmark_values = [
            {"date": str(d.date()), "value": float(v)}
            for d, v in zip(dates, bench_closes)
        ]

        strat_daily = [0.003 if i % 2 == 0 else -0.002 for i in range(n)]
        result = _make_result(strat_daily, benchmark_values=benchmark_values)
        analytics = attribution.analyze_returns(result, risk_free_rate=0.03)

        # Recompute expectations independently from the same inputs.
        # The strategy's daily return series starts on day 2 (pct_change).
        bench_series = pd.Series(bench_closes.values, index=dates)
        bench_ret = bench_series.pct_change().dropna()
        strat_series = pd.Series(strat_daily[1:], index=dates[1:])
        common = strat_series.index.intersection(bench_ret.index)
        strat = strat_series.loc[common].values
        bench = bench_ret.loc[common].values
        cov = np.cov(strat, bench, ddof=1)
        expected_beta = cov[0, 1] / cov[1, 1]
        expected_alpha = ((strat.mean() - 0.03 / 244)
                          - expected_beta * (bench.mean() - 0.03 / 244)) * 244
        expected_bench_total = float((1 + bench_ret.loc[common]).prod() - 1)

        assert analytics["beta"] == pytest.approx(expected_beta, rel=1e-9)
        assert analytics["alpha"] == pytest.approx(expected_alpha, rel=1e-9)
        assert analytics["benchmark_return"] == pytest.approx(expected_bench_total)

    def test_calc_metrics_renders_na(self, monkeypatch):
        """HTML metric layer must render N/A for the NaN benchmark family."""
        import eqlib.attribution as attribution
        from eqlib.report import _calc_metrics

        nan = float("nan")
        analytics = {
            "total_return": 0.05, "annual_return": 0.05,
            "annual_volatility": 0.10, "sharpe_ratio": 0.5,
            "sortino_ratio": 0.6, "max_drawdown": -0.04,
            "calmar_ratio": 1.25, "win_rate_trade": 0.5,
            "win_rate_daily": 0.5, "profit_loss_ratio": 1.0,
            "win_count": 1, "loss_count": 1, "trade_count": 2,
            "alpha": nan, "beta": nan, "information_ratio": nan,
            "benchmark_return": nan, "excess_return": nan,
            "excess_return_max_drawdown": nan, "excess_return_sharpe": nan,
            "daily_excess_return": nan, "benchmark_volatility": nan,
            "monthly_returns": {}, "rolling_sharpe_60d": [],
            "rolling_volatility_60d": [], "daily_returns_stats": {},
            "drawdown_periods": [],
        }
        monkeypatch.setattr(attribution, "analyze_returns", lambda r: analytics)

        metrics = _calc_metrics({}, [])
        assert metrics["alpha"] == "N/A"
        assert metrics["beta"] == "N/A"
        assert metrics["info_ratio"] == "N/A"
        assert metrics["benchmark_ret"] == "N/A"
        assert metrics["benchmark_ret_pct"] == "N/A"
        assert metrics["excess_return"] == "N/A"
        assert metrics["bm_vol"] == "N/A"
        assert metrics["benchmark_note"] == "基准数据不可用"

    def test_calc_metrics_chart_fallback_marked(self, monkeypatch):
        """Chart-caliber fallback for the headline is explicitly annotated."""
        import eqlib.attribution as attribution
        from eqlib.report import _calc_metrics

        nan = float("nan")
        analytics = {
            "total_return": 0.05, "annual_return": 0.05,
            "annual_volatility": 0.10, "sharpe_ratio": 0.5,
            "sortino_ratio": 0.6, "max_drawdown": -0.04,
            "calmar_ratio": 1.25, "win_rate_trade": 0.5,
            "win_rate_daily": 0.5, "profit_loss_ratio": 1.0,
            "win_count": 1, "loss_count": 1, "trade_count": 2,
            "alpha": nan, "beta": nan, "information_ratio": nan,
            "benchmark_return": nan, "excess_return": nan,
            "excess_return_max_drawdown": nan, "excess_return_sharpe": nan,
            "daily_excess_return": nan, "benchmark_volatility": nan,
            "monthly_returns": {}, "rolling_sharpe_60d": [],
            "rolling_volatility_60d": [], "daily_returns_stats": {},
            "drawdown_periods": [],
        }
        monkeypatch.setattr(attribution, "analyze_returns", lambda r: analytics)

        bench_data = [{"time": "2024-01-02", "value": 0.0},
                      {"time": "2024-02-01", "value": 10.0}]
        metrics = _calc_metrics({}, bench_data)
        assert metrics["benchmark_ret"] == "10.00%"
        assert metrics["benchmark_note"] == "基准指标不可用，卡片值为图表口径"
        # excess = total - chart bench in the fallback path
        assert metrics["excess_return"] == "-5.00%"

    def test_calc_metrics_prefers_analytics_caliber(self, monkeypatch):
        """Single source of truth: analytics benchmark wins over the chart."""
        import eqlib.attribution as attribution
        from eqlib.report import _calc_metrics

        analytics = {
            "total_return": 0.05, "annual_return": 0.05,
            "annual_volatility": 0.10, "sharpe_ratio": 0.5,
            "sortino_ratio": 0.6, "max_drawdown": -0.04,
            "calmar_ratio": 1.25, "win_rate_trade": 0.5,
            "win_rate_daily": 0.5, "profit_loss_ratio": 1.0,
            "win_count": 1, "loss_count": 1, "trade_count": 2,
            "alpha": 0.01, "beta": 0.9, "information_ratio": 0.3,
            "benchmark_return": 0.08, "excess_return": -0.03,
            "excess_return_max_drawdown": -0.02, "excess_return_sharpe": 0.1,
            "daily_excess_return": -0.01, "benchmark_volatility": 0.12,
            "monthly_returns": {}, "rolling_sharpe_60d": [],
            "rolling_volatility_60d": [], "daily_returns_stats": {},
            "drawdown_periods": [],
        }
        monkeypatch.setattr(attribution, "analyze_returns", lambda r: analytics)

        # Chart says +10% while analytics says +8% -> analytics must win.
        bench_data = [{"time": "2024-01-02", "value": 0.0},
                      {"time": "2024-02-01", "value": 10.0}]
        metrics = _calc_metrics({}, bench_data)
        assert metrics["benchmark_ret"] == "8.00%"
        assert metrics["benchmark_note"] == ""
        # Excess is the arithmetic gap vs the displayed benchmark caliber.
        assert metrics["excess_return"] == "-3.00%"

    def test_report_json_nan_targets_are_unknown_not_failed(self, tmp_path, monkeypatch):
        """NaN alpha/beta must surface as pass=None, never as a failed target."""
        import eqlib.attribution as attribution
        import eqlib.data as data_mod
        from eqlib.report import generate_report_json

        nan = float("nan")
        analytics = {
            "annual_return": 0.12, "sharpe_ratio": 1.1, "max_drawdown": -0.08,
            "win_rate_trade": 0.5, "alpha": nan, "beta": nan, "trade_count": 4,
            "annual_volatility": 0.15, "total_return": 0.1, "sortino_ratio": 1.2,
            "calmar_ratio": 1.5, "win_rate_daily": 0.52, "profit_loss_ratio": 1.8,
            "information_ratio": nan, "excess_return": nan, "benchmark_return": nan,
            "monthly_returns": {}, "rolling_sharpe_60d": [],
            "rolling_volatility_60d": [], "drawdown_periods": [],
            "daily_returns_stats": {}, "per_stock_pnl": {},
        }
        monkeypatch.setattr(attribution, "analyze_returns", lambda r: analytics)
        monkeypatch.setattr(attribution, "fama_french_analysis", lambda r: {})
        monkeypatch.setattr(attribution, "brinson_attribution", lambda r: {})
        monkeypatch.setattr(data_mod, "fetch_stock_data",
                            lambda *a, **k: pd.DataFrame())

        portfolio = SimpleNamespace(starting_cash=100000.0, total_value=110000.0,
                                    positions={})
        context = SimpleNamespace(start_date=dt.date(2024, 1, 1),
                                  end_date=dt.date(2024, 1, 10),
                                  portfolio=portfolio, universe=[])
        result = {
            "context": context,
            "trade_log": [],
            "recorded_values": [
                {"date": dt.date(2024, 1, 1), "total_value": 100000.0},
                {"date": dt.date(2024, 1, 10), "total_value": 110000.0},
            ],
            "benchmark": "000300.XSHG",
            "ohlcv_data": {},
            "data_diagnostics": {},
        }

        out_path = tmp_path / "report.json"
        generate_report_json(result, out_path)
        payload = json.loads(out_path.read_text())

        targets = {t["metric"]: t for t in payload["targets"]}
        assert targets["alpha"]["pass"] is None
        assert targets["alpha"]["value"] is None
        assert targets["beta"]["pass"] is None
        # Real metrics still evaluate normally.
        assert targets["sharpe_ratio"]["pass"] is True
        # risk_metrics surfaces JSON null for the unavailable family.
        assert payload["risk_metrics"]["alpha"] is None
        assert payload["risk_metrics"]["benchmark_return"] is None
        assert payload["summary"]["benchmark_return"] is None


# ---------------------------------------------------------------------------
# True single-period BHB Brinson attribution (QUANT-P1-04)
# ---------------------------------------------------------------------------

class TestBrinsonBHB:
    """Brinson decomposition must be mathematically closed BHB."""

    def _two_stock_result(self):
        """AAA traded small (+20%), BBB traded big (+10%); universe = both.

        Portfolio: cost 1000 in AAA, 30000 in BBB.
        Benchmark: equal-weight buy&hold of universe (AAA +20%, BBB +10%).
        """
        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.0, "amount": 100,
             "commission": 0.0, "date": dt.date(2024, 1, 3)},
            {"type": "SELL", "security": "AAA", "price": 12.0, "amount": 100,
             "commission": 0.0, "date": dt.date(2024, 1, 20)},
            {"type": "BUY", "security": "BBB", "price": 10.0, "amount": 3000,
             "commission": 0.0, "date": dt.date(2024, 1, 3)},
        ]
        positions = {"BBB": SimpleNamespace(total_value=33000.0, amount=3000)}
        ohlcv = {
            "AAA": _ohlcv([10.0, 12.0]),
            "BBB": _ohlcv([10.0, 11.0]),
        }
        return _make_result(
            [0.001] * 30,
            trades=trades, positions=positions,
            universe=["AAA", "BBB"], ohlcv_data=ohlcv,
        )

    def test_closed_math_two_sectors_hand_computed(self):
        from eqlib.attribution import brinson_attribution

        result = self._two_stock_result()
        br = brinson_attribution(result, sector_data={"AAA": "Tech", "BBB": "Fin"})

        # Hand-computed expectations (see audit QUANT-P1-04 fix):
        w_p_t, w_p_f = 1000 / 31000, 30000 / 31000
        r_p = w_p_t * 0.20 + w_p_f * 0.10          # 3200/31000
        r_b = 0.5 * 0.20 + 0.5 * 0.10              # 0.15
        exp_alloc = (w_p_t - 0.5) * 0.20 + (w_p_f - 0.5) * 0.10
        exp_sel = 0.5 * (0.20 - 0.20) + 0.5 * (0.10 - 0.10)
        exp_inter = (w_p_t - 0.5) * (0.20 - 0.20) + (w_p_f - 0.5) * (0.10 - 0.10)

        assert br["allocation_effect"] == pytest.approx(exp_alloc, abs=1e-12)
        assert br["selection_effect"] == pytest.approx(exp_sel, abs=1e-12)
        assert br["interaction_effect"] == pytest.approx(exp_inter, abs=1e-12)
        assert br["portfolio_return"] == pytest.approx(r_p, abs=1e-12)
        assert br["benchmark_return"] == pytest.approx(r_b, abs=1e-12)
        # Closure: the three effects sum exactly to the active return.
        total = br["allocation_effect"] + br["selection_effect"] + br["interaction_effect"]
        assert total == pytest.approx(br["total_active_return"], abs=1e-12)
        assert br["total_active_return"] == pytest.approx(r_p - r_b, abs=1e-12)
        assert br["benchmark_model"] == "universe_equal_weight"
        # sector_data genuinely drives the grouping: overweighting Tech (whose
        # benchmark leg returned +20%) yields a negative allocation effect.
        assert br["allocation_effect"] < 0
        assert set(br["sectors"]) == {"Tech", "Fin"}
        assert br["sectors"]["Tech"]["weight_portfolio"] == pytest.approx(w_p_t)
        assert br["sectors"]["Tech"]["weight_benchmark"] == pytest.approx(0.5)

    def test_sector_data_changes_result(self):
        """The sector_data parameter must actually affect the attribution."""
        from eqlib.attribution import brinson_attribution

        result = self._two_stock_result()
        with_sectors = brinson_attribution(
            result, sector_data={"AAA": "Tech", "BBB": "Fin"})
        without = brinson_attribution(result)

        # Without sector data there is exactly one sector: allocation and
        # interaction are identically zero, selection carries everything.
        assert without["allocation_effect"] == pytest.approx(0.0, abs=1e-15)
        assert without["interaction_effect"] == pytest.approx(0.0, abs=1e-15)
        assert without["selection_effect"] == pytest.approx(
            without["total_active_return"], abs=1e-12)
        # Same total active return either way (closure preserved).
        assert with_sectors["total_active_return"] == pytest.approx(
            without["total_active_return"], abs=1e-12)
        # But the split differs — the parameter is not decorative.
        assert with_sectors["allocation_effect"] != pytest.approx(
            without["allocation_effect"], abs=1e-6)

    def test_evaluator_scenario_no_split_artifact(self):
        """Single stock +10% vs universe benchmark +5% -> total active +5%.

        Regression for the audit reproduction where the old code reported
        +2.5%/+2.5%/+2.5% = +7.5% against a true +5% active return.
        """
        from eqlib.attribution import brinson_attribution

        trades = [
            {"type": "BUY", "security": "AAA", "price": 10.0, "amount": 10000,
             "commission": 0.0, "date": dt.date(2024, 1, 3)},
        ]
        positions = {"AAA": SimpleNamespace(total_value=110000.0, amount=10000)}
        ohlcv = {
            "AAA": _ohlcv([10.0, 11.0]),   # +10%
            "XXX": _ohlcv([10.0, 10.0]),   # 0%  -> universe mean = +5%
        }
        result = _make_result(
            [0.001] * 30,
            trades=trades, positions=positions,
            universe=["AAA", "XXX"], ohlcv_data=ohlcv,
        )
        br = brinson_attribution(result)

        assert br["portfolio_return"] == pytest.approx(0.10, abs=1e-12)
        assert br["benchmark_return"] == pytest.approx(0.05, abs=1e-12)
        assert br["total_active_return"] == pytest.approx(0.05, abs=1e-12)
        total = (br["allocation_effect"] + br["selection_effect"]
                 + br["interaction_effect"])
        assert total == pytest.approx(0.05, abs=1e-12)

    def test_scalar_benchmark_series_model(self):
        """Caller-supplied benchmark_returns: uniform per-sector benchmark."""
        from eqlib.attribution import brinson_attribution

        result = self._two_stock_result()
        bench_daily = pd.Series(
            [0.001] * 30,
            index=pd.bdate_range("2024-01-02", periods=30, freq="B"),
        )
        br = brinson_attribution(result, benchmark_returns=bench_daily)

        expected_bench = float((1 + bench_daily).prod() - 1)
        assert br["benchmark_model"] == "scalar_series"
        assert br["benchmark_return"] == pytest.approx(expected_bench)
        # Scalar benchmark is uniform across sectors -> allocation is 0.
        assert br["allocation_effect"] == pytest.approx(0.0, abs=1e-12)
        total = (br["allocation_effect"] + br["selection_effect"]
                 + br["interaction_effect"])
        assert total == pytest.approx(br["total_active_return"], abs=1e-12)
        assert br["total_active_return"] == pytest.approx(
            br["portfolio_return"] - expected_bench, abs=1e-12)

    def test_empty_result_returns_none(self):
        from eqlib.attribution import brinson_attribution

        result = _make_result([0.001] * 10)
        assert brinson_attribution(result) is None
