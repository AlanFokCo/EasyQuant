"""Inline profiler for the combined strategy backtest.

Adds timing instrumentation to _compute_indicators and attribute_history
to identify the actual performance bottleneck.

Usage:
    python examples/21_combined_strategy/profile_bottleneck.py
"""

import os
import sys
import time
import json

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import initialize, STOCK_POOL, _compute_indicators
from eqlib import run_backtest
from eqlib.data import attribute_history

# Monkey-patch _compute_indicators with timing
_original_compute_indicators = _compute_indicators
_timing_data = {}

def _profiled_compute_indicators(code):
    t0 = time.time()
    result = _original_compute_indicators(code)
    elapsed = time.time() - t0
    _timing_data.setdefault(code, []).append(elapsed)
    return result

# Monkey-patch attribute_history with timing
_original_attribute_history = attribute_history
_attr_timing = {"calls": 0, "total": 0.0, "by_count": {}}

def _profiled_attribute_history(security, count, unit="1d", fields=("close",), **kwargs):
    t0 = time.time()
    result = _original_attribute_history(security, count, unit, fields, **kwargs)
    elapsed = time.time() - t0
    _attr_timing["calls"] += 1
    _attr_timing["total"] += elapsed
    _attr_timing["by_count"].setdefault(count, {"count": 0, "total": 0.0})
    _attr_timing["by_count"][count]["count"] += 1
    _attr_timing["by_count"][count]["total"] += elapsed
    return result

# Apply monkey patches
import combined_strategy
combined_strategy._compute_indicators = _profiled_compute_indicators

import eqlib.data
eqlib.data.attribute_history = _profiled_attribute_history

# Also patch in eqlib.utils.indicators if they call attribute_history
import eqlib.utils.indicators as indicators_mod
if hasattr(indicators_mod, 'attribute_history'):
    indicators_mod.attribute_history = _profiled_attribute_history

if __name__ == "__main__":
    START_DATE = "2022-01-01"
    END_DATE   = "2022-03-31"  # ~60 trading days for quick profiling
    STARTING_CASH = 500_000
    BENCHMARK = "000300.XSHG"

    print("=" * 60)
    print("Profiling: %s to %s (%d stocks)" % (START_DATE, END_DATE, len(STOCK_POOL)))
    print("=" * 60)

    t_start = time.time()

    result = run_backtest(
        initialize_func=initialize,
        start_date=START_DATE,
        end_date=END_DATE,
        starting_cash=STARTING_CASH,
        benchmark=BENCHMARK,
        securities=STOCK_POOL,
        use_local=True,
    )

    t_total = time.time() - t_start

    print("\nTotal backtest time: %.2fs" % t_total)

    if result:
        days = len(result.get("recorded_values", []))
        trades = len(result.get("trade_log", []))
        print("Trading days: %d" % days)
        print("Trades: %d" % trades)
        if days > 0:
            print("Per-day average: %.3fs" % (t_total / days))

    # attribute_history timing
    print("\n--- attribute_history ---")
    print("Total calls: %d" % _attr_timing["calls"])
    print("Total time:  %.2fs (%.1f%% of backtest)" % (
        _attr_timing["total"], _attr_timing["total"] / t_total * 100))
    if _attr_timing["calls"] > 0:
        print("Avg per call: %.4fms" % (_attr_timing["total"] / _attr_timing["calls"] * 1000))
    print("\nBy bars_needed (count):")
    for count in sorted(_attr_timing["by_count"].keys()):
        info = _attr_timing["by_count"][count]
        print("  count=%d: %d calls, %.2fs total, %.2fms avg" % (
            count, info["count"], info["total"],
            info["total"] / info["count"] * 1000 if info["count"] > 0 else 0))

    # _compute_indicators timing
    print("\n--- _compute_indicators per stock ---")
    total_ind_time = 0.0
    total_ind_calls = 0
    for code in sorted(_timing_data.keys()):
        times = _timing_data[code]
        avg_ms = sum(times) / len(times) * 1000
        total_s = sum(times)
        total_ind_time += total_s
        total_ind_calls += len(times)
        print("  %s: %d calls, %.2fs total, %.1fms avg" % (
            code, len(times), total_s, avg_ms))

    print("\n  TOTAL _compute_indicators: %.2fs (%.1f%% of backtest)" % (
        total_ind_time, total_ind_time / t_total * 100))
    print("  Total calls: %d" % total_ind_calls)
    if total_ind_calls > 0:
        print("  Avg per call: %.1fms" % (total_ind_time / total_ind_calls * 1000))

    # Residual time
    residual = t_total - _attr_timing["total"] - total_ind_time
    print("\n--- Residual (other code) ---")
    print("  %.2fs (%.1f%%)" % (residual, residual / t_total * 100))
