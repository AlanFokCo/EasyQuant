"""Tests for ptrade_adapter.py — verifies code conversion, Position/Portfolio,
g namespace, and API surface without requiring QMT runtime."""

import builtins
import datetime
import importlib.util
import inspect
import sys
from types import SimpleNamespace

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
        self.barpos = 0

    def get_bar_timetag(self, barpos):
        assert barpos == self.barpos
        return int(self.timestamp.timestamp() * 1000)

    def get_market_data(self, fields, stock_code, **_kwargs):
        frame = self.frames.get(stock_code[0], pd.DataFrame())
        return frame.loc[:, [field for field in fields if field in frame.columns]]


class _StrictTimeQMTContext(_FakeQMTContext):
    def __init__(self, frames=None, timestamp=None):
        super().__init__(frames=frames, timestamp=timestamp)
        self.barpos = 17
        self.timetag_calls = []

    def get_bar_timetag(self, barpos):
        self.timetag_calls.append(barpos)
        if barpos != self.barpos:
            raise AssertionError(f"expected barpos {self.barpos}, got {barpos}")
        return int(self.timestamp.timestamp() * 1000)


class _HistoryQMTContext:
    def __init__(self):
        self.requested_counts = []
        self.frame = pd.DataFrame(
            {"close": [10.0, 11.0]},
            index=pd.to_datetime(
                ["2026-07-20 15:00:00", "2026-07-21 09:30:00"]
            ),
        )

    def get_market_data(self, fields, stock_code, **kwargs):
        self.requested_counts.append(kwargs["count"])
        return self.frame.loc[:, fields].tail(kwargs["count"])


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

    def test_native_builtins_do_not_overwrite_compatibility_wrapper(
        self,
        monkeypatch,
    ):
        calls = []

        def native_order_target_value(
            stockcode,
            target_value,
            style,
            price,
            ContextInfo,
            accId="",
        ):
            calls.append(
                (stockcode, target_value, style, price, ContextInfo, accId)
            )

        native_names = (
            "order_shares",
            "order_value",
            "order_percent",
            "order_target_value",
            "order_target_percent",
            "order_lots",
            "get_trade_detail_data",
            "get_last_order_id",
            "get_value_by_order_id",
            "can_cancel_order",
            "cancel",
            "cancel_task",
            "pause_task",
            "resume_task",
            "do_order",
            "passorder",
            "algo_passorder",
            "smart_algo_passorder",
            "get_etf_info",
            "get_etf_iopv",
            "query_credit_opvolume",
            "credit_opvolume_callback",
        )
        for name in native_names:
            monkeypatch.setattr(
                builtins,
                name,
                native_order_target_value,
                raising=False,
            )

        module_name = "eqlib._ptrade_adapter_native_test"
        spec = importlib.util.spec_from_file_location(module_name, pa.__file__)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            qmt_context = object()
            module._context = SimpleNamespace(_qmt=qmt_context)

            module.order_target_value("600519", 250_000)
        finally:
            sys.modules.pop(module_name, None)

        assert calls == [
            ("600519.SH", 250_000, "LATEST", 0, qmt_context, "")
        ]

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


class TestHistory:
    def test_history_requests_and_returns_completed_bars_only(self, monkeypatch):
        _reset_adapter(monkeypatch)
        qmt = _HistoryQMTContext()
        pa._context = SimpleNamespace(_qmt=qmt)

        result = pa.history(
            end_date=datetime.date(2026, 7, 21),
            count=1,
            fields=["close"],
            security_list=["600519"],
        )

        assert qmt.requested_counts == [2]
        assert result["close"].tolist() == [10.0]
        assert result.index.tolist() == [
            pd.Timestamp("2026-07-20 15:00:00")
        ]


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

    def test_lifecycle_uses_bar_position_for_qmt_current_time(self, monkeypatch):
        _reset_adapter(monkeypatch)
        start_dt = datetime.datetime(2026, 7, 21, 9, 30)
        qmt = _StrictTimeQMTContext(timestamp=start_dt)

        pa.start(qmt)

        assert pa._context.current_dt == start_dt
        assert qmt.timetag_calls == [17]

        bar_dt = datetime.datetime(2026, 7, 21, 9, 31)
        qmt.barpos = 18
        qmt.timestamp = bar_dt
        pa.on_bar(qmt)

        assert pa._context.current_dt == bar_dt
        assert qmt.timetag_calls == [17, 18]

    def test_weekly_callback_executes_on_configured_friday(self, monkeypatch):
        _reset_adapter(monkeypatch)
        callback_dates = []

        def initialize(_context):
            pa.run_weekly(
                lambda context: callback_dates.append(context.current_dt.date()),
                day_of_week=4,
                time="09:30",
            )

        pa._initialize_func = initialize
        qmt = _StrictTimeQMTContext(
            timestamp=datetime.datetime(2026, 7, 20, 9, 30)
        )
        pa.start(qmt)

        qmt.barpos = 18
        qmt.timestamp = datetime.datetime(2026, 7, 24, 9, 30)
        pa.on_bar(qmt)
        qmt.barpos = 19
        qmt.timestamp = datetime.datetime(2026, 7, 24, 9, 31)
        pa.on_bar(qmt)

        assert callback_dates == [datetime.date(2026, 7, 24)]

    def test_monthly_day_one_executes_on_first_trading_day(self, monkeypatch):
        _reset_adapter(monkeypatch)
        callback_dates = []

        def initialize(_context):
            pa.run_monthly(
                lambda context: callback_dates.append(context.current_dt.date()),
                day_of_month=1,
                time="09:30",
            )

        pa._initialize_func = initialize
        qmt = _StrictTimeQMTContext(
            timestamp=datetime.datetime(2026, 8, 31, 9, 30)
        )
        pa.start(qmt)

        qmt.barpos = 18
        qmt.timestamp = datetime.datetime(2026, 9, 2, 9, 30)
        pa.on_bar(qmt)
        qmt.barpos = 19
        qmt.timestamp = datetime.datetime(2026, 9, 2, 9, 31)
        pa.on_bar(qmt)

        assert callback_dates == [datetime.date(2026, 9, 2)]

    def test_monthly_day_one_does_not_execute_midmonth(self, monkeypatch):
        _reset_adapter(monkeypatch)
        callback_dates = []

        def initialize(_context):
            pa.run_monthly(
                lambda context: callback_dates.append(context.current_dt.date()),
                day_of_month=1,
                time="09:30",
            )

        pa._initialize_func = initialize
        qmt = _StrictTimeQMTContext(
            timestamp=datetime.datetime(2026, 7, 21, 9, 30)
        )
        pa.start(qmt)
        pa.on_bar(qmt)

        assert callback_dates == []

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
