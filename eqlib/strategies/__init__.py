"""EasyQuant built-in strategy templates.

Usage:
    from eqlib.strategies import momentum_rotation_strategy

Or copy the strategy source code directly into Web Strategy Studio.
"""

from .momentum_rotation import momentum_rotation_strategy
from .ma_crossover import ma_crossover_strategy
from .grid_trading import grid_trading_strategy

__all__ = [
    "momentum_rotation_strategy",
    "ma_crossover_strategy",
    "grid_trading_strategy",
]
