"""Shared constants for EasyQuant.

Centralizing financial constants here ensures consistency across modules
(attribution, report, optimizer, utils/stats) and makes project-wide
adjustments a single-line change.
"""

import datetime

# Annualised risk-free rate used in Sharpe, Sortino, alpha, and optimizer
# calculations.  The default of 3% is broadly consistent with Chinese
# government 1-year bond yields.  Override via module-level parameters where
# a different assumption is required.
RISK_FREE_RATE: float = 0.03

# Number of trading days per year for Chinese A-share markets.
# A-shares have ~242-245 trading days/year (Chinese public holidays remove
# ~10 more days vs US).  Using 244 as the midpoint.
TRADING_DAYS_PER_YEAR: int = 244

# ── A-share daily price-limit rules (one-sided ratios) ───────────────────────
# ChiNext (300xxx) moved from ±10% to ±20% on 2020-08-24 (registration-based
# IPO reform, SZSE announcement 2020-06-12).  Before that date the ±10% main
# board rule applied.
CHINEXT_PRICE_LIMIT_REFORM_DATE: datetime.date = datetime.date(2020, 8, 24)

# One-sided daily price-limit ratios by board / status.
MAIN_BOARD_PRICE_LIMIT: float = 0.10   # SSE/SZSE main board (non-ST)
ST_PRICE_LIMIT: float = 0.05           # main-board ST / *ST stocks
STAR_MARKET_PRICE_LIMIT: float = 0.20  # 688xxx, since inception 2019-07-22
CHINEXT_PRICE_LIMIT: float = 0.20      # 300xxx, on/after the reform date
BSE_PRICE_LIMIT: float = 0.30          # Beijing Stock Exchange (8xx/92x/43x)

# ── Delisting handling (backtest) ────────────────────────────────────────────
# A held security whose bar series has ended is treated as delisted once no
# bar has been seen for more than this many exchange trading days.  The
# threshold is a documented heuristic: post-2019 exchange rules cap most
# suspensions at ~25 trading days, so a longer unbroken gap almost always
# means the data series (and the listing) has ended.  Configure per strategy
# via set_option('delist_gap_days', N).
DEFAULT_DELIST_GAP_DAYS: int = 30

# ── Paper-trading session clock (CST) ────────────────────────────────────────
# Orders are only matched while the market is in session; outside this window
# the loop idles.  The first fill of a day waits for the open call auction
# (09:15-09:25) to complete so that fills use a real traded price.
PAPER_SESSION_START: datetime.time = datetime.time(9, 15)
PAPER_FIRST_FILL_TIME: datetime.time = datetime.time(9, 25)
PAPER_SESSION_END: datetime.time = datetime.time(15, 0)

# Consecutive failures after which a paper-trading user callback (scheduled
# function or handle_data) is disabled instead of killing the process.
PAPER_CALLBACK_MAX_FAILURES: int = 3
