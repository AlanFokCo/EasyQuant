"""Shared constants for EasyQuant.

Centralizing financial constants here ensures consistency across modules
(attribution, report, optimizer, utils/stats) and makes project-wide
adjustments a single-line change.
"""

# Annualised risk-free rate used in Sharpe, Sortino, alpha, and optimizer
# calculations.  The default of 3% is broadly consistent with Chinese
# government 1-year bond yields.  Override via module-level parameters where
# a different assumption is required.
RISK_FREE_RATE: float = 0.03

# Number of trading days per year for Chinese A-share markets.
# A-shares have ~242-245 trading days/year (Chinese public holidays remove
# ~10 more days vs US).  Using 244 as the midpoint.
TRADING_DAYS_PER_YEAR: int = 244
