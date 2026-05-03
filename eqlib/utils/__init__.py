"""Utility functions for quantitative analysis.

Submodules:
- indicators: technical indicators (MA, MACD, RSI, KDJ, etc.)
- stats: statistical utilities (rolling metrics, regression, VaR, etc.)
- money: position sizing and money management (Kelly, ATR sizing, etc.)
- levels: support/resistance, pivot points, Fibonacci retracement, etc.
"""

from eqlib.utils.indicators import (
    ma, ema, sma, wma, vwap,
    macd, rsi, kdj, boll, atr, cci, wr, roc, obv, adx,
    golden_cross, death_cross,
)

from eqlib.utils.stats import (
    rolling_corr, rolling_beta, rolling_sharpe,
    zscore, percentile_rank,
    linear_regression,
    downside_deviation, value_at_risk, conditional_var,
    drawdown, max_drawdown,
    consecutive_wins, consecutive_losses,
    fibonacci, comb, perm,
    compound_return, cagr, log_return,
)

from eqlib.utils.money import (
    kelly_criterion, half_kelly, kelly_from_returns,
    fixed_fraction_size, fixed_ratio_size, percent_of_equity,
    volatility_target_size, atr_position_size,
    martingale_size, anti_martingale_size,
    equal_weight, risk_parity_weights, volatility_normalize,
)

from eqlib.utils.levels import (
    # Pivot Points
    pivot_classic, pivot_fibonacci, pivot_woodie,
    pivot_camarilla, pivot_demark,
    # Support / Resistance
    swing_highs_lows, support_resistance_levels,
    fibonacci_retracement, donchian,
    psychological_levels, volume_profile_support_resistance,
    ma_support_resistance, prev_day_levels,
    # Trailing stop & gaps
    trailing_stop, gap_up_down,
)

__all__ = [
    # Indicators
    "ma", "ema", "sma", "wma", "vwap",
    "macd", "rsi", "kdj", "boll", "atr", "cci", "wr", "roc", "obv", "adx",
    "golden_cross", "death_cross",
    # Stats
    "rolling_corr", "rolling_beta", "rolling_sharpe",
    "zscore", "percentile_rank",
    "linear_regression",
    "downside_deviation", "value_at_risk", "conditional_var",
    "drawdown", "max_drawdown",
    "consecutive_wins", "consecutive_losses",
    "fibonacci", "comb", "perm",
    "compound_return", "cagr", "log_return",
    # Money management
    "kelly_criterion", "half_kelly", "kelly_from_returns",
    "fixed_fraction_size", "fixed_ratio_size", "percent_of_equity",
    "volatility_target_size", "atr_position_size",
    "martingale_size", "anti_martingale_size",
    "equal_weight", "risk_parity_weights", "volatility_normalize",
    # Support / Resistance
    "pivot_classic", "pivot_fibonacci", "pivot_woodie",
    "pivot_camarilla", "pivot_demark",
    "swing_highs_lows", "support_resistance_levels",
    "fibonacci_retracement", "donchian",
    "psychological_levels", "volume_profile_support_resistance",
    "ma_support_resistance", "prev_day_levels",
    "trailing_stop", "gap_up_down",
]
