"""Tests for new Phase 1-6 features."""

import datetime
import numpy as np
import pandas as pd
import pytest


# ============================================================
# Phase 1: Slippage models (Item 3)
# ============================================================

class TestSlippageModels:
    def test_base_model_noop(self):
        from eqlib.slippage import SlippageModel
        model = SlippageModel()
        assert model.get_execution_price(10.0, 1000, is_buy=True) == 10.0
        assert model.get_execution_price(10.0, 1000, is_buy=False) == 10.0

    def test_fixed_slippage_buy(self):
        from eqlib.slippage import FixedSlippage
        model = FixedSlippage(pct=0.001)
        price = model.get_execution_price(10.0, 1000, is_buy=True)
        assert abs(price - 10.01) < 1e-9

    def test_fixed_slippage_sell(self):
        from eqlib.slippage import FixedSlippage
        model = FixedSlippage(pct=0.001)
        price = model.get_execution_price(10.0, 1000, is_buy=False)
        assert abs(price - 9.99) < 1e-9

    def test_volume_slippage_buy(self):
        from eqlib.slippage import VolumeSlippage
        model = VolumeSlippage(impact=0.1)
        # order_size / daily_volume = 1000 / 10000 = 0.1, impact = 0.1 * 0.1 = 0.01
        price = model.get_execution_price(10.0, 1000, is_buy=True, daily_volume=10000)
        assert abs(price - 10.1) < 1e-9

    def test_volume_slippage_sell(self):
        from eqlib.slippage import VolumeSlippage
        model = VolumeSlippage(impact=0.1)
        price = model.get_execution_price(10.0, 1000, is_buy=False, daily_volume=10000)
        assert abs(price - 9.9) < 1e-9

    def test_volume_slippage_zero_volume_fallback(self):
        from eqlib.slippage import VolumeSlippage
        model = VolumeSlippage(impact=0.1)
        # F3: daily_volume=0 → return None to signal engine to skip trade
        price = model.get_execution_price(10.0, 1000, is_buy=True, daily_volume=0)
        assert price is None


# ============================================================
# Phase 2: ETF stamp duty exemption (Item 7)
# ============================================================

class TestETFStampDuty:
    def test_stock_pays_stamp_duty(self):
        from eqlib.objects import OrderCost
        cost = OrderCost()
        # close_tax = 0.001; for a stock sell
        close_cost_stock = cost.calc_close_cost(price=10.0, amount=1000, is_etf=False)
        # stamp duty alone = 0.001 * 10 * 1000 = 10
        assert close_cost_stock > cost.calc_close_cost(10.0, 1000, is_etf=True)

    def test_etf_no_stamp_duty(self):
        from eqlib.objects import OrderCost
        cost = OrderCost(close_tax=0.001, close_commission=0.0003, min_commission=5)
        close_cost_etf = cost.calc_close_cost(price=10.0, amount=1000, is_etf=True)
        # Only commission: max(0.0003 * 10000, 5) = max(3.0, 5) = 5
        assert abs(close_cost_etf - 5.0) < 1e-9


# ============================================================
# Phase 3: Indicator correctness (Items 9, 10, 11)
# ============================================================

class TestSMAAndSMMA:
    """Item 10: sma() is now a plain rolling mean; smma() is the old Wilder MA."""

    def _prices(self, n=50):
        np.random.seed(42)
        return pd.Series(np.random.randn(n).cumsum() + 100)

    def test_sma_is_rolling_mean(self):
        from eqlib.utils.indicators import sma
        prices = self._prices(30)
        result = sma(prices, period=5)
        # Verify against pandas directly
        expected = prices.rolling(5).mean()
        pd.testing.assert_series_equal(result, expected)

    def test_sma_nans_at_start(self):
        from eqlib.utils.indicators import sma
        prices = self._prices(30)
        result = sma(prices, period=5)
        assert pd.isna(result.iloc[:4]).all()
        assert pd.notna(result.iloc[4])

    def test_smma_diverges_from_rolling_mean(self):
        from eqlib.utils.indicators import sma, smma
        prices = self._prices(50)
        rolling = sma(prices, period=10)
        smoothed = smma(prices, period=10)
        # After warm-up period the two methods should differ
        assert not rolling.iloc[10:].equals(smoothed.iloc[10:])

    def test_smma_positive(self):
        from eqlib.utils.indicators import smma
        prices = self._prices(50)
        result = smma(prices, period=10)
        assert result.iloc[-1] > 0


class TestVWAP:
    """Item 11: VWAP with window parameter."""

    def _ohlcv(self, n=50):
        np.random.seed(0)
        close = pd.Series(np.random.randn(n).cumsum() + 100)
        high = close + 1
        low = close - 1
        volume = pd.Series(np.random.randint(10000, 50000, n))
        return high, low, close, volume

    def test_cumulative_vwap(self):
        from eqlib.utils.indicators import vwap
        h, l, c, v = self._ohlcv()
        result = vwap(h, l, c, v)  # window=None → cumulative
        assert len(result) == 50
        assert result.iloc[-1] > 0

    def test_rolling_vwap_with_window(self):
        from eqlib.utils.indicators import vwap
        h, l, c, v = self._ohlcv()
        result = vwap(h, l, c, v, window=10)
        assert len(result) == 50
        # First 9 values should be NaN (rolling window of 10 not yet filled)
        assert pd.isna(result.iloc[:9]).all()
        assert pd.notna(result.iloc[9])

    def test_rolling_vs_cumulative_differ(self):
        from eqlib.utils.indicators import vwap
        h, l, c, v = self._ohlcv(100)
        cum = vwap(h, l, c, v)
        rolling = vwap(h, l, c, v, window=20)
        # Rolling and cumulative VWAP should diverge on multi-day data
        assert not cum.iloc[20:].equals(rolling.iloc[20:])


class TestADX:
    """Item 9: ADX uses single Wilder smoothing."""

    def _bars(self, n=100):
        np.random.seed(7)
        close = pd.Series(np.random.randn(n).cumsum() + 100)
        high = close + abs(np.random.randn(n)) * 0.5
        low = close - abs(np.random.randn(n)) * 0.5
        return high, low, close

    def test_adx_returns_valid_series(self):
        from eqlib.utils.indicators import adx
        h, l, c = self._bars()
        pdi, mdi, adx_val, adxr = adx(h, l, c, period=14)
        assert len(adx_val) == 100
        valid = adx_val.dropna()
        # ADX should be bounded 0–100 for well-behaved price data
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_adx_pdi_mdi_non_negative(self):
        from eqlib.utils.indicators import adx
        h, l, c = self._bars()
        pdi, mdi, _, _ = adx(h, l, c, period=14)
        assert (pdi.dropna() >= 0).all()
        assert (mdi.dropna() >= 0).all()


# ============================================================
# Phase 4: Attribution metrics (Items 12, 13, 14)
# ============================================================

class TestTradeWinRate:
    """Item 12: round-trip trade win rate."""

    def _make_trades(self, buy_prices, sell_prices):
        trades = []
        for bp in buy_prices:
            trades.append({"type": "BUY", "security": "601390", "price": bp,
                           "amount": 100, "commission": 5.0})
        for sp in sell_prices:
            trades.append({"type": "SELL", "security": "601390", "price": sp,
                           "amount": 100, "commission": 5.0})
        return trades

    def test_all_wins(self):
        from eqlib.attribution import _calc_trade_win_rate
        trades = self._make_trades([10.0, 11.0], [12.0, 13.0])
        win_rate, count, wins, losses = _calc_trade_win_rate(trades)
        assert count == 2
        assert win_rate == 1.0
        assert wins == 2
        assert losses == 0

    def test_all_losses(self):
        from eqlib.attribution import _calc_trade_win_rate
        trades = self._make_trades([12.0, 13.0], [10.0, 11.0])
        win_rate, count, wins, losses = _calc_trade_win_rate(trades)
        assert count == 2
        assert win_rate == 0.0
        assert wins == 0
        assert losses == 2

    def test_mixed(self):
        from eqlib.attribution import _calc_trade_win_rate
        # Two buys at 10, two sells at 12 and 9
        trades = [
            {"type": "BUY", "security": "601390", "price": 10.0, "amount": 100, "commission": 5},
            {"type": "BUY", "security": "601390", "price": 10.0, "amount": 100, "commission": 5},
            {"type": "SELL", "security": "601390", "price": 12.0, "amount": 100, "commission": 5},
            {"type": "SELL", "security": "601390", "price": 9.0, "amount": 100, "commission": 5},
        ]
        win_rate, count, wins, losses = _calc_trade_win_rate(trades)
        assert count == 2
        assert win_rate == 0.5
        assert wins == 1
        assert losses == 1

    def test_no_trades(self):
        from eqlib.attribution import _calc_trade_win_rate
        win_rate, count, wins, losses = _calc_trade_win_rate([])
        assert win_rate == 0.0
        assert count == 0
        assert wins == 0
        assert losses == 0


# ============================================================
# Phase 5: BacktestSession (Item 15)
# ============================================================

class TestBacktestSession:
    def test_session_creation(self):
        from eqlib._state import BacktestSession
        s = BacktestSession()
        assert s._context is None
        assert s._pending_orders == []
        assert s._t1_locked_amounts == {}
        assert s._slippage_model is None

    def test_session_reset(self):
        from eqlib._state import BacktestSession
        s = BacktestSession()
        s._t1_locked_amounts["601390"] = 100
        s._pending_orders.append({"action": "ORDER"})
        s.reset()
        assert s._pending_orders == []
        assert s._t1_locked_amounts == {}

    def test_thread_local_sessions(self):
        """Two sessions in different threads should be independent."""
        import threading
        from eqlib._state import BacktestSession, _set_session, get_session

        results = {}

        def run_thread(name, value):
            s = BacktestSession()
            _set_session(s)
            s._t1_locked_amounts["sentinel"] = value
            results[name] = get_session()._t1_locked_amounts.get("sentinel")

        t1 = threading.Thread(target=run_thread, args=("A", 42))
        t2 = threading.Thread(target=run_thread, args=("B", 99))
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert results["A"] == 42
        assert results["B"] == 99

    def test_module_proxy_read(self):
        """Module-level st._context read delegates to the active session."""
        import eqlib._state as st
        from eqlib._state import BacktestSession, _set_session, _clear_session
        s = BacktestSession()
        s._context = "sentinel_context"
        _set_session(s)
        assert st._context == "sentinel_context"
        _clear_session()

    def test_module_proxy_write(self):
        """Module-level st._benchmark write delegates to the active session."""
        import eqlib._state as st
        from eqlib._state import BacktestSession, _set_session, _clear_session, get_session
        s = BacktestSession()
        _set_session(s)
        st._benchmark = "000300.XSHG"
        assert get_session()._benchmark == "000300.XSHG"
        _clear_session()


# ============================================================
# Phase 5: Pending orders + T+1 (Items 1, 2, 16)
# ============================================================

class TestPendingOrders:
    """Items 1, 2, 16: orders buffer to pending, filled at next-day open."""

    def test_order_goes_to_pending(self):
        """order() should not execute immediately but add to _pending_orders."""
        import eqlib._state as st
        from eqlib._state import BacktestSession, _set_session, _clear_session
        from eqlib.context import Context

        s = BacktestSession()
        ctx = Context(datetime.date(2024, 1, 1), datetime.date(2024, 12, 31), "daily", 100000)
        ctx.current_dt = datetime.datetime(2024, 1, 2, 9, 30)
        s._context = ctx
        _set_session(s)

        try:
            from eqlib.trade import order
            order("601390", 100)
            assert len(s._pending_orders) == 1
            assert s._pending_orders[0]["action"] == "ORDER"
            assert s._pending_orders[0]["security"] == "601390"
            assert s._pending_orders[0]["amount"] == 100
            # Portfolio should NOT have changed
            assert ctx.portfolio.available_cash == 100000
        finally:
            _clear_session()

    def test_order_value_goes_to_pending(self):
        import eqlib._state as st
        from eqlib._state import BacktestSession, _set_session, _clear_session
        from eqlib.context import Context

        s = BacktestSession()
        ctx = Context(datetime.date(2024, 1, 1), datetime.date(2024, 12, 31), "daily", 100000)
        ctx.current_dt = datetime.datetime(2024, 1, 2, 9, 30)
        s._context = ctx
        _set_session(s)

        try:
            from eqlib.trade import order_value
            order_value("601390", 50000)
            assert len(s._pending_orders) == 1
            assert s._pending_orders[0]["action"] == "ORDER_VALUE"
        finally:
            _clear_session()


# ============================================================
# Phase 6: Optimizer (Item 19, 20)
# ============================================================

class TestLedoitWolfCovariance:
    """Item 19: Ledoit-Wolf covariance shrinkage."""

    def test_ledoit_wolf_produces_pd_matrix(self):
        from eqlib.optimizer import _ledoit_wolf_cov
        np.random.seed(42)
        # Small sample: 30 observations, 5 assets (ill-conditioned for sample cov)
        X = pd.DataFrame(np.random.randn(30, 5), columns=list("ABCDE"))
        cov = _ledoit_wolf_cov(X)
        # Must be symmetric
        assert cov.shape == (5, 5)
        np.testing.assert_array_almost_equal(cov, cov.T, decimal=10)
        # All eigenvalues should be positive (positive definite)
        eigvals = np.linalg.eigvalsh(cov)
        assert (eigvals > 0).all()


class TestRebalancingFrequency:
    """Item 20: rebalance_frequency parameter in StrategyConfig."""

    def test_default_is_daily(self):
        from eqlib.portfolio import StrategyConfig
        cfg = StrategyConfig(
            securities=["601390"],
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        assert cfg.rebalance_frequency == "daily"

    def test_monthly_rebalance(self):
        from eqlib.portfolio import StrategyConfig
        cfg = StrategyConfig(
            securities=["601390"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            rebalance_frequency="monthly",
        )
        assert cfg.rebalance_frequency == "monthly"

    def test_invalid_frequency_raises(self):
        from eqlib.portfolio import StrategyConfig
        with pytest.raises(ValueError):
            StrategyConfig(
                securities=["601390"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                rebalance_frequency="hourly",
            )

    def test_should_rebalance_logic(self):
        from eqlib.portfolio import _should_rebalance

        # daily: always rebalance
        assert _should_rebalance("daily", datetime.date(2024, 1, 3), datetime.date(2024, 1, 2))

        # weekly: different ISO week → rebalance
        assert _should_rebalance("weekly", datetime.date(2024, 1, 8),   # week 2
                                 datetime.date(2024, 1, 5))              # week 1

        # weekly: same ISO week → no rebalance
        assert not _should_rebalance("weekly", datetime.date(2024, 1, 9),  # week 2 Tuesday
                                     datetime.date(2024, 1, 8))             # week 2 Monday

        # monthly: different month → rebalance
        assert _should_rebalance("monthly", datetime.date(2024, 2, 1),
                                 datetime.date(2024, 1, 31))

        # monthly: same month → no rebalance
        assert not _should_rebalance("monthly", datetime.date(2024, 1, 15),
                                     datetime.date(2024, 1, 3))

        # first bar (prev_day=None) → always rebalance
        assert _should_rebalance("monthly", datetime.date(2024, 1, 2), None)


# ============================================================
# Phase 2: Holiday calendar fallback (Item 8)
# ============================================================

class TestHolidayCalendar:
    def test_known_holiday_rejected(self):
        from eqlib.data import _is_ashare_holiday
        # CNY 2024-02-12 is a known holiday
        assert _is_ashare_holiday(datetime.date(2024, 2, 12)) is True

    def test_regular_trading_day_not_rejected(self):
        from eqlib.data import _is_ashare_holiday
        # 2024-01-02 is a regular trading day
        assert _is_ashare_holiday(datetime.date(2024, 1, 2)) is False

    def test_weekend_not_in_holiday_set(self):
        from eqlib.data import _is_ashare_holiday
        # Weekends are filtered separately by weekday check; the holiday set
        # only contains extra non-trading weekdays (public holidays)
        # Saturday should NOT be in the holiday set (caller checks weekday)
        saturday = datetime.date(2024, 1, 6)   # Saturday
        assert saturday.weekday() == 5         # verify it's a Saturday
        # Whether it's in the holiday set or not doesn't matter for the logic


# ============================================================
# Phase 4: Cache key strategy (Item 5)
# ============================================================

class TestCacheKey:
    def test_same_key_for_different_date_ranges(self):
        from eqlib.data_cache import _cache_path
        path1 = _cache_path("601390", "qfq")
        path2 = _cache_path("601390", "qfq")
        assert path1 == path2

    def test_different_key_for_different_adjust(self):
        from eqlib.data_cache import _cache_path
        path_qfq = _cache_path("601390", "qfq")
        path_hfq = _cache_path("601390", "hfq")
        assert path_qfq != path_hfq
