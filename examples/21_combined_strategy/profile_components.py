"""Component-level profiler for _compute_indicators.

Times each individual indicator (RSI, MACD, Bollinger, ATR, Donchian, S/R)
plus the attribute_history call to find exactly which component is slow.

Usage:
    python examples/21_combined_strategy/profile_components.py
"""

import os
import sys
import time
import pandas as pd

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from combined_strategy import (
    initialize, STOCK_POOL,
    RSI_PERIOD, BOLL_PERIOD, BOLL_STD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ATR_PERIOD, DONCHIAN_PERIOD, SR_LOOKBACK, SR_TOLERANCE,
)
from eqlib import run_backtest
from eqlib.data import attribute_history
from eqlib import utils
from eqlib.utils.levels import support_resistance_levels

# Component timing accumulators
_comp = {}

def _t(name, fn, *args, **kwargs):
    t0 = time.time()
    result = fn(*args, **kwargs)
    elapsed = time.time() - t0
    _comp.setdefault(name, []).append(elapsed)
    return result

def _profiled_compute_indicators(code):
    bars_needed = max(SR_LOOKBACK, MACD_SLOW + MACD_SIGNAL,
                      BOLL_PERIOD, ATR_PERIOD, DONCHIAN_PERIOD) + 30

    # Time attribute_history
    hist = _t("attribute_history", attribute_history, code, bars_needed, "1d",
              ["open", "high", "low", "close", "volume"])
    if hist is None or hist.empty or len(hist) < SR_LOOKBACK:
        return None

    close  = hist["close"]
    high   = hist["high"]
    low    = hist["low"]
    volume = hist["volume"]
    price  = close.iloc[-1]

    # Time each indicator
    rsi_series = _t("rsi", utils.rsi, close, period=RSI_PERIOD)
    current_rsi = rsi_series.iloc[-1]

    bb_upper, bb_mid, bb_lower = _t("bollinger", utils.boll, close,
                                       period=BOLL_PERIOD, num_std=BOLL_STD)

    dif, dea, macd_hist = _t("macd", utils.macd, close,
                              fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    macd_golden = (dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2])
    macd_death  = (dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2])

    atr_series = _t("atr", utils.atr, high, low, close, ATR_PERIOD)
    current_atr = atr_series.iloc[-1]

    dc_upper, dc_mid, dc_lower = _t("donchian", utils.donchian, high, low, close,
                                      period=DONCHIAN_PERIOD)

    sr = _t("support_resistance", support_resistance_levels,
            high, low, close, lookback=SR_LOOKBACK, tolerance=SR_TOLERANCE)
    nearest_support = sr.get("nearest_support")
    nearest_resistance = sr.get("nearest_resistance")

    avg_vol_20 = volume.tail(20).mean()
    current_vol = volume.iloc[-1]
    vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

    return {
        "price": price, "rsi": current_rsi,
        "bb_upper": bb_upper.iloc[-1], "bb_mid": bb_mid.iloc[-1], "bb_lower": bb_lower.iloc[-1],
        "macd_golden": macd_golden, "macd_death": macd_death,
        "dif": dif.iloc[-1], "dea": dea.iloc[-1],
        "atr": current_atr, "dc_upper": dc_upper.iloc[-1], "dc_lower": dc_lower.iloc[-1],
        "nearest_support": nearest_support, "nearest_resistance": nearest_resistance,
        "vol_ratio": vol_ratio,
    }

# Patch it
import combined_strategy
combined_strategy._compute_indicators = _profiled_compute_indicators

if __name__ == "__main__":
    START_DATE = "2022-01-01"
    END_DATE   = "2022-02-28"  # ~40 trading days for quick profiling
    STARTING_CASH = 500_000
    BENCHMARK = "000300.XSHG"

    print("Component-level profiling: %s to %s" % (START_DATE, END_DATE))
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
        print("Trading days: %d, Trades: %d" % (days, trades))

    print("\n" + "=" * 60)
    print("Component breakdown (all stocks combined)")
    print("=" * 60)
    print("%-25s %8s %8s %8s %6s" % ("Component", "Calls", "Total(s)", "Avg(ms)", "%Total"))

    grand_total = 0.0
    for name in ["attribute_history", "rsi", "bollinger", "macd", "atr",
                  "donchian", "support_resistance"]:
        times = _comp.get(name, [])
        n = len(times)
        total = sum(times)
        avg_ms = total / n * 1000 if n > 0 else 0
        grand_total += total
        pct = total / t_total * 100
        print("%-25s %8d %8.2f %8.2f %5.1f%%" % (name, n, total, avg_ms, pct))

    print("%-25s %8.2f %6.1f%%" % ("TIMED TOTAL", grand_total, grand_total / t_total * 100))
    print("%-25s %8.2f %6.1f%%" % ("RESIDUAL", t_total - grand_total, (t_total - grand_total) / t_total * 100))
