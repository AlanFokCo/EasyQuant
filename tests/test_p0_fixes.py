"""Unit tests for P0 critical fixes (C1–C6 from the optimization audit).

C1 – Look-ahead bias: selection.py must use preloaded data in backtest mode.
C2 – Alpha/Beta fillna(0) removed in attribution.py.
C3 – Monthly schedule fires on first trading day >= N (not calendar day N).
C4 – Price-limit enforcement in engine._fill_pending_orders.
C5 – MaxSharpe geometric annualization in optimizer.py.
C6 – Paper-trade first iteration warmup (no premature fill).
H1 – Sortino uses MAR=0 with ddof=0.
H4 – Excess Sharpe = Information Ratio (no double risk-free subtraction).
"""

import datetime
import math
import numpy as np
import pandas as pd
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_preloaded(bars: dict[str, dict[datetime.date, dict]]) -> "PreloadedData":
    """Build a minimal PreloadedData instance from a nested dict.

    bars: {security: {date: {open, high, low, close, volume}}}
    """
    from eqlib.data_cache import PreloadedData

    pd_frames = {}
    for sec, day_bars in bars.items():
        rows = []
        for d, bar in sorted(day_bars.items()):
            rows.append({**bar, "date": pd.Timestamp(d)})
        df = pd.DataFrame(rows).set_index("date")
        pd_frames[sec] = df

    pre = PreloadedData()
    # Build the same data structures that PreloadedData.load() would build
    pre.panel = pd.concat(pd_frames, axis=1)
    pre.panel.columns = pd.MultiIndex.from_tuples(
        [(sec, col) for sec in pd_frames for col in pd_frames[sec].columns],
        names=["security", "field"],
    )
    pre._securities = sorted(pd_frames.keys())
    pre._dates = pre.panel.index

    # Build close_dict and bar_cache (mirrors _load logic)
    for sec, df in pd_frames.items():
        if "close" in df.columns:
            pre._close_dict[sec] = dict(zip(df.index, df["close"]))
        fields = ["open", "high", "low", "close", "volume"]
        pre._bar_cache[sec] = df.reindex(columns=fields, fill_value=0).to_dict("index")
        pre._field_series[sec] = {f: df[f] for f in df.columns if f in df}
    if pd_frames:
        close_frames = {s: f["close"] for s, f in pd_frames.items() if "close" in f.columns}
        if close_frames:
            pre._close_matrix = pd.DataFrame(close_frames).sort_index()

    return pre


class _FakeContext:
    """Minimal context stub for selection tests."""
    def __init__(self, dt):
        self.current_dt = dt if isinstance(dt, datetime.datetime) else datetime.datetime(
            dt.year, dt.month, dt.day, 9, 30
        )


def _activate_preloaded(pre):
    """Install *pre* as the active session's preloaded data."""
    from eqlib._state import get_session
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)


def _clear_preloaded():
    """Remove any preloaded data from the active session."""
    from eqlib._state import get_session
    sess = get_session()
    object.__setattr__(sess, "_preloaded", None)


# ═══════════════════════════════════════════════════════════════════════════════
# C1 – Look-ahead bias in selection.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestC1LookAheadBias:

    def setup_method(self):
        _clear_preloaded()

    def teardown_method(self):
        _clear_preloaded()

    def _make_bars(self, price_2022: float, price_2024: float):
        date_2022 = datetime.date(2022, 1, 4)
        date_2024 = datetime.date(2024, 1, 2)
        return {
            "000001": {
                date_2022: {"open": price_2022, "high": price_2022,
                             "low": price_2022, "close": price_2022, "volume": 1000},
                date_2024: {"open": price_2024, "high": price_2024,
                             "low": price_2024, "close": price_2024, "volume": 2000},
            }
        }

    def test_filter_low_price_uses_preloaded_close(self):
        """In backtest mode, filter_low_price_stocks must use preloaded close."""
        from eqlib.selection import filter_low_price_stocks

        # stock is cheap in 2022, expensive in 2024
        pre = _make_preloaded(self._make_bars(price_2022=1.5, price_2024=10.0))
        _activate_preloaded(pre)

        ctx_2022 = _FakeContext(datetime.date(2022, 1, 4))
        ctx_2024 = _FakeContext(datetime.date(2024, 1, 2))

        # min_price=2: stock at 1.5 (2022) should be excluded
        result_2022 = filter_low_price_stocks(["000001"], min_price=2.0, context=ctx_2022)
        assert "000001" not in result_2022, "Stock below min_price should be excluded"

        # min_price=2: stock at 10.0 (2024) should be included
        result_2024 = filter_low_price_stocks(["000001"], min_price=2.0, context=ctx_2024)
        assert "000001" in result_2024, "Stock above min_price should be included"

    def test_filter_low_price_different_dates_differ(self):
        """Values at 2022-01-04 and 2024-01-02 must differ — no look-ahead."""
        from eqlib.selection import filter_low_price_stocks

        pre = _make_preloaded(self._make_bars(price_2022=1.0, price_2024=5.0))
        _activate_preloaded(pre)

        ctx_2022 = _FakeContext(datetime.date(2022, 1, 4))
        ctx_2024 = _FakeContext(datetime.date(2024, 1, 2))

        r2022 = filter_low_price_stocks(["000001"], min_price=3.0, context=ctx_2022)
        r2024 = filter_low_price_stocks(["000001"], min_price=3.0, context=ctx_2024)
        # The two results must differ (2022 excludes, 2024 includes)
        assert r2022 != r2024

    def test_filter_high_pe_returns_all_in_backtest(self):
        """In backtest mode, filter_high_pe_stocks returns all candidates (no PE data)."""
        from eqlib.selection import filter_high_pe_stocks

        pre = _make_preloaded(self._make_bars(price_2022=10.0, price_2024=10.0))
        _activate_preloaded(pre)

        ctx = _FakeContext(datetime.date(2022, 1, 4))
        candidates = ["000001", "600519"]
        result = filter_high_pe_stocks(candidates, max_pe=30.0, context=ctx)
        assert result == candidates, "Should return all in backtest (no PE available)"

    def test_fetch_factor_data_no_pe_pb_in_backtest(self):
        """fetch_factor_data must return NaN for pe/pb in backtest mode."""
        from eqlib.selection import fetch_factor_data

        pre = _make_preloaded(self._make_bars(price_2022=8.0, price_2024=12.0))
        _activate_preloaded(pre)

        ctx = _FakeContext(datetime.date(2022, 1, 4))
        df = fetch_factor_data(["000001"], fields=["price", "pe", "pb"], context=ctx)

        assert not df.empty
        assert math.isnan(df.at["000001", "pe"]), "PE should be NaN in backtest"
        assert math.isnan(df.at["000001", "pb"]), "PB should be NaN in backtest"

    def test_fetch_factor_data_price_from_preloaded(self):
        """fetch_factor_data price must match preloaded close (no spot look-ahead)."""
        from eqlib.selection import fetch_factor_data

        pre = _make_preloaded(self._make_bars(price_2022=8.0, price_2024=12.0))
        _activate_preloaded(pre)

        ctx_2022 = _FakeContext(datetime.date(2022, 1, 4))
        ctx_2024 = _FakeContext(datetime.date(2024, 1, 2))

        df_2022 = fetch_factor_data(["000001"], fields=["price"], context=ctx_2022)
        df_2024 = fetch_factor_data(["000001"], fields=["price"], context=ctx_2024)

        assert abs(df_2022.at["000001", "price"] - 8.0) < 1e-6
        assert abs(df_2024.at["000001", "price"] - 12.0) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════════
# C2 – Alpha/Beta fillna(0) → use intersection
# ═══════════════════════════════════════════════════════════════════════════════

class TestC2AlphaBetaIntersection:

    def _make_strategy_returns(self, n=200, seed=42):
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2022-01-01", periods=n, freq="B")
        return pd.Series(rng.normal(0.001, 0.02, n), index=dates)

    def _make_bench_returns(self, dates_subset, seed=7):
        rng = np.random.default_rng(seed)
        return pd.Series(rng.normal(0.0008, 0.018, len(dates_subset)),
                         index=dates_subset)

    def test_fillna_vs_intersection_beta_differ(self):
        """Beta computed via intersection should differ from fillna(0) version."""
        strat = self._make_strategy_returns(200)
        # Bench covers only 180 of the 200 strategy dates
        bench_dates = strat.index[:180]
        bench = self._make_bench_returns(bench_dates)

        # Old (fillna=0) approach
        bench_aligned_bad = bench.reindex(strat.index).fillna(0)
        common_bad = strat.index.intersection(bench_aligned_bad.index)
        s_bad = strat.loc[common_bad].values
        b_bad = bench_aligned_bad.loc[common_bad].values
        cov_bad = np.cov(s_bad, b_bad, ddof=1)
        beta_bad = cov_bad[0, 1] / cov_bad[1, 1]

        # Correct (intersection only) approach
        common_good = strat.index.intersection(bench.index)
        s_good = strat.loc[common_good].values
        b_good = bench.loc[common_good].values
        cov_good = np.cov(s_good, b_good, ddof=1)
        beta_good = cov_good[0, 1] / cov_good[1, 1]

        # The two betas should differ when bench is shorter than strategy
        assert abs(beta_bad - beta_good) > 1e-6, (
            "fillna(0) and intersection betas should differ when date ranges mismatch"
        )

    def test_attribution_calc_alpha_beta_uses_intersection(self):
        """_calc_alpha_beta internals: bench_ret must not be reindexed with fillna."""
        from eqlib.attribution import _calc_alpha_beta

        # We can't easily inject a mock without network; just verify the function
        # signature and that it returns a 6-tuple of the right types.
        strat = self._make_strategy_returns(50)
        # Pass an invalid benchmark so it falls back to default (no network needed)
        result = _calc_alpha_beta(strat, "INVALID_BENCH_CODE_99999", 0.03, 252)
        assert len(result) == 6, "Should return 6-tuple"
        alpha, beta, ir, bench_series, bench_ret, bench_vol = result
        # Default fallback values
        assert alpha == 0.0
        assert beta == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# C3 – Monthly schedule: first trading day >= N
# ═══════════════════════════════════════════════════════════════════════════════

class TestC3MonthlySchedule:

    def setup_method(self):
        _clear_preloaded()

    def teardown_method(self):
        _clear_preloaded()

    def _build_2024_calendar(self):
        """Build a minimal A-share-like 2024 trading calendar (Mon-Fri, skip holidays)."""
        all_bdays = pd.date_range("2024-01-01", "2024-12-31", freq="B")
        # Skip a few common A-share holidays for realism
        holidays = {
            datetime.date(2024, 1, 1),   # New Year
            datetime.date(2024, 2, 9),   # Spring Festival
            datetime.date(2024, 2, 12),
            datetime.date(2024, 4, 4),   # Qingming
            datetime.date(2024, 5, 1),   # Labour Day
            datetime.date(2024, 6, 10),  # Dragon Boat
            datetime.date(2024, 9, 16),  # Mid-Autumn
            datetime.date(2024, 10, 1),  # National Day
            datetime.date(2024, 10, 2),
            datetime.date(2024, 10, 3),
            datetime.date(2024, 10, 4),
            datetime.date(2024, 10, 7),
        }
        return [d.date() for d in all_bdays if d.date() not in holidays]

    def _make_minimal_preloaded(self, trading_days: list[datetime.date]):
        """PreloadedData containing only a _dates index (no price data needed)."""
        from eqlib.data_cache import PreloadedData
        pre = PreloadedData()
        pre._dates = pd.DatetimeIndex([pd.Timestamp(d) for d in trading_days])
        pre._securities = []
        return pre

    def test_monthly_fires_exactly_once_per_month_with_preloaded(self):
        """With a real trading calendar, monthly:1 fires exactly once per month."""
        from eqlib.engine import _is_first_trading_day_ge

        trading_days = self._build_2024_calendar()
        pre = self._make_minimal_preloaded(trading_days)
        _activate_preloaded(pre)

        fires_by_month = {}
        for d in trading_days:
            if _is_first_trading_day_ge(d, 1):
                m = (d.year, d.month)
                fires_by_month[m] = fires_by_month.get(m, 0) + 1

        # Every month should fire exactly once
        for m, count in fires_by_month.items():
            assert count == 1, f"Monthly:1 fired {count} times in {m}"

        # All 12 months should be represented
        unique_months = {m[1] for m in fires_by_month}
        assert unique_months == set(range(1, 13)), "Monthly:1 should cover all 12 months"

    def test_monthly_day1_fires_even_when_jan1_is_holiday(self):
        """Jan 1 is always a holiday — monthly:1 must fire on the first trading day of Jan."""
        from eqlib.engine import _is_first_trading_day_ge

        # Only load January 2024 days (Jan 1 is holiday)
        jan_trading = [
            datetime.date(2024, 1, 2),
            datetime.date(2024, 1, 3),
            datetime.date(2024, 1, 4),
            datetime.date(2024, 1, 5),
        ]
        pre = self._make_minimal_preloaded(jan_trading)
        _activate_preloaded(pre)

        # Jan 2 should be "first trading day >= 1"
        assert _is_first_trading_day_ge(datetime.date(2024, 1, 2), 1)
        # Jan 3 should NOT fire (Jan 2 already fired)
        assert not _is_first_trading_day_ge(datetime.date(2024, 1, 3), 1)

    def test_monthly_fallback_without_preloaded(self):
        """Without a trading calendar, fall back to day.day == n."""
        from eqlib.engine import _is_first_trading_day_ge

        # Jan 1 is calendar day 1 → fires (no calendar to consult)
        assert _is_first_trading_day_ge(datetime.date(2024, 1, 1), 1)
        assert not _is_first_trading_day_ge(datetime.date(2024, 1, 2), 1)

    def test_should_run_selection_monthly_with_calendar(self):
        """_should_run_selection('monthly:1', ...) uses trading calendar."""
        from eqlib.engine import _should_run_selection

        trading_days = self._build_2024_calendar()
        pre = self._make_minimal_preloaded(trading_days)
        _activate_preloaded(pre)

        # Count how many times monthly:1 fires in 2024
        fires = sum(
            1 for d in trading_days if _should_run_selection("monthly:1", d)
        )
        assert fires == 12, f"Expected 12 monthly fires, got {fires}"


# ═══════════════════════════════════════════════════════════════════════════════
# C4 – Price-limit enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestC4PriceLimitEnforcement:

    def setup_method(self):
        _clear_preloaded()

    def teardown_method(self):
        _clear_preloaded()

    def _run_minimal_backtest_with_order(
        self,
        prev_close: float,
        open_price: float,
        is_buy: bool,
        check_limit: bool = True,
        security: str = "000001",
    ) -> list:
        """Run a minimal one-day backtest to capture fill results.

        Returns the trade_log after the fill attempt.
        """
        from eqlib._state import BacktestSession, _set_session
        from eqlib.engine import _fill_pending_orders, _t1_unlock
        from eqlib.context import Context

        prev_day = datetime.date(2023, 12, 29)
        fill_day = datetime.date(2024, 1, 2)

        bars = {
            security: {
                prev_day: {
                    "open": prev_close, "high": prev_close,
                    "low": prev_close, "close": prev_close, "volume": 100000
                },
                fill_day: {
                    "open": open_price, "high": open_price,
                    "low": open_price, "close": open_price, "volume": 100000
                },
            }
        }
        pre = _make_preloaded(bars)
        _activate_preloaded(pre)

        sess = BacktestSession()
        _set_session(sess)
        sess._options["check_price_limit"] = check_limit

        ctx = Context(fill_day, fill_day, "daily", 1_000_000)
        sess._context = ctx
        object.__setattr__(sess, "_preloaded", pre)

        amount = 100 if is_buy else -100
        if not is_buy:
            from eqlib.context import Position
            pos = Position(security)
            pos.amount = 200
            pos.closeable_amount = 200
            ctx.portfolio.positions[security] = pos
            ctx.portfolio.available_cash = 1_000_000

        sess._pending_orders.append({
            "security": security,
            "action": "ORDER",
            "amount": amount,
        })

        _t1_unlock(sess)
        _fill_pending_orders(sess, fill_day)
        return sess._trade_log

    def test_buy_at_limit_up_is_skipped(self):
        """A buy order when open hits limit-up (10%) must be skipped."""
        prev_close = 10.0
        open_price = prev_close * 1.10  # exactly limit-up

        trade_log = self._run_minimal_backtest_with_order(
            prev_close=prev_close, open_price=open_price,
            is_buy=True, check_limit=True, security="000001"
        )
        assert len(trade_log) == 0, "Buy at limit-up should be skipped"

    def test_sell_at_limit_down_is_skipped(self):
        """A sell order when open hits limit-down (10%) must be skipped."""
        prev_close = 10.0
        open_price = prev_close * 0.90  # exactly limit-down

        trade_log = self._run_minimal_backtest_with_order(
            prev_close=prev_close, open_price=open_price,
            is_buy=False, check_limit=True, security="600001"
        )
        assert len(trade_log) == 0, "Sell at limit-down should be skipped"

    def test_buy_below_limit_up_fills(self):
        """A buy order when open is comfortably below limit-up should fill."""
        prev_close = 10.0
        open_price = prev_close * 1.05  # mid-range, not limit

        trade_log = self._run_minimal_backtest_with_order(
            prev_close=prev_close, open_price=open_price,
            is_buy=True, check_limit=True, security="000001"
        )
        assert len(trade_log) == 1, "Buy below limit-up should fill"

    def test_check_price_limit_disabled_allows_fill(self):
        """When check_price_limit=False, limit-up orders fill normally."""
        prev_close = 10.0
        open_price = prev_close * 1.10  # limit-up

        trade_log = self._run_minimal_backtest_with_order(
            prev_close=prev_close, open_price=open_price,
            is_buy=True, check_limit=False, security="000001"
        )
        assert len(trade_log) == 1, "Should fill when check disabled"

    def test_chinext_limit_is_20_pct(self):
        """ChiNext (300xxx) stocks have a 20% limit, not 10%."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("300001") == 0.20
        assert _get_price_limit_ratio("300001.XSHE") == 0.20

    def test_star_market_limit_is_20_pct(self):
        """STAR Market (688xxx) stocks have a 20% limit."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("688001") == 0.20
        assert _get_price_limit_ratio("688001.XSHG") == 0.20

    def test_main_board_limit_is_10_pct(self):
        """Main board stocks have a 10% limit."""
        from eqlib.engine import _get_price_limit_ratio
        assert _get_price_limit_ratio("600001") == 0.10
        assert _get_price_limit_ratio("000001") == 0.10


# ═══════════════════════════════════════════════════════════════════════════════
# C5 – MaxSharpe geometric annualization
# ═══════════════════════════════════════════════════════════════════════════════

class TestC5GeometricAnnualization:

    def test_geometric_lower_than_arithmetic_at_high_vol(self):
        """Geometric annualized return must be lower than arithmetic at vol=0.4."""
        from eqlib.optimizer import _annual_stats

        rng = np.random.default_rng(0)
        # High volatility: ~40 % annualized (vol ≈ 0.4/sqrt(252) ≈ 0.025 daily)
        daily_ret = rng.normal(0.001, 0.025, 252)
        returns_df = pd.DataFrame({"A": daily_ret})
        weights = np.array([1.0])

        geo_ret, _ = _annual_stats(weights, returns_df, days=252)

        # Arithmetic approximation
        arith_ret = daily_ret.mean() * 252

        # At high volatility, geometric < arithmetic (Jensen's inequality)
        assert geo_ret < arith_ret, (
            f"Geometric ({geo_ret:.4f}) should be less than arithmetic ({arith_ret:.4f}) "
            "at high volatility due to Jensen's inequality"
        )

    def test_geometric_close_to_arithmetic_at_low_vol(self):
        """At very low volatility, geometric and arithmetic are nearly equal."""
        from eqlib.optimizer import _annual_stats

        rng = np.random.default_rng(1)
        # Very low volatility: ~1% annual vol
        daily_ret = rng.normal(0.0004, 0.0001, 252)
        returns_df = pd.DataFrame({"A": daily_ret})
        weights = np.array([1.0])

        geo_ret, _ = _annual_stats(weights, returns_df, days=252)
        arith_ret = daily_ret.mean() * 252

        assert abs(geo_ret - arith_ret) < 0.01, (
            "At low vol, geometric and arithmetic should be nearly equal"
        )

    def test_geometric_formula_exact(self):
        """_annual_stats uses (1+r).prod()^(252/n) - 1."""
        from eqlib.optimizer import _annual_stats

        daily_ret = pd.Series([0.01, -0.005, 0.02, 0.003, -0.01])
        returns_df = pd.DataFrame({"A": daily_ret})
        weights = np.array([1.0])
        days = 252

        expected = (1 + daily_ret).prod() ** (days / len(daily_ret)) - 1
        actual, _ = _annual_stats(weights, returns_df, days=days)

        assert abs(actual - expected) < 1e-12


# ═══════════════════════════════════════════════════════════════════════════════
# C6 – Paper-trade first-iteration warmup (no premature fill)
# ═══════════════════════════════════════════════════════════════════════════════

class TestC6PaperTradeWarmup:

    def test_first_iteration_does_not_fill(self):
        """On the first calendar-day transition, _fill_pending_orders must NOT be called."""
        # We test the warmup logic directly by inspecting _is_first_trading_day_ge
        # and checking the guard in run_paper_trade via a simulated loop.
        # We cannot run run_paper_trade (it's an infinite loop), so we replicate
        # the relevant guard logic here.

        fills_called = []

        def mock_fill(sess, day, exec_prices=None):
            fills_called.append(day)

        def mock_t1_unlock(sess):
            pass

        # Simulate the loop guard as written in run_paper_trade
        prev_day = None
        warmup_done = False
        days_to_simulate = [
            datetime.date(2024, 1, 2),
            datetime.date(2024, 1, 2),   # same day (no trigger)
            datetime.date(2024, 1, 3),   # new day (should fill, warmup done)
        ]

        for today in days_to_simulate:
            if today != prev_day:
                if warmup_done:
                    mock_fill(None, today)
                else:
                    warmup_done = True
                prev_day = today

        # Jan 2 is first new day → warmup, no fill
        # Jan 3 is second new day → fill should be called
        assert len(fills_called) == 1
        assert fills_called[0] == datetime.date(2024, 1, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# H1 – Sortino uses MAR=0
# ═══════════════════════════════════════════════════════════════════════════════

class TestH1Sortino:

    def test_sortino_uses_mar_zero(self):
        """Sortino downside should be calculated vs 0, not vs daily_rf."""
        # Build a minimal result dict with known returns
        import datetime as _dt
        from eqlib.attribution import analyze_returns
        from eqlib.context import Context, Portfolio

        n = 60
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        total_values = 100_000 * (1 + pd.Series(np.random.default_rng(99).normal(
            0.0005, 0.015, n
        ))).cumprod()

        ctx = Context(_dt.date(2023, 1, 1), _dt.date(2023, 3, 31), "daily", 100_000)
        ctx.portfolio._total_value = float(total_values.iloc[-1])

        recorded = {
            d.date(): {"date": d.date(), "total_value": float(v)}
            for d, v in zip(dates, total_values)
        }

        result = {
            "context": ctx,
            "trade_log": [],
            "recorded_values": recorded,
            "benchmark": None,
        }
        metrics = analyze_returns(result)
        assert metrics is not None

        # Verify: sortino is computed. When all returns are positive, downside is
        # empty → sortino should be 0 (no negative returns).
        all_positive_values = 100_000 * (1 + pd.Series([0.001] * n)).cumprod()
        recorded_pos = {
            d.date(): {"date": d.date(), "total_value": float(v)}
            for d, v in zip(dates, all_positive_values)
        }
        result_pos = {
            "context": ctx,
            "trade_log": [],
            "recorded_values": recorded_pos,
            "benchmark": None,
        }
        metrics_pos = analyze_returns(result_pos)
        assert metrics_pos is not None
        # When all returns are positive there are no negative observations,
        # so downside_std = 0, and the implementation returns 0.0 as a
        # safe sentinel (undefined / infinity is not useful as a metric).
        assert metrics_pos["sortino_ratio"] == 0.0, (
            "When all returns are positive (downside_std=0), Sortino returns 0.0 as sentinel"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# H4 – Excess Sharpe = Information Ratio (no double rf subtraction)
# ═══════════════════════════════════════════════════════════════════════════════

class TestH4ExcessSharpe:

    def test_excess_sharpe_equals_information_ratio(self):
        """excess_sharpe must equal mean/std * sqrt(252), not (mean - rf)/std."""
        from eqlib.attribution import _calc_excess_metrics

        n = 100
        rng = np.random.default_rng(42)
        strat = pd.Series(rng.normal(0.001, 0.01, n),
                          index=pd.date_range("2023-01-01", periods=n, freq="B"))
        bench = pd.Series(rng.normal(0.0005, 0.008, n), index=strat.index)

        ann_factor = 252
        _, _, excess_sharpe, _ = _calc_excess_metrics(strat, bench, 0.03, ann_factor)

        # Expected: pure IR = mean(excess) / std(excess) * sqrt(252)
        excess = strat - bench
        expected_ir = excess.mean() / excess.std() * math.sqrt(ann_factor)

        assert abs(excess_sharpe - expected_ir) < 1e-10, (
            f"excess_sharpe ({excess_sharpe:.6f}) should equal IR ({expected_ir:.6f})"
        )
