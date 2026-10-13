"""Runtime execution coverage for one minimal example (offline, deterministic).

``tests/test_examples_smoke.py`` validates that every example compiles,
imports, and follows style standards, but it never executes a backtest.
This module executes the example with the smallest data needs
(``examples/03_run_backtest.py``) end-to-end with the data-fetch layer
stubbed by a deterministic synthetic OHLCV frame, so broken engine/example
wiring fails loudly instead of passing vacuously. No network access is used.
"""

from __future__ import annotations

from pathlib import Path
import runpy

import pandas as pd
import pytest

from eqlib import _state, data, data_cache

import examples._defaults as defaults


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_03 = EXAMPLES_DIR / "03_run_backtest.py"

_DAYS = 220


@pytest.fixture(autouse=True)
def isolated_session():
    """Keep the backtest's global session/price caches out of other tests."""
    previous = _state.get_session()
    _state._set_session(_state.BacktestSession())
    data.clear_cache()
    yield
    data.clear_cache()
    _state._set_session(previous)


def _synthetic_ohlcv() -> pd.DataFrame:
    """Daily bars with guaranteed MA(10/30) golden and death crosses.

    Three deterministic trend segments (down, up, down) ensure the example's
    10/30 moving-average crossover produces at least one buy and one sell.
    Dates are real exchange trading days (the engine's calendar is
    exchange-authoritative: bars dated on Chinese holidays would be skipped,
    and the one-day crossover event would fall between calendar days).
    The frame always lies inside the example's backtest window regardless of
    when the test runs.
    """
    from eqlib import engine as _engine

    end = pd.Timestamp(defaults.END_DATE).date()
    start = end - pd.Timedelta(days=int(_DAYS * 1.7))
    dates = pd.DatetimeIndex(
        pd.to_datetime([str(d) for d in
                        _engine._get_trading_days(start, end)[-_DAYS:]])
    )
    assert len(dates) == _DAYS, "exchange calendar must yield enough days"
    closes = (
        [15.0 - 0.08 * i for i in range(60)]  # downtrend: fast MA below slow
        + [10.2 + 0.10 * i for i in range(80)]  # uptrend: golden cross
        + [18.2 - 0.10 * i for i in range(_DAYS - 140)]  # downtrend: death cross
    )
    frame = pd.DataFrame(
        {
            "open": [close * 0.995 for close in closes],
            "close": closes,
            "high": [close * 1.01 for close in closes],
            "low": [close * 0.99 for close in closes],
            "volume": [2_000_000.0] * _DAYS,
        },
        index=dates,
    )
    frame.index.name = "date"
    return frame


def test_example_03_run_backtest_executes_end_to_end_offline(
    monkeypatch, tmp_path
):
    """The example's __main__ block completes and logs real trades."""
    bars = _synthetic_ohlcv()

    # Stub the data-fetch layer: no network, no local CSV store, and every
    # disk write redirected into tmp_path so the repo's data/ cache and the
    # parquet cache are never polluted by synthetic bars.
    monkeypatch.setattr(
        data, "fetch_stock_data", lambda *args, **kwargs: bars.copy()
    )
    # engine binds fetch_stock_data at module top level; stub that reference
    # too so no code path can slip past the stub onto the network.
    from eqlib import engine

    monkeypatch.setattr(
        engine, "fetch_stock_data", lambda *args, **kwargs: bars.copy()
    )
    monkeypatch.setattr(
        data_cache, "load_stock_local", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        data_cache, "save_stock_local", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        data_cache, "_save_to_disk", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(data_cache, "_LOCAL_DATA_DIR", str(tmp_path))

    namespace = runpy.run_path(str(EXAMPLE_03), run_name="__main__")

    result = namespace["result"]
    assert result is not None, "example 03 returned no backtest result"
    trade_log = result["trade_log"]
    assert trade_log, "synthetic MA crosses must produce a non-empty trade log"
    sides = {str(trade.get("type", "")).upper() for trade in trade_log}
    assert "BUY" in sides
    assert "SELL" in sides
    portfolio = result["context"].portfolio
    assert portfolio.total_value > 0
