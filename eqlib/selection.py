"""Stock selection framework for periodic portfolio rebalancing.

Provides:
- StockSelector base class with filter() and rank() methods
- Utility filters: filter_st_stocks, filter_paused_stocks
- Built-in selectors: TopNSelector, MultiFactorSelector
- Helper to fetch multi-dimensional factor data (financial + technical + market)

Usage patterns:

1. **Parameter-style (recommended for run_strategy/run_backtest)::**

    def my_selection(context):
        # Return a list of selected security codes
        return ['601390', '600519', '000858']

    result = run_strategy(
        initialize_func=initialize,
        selection_func=my_selection,
        selection_rebalance='monthly:1',
    )

2. **Declarative-style (call run_selection from initialize)::**

    def initialize(context):
        run_selection(my_selection, rebalance='weekly:0')

3. **StockSelector subclass::**

    class MySelector(StockSelector):
        def filter(self, candidates, context):
            return filter_st_stocks(candidates)
        def rank(self, securities, context):
            return TopNSelector('pe', top_n=5).rank(securities, context)

Rebalance formats:
    'monthly:N'  — Nth day of month (1-31), e.g. 'monthly:1' (1st)
    'weekly:N'   — Nth weekday (0=Mon .. 4=Fri), e.g. 'weekly:0' (Monday)
    'daily'      — every trading day
"""

from typing import Optional
import pandas as pd


class StockSelector:
    """Base class for stock selection strategies.

    Subclass and override ``filter`` and/or ``rank`` to implement custom
    selection logic.  Typical usage::

        class MySelector(StockSelector):
            def filter(self, candidates, context):
                return filter_st_stocks(candidates)
            def rank(self, securities, context):
                return TopNSelector('pe', top_n=5).rank(securities, context)

        # Then in selection_func:
        selector = MySelector()
        filtered = selector.filter(context.universe, context)
        return selector.rank(filtered, context)
    """

    def filter(self, candidates: list[str], context) -> list[str]:
        """Filter the candidate universe.

        Parameters:
            candidates: list of security codes (e.g. ``['601390', '000858']``).
                Both bare codes and exchange-suffixed codes (e.g. ``601390.XSHG``)
                are accepted.
            context: the current BacktestSession context

        Returns:
            filtered list of security codes that pass all criteria
        """
        return candidates

    def rank(self, securities: list[str], context) -> list[str]:
        """Rank and select securities from the filtered universe.

        Parameters:
            securities: filtered list of security codes
            context: the current BacktestSession context

        Returns:
            ordered list of selected security codes (best first)
        """
        return securities


# ── Internal helpers ─────────────────────────────────────────────────────────

def _bare(code: str) -> str:
    """Strip exchange suffix from a security code."""
    return code.replace(".XSHG", "").replace(".XSHE", "")


def _to_bare_list(codes: list[str]) -> list[str]:
    """Convert a list of security codes to bare codes."""
    return [_bare(c) for c in codes]


# ── Utility filters ──────────────────────────────────────────────────────────


def filter_st_stocks(securities: list[str]) -> list[str]:
    """Remove ST / *ST stocks from the candidate list.

    Uses ``get_extras('is_st', ...)`` which checks the **current** stock name
    for 'ST'.

    .. warning:: **Point-in-time limitation.**
        ``is_st`` data comes from a real-time akshare API call and reflects
        today's ST designation, **not** the designation at ``context.current_dt``
        during backtesting.  This means:

        * Stocks that *were* ST in the past but have since recovered will be
          incorrectly included in historical backtests.
        * Stocks that *became* ST after the backtest period will be incorrectly
          excluded.

        For rigorous historical ST filtering, maintain a point-in-time ST list
        keyed by date and use it inside your strategy callback.  The current
        implementation is best suited for live and near-real-time screening
        where staleness is less than one trading day.

    Parameters:
        securities: candidate list (bare or exchange-suffixed codes)

    Returns:
        stocks that are NOT ST

    Example::

        candidates = filter_st_stocks(context.universe)
    """
    from eqlib.data import get_extras

    # F2: WARNING — this filter uses current-day ST status from akshare,
    # not point-in-time data. During historical backtests, this introduces
    # survivorship bias: stocks that were ST in the past but aren't today
    # will NOT be filtered out, and stocks that are ST today but weren't
    # in the past WILL be incorrectly filtered.
    import warnings
    from eqlib._state import _context
    if hasattr(_context, 'current_dt') and _context.current_dt is not None:
        warnings.warn(
            "filter_st_stocks uses current-day ST status, not point-in-time data. "
            "This may introduce survivorship bias in backtests.",
            stacklevel=2,
        )

    # get_extras returns bare codes as keys; convert input to bare
    bare_codes = _to_bare_list(securities)
    is_st = get_extras('is_st', bare_codes)
    return [s for s in securities if not is_st.get(_bare(s), False)]


def filter_paused_stocks(securities: list[str], context=None) -> list[str]:
    """Remove paused/suspended stocks (volume == 0).

    During backtest, uses preloaded volume data for the current trading date.
    In live/real-time context, falls back to ``get_current_data()``.

    Parameters:
        securities: candidate list (bare or exchange-suffixed codes)
        context: optional context object (used to get current date during backtest)

    Returns:
        stocks that are actively trading

    Example::

        active = filter_paused_stocks(candidates, context)
    """
    from eqlib.engine import _get_preloaded

    preloaded = _get_preloaded()
    if preloaded is not None and preloaded._dates is not None and len(preloaded._dates) > 0:
        # Backtest mode: use preloaded data
        if context is not None:
            current_date = context.current_dt.date()
        else:
            import datetime
            current_date = datetime.date.today()

        result = []
        for s in securities:
            bar = preloaded.get_bar(current_date, s)
            if bar is None:
                bar = preloaded.get_bar(current_date, _bare(s))
            if bar is not None and bar.get("volume", 0) > 0:
                result.append(s)
        return result

    # Fallback: live mode
    from eqlib.data import get_current_data
    market = get_current_data()
    result = []
    for s in securities:
        info = market.get(_bare(s))
        if info is None:
            continue
        vol = info.get("volume", 0)
        try:
            vol = float(vol)
        except (ValueError, TypeError):
            vol = 0
        if vol > 0:
            result.append(s)
    return result


def filter_low_price_stocks(
    securities: list[str], min_price: float = 2.0, context=None
) -> list[str]:
    """Remove stocks below a minimum price threshold.

    In backtest mode the closing price from preloaded data is used for the
    current trading date (``context.current_dt``).  In live mode the real-time
    snapshot returned by ``get_current_data()`` is used.

    Parameters:
        securities: candidate list
        min_price: minimum stock price (default 2.0)
        context: optional context object (provides the current date during
            backtest; when omitted the function still works but defaults to
            today in live mode)

    Returns:
        stocks with price >= min_price
    """
    from eqlib.engine import _get_preloaded

    preloaded = _get_preloaded()
    in_backtest = (
        preloaded is not None
        and preloaded._dates is not None
        and len(preloaded._dates) > 0
    )

    if in_backtest:
        # Use preloaded close price — no look-ahead bias
        if context is not None:
            current_date = context.current_dt.date()
        else:
            import datetime
            current_date = datetime.date.today()

        result = []
        for s in securities:
            price = preloaded.get_close(current_date, s)
            if price is None:
                price = preloaded.get_close(current_date, _bare(s))
            if price is not None and price >= min_price:
                result.append(s)
        return result

    # Live mode: use real-time snapshot
    from eqlib.data import get_current_data

    market = get_current_data()
    result = []
    for s in securities:
        info = market.get(_bare(s))
        if info is None:
            continue
        price = info.get("price", 0)
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0
        if price >= min_price:
            result.append(s)
    return result


def filter_high_pe_stocks(
    securities: list[str], max_pe: float = 100.0, context=None
) -> list[str]:
    """Remove stocks with P/E ratio above the threshold.

    .. warning::
        In backtest mode, historical PE data is not available in the preloaded
        OHLCV panel.  This function therefore returns *all* candidates unchanged
        during backtests to avoid introducing look-ahead bias from real-time PE
        snapshots.  Use fundamental data from ``get_financial_abstract`` with
        proper disclosure-date filtering if PE screening is needed.

    In live mode the real-time PE from ``get_current_data()`` is used.

    Parameters:
        securities: candidate list
        max_pe: maximum P/E ratio (default 100.0)
        context: optional context object (currently unused; reserved for future
            backtest-mode PE support)

    Returns:
        stocks with PE <= max_pe (live mode), or all candidates (backtest mode)
    """
    from eqlib.engine import _get_preloaded
    from eqlib.logger import log

    preloaded = _get_preloaded()
    in_backtest = (
        preloaded is not None
        and preloaded._dates is not None
        and len(preloaded._dates) > 0
    )

    if in_backtest:
        # PE/PB are not available in preloaded OHLCV data.  Returning all
        # candidates is the conservative (no-look-ahead) choice.
        # Warn only once per session to avoid flooding the log.
        from eqlib._state import get_session
        sess = get_session()
        warned_key = "_filter_high_pe_warned"
        opts = getattr(sess, "_options", None) or {}
        if not opts.get(warned_key, False):
            log.warn(
                "filter_high_pe_stocks: PE data unavailable in backtest mode — "
                "returning all candidates without PE filtering to avoid look-ahead bias."
            )
            # Only write back if _options is a real dict (i.e. session is initialized)
            if isinstance(getattr(sess, "_options", None), dict):
                sess._options[warned_key] = True
        return list(securities)

    # Live mode: use real-time snapshot
    from eqlib.data import get_current_data

    market = get_current_data()
    result = []
    for s in securities:
        info = market.get(_bare(s))
        if info is None:
            continue
        pe = info.get("pe", None)
        if pe is None:
            continue
        try:
            pe = float(pe)
        except (ValueError, TypeError):
            continue
        if pe <= max_pe:
            result.append(s)
    return result


# ── Multi-dimensional data fetching ──────────────────────────────────────────


def fetch_factor_data(
    securities: list[str],
    fields: Optional[list[str]] = None,
    context=None,
) -> pd.DataFrame:
    """Fetch multi-dimensional data for a list of securities.

    **Backtest vs live behaviour**

    In backtest mode (preloaded OHLCV panel is available):
        - OHLCV fields (``price``, ``open``, ``high``, ``low``, ``close``,
          ``volume``, ``money``, ``pct_change``, ``turnover``) are sourced from
          the preloaded panel for ``context.current_dt`` — no look-ahead bias.
        - Valuation fields (``pe``, ``pb``, ``total_value``) require a
          real-time snapshot and are therefore returned as ``NaN`` in backtest
          mode to avoid future-function contamination.
        - Technical indicators (``ma5``, ``ma10``, ``ma20``, ``rsi14``) are
          computed from the preloaded history up to ``context.current_dt``.

    In live mode:
        - All fields are sourced from ``get_current_data()`` (real-time
          akshare snapshot), which includes PE/PB.

    Parameters:
        securities: list of security codes (bare or exchange-suffixed)
        fields: optional list of fields to include.  When None, returns all
            available fields.
        context: optional context object (provides the current date during
            backtest for correct data slicing)

    Returns:
        DataFrame indexed by security code with columns for each field.
        Securities where data cannot be retrieved are omitted.
        Missing values are ``NaN`` — never silently replaced with 0.

    Available fields:
        OHLCV: price, pct_change, turnover, volume, money, high, low, open,
               prev_close
        Valuation (live only): pe, pb, total_value
        Technical: ma5, ma10, ma20, rsi14

    Example::

        df = fetch_factor_data(context.universe, fields=['price', 'rsi14'], context=context)
        for code in df.index:
            print(code, df.at[code, 'price'])
    """
    from eqlib.engine import _get_preloaded
    from eqlib.utils.indicators import rsi

    preloaded = _get_preloaded()
    in_backtest = (
        preloaded is not None
        and preloaded.panel is not None
        and preloaded._dates is not None
        and len(preloaded._dates) > 0
    )

    # Determine the as-of date for backtest slicing
    if in_backtest:
        if context is not None:
            current_date = context.current_dt.date()
            current_ts = pd.Timestamp(current_date)
        else:
            import datetime
            current_date = datetime.date.today()
            current_ts = pd.Timestamp(current_date)

    rows = []
    for s in securities:
        bare_s = _bare(s)
        row: dict = {"security": s}

        if in_backtest:
            # ── Backtest mode: use preloaded OHLCV — no look-ahead bias ──────
            bar = preloaded.get_bar(current_date, s)
            if bar is None:
                bar = preloaded.get_bar(current_date, bare_s)

            if bar is not None:
                row["price"] = bar.get("close")
                row["open"] = bar.get("open")
                row["high"] = bar.get("high")
                row["low"] = bar.get("low")
                row["close"] = bar.get("close")
                row["volume"] = bar.get("volume")
                row["money"] = bar.get("money")
                # pct_change / turnover from field_series if available
                sec_series = preloaded._field_series.get(s) or preloaded._field_series.get(bare_s)
                if sec_series is not None:
                    for field in ("pct_change", "turnover"):
                        if field in sec_series:
                            s_f = sec_series[field].loc[:current_ts]
                            if not s_f.empty:
                                row[field] = float(s_f.iloc[-1])

            # PE/PB require a real-time snapshot — return NaN to avoid
            # look-ahead bias.  Users should use get_financial_abstract with
            # proper disclosure-date filtering for valuation factors.
            row["pe"] = float("nan")
            row["pb"] = float("nan")
            row["total_value"] = float("nan")

            # Technical indicators from preloaded history up to current_dt
            sec_df = None
            try:
                sec_df = (preloaded.panel.get(s) if hasattr(preloaded.panel, "get")
                          else None)
                if sec_df is None:
                    # MultiIndex panel: extract sub-DataFrame for this security
                    if s in preloaded.panel.columns.get_level_values("security"):
                        sec_df = preloaded.panel.xs(s, axis=1, level="security")
                    elif bare_s in preloaded.panel.columns.get_level_values("security"):
                        sec_df = preloaded.panel.xs(bare_s, axis=1, level="security")
            except Exception:
                pass

            if sec_df is not None and not sec_df.empty and "close" in sec_df.columns:
                closes = sec_df["close"].loc[:current_ts].dropna()
                if len(closes) >= 5:
                    row["ma5"] = float(closes.tail(5).mean())
                if len(closes) >= 10:
                    row["ma10"] = float(closes.tail(10).mean())
                if len(closes) >= 20:
                    row["ma20"] = float(closes.tail(20).mean())
                if len(closes) >= 15:
                    rsi_val = rsi(closes, 14)
                    if not rsi_val.dropna().empty:
                        row["rsi14"] = float(rsi_val.iloc[-1])

        else:
            # ── Live mode: real-time snapshot includes PE/PB ─────────────────
            from eqlib.data import get_current_data

            market = get_current_data()
            info = market.get(bare_s) or market.get(s)
            if info is not None:
                for k in (
                    "price", "pct_change", "total_value", "pe", "pb", "turnover",
                    "volume", "money", "high", "low", "open", "prev_close",
                ):
                    v = info.get(k)
                    try:
                        row[k] = float(v) if v is not None else float("nan")
                    except (ValueError, TypeError):
                        row[k] = float("nan")

            # Technical indicators from preloaded history (if available)
            if preloaded is not None and preloaded.panel is not None:
                try:
                    sec_df = None
                    if s in preloaded.panel.columns.get_level_values("security"):
                        sec_df = preloaded.panel.xs(s, axis=1, level="security")
                    elif bare_s in preloaded.panel.columns.get_level_values("security"):
                        sec_df = preloaded.panel.xs(bare_s, axis=1, level="security")
                    if sec_df is not None and not sec_df.empty and "close" in sec_df.columns:
                        closes = sec_df["close"].dropna()
                        if len(closes) >= 5:
                            row["ma5"] = float(closes.tail(5).mean())
                        if len(closes) >= 10:
                            row["ma10"] = float(closes.tail(10).mean())
                        if len(closes) >= 20:
                            row["ma20"] = float(closes.tail(20).mean())
                        if len(closes) >= 15:
                            rsi_val = rsi(closes, 14)
                            if not rsi_val.dropna().empty:
                                row["rsi14"] = float(rsi_val.iloc[-1])
                except Exception:
                    pass

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("security")
    if fields:
        df = df[[f for f in fields if f in df.columns]]
    return df


# ── Built-in selectors ───────────────────────────────────────────────────────


class TopNSelector(StockSelector):
    """Select Top-N stocks ranked by a single factor.

    Parameters:
        factor: column name to rank by (e.g. 'pe', 'pct_change', 'total_value')
        top_n: number of stocks to select
        ascending: True for lowest-first (e.g. low PE), False for highest-first

    Example::

        # Select 5 stocks with lowest PE
        sel = TopNSelector(factor='pe', top_n=5, ascending=True)
        selected = sel.rank(context.universe, context)

        # Select 3 stocks with highest momentum
        sel = TopNSelector(factor='pct_change', top_n=3, ascending=False)
    """

    def __init__(self, factor: str = "pe", top_n: int = 5, ascending: bool = True):
        self.factor = factor
        self.top_n = top_n
        self.ascending = ascending

    def rank(self, securities: list[str], context) -> list[str]:
        df = fetch_factor_data(securities, fields=[self.factor])
        if df.empty or self.factor not in df.columns:
            return securities[:self.top_n] if len(securities) > self.top_n else securities

        df = df.dropna(subset=[self.factor])
        df = df.sort_values(self.factor, ascending=self.ascending)
        return df.head(self.top_n).index.tolist()


class MultiFactorSelector(StockSelector):
    """Rank stocks by a weighted composite score of multiple factors.

    Parameters:
        factors: dict mapping factor_name -> weight (positive weight means
            higher values are better; use negative weight for inverse ranking
            such as PE where lower is preferred)
        top_n: number of stocks to select

    Example::

        # Low PE + low PB + high momentum
        selector = MultiFactorSelector(
            factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
            top_n=5,
        )
        selected = selector.rank(context.universe, context)
    """

    def __init__(self, factors: Optional[dict] = None, top_n: int = 5):
        self.factors = factors or {"pe": -0.4, "pb": -0.2, "pct_change": 0.4}
        self.top_n = top_n

    def rank(self, securities: list[str], context) -> list[str]:
        factor_names = list(self.factors.keys())
        df = fetch_factor_data(securities, fields=factor_names)
        if df.empty:
            return securities[:self.top_n] if len(securities) > self.top_n else securities

        # Drop rows where all factors are NaN
        df = df.dropna(subset=factor_names, how="all")

        # Z-score normalize each factor
        normalized = pd.DataFrame(index=df.index)
        for col in factor_names:
            s = df[col]
            std = s.std()
            mean = s.mean()
            if std > 0:
                normalized[col] = (s - mean) / std
            else:
                normalized[col] = 0.0

        # Apply weights: negative weight flips the sign
        scores = pd.Series(0.0, index=normalized.index)
        for col, w in self.factors.items():
            if col in normalized.columns:
                scores += w * normalized[col]

        # Higher score = better, sort descending
        scores = scores.sort_values(ascending=False)
        return scores.head(self.top_n).index.tolist()
