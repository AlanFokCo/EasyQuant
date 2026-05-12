"""Standalone component profiler - preloads data then times each indicator.

Usage:
    python examples/21_combined_strategy/profile_fast.py
"""

import os
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import (
    STOCK_POOL,
    RSI_PERIOD, BOLL_PERIOD, BOLL_STD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ATR_PERIOD, DONCHIAN_PERIOD, SR_LOOKBACK, SR_TOLERANCE,
)
from eqlib.data_cache import PreloadedData
from eqlib import utils
from eqlib.utils.levels import support_resistance_levels
import pandas as pd
import datetime

# ── Preload data ──
print("Preloading data...")
t0 = time.time()
preloaded = PreloadedData()
end_date = datetime.date(2024, 12, 31)
warmup_start = datetime.date(2021, 1, 1)
preloaded.load(STOCK_POOL, warmup_start, end_date, adjust="qfq", use_local=True)
t_load = time.time() - t0
print("Data loaded in %.2fs (%d securities, %d dates)" % (
    t_load, len(preloaded.panel.columns.get_level_values(0).unique()),
    len(preloaded._dates) if preloaded._dates is not None else 0))

# Set up session context so attribute_history works
from eqlib._state import BacktestSession, _set_session
from eqlib.context import Context
from eqlib.engine import _preloaded

session = BacktestSession()
session._preloaded = preloaded
_set_session(session)
_preloaded = preloaded

context = Context(
    datetime.date(2022, 1, 1),
    datetime.date(2024, 12, 31),
    "daily",
    500000,
)
session._context = context

# Now import attribute_history (it reads from _get_preloaded which uses session)
from eqlib.data import attribute_history

# ── Pick a representative date ──
test_date = datetime.datetime(2022, 3, 15, 9, 30)
context.current_dt = test_date

# Pick a stock with good data
test_stock = "601398"  # ICBC - should have local data

print("\nTesting with %s on %s" % (test_stock, test_date.date()))
print("=" * 60)

bars_needed = max(SR_LOOKBACK, MACD_SLOW + MACD_SIGNAL,
                  BOLL_PERIOD, ATR_PERIOD, DONCHIAN_PERIOD) + 30  # = 90

# ── Time attribute_history ──
N = 50  # iterations
print("\n1. attribute_history (count=%d, %d iterations)" % (bars_needed, N))
t0 = time.time()
for _ in range(N):
    hist = attribute_history(test_stock, bars_needed, "1d",
                             ["open", "high", "low", "close", "volume"])
t_attr = (time.time() - t0) / N
print("   avg: %.2fms | result len=%d, empty=%s" % (t_attr * 1000, len(hist) if hist is not None else 0, hist.empty if hist is not None else "None"))

if hist is None or hist.empty:
    print("   ERROR: no data returned! Cannot profile further.")
    sys.exit(1)

close = hist["close"]
high = hist["high"]
low = hist["low"]
volume = hist["volume"]

# ── Time each indicator ──
components = [
    ("rsi", lambda: utils.rsi(close, period=RSI_PERIOD)),
    ("bollinger", lambda: utils.boll(close, period=BOLL_PERIOD, num_std=BOLL_STD)),
    ("macd", lambda: utils.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)),
    ("atr", lambda: utils.atr(high, low, close, ATR_PERIOD)),
    ("donchian", lambda: utils.donchian(high, low, close, period=DONCHIAN_PERIOD)),
    ("support_resistance", lambda: support_resistance_levels(
        high, low, close, lookback=SR_LOOKBACK, tolerance=SR_TOLERANCE)),
]

for name, fn in components:
    # Warmup
    fn()
    t0 = time.time()
    for _ in range(N):
        fn()
    avg_ms = (time.time() - t0) / N * 1000
    print("%-25s avg: %.2fms" % (name, avg_ms))

# ── Time _compute_factors (weekly stock selection) ──
print("\n2. Full _compute_factors for all 6 stocks with data")
from combined_strategy import _compute_factors
t0 = time.time()
for code in STOCK_POOL:
    f = _compute_factors(code)
    status = "OK" if f else "None"
    print("   %s: %s" % (code, status))
t_factors = time.time() - t0
print("   Total for 12 stocks: %.2fs" % t_factors)

# ── Time _compute_indicators for all stocks ──
print("\n3. Full _compute_indicators for all 12 stocks")
from combined_strategy import _compute_indicators
t0 = time.time()
for code in STOCK_POOL:
    ind = _compute_indicators(code)
    status = "OK" if ind else "None"
    print("   %s: %s" % (code, status))
t_ind = time.time() - t0
print("   Total for 12 stocks: %.2fs" % t_ind)

# ── Extrapolate to full backtest ──
print("\n" + "=" * 60)
print("Extrapolation to full 3-year backtest (~730 trading days)")
print("=" * 60)
trading_days = 730

# Daily: _compute_indicators for 12 stocks
daily_ind_time = t_ind
daily_total = daily_ind_time
print("Daily indicators (12 stocks): %.2fs/day -> %.0fs total (%.1f min)" % (
    daily_total, daily_total * trading_days, daily_total * trading_days / 60))

# Weekly: _compute_factors for 12 stocks (~260 weeks in 3 years)
weeks = 260
print("Weekly factors (12 stocks):  %.2fs/call -> %.0fs total (%.1f min)" % (
    t_factors, t_factors * weeks, t_factors * weeks / 60))

total_est = daily_total * trading_days + t_factors * weeks
print("\nEstimated total: %.0fs (%.1f minutes)" % (total_est, total_est / 60))
