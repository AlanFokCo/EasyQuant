"""Tests for ptrade_adapter.py — verifies code conversion, Position/Portfolio,
g namespace, and API surface without requiring QMT runtime."""

import datetime
import inspect
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '.')
import eqlib.ptrade_adapter as pa
from eqlib.strategies.ashare_sr_leader import (
    CandidateChannel,
    MarketState,
    PortfolioRiskState,
    StrategyKind,
    StrategyParams,
    make_initialize,
    reduce_portfolio_to_budget,
    select_robust_candidates,
)


class _FakeQMTContext:
    capital = 1_000_000
    start = "2026-07-01"
    end = "2026-07-31"

    def __init__(self, frames=None, timestamp=None):
        self.frames = frames or {}
        self.timestamp = timestamp or datetime.datetime(2026, 7, 21, 9, 30)

    def get_bar_timetag(self):
        return int(self.timestamp.timestamp() * 1000)

    def get_market_data(self, fields, stock_code, **_kwargs):
        frame = self.frames.get(stock_code[0], pd.DataFrame())
        return frame.loc[:, [field for field in fields if field in frame.columns]]


def _ohlcv(close_values):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.linspace(1_000_000, 2_000_000, len(close)),
        }
    )


def _reset_adapter(monkeypatch):
    monkeypatch.setattr(pa, "_context", None)
    monkeypatch.setattr(pa, "_initialize_func", None)
    monkeypatch.setattr(pa, "_daily_funcs", [])
    monkeypatch.setattr(pa, "_weekly_funcs", [])
    monkeypatch.setattr(pa, "_monthly_funcs", [])
    monkeypatch.setattr(pa, "_before_start_funcs", [])
    monkeypatch.setattr(pa, "_after_end_funcs", [])
    monkeypatch.setattr(pa, "_handle_data_func", None)
    monkeypatch.setattr(pa, "_account", "")
    monkeypatch.setattr(pa, "g", pa._SimpleG())


class TestGNamespace:
    """g should support attribute access like eqlib's _GProxy."""

    def setup_method(self):
        # Reset g for each test
        pa.g = pa._SimpleG()

    def test_g_is_simple_g(self):
        assert isinstance(pa.g, pa._SimpleG)

    def test_g_set_get_attribute(self):
        pa.g.security = '601390'
        assert pa.g.security == '601390'

    def test_g_multiple_attributes(self):
        pa.g.security = '601390'
        pa.g.fast_period = 5
        pa.g.slow_period = 20
        assert pa.g.fast_period == 5
        assert pa.g.slow_period == 20

    def test_g_repr(self):
        pa.g.security = '601390'
        assert 'security' in repr(pa.g)


class TestCodeConversion:
    """_to_qmt_code and _to_eq_code should handle SH/SZ/BJ exchanges."""

    def test_sh_by_prefix(self):
        assert pa._to_qmt_code('601390') == '601390.SH'

    def test_sz_by_prefix(self):
        assert pa._to_qmt_code('000001') == '000001.SZ'
        assert pa._to_qmt_code('300750') == '300750.SZ'

    def test_bj_by_prefix(self):
        assert pa._to_qmt_code('830799') == '830799.BJ'
        assert pa._to_qmt_code('430047') == '430047.BJ'

    def test_xshg_to_sh(self):
        assert pa._to_qmt_code('601390.XSHG') == '601390.SH'

    def test_xshe_to_sz(self):
        assert pa._to_qmt_code('000001.XSHE') == '000001.SZ'

    def test_xbje_to_bj(self):
        assert pa._to_qmt_code('830799.XBJE') == '830799.BJ'

    def test_qmt_passthrough(self):
        assert pa._to_qmt_code('601390.SH') == '601390.SH'
        assert pa._to_qmt_code('000001.SZ') == '000001.SZ'
        assert pa._to_qmt_code('830799.BJ') == '830799.BJ'

    def test_none_and_empty(self):
        assert pa._to_qmt_code(None) == ''
        assert pa._to_qmt_code('') == ''

    def test_eq_sh(self):
        assert pa._to_eq_code('601390.SH') == '601390.XSHG'

    def test_eq_sz(self):
        assert pa._to_eq_code('000001.SZ') == '000001.XSHE'

    def test_eq_bj(self):
        assert pa._to_eq_code('830799.BJ') == '830799.XBJE'

    def test_eq_none_and_empty(self):
        assert pa._to_eq_code(None) == ''
        assert pa._to_eq_code('') == ''

    def test_roundtrip_sh(self):
        assert pa._to_eq_code(pa._to_qmt_code('601390.XSHG')) == '601390.XSHG'

    def test_roundtrip_sz(self):
        assert pa._to_eq_code(pa._to_qmt_code('000001.XSHE')) == '000001.XSHE'

    def test_roundtrip_bj(self):
        assert pa._to_eq_code(pa._to_qmt_code('830799.XBJE')) == '830799.XBJE'


class TestPosition:
    """Position should track T+1 closeable_amount."""

    def test_defaults(self):
        pos = pa.Position('601390', 100, 10.0)
        assert pos.amount == 100
        assert pos.avg_cost == 10.0
        assert pos.closeable_amount == 100
        assert pos.total_amount == 100
        assert pos.value == 1000.0

    def test_explicit_closeable(self):
        pos = pa.Position('601390', 100, 10.0, closeable_amount=50)
        assert pos.closeable_amount == 50
        assert pos.amount == 100

    def test_total_value_uses_market_value(self):
        pos = pa.Position(
            "601390",
            100,
            10.0,
            closeable_amount=100,
            market_value=1_250.0,
        )

        assert pos.total_value == 1_250.0
        assert pos.value == 1_250.0


class TestPortfolioSource:
    """Portfolio.update_from_qmt should use correct QMT fields."""

    def test_uses_call_qmt_builtin(self):
        src = inspect.getsource(pa.Portfolio.update_from_qmt)
        assert '_call_qmt_builtin' in src

    def test_uses_cost_price_not_open_price(self):
        src = inspect.getsource(pa.Portfolio.update_from_qmt)
        assert 'm_dCostPrice' in src

    def test_uses_can_use_volume(self):
        src = inspect.getsource(pa.Portfolio.update_from_qmt)
        assert 'm_nCanUseVolume' in src

    def test_not_silent_except(self):
        src = inspect.getsource(pa.Portfolio.update_from_qmt)
        assert 'portfolio sync error' in src

    def test_cleans_stale_positions(self):
        src = inspect.getsource(pa.Portfolio.update_from_qmt)
        assert 'not in seen' in src


class TestOrderFunctions:
    """Order functions should use _call_qmt_builtin, not bare QMT builtins."""

    def test_order_uses_builtin(self):
        src = inspect.getsource(pa.order)
        assert '_call_qmt_builtin' in src

    def test_order_value_uses_builtin(self):
        src = inspect.getsource(pa.order_value)
        assert '_call_qmt_builtin' in src

    def test_order_target_value_uses_builtin(self):
        src = inspect.getsource(pa.order_target_value)
        assert '_call_qmt_builtin' in src

    def test_order_lots_exists(self):
        assert callable(pa.order_lots)

    def test_order_pct_exists(self):
        assert callable(pa.order_pct)


class TestLifecycle:
    """start() and on_bar() should have correct timing logic."""

    def test_start_no_before_trading_call(self):
        src = inspect.getsource(pa.start)
        lines = [l.strip() for l in src.split('\n')
                 if 'func(_context)' in l and 'before' in l.lower()]
        assert len(lines) == 0

    def test_on_bar_checks_15_00(self):
        src = inspect.getsource(pa.on_bar)
        assert 'now.hour == 15' in src

    def test_on_bar_scheduled_time_check(self):
        src = inspect.getsource(pa.on_bar)
        assert "t.split(':')" in src
        assert 'total_seconds()' in src

    def test_start_initializes_robust_factory_with_adapter_runtime(self, monkeypatch):
        _reset_adapter(monkeypatch)
        expected_dt = datetime.datetime(2026, 7, 21, 9, 30)
        qmt = _FakeQMTContext(timestamp=expected_dt)
        pa._initialize_func = make_initialize(
            StrategyKind.ADAPTIVE_COMPOSITE,
            params=StrategyParams(robust_enabled=True),
            universe=["600519"],
        )

        pa.start(qmt)

        assert pa._context.current_dt == expected_dt
        assert pa._context.sr_risk_tracker.high_water == 1_000_000
        assert len(pa._monthly_funcs) == 1
        assert len(pa._weekly_funcs) == 1

    def test_real_ptrade_context_supports_selection_and_no_return_reduction(
        self,
        monkeypatch,
    ):
        _reset_adapter(monkeypatch)
        stock = _ohlcv(np.linspace(10.0, 15.0, 30))
        benchmark = _ohlcv(np.linspace(10.0, 11.0, 30))
        qmt = _FakeQMTContext(
            frames={
                "600519.SH": stock,
                "000300.SH": benchmark,
            }
        )
        params = StrategyParams(
            robust_enabled=True,
            level_window=6,
            short_level_window=4,
            atr_period=3,
            atr_multiplier=0.0,
            volume_window=3,
            volume_ratio_min=0.5,
            rs_window=5,
            min_avg_volume=1,
            min_primary_candidates=1,
            fallback_trend_window=8,
            fallback_medium_window=5,
            fallback_trend_lookback=2,
        )
        pa._initialize_func = make_initialize(
            StrategyKind.ADAPTIVE_COMPOSITE,
            params=params,
            universe=["600519"],
        )
        pa.start(qmt)
        context = pa._context

        selected = select_robust_candidates(
            context,
            StrategyKind.ADAPTIVE_COMPOSITE,
            params,
            ["600519"],
            benchmark,
            MarketState.NEUTRAL,
            PortfolioRiskState.NORMAL,
        )

        assert selected
        assert selected[0].code == "600519"
        assert selected[0].channel is CandidateChannel.PRIMARY

        context.portfolio.positions = {
            "600519": pa.Position(
                "600519",
                amount=50_000,
                avg_cost=8.0,
                market_value=500_000.0,
            )
        }
        context.portfolio.total_value = 1_000_000.0
        context.sr_code_channels = {
            "600519": CandidateChannel.PRIMARY.value,
        }
        queued = []
        monkeypatch.setattr(
            pa,
            "order_target_value",
            lambda code, value: queued.append((code, value)),
        )

        reduce_portfolio_to_budget(context, exposure_budget=0.25)

        assert queued == [("600519", 250_000.0)]


class TestDocstring:
    """Module docstring should use consistent .iloc[-1] syntax."""

    def test_no_bare_bracket_indexing(self):
        assert "['close'][-1]" not in pa.__doc__
