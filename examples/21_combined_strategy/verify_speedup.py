"""Verify numpy-based indicator speed vs pandas.

Quick test to see if replacing pandas rolling/ewm with numpy helps.
"""

import os
import sys
import time
import numpy as np
import pandas as pd

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import STOCK_POOL
from eqlib.data_cache import PreloadedData
from eqlib import utils
from eqlib.utils.levels import support_resistance_levels
import datetime

# Preload
preloaded = PreloadedData()
preloaded.load(STOCK_POOL, datetime.date(2021,1,1), datetime.date(2024,12,31),
               adjust="qfq", use_local=True)

# Set up session
from eqlib._state import BacktestSession, _set_session
from eqlib.context import Context
from eqlib.engine import _preloaded
session = BacktestSession()
session._preloaded = preloaded
_set_session(session)
_preloaded = preloaded
context = Context(datetime.date(2022,1,1), datetime.date(2024,12,31), "daily", 500000)
session._context = context
context.current_dt = datetime.datetime(2022, 3, 15, 9, 30)

from eqlib.data import attribute_history

# Get data for one stock
hist = attribute_history("601398", 120, "1d", ["open", "high", "low", "close", "volume"])
close = hist["close"]
high = hist["high"]
low = hist["low"]

N = 100

# ── Test 1: pandas Series (current) ──
print("=== Current: pandas Series ===")
t0 = time.time()
for _ in range(N):
    utils.rsi(close, 14)
print("RSI (pandas):     %.2fms" % ((time.time()-t0)/N*1000))

t0 = time.time()
for _ in range(N):
    utils.atr(high, low, close, 14)
print("ATR (pandas):     %.2fms" % ((time.time()-t0)/N*1000))

t0 = time.time()
for _ in range(N):
    utils.macd(close, 12, 26, 9)
print("MACD (pandas):    %.2fms" % ((time.time()-t0)/N*1000))

t0 = time.time()
for _ in range(N):
    utils.boll(close, 20, 2.0)
print("Bollinger (pandas): %.2fms" % ((time.time()-t0)/N*1000))

# ── Test 2: numpy arrays ──
close_np = close.values
high_np = high.values
low_np = low.values

def ema_np(data, period):
    """Numpy EMA using cumprod approach."""
    result = np.empty_like(data)
    result[:] = np.nan
    result[period-1] = data[:period].mean()
    alpha = 2.0 / (period + 1)
    for i in range(period, len(data)):
        result[i] = result[i-1] * (1-alpha) + data[i] * alpha
    return result

def rsi_np(close, period=14):
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # prepend NaN for first element
    gain = np.concatenate([[np.nan], gain])
    loss = np.concatenate([[np.nan], loss])

    avg_gain = np.empty_like(gain)
    avg_loss = np.empty_like(loss)
    avg_gain[:] = np.nan
    avg_loss[:] = np.nan

    # Seed with SMA
    avg_gain[period] = gain[1:period+1].mean()
    avg_loss[period] = loss[1:period+1].mean()

    alpha = 1.0 / period
    for i in range(period+1, len(close)):
        avg_gain[i] = avg_gain[i-1] * (1-alpha) + gain[i] * alpha
        avg_loss[i] = avg_loss[i-1] * (1-alpha) + loss[i] * alpha

    rs = np.where(avg_loss != 0, avg_gain / avg_loss, np.nan)
    return 100 - 100 / (1 + rs)

print("\n=== Numpy arrays (pure Python loop) ===")
t0 = time.time()
for _ in range(N):
    rsi_np(close_np, 14)
print("RSI (numpy loop): %.2fms" % ((time.time()-t0)/N*1000))

# ── Test 3: pandas but on full preloaded data once ──
# Get the full series for one stock
full_close = preloaded._field_series["601398"]["close"]
full_high = preloaded._field_series["601398"]["high"]
full_low = preloaded._field_series["601398"]["low"]

print("\n=== Precompute once on full data, then index ===")
t0 = time.time()
# Compute RSI on full 969-bar series ONCE
full_rsi = utils.rsi(full_close, 14)
full_atr = utils.atr(full_high, full_low, full_close, 14)
full_dif, full_dea, full_hist = utils.macd(full_close, 12, 26, 9)
full_bb_upper, full_bb_mid, full_bb_lower = utils.boll(full_close, 20, 2.0)
t_precompute = time.time() - t0
print("Precompute all indicators on 969 bars: %.2fms (ONE TIME)" % (t_precompute * 1000))

# Now just read the last value
t0 = time.time()
for _ in range(N):
    _ = full_rsi.iloc[-1]
print("Read last value (pandas): %.4fms" % ((time.time()-t0)/N*1000))

# Using numpy array
rsi_np_arr = full_rsi.values
t0 = time.time()
for _ in range(N):
    _ = rsi_np_arr[-1]
print("Read last value (numpy): %.4fms" % ((time.time()-t0)/N*1000))

print("\n=== Conclusion ===")
print("Current: 12 stocks × daily RSI(71ms) + ATR(53ms) + MACD(16ms) + Boll(40ms)")
print("         = ~2.2s per day for indicators alone")
print("Alternative: precompute all indicators once per stock = %.0fms total" % (t_precompute * 1000))
print("Then daily read = sub-millisecond per stock")
