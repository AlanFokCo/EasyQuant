"""Attribute_history deep profiler.

Tests how long attribute_history takes with different parameters and data paths.
Runs outside the backtest engine to isolate the call.

Usage:
    python examples/21_combined_strategy/profile_attr_history.py
"""

import os
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import STOCK_POOL
from eqlib.data_cache import PreloadedData
from eqlib.data import attribute_history
from eqlib.engine import _get_preloaded, _preloaded, run_backtest
from combined_strategy import initialize

# First, run a short backtest to set up the preloaded data
print("Running short backtest to set up data...")
result = run_backtest(
    initialize_func=initialize,
    start_date="2022-01-01",
    end_date="2022-01-31",
    starting_cash=500_000,
    benchmark="000300.XSHG",
    securities=STOCK_POOL,
    use_local=True,
)

print("Backtest done. Now profiling attribute_history...\n")

# attribute_history should still work within the backtest context
# Let's test it by running another short backtest with inline timing

from eqlib import run_backtest as rb
import eqlib.data as data_mod

original = data_mod.attribute_history
timings = {"total": 0, "calls": 0}

def timed_attr(security, count, unit="1d", fields=("close",), **kw):
    t0 = time.time()
    result = original(security, count, unit, fields, **kw)
    elapsed = time.time() - t0
    timings["total"] += elapsed
    timings["calls"] += 1
    return result

data_mod.attribute_history = timed_attr

print("Running 2nd backtest with timed attribute_history...")
t0 = time.time()
result2 = rb(
    initialize_func=initialize,
    start_date="2022-01-01",
    end_date="2022-02-28",
    starting_cash=500_000,
    benchmark="000300.XSHG",
    securities=STOCK_POOL,
    use_local=True,
)
t_backtest = time.time() - t0

print("\nBacktest time: %.2fs" % t_backtest)
print("attribute_history calls: %d" % timings["calls"])
print("attribute_history total: %.2fs (%.1f%%)" % (
    timings["total"], timings["total"] / t_backtest * 100))
if timings["calls"] > 0:
    print("attribute_history avg: %.2fms" % (timings["total"] / timings["calls"] * 1000))

# Now test attribute_history directly outside backtest context
print("\n--- Direct attribute_history test (outside backtest) ---")
# This should use the preloaded data path if session is still active
try:
    preloaded = _get_preloaded()
    if preloaded and preloaded.panel is not None:
        print("Preloaded data available: %d securities" % len(preloaded.panel.columns.get_level_values(0).unique()))

        # Test 1: attribute_history from preloaded (inside session)
        for code in ["601398", "002594", "601088"]:
            # Test with different count values
            for count in [20, 60, 90, 110]:
                t0 = time.time()
                for _ in range(10):
                    df = attribute_history(code, count, "1d", ["open", "high", "low", "close", "volume"])
                elapsed = time.time() - t0
                print("  %s count=%d: %.2fms/call (empty=%s, len=%s)" % (
                    code, count, elapsed/10*1000, df.empty if df is not None else "None", len(df) if df is not None else "N/A"))
    else:
        print("Preloaded data not available")
except Exception as e:
    print("Error: %s" % e)
