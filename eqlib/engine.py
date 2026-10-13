"""Backtest engine: drives the strategy lifecycle
(initialize -> handle_data / run_daily -> report)."""

import datetime
import math
import time
import pandas as pd
from typing import Optional
from eqlib.context import Context
from eqlib.data import fetch_stock_data, get_price, _get_trading_days_range
from eqlib.data_cache import PreloadedData
from eqlib.objects import GlobalObject, Order, LimitOrder, MarketOrder
import eqlib._state as st
from eqlib._state import BacktestSession, _set_session, _clear_session, reset_all
from eqlib.constants import (
    BSE_PRICE_LIMIT,
    CHINEXT_PRICE_LIMIT,
    CHINEXT_PRICE_LIMIT_REFORM_DATE,
    DEFAULT_DELIST_GAP_DAYS,
    MAIN_BOARD_PRICE_LIMIT,
    PAPER_CALLBACK_MAX_FAILURES,
    PAPER_FIRST_FILL_TIME,
    PAPER_SESSION_END,
    PAPER_SESSION_START,
    ST_PRICE_LIMIT,
    STAR_MARKET_PRICE_LIMIT,
)
from eqlib.logger import log


# ── Pre-loaded data is stored on the active session ───────────────────────────
# Access via _get_preloaded(); this allows concurrent backtests in separate
# threads to each have their own PreloadedData without global aliasing.

def _get_preloaded() -> PreloadedData:
    """Return the active session's PreloadedData (may be None if not yet set)."""
    sess = st.get_session()
    return getattr(sess, '_preloaded', None) or _preloaded_fallback


# Fallback for when no session is active (e.g., module-level imports before
# run_backtest has been called).  _get_preloaded() returns this when the
# session has no _preloaded set.
_preloaded_fallback = PreloadedData()


# Slight over-estimate of effective cost rate used when computing the max
# affordable shares for a buy order (avoids fractional-lot overshoot).
_COMMISSION_BUFFER = 1.001

# HIGH-11: default maximum slippage percentage used when a slippage model
# does not expose a max_pct attribute.  Combined with commission to give a
# conservative upper bound on total buy cost per share.
_DEFAULT_SLIPPAGE_MAX_PCT = 0.005


def _bare_code(security: str) -> str:
    """Strip exchange suffix (.XSHG / .XSHE) from a security code."""
    return security.replace(".XSHG", "").replace(".XSHE", "")


class SecurityBar:
    """Lightweight bar object with __slots__ to avoid per-call class creation."""
    __slots__ = ("open", "high", "low", "close", "volume", "money")

    def __init__(self, d: dict):
        self.open = d.get("open", 0)
        self.high = d.get("high", 0)
        self.low = d.get("low", 0)
        self.close = d.get("close", 0)
        self.volume = d.get("volume", 0)
        self.money = d.get("money", 0)


def set_order_cost(cost, type: str = "stock", ref=None):
    """Set order cost parameters."""
    from eqlib.objects import OrderCost
    sess = st.get_session()
    sess._order_cost_config = cost
    sess._order_cost = OrderCost(
        open_tax=cost.open_tax,
        close_tax=cost.close_tax,
        open_commission=cost.open_commission,
        close_commission=cost.close_commission,
        close_today_commission=cost.close_today_commission,
        min_commission=cost.min_commission,
    )


def set_slippage(model):
    """Set the slippage model for the current session.

    Parameters:
        model: a SlippageModel instance (e.g., FixedSlippage or VolumeSlippage),
               or None to disable slippage.

    Example::

        from eqlib.slippage import FixedSlippage
        set_slippage(FixedSlippage(pct=0.001))
    """
    st.get_session()._slippage_model = model


def set_benchmark(security):
    """Set benchmark security."""
    st.get_session()._benchmark = security


def set_option(name, value):
    """Set strategy option."""
    st.get_session()._options[name] = value


def set_order_timeout(seconds: int):
    """Set order timeout threshold in seconds.

    Orders that remain pending for longer than this threshold are
    automatically cancelled with status STATUS_EXPIRED.

    Parameters:
        seconds: timeout in seconds. Default is mode-based:
            - Live/paper trading: 3600 (1 hour)
            - Backtest: 86400 (1 day)
            Set to 0 or negative to disable timeout.

    Example::

        # Cancel orders after 30 minutes in live trading
        set_order_timeout(1800)

        # Disable timeout (orders never expire)
        set_order_timeout(0)
    """
    sess = st.get_session()
    if seconds <= 0:
        sess._order_timeout_seconds = None  # Disable timeout
    else:
        sess._order_timeout_seconds = seconds


def set_notification_webhook(platform: str, url: str, secret: str = None):
    """Configure webhook for trade notifications.

    When paper trading generates signals or executes orders, notifications
    will be sent to the configured webhook platform (DingTalk or Feishu).

    Parameters:
        platform: "dingtalk" or "feishu"
        url: webhook URL from the platform
            - DingTalk: https://oapi.dingtalk.com/robot/send?access_token=xxx
            - Feishu: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
        secret: (optional) secret for DingTalk signature verification

    Example::

        # DingTalk with signature
        set_notification_webhook("dingtalk", "https://oapi.dingtalk.com/...", "SECxxx")

        # Feishu
        set_notification_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/xxx")

        # Disable notifications
        set_notification_webhook(None, None)
    """
    from eqlib.notification import DingTalkSender, FeishuSender
    sess = st.get_session()
    if platform == "dingtalk" and url:
        sess._notification_sender = DingTalkSender(url, secret=secret)
    elif platform == "feishu" and url:
        sess._notification_sender = FeishuSender(url)
    else:
        sess._notification_sender = None


def enable_notification(events: list = None):
    """Enable notification for specific trade events.

    By default, notifications are disabled. Call this function to
    enable notifications for specific events.

    Parameters:
        events: list of event names to enable notifications for.
            Supported events:
            - "signal": when strategy generates a trading signal (recommended)
            - "queued": when order is queued
            - "filled": when order is filled
            Default: ["signal"]

    Example::

        # Enable signal notifications (recommended for paper trading)
        enable_notification(["signal"])

        # Enable all notifications
        enable_notification(["signal", "filled"])

        # Disable all notifications
        enable_notification([])
    """
    sess = st.get_session()
    if events is None:
        events = ["signal"]
    sess._notification_events = list(events)


def notify_signal(
    security: str,
    side: str,
    amount: int,
    current_price: float = None,
    price_range: tuple = None,
    strategy_name: str = None,
    trigger_point: str = None
):
    """Send actionable trade signal notification.

    Call this function in your strategy when you detect a trading signal.
    It sends a notification to the configured webhook with concrete
    trading advice.

    Parameters:
        security: Stock code (e.g., "601390" or "601390.XSHG")
        side: "buy" or "sell"
        amount: Number of shares to trade (must be multiple of 100)
        current_price: Current market price (optional)
        price_range: Tuple of (low, high) recommended execution price range
        strategy_name: 策略名称 (e.g., "双均线金叉策略")
        trigger_point: 触发点详情 (e.g., "MA5=5.25 上穿 MA20=4.80, 金叉形成")

    Example::

        def handle_data(context, data):
            price = data.current(g.security, 'close')
            ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
            ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()

            if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
                notify_signal(
                    security=g.security,
                    side="buy",
                    amount=1000,
                    current_price=price,
                    price_range=(price * 0.98, price * 1.02),
                    strategy_name="双均线金叉策略",
                    trigger_point=f"MA5={ma5:.2f} 上穿 MA20={ma20:.2f}, 金叉形成"
                )
                order(g.security, 1000)

    Returns:
        True if notification was sent successfully, False otherwise.
    """
    from eqlib.notification import notify_signal as _notify_signal
    return _notify_signal(
        security=security,
        side=side,
        amount=amount,
        current_price=current_price,
        price_range=price_range,
        context=st.get_session()._context,
        strategy_name=strategy_name,
        trigger_point=trigger_point
    )


def _register_on_order_queued(func):
    """Internal: register callback for order queued events."""
    st.get_session()._on_order_queued_funcs.append(func)


def _register_on_order_filled(func):
    """Internal: register callback for order filled events."""
    st.get_session()._on_order_filled_funcs.append(func)


def run_daily(func, time="every_bar"):
    """Schedule a function to run every trading day.

    Parameters:
        func: callable taking (context) as argument
        time: execution time, e.g., '09:30', '14:50', 'every_bar'
    """
    st.get_session()._scheduled_funcs.append(("daily", time, func))


def run_weekly(func, day_of_week: int = 1, time="09:30"):
    """Schedule a function to run weekly.

    Parameters:
        func: callable taking (context) as argument
        day_of_week: 0=Monday, 1=Tuesday, ..., 4=Friday
        time: execution time, e.g., '09:30'
    """
    st.get_session()._scheduled_funcs.append(("weekly", day_of_week, time, func))


def run_monthly(func, day_of_month: int = 1, time="09:30"):
    """Schedule a function to run monthly.

    Parameters:
        func: callable taking (context) as argument
        day_of_month: day of month, 1-31
        time: execution time, e.g., '09:30'
    """
    st.get_session()._scheduled_funcs.append(("monthly", day_of_month, time, func))


def run_selection(func, rebalance: str = "monthly:1"):
    """Register a stock selection function to run periodically.

    The selection function should return a list of security codes that will
    automatically update ``context.universe``.

    Parameters:
        func: callable taking (context) and returning a list of security codes
        rebalance: schedule string, e.g. "monthly:1" (1st of month),
            "weekly:0" (Monday), or "daily"

    Example::

        def my_selection(context):
            # Return top 10 stocks by PE ratio
            from eqlib.selection import TopNSelector
            sel = TopNSelector(factor='pe', top_n=10, ascending=True)
            return sel.rank(context.universe, context)

        run_selection(my_selection, rebalance='monthly:1')
    """
    sess = st.get_session()
    # Store selection config on the session for the engine to pick up
    object.__setattr__(sess, '_selection_func', func)
    object.__setattr__(sess, '_selection_rebalance', rebalance)


def _is_first_trading_day_ge(day: datetime.date, n: int) -> bool:
    """Return True if *day* is the first trading day in its month with day.day >= n.

    Uses the active session's preloaded trading calendar when available;
    falls back to a simple "day.day == n" comparison otherwise (which is
    correct when the calendar is not loaded, e.g., in tests).

    This fixes the A-share quirk where Jan 1 (and other month-start dates)
    are always holidays — previously ``monthly:1`` would never fire.
    """
    if day.day < n:
        return False
    preloaded = _get_preloaded()
    if preloaded is not None and preloaded._dates is not None and len(preloaded._dates) > 0:
        # Check whether any earlier trading day in [n, day.day-1] exists this month
        for d in preloaded._dates:
            ts = pd.Timestamp(d).date()
            if ts.year == day.year and ts.month == day.month:
                if n <= ts.day < day.day:
                    return False
        return True
    # Fallback: simple day-of-month comparison
    return day.day == n


def _should_run_schedule(sched, day) -> bool:
    """Check if a scheduled function should run on the given date."""
    t = sched[0]
    if t == "daily":
        return True
    if t == "weekly":
        return day.weekday() == sched[1]
    if t == "monthly":
        return _is_first_trading_day_ge(day, sched[1])
    return False


def _should_run_selection(rebalance: str, day) -> bool:
    """Check if stock selection should run on the given date.

    Parameters:
        rebalance: schedule string, e.g. "monthly:1", "weekly:0", "daily"
        day: datetime.date to check
    """
    if not rebalance:
        return False
    if rebalance == "daily":
        return True
    if ":" in rebalance:
        kind, val = rebalance.split(":", 1)
        try:
            n = int(val)
        except ValueError:
            return False
        if kind == "monthly":
            return _is_first_trading_day_ge(day, n)
        if kind == "weekly":
            return day.weekday() == n
    return False


def _get_sched_time(sched) -> str:
    """Get the time string from a schedule entry."""
    return sched[2 if sched[0] != "daily" else 1]


def _get_sched_func(sched):
    """Get the function from a schedule entry."""
    return sched[3 if sched[0] != "daily" else 2]


def _register_before_start(func):
    """Register a before_trading_start callback."""
    st.get_session()._before_trading_start_funcs.append(func)


def _register_after_end(func):
    """Register an after_trading_end callback."""
    st.get_session()._after_trading_end_funcs.append(func)


def record(**kwargs):
    """Record a data point for charting."""
    sess = st.get_session()
    entry = {"date": sess._context.current_dt.date()}
    entry.update(kwargs)
    sess._recorded_values[sess._context.current_dt.date()] = entry


def _get_price_fast(security, day) -> Optional[float]:
    """Get closing price for a security on a given day (O(1) dict lookup)."""
    return _get_preloaded().get_close(day, security)


def _get_open_fast(security, day) -> Optional[float]:
    """Get opening price for a security on a given day."""
    bar = _get_preloaded().get_bar(day, security)
    if bar:
        return bar.get("open")
    return None


def _get_volume_fast(security, day) -> Optional[float]:
    """Get daily volume for a security (used by VolumeSlippage).

    Returns:
        None  — no bar exists for this security on this day (treat as suspended
                when set_option('treat_missing_bar_as_suspended', True), default True).
        0.0   — bar exists but volume is 0 (treat as suspended only when
                set_option('treat_missing_bar_as_suspended', True), default True).
        float — positive daily volume.
    """
    bar = _get_preloaded().get_bar(day, security)
    if bar is None:
        return None
    return float(bar.get("volume", 0))


def _get_last_close_before(security, day) -> Optional[float]:
    """Return the security's last available close strictly before *day*.

    Unlike ``get_prev_trading_day`` + ``get_close`` (which only looks at the
    immediately preceding union-calendar day), this walks back over the
    security's own bar series, so a stock resuming from suspension still
    compares against its last genuinely traded close — which is exactly the
    reference price the exchange uses for the post-suspension price limit.

    O(number of bars for the security); called at most once per pending
    order per day.
    """
    preloaded = _get_preloaded()
    if preloaded is None or not getattr(preloaded, "_close_dict", None):
        return None
    ts_day = pd.Timestamp(day)
    for sec in (security, _bare_code(security)):
        sec_dict = preloaded._close_dict.get(sec)
        if not sec_dict:
            continue
        best_ts = None
        best_val = None
        for ts, val in sec_dict.items():
            try:
                key = ts if isinstance(ts, pd.Timestamp) else pd.Timestamp(ts)
            except Exception:
                continue
            if key < ts_day and (best_ts is None or key > best_ts):
                if val is not None and val == val:  # skip NaN
                    best_ts, best_val = key, val
        if best_val is not None:
            return float(best_val)
    return None


def set_handle_data(func):
    """Register the user's handle_data function."""
    st.get_session()._handle_data_func = func


class _LazyData(dict):
    """Lazy data dict: fetches bars on first access per security."""

    def __init__(self, context):
        super().__init__()
        self._context = context

    def __missing__(self, key):
        day = self._context.current_dt.date()
        preloaded = _get_preloaded()
        if preloaded is None:
            return None
        bar = preloaded.get_bar(day, key)
        if bar is not None:
            result = SecurityBar(bar)
            self[key] = result
            return result
        return None

    def current(self, security, fields=None):
        """Return the current bar value(s) for *security*.

        ``fields`` may be a single field name (``'close'``) or an iterable of
        field names.  Returns ``None`` when no bar is available for today.
        """
        bar = self[security]
        if bar is None:
            return None
        if fields is None:
            return bar
        if isinstance(fields, str):
            return getattr(bar, fields, None)
        return {f: getattr(bar, f, None) for f in fields}

    def attribute_history(self, security, count, unit="1d", fields=("close",),
                          df=True, skip_paused=True, fq="pre"):
        """Delegate to the module-level :func:`eqlib.attribute_history`.

        Point-in-time safety is enforced there (bars for the current day are
        excluded).
        """
        from eqlib.data import attribute_history
        return attribute_history(
            security, count, unit=unit, fields=fields, df=df,
            skip_paused=skip_paused, fq=fq,
        )


# ── Pending-order fill logic (look-ahead bias fix) ─────────────────────────────

def _t1_unlock(sess: BacktestSession):
    """Unlock shares bought on the previous day (T+1 enforcement).

    At the start of each new trading day we:
    1. Clear the ``_t1_locked_amounts`` registry (previous day's buys are
       now freely tradeable).
    2. Restore ``closeable_amount`` to the full position size for all
       existing positions.
    """
    sess._t1_locked_amounts.clear()
    for pos in sess._context.portfolio.positions.values():
        pos.closeable_amount = pos.amount


def _as_date(dt_like) -> Optional[datetime.date]:
    """Normalize date/datetime/Timestamp-like input to ``datetime.date``."""
    if dt_like is None:
        return None
    if isinstance(dt_like, datetime.datetime):
        return dt_like.date()
    if isinstance(dt_like, datetime.date):
        return dt_like
    return pd.Timestamp(dt_like).date()


def _lookup_st_status(session: Optional[BacktestSession], security: str,
                      context_dt) -> Optional[bool]:
    """Resolve ST status for *security* as of *context_dt* (point-in-time).

    Resolution order:
      1. User-injected PIT map ``set_option('st_status_map', ...)``, mapping a
         bare or suffixed code to one of:
           - ``bool`` — static ST flag for the whole run;
           - ``(start_date, end_date_or_None)`` tuple or list of such tuples —
             ST while ``start <= context_dt <= end`` (``None`` end = ongoing);
           - ``callable(bare_code, date) -> bool`` — full user PIT logic.
      2. Paper/live sessions only: network detection via ``get_extras`` and a
         spot-name fallback (akshare).  Never called in backtests.

    Returns ``None`` when the status is unknown.  Callers then assume non-ST
    (documented conservative approximation: without a PIT source we do not
    tighten a stock to ±5 %, which would otherwise wrongly reject legitimate
    main-board fills).
    """
    if session is not None:
        st_map = session._options.get("st_status_map")
        if st_map:
            bare = _bare_code(security)
            key = security if security in st_map else bare
            if key in st_map:
                entry = st_map[key]
                day = _as_date(context_dt) or datetime.date.today()
                if callable(entry):
                    try:
                        return bool(entry(bare, day))
                    except Exception as exc:
                        log.warn(f"st_status_map callable failed for {bare}: {exc}")
                        return None
                if isinstance(entry, bool):
                    return entry
                intervals = entry
                if isinstance(intervals, tuple) and len(intervals) == 2:
                    intervals = [intervals]
                try:
                    for start, end in intervals:
                        s = _as_date(start)
                        e = _as_date(end)
                        if (s is None or day >= s) and (e is None or day <= e):
                            return True
                    return False
                except (TypeError, ValueError):
                    log.warn(f"st_status_map entry for {key} not understood: {entry!r}")
                    return None

    # Network detection is only allowed in paper/live sessions.
    if session is None or not session._options.get("_is_paper_trading", False):
        return None
    bare = _bare_code(security)
    try:
        from eqlib.data import get_extras
        st_map = get_extras("is_st", security_list=[bare])
        if bare in st_map:
            return bool(st_map[bare])
    except Exception:
        pass
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"] == bare]
        if len(row) > 0:
            name = str(row.iloc[0]["名称"])
            return "ST" in name.upper()
    except Exception:
        pass
    return None


def _st_map_covers(session: Optional[BacktestSession], security: str) -> bool:
    """True when the user-injected st_status_map has an entry for *security*.

    Map-covered securities bypass the 30-day date-stamped limit cache so the
    ST on/off boundary is point-in-time exact instead of blurred by caching.
    """
    if session is None:
        return False
    st_map = session._options.get("st_status_map")
    if not st_map:
        return False
    return security in st_map or _bare_code(security) in st_map


def _get_price_limit_ratio(security: str, context_dt: datetime.date = None,
                           session: BacktestSession = None) -> float:
    """Return the daily price-limit ratio (one-sided) for a security.

    Board classification (date-aware):
        688xxx.XSHG  → STAR Market: ±20 % (since inception 2019-07-22)
        300xxx.XSHE  → ChiNext: ±10 % before 2020-08-24, ±20 % on/after
                       (registration-based reform; ST stocks on ChiNext keep
                       the same board-wide limit)
        83/87/43/92x → Beijing Stock Exchange: ±30 %
        ST / *ST     → ±5 % (main board only; see ST resolution below)
        All others   → Main board / SME: ±10 %

    Parameters:
        security: stock code (e.g., "601390.XSHG")
        context_dt: date of the trade being evaluated.  Drives the ChiNext
            regime switch and the PIT ST lookup.  ``None`` means "current
            rules" (ChiNext ±20 %).
        session: optional BacktestSession for caching and mode detection

    Documented assumptions / approximations:
        - New-stock limit-free windows are NOT modelled (first 5 sessions for
          registration-board IPOs, day-1 +44 %/−36 % for main-board IPOs):
          the listing date is not available offline, and during a genuine
          no-limit window no price limit exists to enforce anyway.
        - ST status without a PIT source assumes non-ST (±10 % main board).
          Inject ``set_option('st_status_map', {...})`` for PIT-correct ST
          handling in backtests; paper/live sessions detect ST via akshare.
        - ``context_dt`` before the ChiNext reform yields ±10 % for 300xxx.
    """
    context_day = _as_date(context_dt)

    # ── Check session cache first ─────────────────────────────────────────
    # Plain-float entries are date-independent overrides (user-injected) or
    # structural limits (STAR/BSE).  Dict entries carry a date stamp and
    # expire after 30 days (ST / main-board results are date-dependent).
    if session is not None:
        cache = session._options.get("_price_limit_cache")
        if cache is not None and security in cache:
            entry = cache[security]
            if isinstance(entry, (int, float)):
                return entry
            if isinstance(entry, dict):
                cached_date = entry.get("date")
                # Map-covered securities skip the dated cache (PIT-exact).
                if _st_map_covers(session, security):
                    pass
                elif cached_date and context_day and \
                        abs((context_day - cached_date).days) < 30:
                    return entry["ratio"]

    bare = _bare_code(security)
    # BSE (Beijing Stock Exchange): ±30%
    if bare.startswith(("83", "87", "43", "92")):
        _cache_price_limit(session, security, BSE_PRICE_LIMIT)
        return BSE_PRICE_LIMIT
    # STAR Market: ±20% since inception (2019-07-22)
    if bare.startswith("688"):
        _cache_price_limit(session, security, STAR_MARKET_PRICE_LIMIT)
        return STAR_MARKET_PRICE_LIMIT
    # ChiNext: ±10% before the 2020-08-24 reform, ±20% on/after.
    # Date-dependent → deliberately not stored in the never-expiring
    # structural float cache.
    if bare.startswith("300"):
        if context_day is not None and context_day < CHINEXT_PRICE_LIMIT_REFORM_DATE:
            return MAIN_BOARD_PRICE_LIMIT
        return CHINEXT_PRICE_LIMIT

    # Main board: ST stocks trade at ±5%.  ST status is point-in-time and
    # only applies to the main board (ChiNext/STAR/BSE returned above).
    st_status = _lookup_st_status(session, security, context_day)
    if _st_map_covers(session, security):
        # User-injected PIT map: return the exact result uncached so the
        # ST on/off boundary is honoured to the day.
        return ST_PRICE_LIMIT if st_status is True else MAIN_BOARD_PRICE_LIMIT
    if st_status is True:
        _cache_price_limit_st(session, security, ST_PRICE_LIMIT, context_day)
        return ST_PRICE_LIMIT

    # Non-ST (or unknown → documented non-ST assumption): ±10%.  Cache with
    # a date stamp so a later ST onset within the same run is not masked by
    # a stale permanent entry.
    _cache_price_limit_st(session, security, MAIN_BOARD_PRICE_LIMIT, context_day)
    return MAIN_BOARD_PRICE_LIMIT


def _cache_price_limit(session, security, ratio):
    """Store structural price-limit ratio in session cache (never expires)."""
    if session is not None:
        cache = session._options.setdefault("_price_limit_cache", {})
        cache[security] = ratio


def _cache_price_limit_st(session, security, ratio, context_dt):
    """Store ST-based price-limit ratio with date stamp (expires after 30 days)."""
    if session is not None:
        cache = session._options.setdefault("_price_limit_cache", {})
        cache[security] = {"ratio": ratio, "date": context_dt or datetime.date.today()}


def _fill_pending_orders(sess, day, exec_prices=None, max_daily_volume_pct=0.10):
    """Match a snapshot of the queue; retain unprocessed requests on failure.

    The volume budget is shared by buys and sells for each security/day,
    including repeated calls to this function during paper trading.
    """
    from eqlib.objects import Order
    pending = list(sess._pending_orders)
    sess._pending_orders.clear()
    retained = []
    terminal = {Order.STATUS_FILLED, Order.STATUS_CANCELLED,
                Order.STATUS_EXPIRED, Order.STATUS_REJECTED}
    try:
        for index, req in enumerate(pending):
            obj = req.get("order_obj")
            if obj and obj.status in terminal:
                continue
            sess._pending_orders = [req]
            try:
                _fill_order_batch(sess, day, exec_prices, max_daily_volume_pct)
            except Exception:
                if not obj or obj.status not in terminal:
                    retained.append(req)
                retained.extend(pending[index + 1:])
                raise
            finally:
                retained.extend(sess._pending_orders)
                sess._pending_orders = []
    finally:
        # Cancellation callbacks may remove a partially filled remainder.
        seen = set()
        for req in retained:
            obj = req.get("order_obj")
            identity = obj.order_id if obj else id(req)
            if identity not in seen and (not obj or obj.status not in terminal):
                sess._pending_orders.append(req)
                seen.add(identity)
        for req in pending:
            obj = req.get("order_obj")
            if obj and obj.status in terminal:
                sess._order_timestamps.pop(obj.order_id, None)


def _fill_order_batch(sess: BacktestSession, day: datetime.date,
                         exec_prices: Optional[dict] = None,
                         max_daily_volume_pct: float = 0.10):
    """Fill all pending orders at today's open price.

    Orders buffered during yesterday's strategy execution are executed here,
    eliminating look-ahead bias.  Slippage is applied to each fill.
    After a buy is filled, the new shares are registered as T+1-locked
    (``closeable_amount`` is NOT increased for those shares until tomorrow).

    Phase 2 enhancements:
    - Large orders exceeding max_daily_volume_pct of daily volume are partially
      filled; remaining amount stays in pending queue.
    - Order status tracking: pending→submitted→partial_fill→filled.

    Market-rule semantics (declared 2026-10-12):
    - Price-limit enforcement is ON by default in every mode
      (``set_option('check_price_limit', False)`` disables): buys whose open
      touches the fen-rounded limit-up price and sells touching limit-down
      are cancelled (reason "limit-up" / "limit-down").
    - Suspension: a security with no bar today (or a zero-volume bar with
      ``treat_missing_bar_as_suspended``) cannot trade; the order is
      cancelled the same day (reason "no price data" / "suspended") — it is
      never deferred to a later day.
    - Paper/live (``exec_prices is not None``): a missing quote is transient,
      so the order stays pending instead of being cancelled (the order
      timeout governs expiry).

    Parameters:
        sess: the active BacktestSession
        day: the fill date (used for preloaded price lookup)
        exec_prices: optional dict mapping security code (bare or full) to
            execution price.  When provided (e.g. for live/paper trading),
            these prices take precedence over preloaded data.  The suspension
            check is skipped for securities whose price is found in this dict.
        max_daily_volume_pct: maximum fraction of daily volume that can be
            filled in a single day (default 0.10 = 10%). Orders exceeding this
            limit are partially filled; remaining amount stays pending.
    """
    from eqlib.context import Position
    from eqlib.objects import OrderCost, Order
    from eqlib.data import _is_etf

    pending = list(sess._pending_orders)
    sess._pending_orders.clear()

    if not pending:
        return

    slippage = sess._slippage_model
    cost_cfg: OrderCost = sess._order_cost or OrderCost()
    portfolio = sess._context.portfolio

    # Orders that are partially filled and need to stay pending
    still_pending = []

    for order_req in pending:
        from eqlib.trade import _resolve_security, _normalize_security
        security = _resolve_security(order_req["security"], portfolio)
        order_req["security"] = security
        action = order_req["action"]
        order_obj: Order = order_req.get("order_obj")

        # ── Phase 2.4: Order timeout check ───────────────────────────────────────
        # Check if order has exceeded its timeout threshold.
        # Live/paper trading: default 1 hour (3600s) using wall-clock time
        # Backtest: count trading days elapsed (default: disabled / None)
        if order_obj and order_obj.order_id in sess._order_timestamps:
            submit_stamp = sess._order_timestamps[order_obj.order_id]
            is_backtest = exec_prices is None

            timed_out = False
            elapsed_display = ""

            if is_backtest:
                # A-REG1: Count trading days elapsed, not wall-clock seconds.
                # Orders fill on T+1 so wall-clock timeout always expires.
                timeout_days = sess._order_timeout_seconds  # reuse field; None = disabled
                if timeout_days is None:
                    # Backtest default: disabled (None). Users can opt-in via set_order_timeout().
                    timed_out = False
                else:
                    # Convert seconds to trading days if user set via set_order_timeout(seconds)
                    timeout_trading_days = max(1, timeout_days // 86400) if timeout_days > 0 else 0
                    if timeout_trading_days <= 0:
                        timed_out = False
                    else:
                        # Extract date from submit_stamp (may be date or datetime)
                        if isinstance(submit_stamp, datetime.datetime):
                            submit_date = submit_stamp.date()
                        elif isinstance(submit_stamp, datetime.date):
                            submit_date = submit_stamp
                        else:
                            submit_date = submit_stamp
                        # Count trading days between submit_date and current day.
                        # Prefer the exchange calendar captured at backtest
                        # start; fall back to the preloaded union (legacy) and
                        # finally to calendar days.
                        calendar = sess._options.get("_exchange_trading_days")
                        if not calendar:
                            preloaded = _get_preloaded()
                            if preloaded is not None and getattr(preloaded, "_dates", None) is not None \
                                    and len(preloaded._dates) > 0:
                                calendar = [d.date() if hasattr(d, "date") else d
                                            for d in preloaded._dates]
                        if calendar:
                            try:
                                submit_idx = next(i for i, d in enumerate(calendar) if d >= submit_date)
                                current_idx = next(i for i, d in enumerate(calendar) if d >= day)
                                days_elapsed = current_idx - submit_idx
                            except StopIteration:
                                days_elapsed = 0
                        else:
                            # Fallback: use calendar days (conservative)
                            days_elapsed = (day - submit_date).days
                        elapsed_display = f"{days_elapsed} trading days"
                        timed_out = days_elapsed > timeout_trading_days
            else:
                # Live/paper: wall-clock timeout
                current_time = datetime.datetime.now()
                timeout_seconds = sess._order_timeout_seconds
                if timeout_seconds is None:
                    timeout_seconds = 3600  # 1 hour default for live
                if not isinstance(submit_stamp, datetime.datetime):
                    # Legacy persisted requests recorded only a date.
                    submit_stamp = datetime.datetime.combine(submit_stamp, datetime.time())
                elapsed_seconds = (current_time - submit_stamp).total_seconds()
                elapsed_display = f"{elapsed_seconds:.0f}s"
                timed_out = elapsed_seconds > timeout_seconds

            if timed_out:
                log.warn(f"ORDER TIMEOUT {security}: order_id={order_obj.order_id} "
                         f"elapsed={elapsed_display} — order cancelled")
                order_obj.transition_to(Order.STATUS_EXPIRED, reason="timeout")
                sess._trade_log.append({
                    "type": "ORDER_TIMEOUT",
                    "date": day,
                    "security": security,
                    "order_id": order_obj.order_id,
                    "action": action,
                    "elapsed": elapsed_display,
                })
                # Remove timestamp record
                del sess._order_timestamps[order_obj.order_id]
                continue

        # ── Resolve target amount ──────────────────────────────────────────
        if action == "ORDER":
            delta = order_req["amount"]
        elif action == "ORDER_TARGET":
            current = portfolio.positions[security].amount if security in portfolio.positions else 0
            delta = order_req["target_amount"] - current
        elif action == "ORDER_VALUE":
            open_px = ((exec_prices or {}).get(security) or
                       (exec_prices or {}).get(_bare_code(security)) or
                       _get_open_fast(security, day))
            if not open_px or (isinstance(open_px, float) and math.isnan(open_px)):
                if exec_prices is not None:
                    # Live/paper: today's quote may simply not have arrived
                    # yet (pre-open poll, provider hiccup).  Keep the order
                    # pending instead of cancelling it — the session-level
                    # order timeout remains the cleanup path.
                    log.warn(f"fill_pending: no open price for {security} on {day} "
                             f"(ORDER_VALUE kept pending)")
                    still_pending.append(order_req)
                    continue
                log.warn(f"fill_pending: no open price for {security} on {day} (ORDER_VALUE skipped)")
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="no open price")
                continue
            # Estimate exec_price with slippage for accurate share calculation
            is_buy_est = order_req["value"] > 0
            slippage_pct = getattr(sess._slippage_model, "pct", 0) if sess._slippage_model else 0
            est_px = open_px * (1 + slippage_pct) if is_buy_est else open_px * (1 - slippage_pct)
            raw = int(order_req["value"] / est_px)
            delta = _round_lot(abs(raw))
            if order_req["value"] < 0:
                delta = -delta
        elif action == "ORDER_TARGET_VALUE":
            open_px = ((exec_prices or {}).get(security) or
                       (exec_prices or {}).get(_bare_code(security)) or
                       _get_open_fast(security, day))
            if not open_px or (isinstance(open_px, float) and math.isnan(open_px)):
                if exec_prices is not None:
                    log.warn(f"fill_pending: no open price for {security} on {day} "
                             f"(ORDER_TARGET_VALUE kept pending)")
                    still_pending.append(order_req)
                    continue
                log.warn(f"fill_pending: no open price for {security} on {day} (ORDER_TARGET_VALUE skipped)")
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="no open price")
                continue
            # Estimate exec_price with slippage for accurate share calculation
            slippage_pct = getattr(sess._slippage_model, "pct", 0) if sess._slippage_model else 0
            est_px = open_px * (1 + slippage_pct) if order_req["target_value"] > 0 else open_px
            target_sh = _round_lot(int(order_req["target_value"] / est_px)) if order_req["target_value"] > 0 else 0
            current = portfolio.positions[security].amount if security in portfolio.positions else 0
            delta = target_sh - current
        else:
            if order_obj:
                order_obj.transition_to(Order.STATUS_CANCELLED, reason="unknown action")
            continue

        if order_obj:
            order_obj.amount = order_obj.filled_amount + abs(int(delta))
            order_obj._quantity_resolved = True

        # A-REG2: Cancel (not fill) when no position change is needed.
        # PENDING → FILLED is not a valid transition.
        if delta == 0:
            if order_obj:
                order_obj.transition_to(Order.STATUS_CANCELLED, reason="no position change needed")
            continue

        is_buy = delta > 0
        requested_amount = abs(int(delta))

        # B3: Set order side at fill time for target orders (side was None at creation)
        if order_obj and order_obj.side is None:
            order_obj.side = "buy" if is_buy else "sell"

        # ── Resolve execution price ────────────────────────────────────────
        # When exec_prices is provided (paper/live trading), use it first.
        base_price = None
        if exec_prices is not None:
            bare_code = _bare_code(security)
            base_price = exec_prices.get(security) or exec_prices.get(bare_code)
        if not base_price:
            base_price = _get_open_fast(security, day)
        if not base_price:
            if exec_prices is not None:
                # Live/paper: no quote for this security right now — keep the
                # order pending (order timeout governs expiry) rather than
                # cancelling on a transient data gap.
                log.warn(f"fill_pending: no price for {security} on {day} "
                         f"— order kept pending")
                still_pending.append(order_req)
                continue
            log.warn(f"fill_pending: no open price for {security} on {day} — order skipped")
            if order_obj:
                order_obj.transition_to(Order.STATUS_CANCELLED, reason="no price data")
            continue

        # ── Phase 2.3: Limit order check ─────────────────────────────────────
        # Check if order has a LimitOrder style and defer execution if
        # the current price doesn't meet the limit condition.
        order_style = order_req.get("style") or (order_obj.style if order_obj else None)
        if order_style and hasattr(order_style, 'limit_price') and order_style.limit_price is not None:
            limit_price = order_style.limit_price
            if is_buy:
                # Buy limit order: only execute if current price <= limit_price
                # (we want to buy at or below our limit)
                if base_price > limit_price:
                    log.info(f"LIMIT ORDER BUY {security}: current price {base_price:.3f} > "
                             f"limit price {limit_price:.3f} — order deferred")
                    # Keep order in pending queue for future execution
                    still_pending.append(order_req)
                    continue
            else:
                # Sell limit order: only execute if current price >= limit_price
                # (we want to sell at or above our limit)
                if base_price < limit_price:
                    log.info(f"LIMIT ORDER SELL {security}: current price {base_price:.3f} < "
                             f"limit price {limit_price:.3f} — order deferred")
                    # Keep order in pending queue for future execution
                    still_pending.append(order_req)
                    continue

        # ── HIGH-13: warn on large price gaps for ORDER_VALUE / ORDER_TARGET_VALUE ──
        # A significant gap between yesterday's close and today's open suggests
        # a limit-hit or suspension scenario; shares-based orders (order())
        # handle this more predictably than value-based ones.
        if exec_prices is None and action in ("ORDER_VALUE", "ORDER_TARGET_VALUE"):
            prev_close = _get_last_close_before(security, day)
            if prev_close and prev_close > 0:
                gap_ratio = base_price / prev_close
                if gap_ratio > 1.1 or gap_ratio < 0.9:
                    log.warn(
                        f"fill_pending {action} {security}: today's open ({base_price:.3f}) "
                        f"has a large gap vs its last traded close ({prev_close:.3f}, "
                        f"ratio={gap_ratio:.2%}). Consider using order() with explicit "
                        "share counts for more predictable execution."
                    )

        # ── Suspension check (HIGH-12) ─────────────────────────────────────
        # Distinguish "missing bar" (None) from "zero-volume bar" (0.0).
        # treat_missing_bar_as_suspended (default True): missing bar → suspend.
        # volume == 0 is only treated as suspended when the same option is True.
        vol = _get_volume_fast(security, day)
        treat_missing_as_suspended = sess._options.get("treat_missing_bar_as_suspended", True)
        if exec_prices is not None and base_price:
            # Live/paper trading: use a large nominal volume for VolumeSlippage
            vol = (vol if (vol is not None and vol > 0) else 1e9)
        elif vol is None:
            log.warn(f"fill_pending: {security} has no bar on {day} — order skipped")
            if order_obj:
                order_obj.transition_to(Order.STATUS_CANCELLED, reason="no bar data")
            continue
        elif vol == 0 and treat_missing_as_suspended:
            log.warn(f"fill_pending: {security} volume=0 on {day} (appears suspended) — order skipped")
            if order_obj:
                order_obj.transition_to(Order.STATUS_CANCELLED, reason="suspended")
            continue

        # ── Price-limit check (A-share circuit breaker) ─────────────────────
        # Enabled by default in ALL modes (set_option('check_price_limit', False)
        # to disable).  An order marketable only at the limit price cannot
        # execute in reality: buys at a sealed limit-up and sells at a sealed
        # limit-down are impossible, so ignoring this systematically flatters
        # momentum/breakout backtests.
        # Buys at limit-up are unfillable; sells at limit-down are also blocked.
        if sess._options.get("check_price_limit", True):
            # For live/paper trading, use previous close from exec_prices or fetch it
            if exec_prices is not None:
                # Live mode: fetch previous close via akshare
                try:
                    bare = _bare_code(security)
                    from eqlib.data import fetch_stock_data
                    prev_df = fetch_stock_data(
                        bare,
                        start_date=str(day - datetime.timedelta(days=37)),
                        end_date=str(day - datetime.timedelta(days=1)),
                    )
                    if prev_df is not None and len(prev_df) > 0:
                        prev_close = float(prev_df['close'].iloc[-1])
                    else:
                        prev_close = None
                except Exception as exc:
                    log.warn(f"fill_pending: prev_close fetch failed for {security}: {exc}")
                    prev_close = None
            else:
                # Backtest: the limit is computed off the security's last
                # genuinely traded close (suspension-aware), which is the
                # reference the exchange uses when trading resumes.
                prev_close = _get_last_close_before(security, day)

            if prev_close:
                ratio = _get_price_limit_ratio(security, context_dt=day, session=sess)
                # Exchange rule: the limit price is rounded to the fen (0.01).
                limit_up = round(prev_close * (1 + ratio), 2)
                limit_down = round(prev_close * (1 - ratio), 2)
                # A small tolerance (0.1%) absorbs floating-point rounding
                # in price data (e.g. qfq adjusted-price inaccuracies, where
                # a corporate action between the two bars breaks the exact
                # multiplicative relation) so that a price of 10.999 is not
                # incorrectly treated as exactly limit-up (11.000).  The same
                # tolerance is applied to both sides for symmetry.
                _LIMIT_TOL = 0.001
                if is_buy and base_price >= limit_up * (1 - _LIMIT_TOL):
                    log.warn(
                        f"fill_pending BUY {security}: open {base_price:.3f} hit "
                        f"limit-up ({limit_up:.3f}) on {day} — order skipped"
                    )
                    if order_obj:
                        order_obj.transition_to(Order.STATUS_CANCELLED, reason="limit-up")
                    continue
                if not is_buy and base_price <= limit_down * (1 + _LIMIT_TOL):
                    log.warn(
                        f"fill_pending SELL {security}: open {base_price:.3f} hit "
                        f"limit-down ({limit_down:.3f}) on {day} — order skipped"
                    )
                    if order_obj:
                        order_obj.transition_to(Order.STATUS_CANCELLED, reason="limit-down")
                    continue

        if slippage:
            exec_price = slippage.get_execution_price(
                base_price, requested_amount, is_buy, daily_volume=vol
            )
            # F3: slippage model returns None for zero-volume stocks
            if exec_price is None:
                log.warn(f"fill_pending: {security} slippage returned None (zero volume) — order skipped")
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="zero volume")
                continue
        else:
            exec_price = base_price

        if order_style and getattr(order_style, "limit_price", None) is not None:
            if ((is_buy and exec_price > order_style.limit_price) or
                    (not is_buy and exec_price < order_style.limit_price)):
                still_pending.append(order_req)
                continue

        # ── Phase 2.2: Check daily volume limit for partial fill ───────────────
        # Large orders exceeding max_daily_volume_pct of daily volume are
        # partially filled; remaining amount stays in pending queue.
        # This is more realistic for live trading where large orders can
        # significantly impact market prices.
        budget_state = sess._options.setdefault("_fill_volume_budget", {})
        if budget_state.get("day") != day:
            budget_state.clear()
            budget_state.update(day=day, used={})
        volume_key = _normalize_security(security)
        used_volume = budget_state["used"].get(volume_key, 0)
        daily_cap = int(vol * max_daily_volume_pct) if vol and vol > 0 else requested_amount
        max_fill_by_volume = max(0, daily_cap - used_volume)
        # Round to 100-share lots
        max_fill_by_volume = _round_lot(max_fill_by_volume)
        # For sells, also consider closeable_amount
        if not is_buy:
            pos_closeable = portfolio.positions.get(security)
            if pos_closeable:
                max_fill_by_volume = min(max_fill_by_volume, int(pos_closeable.closeable_amount))

        # Determine actual fill amount
        fill_amount = min(requested_amount, max_fill_by_volume)
        if fill_amount <= 0:
            log.warn(f"fill_pending {is_buy and 'BUY' or 'SELL'} {security}: volume limit or closeable_amount=0")
            still_pending.append(order_req)
            continue

        # Check if this is a partial fill
        is_partial_fill = fill_amount < requested_amount
        remaining_amount = requested_amount - fill_amount

        # ── Update Order status ────────────────────────────────────────────────
        if order_obj:
            # 只在 pending 状态时才转换为 submitted，避免 partial_fill -> submitted 的错误转换
            if order_obj.status == Order.STATUS_PENDING:
                order_obj.transition_to(Order.STATUS_SUBMITTED)
                order_obj.submit_time = datetime.datetime.now()

        # ── Execute ────────────────────────────────────────────────────────
        if is_buy:
            rounded = _round_lot(fill_amount)
            if rounded <= 0:
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="sub-lot")
                    print(f"[EasyQuant] Order {order_obj.order_id} cancelled: amount {fill_amount} rounds to 0 lots (rounded={rounded})")
                continue
            commission = round(cost_cfg.calc_open_cost(exec_price, rounded), 2)
            total_cost = round(exec_price * rounded + commission, 2)

            if total_cost > portfolio.available_cash:
                # HIGH-11: use base_price (before slippage) plus a conservative
                # buffer that covers both maximum expected slippage and commission.
                slippage_max_pct = getattr(sess._slippage_model, "max_pct", _DEFAULT_SLIPPAGE_MAX_PCT) \
                    if sess._slippage_model is not None else 0.0
                commission_rate = cost_cfg.open_tax + cost_cfg.open_commission
                effective_rate = 1.0 + slippage_max_pct + commission_rate
                max_affordable = int(portfolio.available_cash / (base_price * effective_rate) // 100) * 100
                rounded = min(rounded, max_affordable)
                if rounded <= 0:
                    log.warn(f"fill_pending BUY {security}: insufficient cash")
                    if order_obj:
                        order_obj.transition_to(Order.STATUS_CANCELLED, reason="insufficient cash")
                    continue
                commission = round(cost_cfg.calc_open_cost(exec_price, rounded), 2)
                total_cost = round(exec_price * rounded + commission, 2)
                # Guard against min_commission pushing total_cost over budget
                while total_cost > portfolio.available_cash and rounded > 0:
                    rounded -= 100
                    if rounded <= 0:
                        break
                    commission = round(cost_cfg.calc_open_cost(exec_price, rounded), 2)
                    total_cost = round(exec_price * rounded + commission, 2)
                if rounded <= 0:
                    log.warn(f"fill_pending BUY {security}: insufficient cash (after min_commission)")
                    if order_obj:
                        order_obj.transition_to(Order.STATUS_CANCELLED, reason="insufficient cash")
                    continue

            # A1: Recompute partial-fill flags after cash-constraint reduction
            if rounded < requested_amount:
                is_partial_fill = True
                remaining_amount = requested_amount - rounded

            portfolio.available_cash = round(portfolio.available_cash - total_cost, 2)

            if security not in portfolio.positions:
                portfolio.positions[security] = Position(security)

            pos = portfolio.positions[security]
            total_cb = round(pos.avg_cost * pos.amount + exec_price * rounded, 4)
            pos.amount += rounded
            # T+1: newly bought shares are not sellable today
            locked = sess._t1_locked_amounts.get(security, 0) + rounded
            sess._t1_locked_amounts[security] = locked
            pos.closeable_amount = pos.amount - locked

            pos.avg_cost = round(total_cb / pos.amount, 4) if pos.amount > 0 else 0
            pos.update(exec_price)
            budget_state["used"][volume_key] = used_volume + rounded

            # ── Update Order status for partial/full fill ───────────────────────
            if order_obj:
                if is_partial_fill and rounded < requested_amount:
                    order_obj.add_partial_fill(rounded, exec_price, datetime.datetime.now())
                    log.info(f"PARTIAL FILL BUY {security}: {rounded}/{requested_amount} @ {exec_price:.3f} "
                             f"(open={base_price:.3f}), comm={commission:.2f}, remaining={remaining_amount}")
                else:
                    order_obj.add_partial_fill(rounded, exec_price, datetime.datetime.now())
                    order_obj.transition_to(Order.STATUS_FILLED)

            log.info(f"FILL BUY {security}: {rounded} @ {exec_price:.3f} "
                     f"(open={base_price:.3f}), comm={commission:.2f}")
            sess._trade_log.append({
                "type": "BUY",
                "date": day,
                "security": security,
                "price": exec_price,
                "amount": rounded,
                "commission": commission,
                "order_id": order_obj.order_id if order_obj else None,
                "partial": is_partial_fill and rounded < requested_amount,
            })

            # ── Trigger user callbacks for order filled (if registered) ───────
            if order_obj:
                trade_info = {
                    "type": "BUY",
                    "price": exec_price,
                    "amount": rounded,
                    "commission": commission,
                    "partial": is_partial_fill and rounded < requested_amount,
                }
                for func in sess._on_order_filled_funcs:
                    try:
                        func(order_obj, sess._context, trade_info)
                    except Exception as e:
                        log.warn(f"on_order_filled callback error: {e}")

        else:
            # Sell
            sell_amount = fill_amount
            if security not in portfolio.positions:
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="no position")
                continue
            pos = portfolio.positions[security]
            # A-share rule: allow selling odd lots (零股) when closing position.
            # If selling entire position, use exact closeable_amount without lot rounding.
            closeable = int(pos.closeable_amount)
            if sell_amount >= closeable:
                sell_amount = closeable  # Allow odd lots when closing
            else:
                sell_amount = min(_round_lot(sell_amount), closeable)

            # B1: Recompute partial-fill flags after lot rounding + closeable cap
            if sell_amount < requested_amount:
                is_partial_fill = True
                remaining_amount = requested_amount - sell_amount

            if sell_amount <= 0:
                if order_obj:
                    order_obj.transition_to(Order.STATUS_CANCELLED, reason="sub-lot")
                    print(f"[EasyQuant] Order {order_obj.order_id} cancelled: sell amount rounds to 0 lots (sell_amount={sell_amount})")
                log.warn(f"fill_pending SELL {security}: closeable_amount=0 (T+1 or no position)")
                continue

            is_etf_sec = _is_etf(_bare_code(security))
            commission = round(cost_cfg.calc_close_cost(exec_price, sell_amount, is_etf=is_etf_sec,
                                                  trade_date=day), 2)
            net = round(exec_price * sell_amount - commission, 2)

            portfolio.available_cash = round(portfolio.available_cash + net, 2)
            pos.amount -= sell_amount
            pos.closeable_amount = max(0, pos.closeable_amount - sell_amount)
            pos.update(exec_price)
            budget_state["used"][volume_key] = used_volume + sell_amount

            if pos.amount <= 0:
                del portfolio.positions[security]

            # ── Update Order status for partial/full fill ───────────────────────
            if order_obj:
                if is_partial_fill and sell_amount < requested_amount:
                    order_obj.add_partial_fill(sell_amount, exec_price, datetime.datetime.now())
                    log.info(f"PARTIAL FILL SELL {security}: {sell_amount}/{requested_amount} @ {exec_price:.3f} "
                             f"(open={base_price:.3f}), comm={commission:.2f}, remaining={remaining_amount}")
                else:
                    order_obj.add_partial_fill(sell_amount, exec_price, datetime.datetime.now())
                    order_obj.transition_to(Order.STATUS_FILLED)

            log.info(f"FILL SELL {security}: {sell_amount} @ {exec_price:.3f} "
                     f"(open={base_price:.3f}), comm={commission:.2f}")
            sess._trade_log.append({
                "type": "SELL",
                "date": day,
                "security": security,
                "price": exec_price,
                "amount": sell_amount,
                "commission": commission,
                "order_id": order_obj.order_id if order_obj else None,
                "partial": is_partial_fill and sell_amount < requested_amount,
            })

            # ── Trigger user callbacks for order filled (if registered) ───────
            if order_obj:
                trade_info = {
                    "type": "SELL",
                    "price": exec_price,
                    "amount": sell_amount,
                    "commission": commission,
                    "partial": is_partial_fill and sell_amount < requested_amount,
                }
                for func in sess._on_order_filled_funcs:
                    try:
                        func(order_obj, sess._context, trade_info)
                    except Exception as e:
                        log.warn(f"on_order_filled callback error: {e}")

        # ── Keep remaining amount in pending queue for partial fills ───────────
        if is_partial_fill and remaining_amount > 0 and order_obj:
            # Create a new order request for remaining amount
            remaining_req = {
                "action": action,
                "security": security,
                "order_obj": order_obj,  # Same Order object tracking partial fills
            }
            if action == "ORDER":
                remaining_req["amount"] = remaining_amount if is_buy else -remaining_amount
            elif action == "ORDER_TARGET":
                # For target orders, keep the original target — the engine
                # recomputes delta = target - current_position on the next bar,
                # so subtracting the filled amount would undershoot the target.
                remaining_req["target_amount"] = order_req["target_amount"]
            elif action == "ORDER_VALUE":
                # For value orders, adjust the value based on fill
                fill_value = (rounded if is_buy else sell_amount) * exec_price
                remaining_req["value"] = order_req["value"] - fill_value if is_buy else order_req["value"] + fill_value
            elif action == "ORDER_TARGET_VALUE":
                # For target value, keep the original target (will be recomputed)
                remaining_req["target_value"] = order_req["target_value"]

            still_pending.append(remaining_req)
            log.info(f"Order {order_obj.order_id} partially filled, {remaining_amount} shares remaining in queue")

    # ── Re-add partially filled orders to pending queue ────────────────────────
    sess._pending_orders.extend(still_pending)


def _last_bar_date(preloaded, security) -> Optional[datetime.date]:
    """Return the last date with a bar for *security* (cached per session).

    The preloaded panel is immutable for the duration of a backtest, so the
    per-security series end is computed once and memoised in
    ``session._options['_series_last_bar']``.
    """
    sess = st.get_session()
    cache = sess._options.setdefault("_series_last_bar", {})
    bare = _bare_code(security)
    if security in cache:
        return cache[security]
    result = None
    bar_cache = getattr(preloaded, "_bar_cache", None) or {}
    for sec in (security, bare):
        sec_dict = bar_cache.get(sec)
        if not sec_dict:
            continue
        try:
            last = max(pd.Timestamp(k) for k in sec_dict.keys())
        except (TypeError, ValueError):
            continue
        if result is None or last > result:
            result = last
    result_date = result.date() if result is not None else None
    cache[security] = result_date
    return result_date


def _handle_delisted_positions(sess: BacktestSession, day: datetime.date,
                                day_pos: dict, trading_days: list) -> None:
    """Force-liquidate positions whose data series has ended (delisting rule).

    Semantics (declared behaviour):
      - A security that stops trading mid-backtest is first treated as
        *suspended*: it stays in the portfolio, valued at its last traded
        close (``Position.update`` fallback), and orders against it are
        cancelled day-by-day with a recorded reason.
      - Once no bar has appeared for more than ``delist_gap_days`` exchange
        trading days (default ``DEFAULT_DELIST_GAP_DAYS`` = 30), the security
        is treated as *delisted* and the position is force-liquidated at the
        last available close, less ``delisted_liquidation_haircut``
        (default 0.0; set to 1.0 to model delisting-to-zero).  Sale costs
        follow the configured OrderCost.  The liquidation is logged loudly
        and recorded in the trade log as ``DELIST_LIQUIDATE``.

    Rationale: post-2019 exchange rules cap most suspensions at ~25 trading
    days, so a longer unbroken gap almost always means the listing (and the
    data series) has ended.  This is a documented heuristic — OHLCV alone
    cannot distinguish a genuine multi-month suspension from a delisting.

    Options (set_option):
      - ``delisted_position_handling``: "liquidate" (default) or "keep"
        (legacy behaviour: hold at last price forever).
      - ``delist_gap_days``: trading-day gap before liquidation (<=0 disables).
      - ``delisted_liquidation_haircut``: fraction of last close deducted
        from liquidation proceeds (0.0 = full last close).
    """
    if sess._options.get("delisted_position_handling", "liquidate") != "liquidate":
        return
    gap_days = sess._options.get("delist_gap_days", DEFAULT_DELIST_GAP_DAYS)
    if gap_days is None or gap_days <= 0:
        return
    haircut = float(sess._options.get("delisted_liquidation_haircut", 0.0))
    haircut = min(max(haircut, 0.0), 1.0)

    portfolio = sess._context.portfolio
    if not portfolio.positions:
        return
    preloaded = _get_preloaded()
    if preloaded is None:
        return

    done = sess._options.setdefault("_delisted_liquidated", set())
    current_idx = day_pos.get(day)
    if current_idx is None:
        return

    from eqlib.objects import OrderCost
    cost_cfg: OrderCost = sess._order_cost or OrderCost()

    for security in list(portfolio.positions):
        if security in done:
            continue
        pos = portfolio.positions[security]
        if pos.amount <= 0:
            continue
        last_date = _last_bar_date(preloaded, security)
        if last_date is None:
            continue
        # Trading days elapsed since the last bar.  The last bar date is
        # normally itself an exchange trading day; use the calendar position
        # when present, else count from the first calendar day after it.
        last_idx = day_pos.get(last_date)
        if last_idx is None:
            last_idx = -1
            for i, d in enumerate(trading_days):
                if d <= last_date:
                    last_idx = i
                else:
                    break
        if current_idx - last_idx <= gap_days:
            continue

        # ── Force liquidation at the last available close ─────────────────
        price = _get_price_fast(security, last_date)
        if not price or price <= 0:
            price = pos.avg_cost if pos.avg_cost > 0 else 0.0
        exec_price = round(price * (1.0 - haircut), 4)
        amount = pos.amount
        proceeds = round(exec_price * amount, 2)
        commission = round(
            cost_cfg.calc_close_cost(exec_price, amount, trade_date=day), 2
        ) if exec_price > 0 else 0.0
        net = round(proceeds - commission, 2)
        portfolio.available_cash = round(portfolio.available_cash + net, 2)
        del portfolio.positions[security]
        done.add(security)
        log.warn(
            f"DELISTING {security}: no bar for {current_idx - last_idx} trading days "
            f"(last bar {last_date}); force-liquidated {amount} shares @ {exec_price:.3f} "
            f"(last close {price:.3f}, haircut={haircut:.0%}), net={net:.2f} on {day}"
        )
        sess._trade_log.append({
            "type": "DELIST_LIQUIDATE",
            "date": day,
            "security": security,
            "price": exec_price,
            "amount": amount,
            "commission": commission,
            "order_id": None,
            "partial": False,
            "reason": f"no bar for {current_idx - last_idx} trading days (last bar {last_date})",
        })
        # Cancel any residual pending orders for the delisted security: no
        # future fills are possible, and leaving them queued would spam
        # per-day cancellation attempts.
        kept = []
        for req in sess._pending_orders:
            req_sec = req.get("security")
            obj = req.get("order_obj")
            if req_sec and _bare_code(req_sec) == _bare_code(security):
                if obj is not None and obj.status not in (
                    obj.STATUS_FILLED, obj.STATUS_CANCELLED,
                    obj.STATUS_EXPIRED, obj.STATUS_REJECTED,
                ):
                    try:
                        obj.transition_to(obj.STATUS_CANCELLED, reason="delisted")
                    except ValueError:
                        pass
                    sess._order_timestamps.pop(obj.order_id, None)
                continue
            kept.append(req)
        sess._pending_orders[:] = kept


def _round_lot(amount) -> int:
    """Round down to nearest 100 shares (A-share lot size)."""
    return int(amount // 100) * 100


def run_backtest(initialize_func, start_date, end_date,
                 starting_cash=100000.0, frequency: str = "daily",
                 benchmark: str = "000300.XSHG", securities=None,
                 use_local: bool = False, max_memory_mb: int = 1024,
                 selection_func=None, selection_rebalance: str = "monthly:1",
                 handle_data=None, debug_mode: bool = False):
    """Main backtest runner.

    Parameters:
        initialize_func: user's initialize(context) function
        start_date: backtest start date
        end_date: backtest end date
        starting_cash: initial capital
        frequency: 'daily' or 'minute'
        benchmark: benchmark stock code
        securities: list of stock codes to preload data for
        use_local: if True, load data from local CSV files first.
        max_memory_mb: memory limit in MB for in-memory dict caches.
        selection_func: optional callable taking (context) and returning
            a list of selected security codes.  Runs periodically on
            rebalance days (see selection_rebalance).
        selection_rebalance: when to run selection_func.  Format:
            - "monthly:N" — Nth day of month (1-31), default "monthly:1"
            - "weekly:N" — Nth weekday (0=Mon, 4=Fri), default "weekly:0"
            - "daily" — every trading day
        handle_data: optional handle_data(context, data) callback.
            Called once per bar during the backtest.
        debug_mode: if True, print extra diagnostic messages to help
            debug why a strategy has no trades, empty data, etc.

    Returns:
        dict with keys: context, trade_log, recorded_values, benchmark, session
    """
    from eqlib.objects import OrderCost

    # ── Normalize date strings to date objects ─────────────────────────────
    if isinstance(start_date, str):
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

    # ── Create a fresh BacktestSession for this run ────────────────────────
    session = BacktestSession()
    _set_session(session)

    try:
        return _run_backtest_core(
            session, initialize_func, start_date, end_date, frequency,
            starting_cash, benchmark, securities, handle_data,
            selection_func, selection_rebalance, use_local, max_memory_mb,
            debug_mode,
        )
    finally:
        _clear_session()


def _run_backtest_core(session, initialize_func, start_date, end_date, frequency,
                       starting_cash, benchmark, securities, handle_data,
                       selection_func, selection_rebalance, use_local, max_memory_mb,
                       debug_mode=False):
    """Core backtest logic, called by run_backtest within a try/finally block."""
    from eqlib.objects import OrderCost
    preloaded = PreloadedData()
    # Attach to session so concurrent threads each have their own PreloadedData.
    # NOTE: do NOT write to any module-level alias — that would break
    # thread-safety.  All code should read via _get_preloaded().
    object.__setattr__(session, '_preloaded', preloaded)

    session._order_cost = OrderCost(
        open_tax=0,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5,
    )
    session._benchmark = benchmark

    # ── Minute mode warning (intraday fill not yet implemented) ────────────
    if frequency == "minute":
        import warnings
        warnings.warn(
            "minute mode currently routes orders to next-day open; "
            "intraday execution is not implemented. "
            "Orders placed during minute bars are buffered and filled at the "
            "next trading day's open price.",
            UserWarning,
            stacklevel=2,
        )

    # ── Create context & call initialize first ──────────────────────────────
    context = Context(start_date, end_date, frequency, starting_cash)
    session._context = context

    import eqlib
    _g = eqlib.g
    for attr in list(_g.__dict__.keys()):
        delattr(_g, attr)
    session._g = GlobalObject()

    initialize_func(context)

    # B2: Register handle_data on the NEW session (not the old one from run_strategy)
    if handle_data is not None:
        session._handle_data_func = handle_data

    # ── Preload OHLCV data (after initialize so we can use context.universe) ─
    _securities = securities or getattr(context, 'universe', None) or []
    if _securities:
        log.step("Preloading market data", status="RUN",
                 securities=len(_securities),
                 source="local" if use_local else "akshare")
        warmup_start = (start_date - datetime.timedelta(days=365)
                        if isinstance(start_date, datetime.date) else start_date)
        preloaded.load(_securities, warmup_start, end_date, adjust="qfq",
                       use_local=use_local, max_memory_mb=max_memory_mb)
        log.step("Market data preloaded", status="OK", securities=len(_securities))

    trading_days = _get_trading_days(start_date, end_date, preloaded)
    if not trading_days:
        log.error("No trading days found")
        return None
    # Exchange calendar is authoritative for this run (see _get_trading_days);
    # keep it on the session for order-timeout day counting and delisting.
    session._options["_exchange_trading_days"] = trading_days
    _trading_day_pos = {d: i for i, d in enumerate(trading_days)}

    # Pick up selection config from session (set via run_selection in initialize)
    # Parameter takes precedence over session-level config
    if selection_func is None:
        selection_func = getattr(session, '_selection_func', None)
    if selection_rebalance == "monthly:1":
        sess_rebalance = getattr(session, '_selection_rebalance', None)
        if sess_rebalance is not None:
            selection_rebalance = sess_rebalance

    total_days = len(trading_days)
    progress_step = max(1, total_days // 10)

    log.section("Backtest started",
                start=start_date, end=end_date, trading_days=total_days,
                cash=f"{starting_cash:,.0f}", benchmark=session._benchmark)
    log.step("Strategy initialized", status="OK",
             scheduled=len(session._scheduled_funcs),
             before_hooks=len(session._before_trading_start_funcs),
             after_hooks=len(session._after_trading_end_funcs),
             has_handle_data=session._handle_data_func is not None,
             selection=selection_func is not None)

    # ── Debug mode: early diagnostics ───────────────────────────────────────
    if debug_mode:
        if not session._scheduled_funcs and session._handle_data_func is None:
            log.warn("[debug_mode] No callbacks registered: strategy will not trade. "
                     "Call run_daily(), run_weekly(), run_monthly() or pass handle_data=.")
        if not getattr(context, 'universe', None):
            log.warn("[debug_mode] context.universe is empty. "
                     "Set context.universe = [...] in initialize() so data can be preloaded.")

    # ── Main trading loop ──────────────────────────────────────────────────
    for idx, day in enumerate(trading_days, start=1):
        context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))

        # ── T+1 unlock: restore closeable_amount for yesterday's buys ──────
        _t1_unlock(session)

        # ── Fill pending orders from previous day at today's open ──────────
        _fill_pending_orders(session, day)

        # ── Delisting rule: force-liquidate positions whose data series ───
        # ended more than `delist_gap_days` trading days ago (see docstring).
        _handle_delisted_positions(session, day, _trading_day_pos, trading_days)

        # ── Portfolio pre-update with open prices (item 17) ────────────────
        open_prices = {}
        for sec in context.portfolio.positions:
            op = _get_open_fast(sec, day)
            open_prices[sec] = op
        context.portfolio._sync_total_value(open_prices)

        data = _LazyData(context)

        # ── Stock selection: run on rebalance days (item 22) ──────────────
        if selection_func is not None:
            if _should_run_selection(selection_rebalance, day):
                try:
                    selected = selection_func(context)
                    if selected:
                        context.universe = selected
                        log.step("Stock selection updated", status="OK",
                                 date=day.isoformat(), selected=len(selected))
                except Exception as e:
                    log.warn(f"Stock selection failed on {day}: {e}")

        # ── Before-trading-start callbacks ─────────────────────────────────
        for func in session._before_trading_start_funcs:
            func(context, data)

        # ── Frequency-specific bar iteration ──────────────────────────────
        if frequency == "minute":
            _run_minute_bars(context, session, day, data)
        else:
            # Daily mode: run scheduled functions + handle_data
            for sched in session._scheduled_funcs:
                if _should_run_schedule(sched, day):
                    t = _get_sched_time(sched)
                    func = _get_sched_func(sched)
                    if t == "every_bar":
                        func(context)
                    else:
                        hour, minute = map(int, t.split(":"))
                        context.current_dt = datetime.datetime.combine(
                            day, datetime.time(hour, minute))
                        func(context)
                        context.current_dt = datetime.datetime.combine(
                            day, datetime.time(9, 30))

            if session._handle_data_func is not None:
                session._handle_data_func(context, data)

        # ── Close prices for end-of-day portfolio mark-to-market ──────────
        close_prices = {}
        for sec in context.portfolio.positions:
            price = _get_price_fast(sec, day)
            close_prices[sec] = price
        context.portfolio._sync_total_value(close_prices)

        # ── Record daily snapshot ──────────────────────────────────────────
        day_entry = session._recorded_values.get(day, {"date": day})
        day_entry["total_value"] = context.portfolio.total_value
        day_entry["cash"] = context.portfolio.available_cash
        session._recorded_values[day] = day_entry

        # ── After-trading-end callbacks ────────────────────────────────────
        context.current_dt = datetime.datetime.combine(day, datetime.time(15, 0))
        for func in session._after_trading_end_funcs:
            func(context, data)
        context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))
        context.previous_date = day

        if idx == 1 or idx % progress_step == 0 or idx == total_days:
            log.progress(idx, total_days, label="Backtest progress",
                         date=day.isoformat(),
                         positions=len(context.portfolio.positions),
                         total_value=context.portfolio.total_value,
                         cash=context.portfolio.available_cash)

    log.section("Backtest finished",
                final_value=f"{context.portfolio.total_value:,.2f}",
                trades=len(session._trade_log),
                records=len(session._recorded_values))

    # ── Fetch benchmark OHLCV for reporting ────────────────────────────────
    benchmark_values = []
    try:
        from eqlib.data import fetch_stock_data
        bench_df = fetch_stock_data(session._benchmark, start_date, end_date)
        if bench_df.empty:
            # Fallback to local data if network fetch fails
            try:
                from eqlib.data_cache import load_stock_local
                from eqlib._state import _unrestricted_fetch
                # Engine-internal full-range read: exempt from the
                # in-session PIT truncation load_stock_local applies to
                # user-facing reads.
                with _unrestricted_fetch():
                    bench_df = load_stock_local(session._benchmark,
                                                start_date.strftime("%Y-%m-%d")[:10],
                                                end_date.strftime("%Y-%m-%d")[:10], "qfq")
            except Exception:
                bench_df = None
        if bench_df is not None and not bench_df.empty and "close" in bench_df.columns:
            benchmark_values = [
                {"date": str(d.date()) if hasattr(d, 'date') else str(d), "value": float(row["close"])}
                for d, row in bench_df.iterrows()
            ]
    except Exception:
        pass

    result = {
        "context": context,
        "trade_log": session._trade_log,
        "recorded_values": sorted(
            session._recorded_values.values(), key=lambda x: x["date"]
        ),
        "benchmark": session._benchmark,
        "benchmark_values": benchmark_values,
        "session": session,
        "ohlcv_data": {},
        "data_diagnostics": dict(getattr(preloaded, "load_stats", {}) or {}),
    }

    # Export preloaded OHLCV data for report generation
    if preloaded.panel is not None and not preloaded.panel.empty:
        for sec in _securities:
            if sec in preloaded.panel.columns.get_level_values(0).unique():
                sec_df = preloaded.panel[sec]
                if not sec_df.empty:
                    result["ohlcv_data"][sec] = sec_df

    # Pre-align CSI300 + SSE cumulative % for HTML charts (same dates as recorded_values)
    try:
        from eqlib.report import attach_chart_dual_indices
        attach_chart_dual_indices(result)
    except Exception:
        pass

    # ── Debug mode: post-backtest diagnostics ─────────────────────────────────
    if debug_mode and not session._trade_log:
        log.warn("[debug_mode] Backtest completed with ZERO trades. Common causes:\n"
                 "  1. No callbacks registered (run_daily/run_weekly/run_monthly or handle_data)\n"
                 "  2. Strategy conditions never met (e.g., price never crossed MA)\n"
                 "  3. Data unavailable for requested securities\n"
                 "  4. Orders cancelled (insufficient cash, price limits, etc.)\n"
                 "  5. context.universe not set, so no data was preloaded\n"
                 "  Tip: Set debug_mode=True and check logs for 'order buffered' or 'cancelled' messages.")

    return result


def _run_minute_bars(context: Context, session: BacktestSession,
                     day: datetime.date, data):
    """Iterate over intraday minute bars for a single trading day (item 18).

    Fetches minute-level data for each security in the universe and runs
    ``handle_data`` once per bar.  Only 1-minute bars are used.
    """
    from eqlib.data import fetch_minute_data

    securities = context.universe or []
    if not securities:
        # Fall back to any held positions
        securities = list(context.portfolio.positions.keys())

    minute_frames = {}
    for sec in securities:
        mdf = fetch_minute_data(sec, period="1m",
                                start_date=day, end_date=day)
        if not mdf.empty:
            minute_frames[sec] = mdf

    if not minute_frames:
        # No minute data for this day — fall back to daily handle_data
        if session._handle_data_func is not None:
            session._handle_data_func(context, data)
        return

    # Collect all unique minute timestamps across all securities
    all_times = sorted(
        set(ts for df in minute_frames.values() for ts in df.index)
    )

    for ts in all_times:
        context.current_dt = ts if isinstance(ts, datetime.datetime) else (
            datetime.datetime.combine(day, ts.time()) if hasattr(ts, 'time') else
            datetime.datetime.combine(day, datetime.time(9, 30))
        )

        # Build a bar dict for this timestamp for each security
        minute_data: dict = {}
        for sec, mdf in minute_frames.items():
            if ts in mdf.index:
                row = mdf.loc[ts]
                minute_data[sec] = SecurityBar({
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "money": float(row.get("money", 0)),
                })

        if session._handle_data_func is not None:
            session._handle_data_func(context, minute_data)

        # Run scheduled funcs that match this timestamp
        for sched in session._scheduled_funcs:
            if _should_run_schedule(sched, day):
                t = _get_sched_time(sched)
                func = _get_sched_func(sched)
                if t == "every_bar":
                    func(context)
                else:
                    # A4: Handle specific-time scheduled functions in minute mode
                    try:
                        hour, minute = map(int, t.split(":"))
                    except (ValueError, AttributeError):
                        continue
                    bar_time = context.current_dt
                    if (hasattr(bar_time, 'hour') and
                            bar_time.hour == hour and bar_time.minute == minute):
                        func(context)


def _get_trading_days(start, end, preloaded: PreloadedData = None) -> list[datetime.date]:
    """Get list of trading days between start and end.

    The EXCHANGE CALENDAR is authoritative: it is deliberately independent of
    the universe's data coverage.  Deriving the calendar from market data
    (the previous behaviour) made suspension days silently vanish from the
    schedule — the same suspension then produced "order deferred", "order
    cancelled", or "day missing entirely" depending on universe composition,
    and a delisted security truncated the whole backtest early.

    With the exchange calendar as the backbone:
      - Suspension days stay in the calendar; orders targeting a security
        with no bar that day are cancelled the same day with a recorded
        reason ("no price data" for a missing bar, "suspended" for a
        zero-volume bar).
      - A security whose data ends early no longer truncates the run; see
        :func:`_handle_delisted_positions` for the delisting rule.

    Source priority:
    1. The bundled exchange calendar (``eqlib/static/ashare_trading_days.json``,
       coverage 2020-01-01..2026-12-31) — deterministic and offline.
    2. ``ak.tool_trade_date_hist_sina()`` — the canonical A-share trading
       calendar from akshare, for ranges outside the bundled coverage.
    3. Inferred calendar via ``data._get_trading_days_range``
       (chinese_calendar workday tiers + bundled holiday rules).

    ``preloaded`` is accepted for backward compatibility and ignored.
    """
    start_d = _as_date(start)
    end_d = _as_date(end)

    # 1. Bundled exchange calendar (offline, deterministic).
    try:
        from eqlib.data import _bundled_ashare_trading_days
        days = _bundled_ashare_trading_days(start_d, end_d)
        if days:
            return list(days)
    except Exception:
        pass

    # 2. akshare canonical calendar (network) for out-of-coverage ranges.
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if not df.empty:
            col = df.columns[0]
            dates = pd.to_datetime(df[col])
            result = [
                d.date() for d in dates
                if start_d <= d.date() <= end_d
            ]
            if result:
                return sorted(result)
    except Exception:
        pass

    # 3. Inferred calendar (chinese_calendar tiers + holiday rules).
    return list(_get_trading_days_range(start_d, end_d))


# ── Paper trading ──────────────────────────────────────────────────────────────

def _paper_is_trading_day(day: datetime.date) -> bool:
    """Best-effort trading-day check for paper trading.

    Uses the akshare exchange calendar with the bundled calendar as offline
    fallback.  If neither can answer (e.g. bundled coverage expired), fail
    open with a loud warning — blocking trading on a stale calendar is worse
    than processing a non-trading day.
    """
    from eqlib.data import get_trade_days
    try:
        days = get_trade_days(start_date=day, end_date=day, strict=True)
    except Exception:
        log.warn(f"paper: trading-day check unavailable for {day}; assuming trading day")
        return True
    return day in days


def _paper_market_phase(now: datetime.datetime) -> str:
    """Classify *now* into the A-share paper-trading session phases.

    Returns one of:
      ``"closed"``     — before 09:15 (no fills, no callbacks, no fetch)
      ``"auction"``    — 09:15–09:25 open call auction (callbacks may run and
                         queue orders, but nothing is matched yet)
      ``"continuous"`` — 09:25–15:00 continuous trading (fills allowed)
      ``"after"``      — 15:00 and later (after_trading_end hooks fire here)
    """
    t = now.time()
    if t < PAPER_SESSION_START:
        return "closed"
    if t < PAPER_FIRST_FILL_TIME:
        return "auction"
    if t < PAPER_SESSION_END:
        return "continuous"
    return "after"


def _paper_run_callback(session: BacktestSession, func, *args,
                        label: str = "callback") -> bool:
    """Run a user callback in paper mode with a consecutive-failure breaker.

    A user exception is logged and counted; after
    ``PAPER_CALLBACK_MAX_FAILURES`` consecutive failures the callback is
    disabled for the rest of the run (circuit breaker) instead of killing
    the paper-trading process.  Returns True when the callback ran cleanly.
    """
    failures = session._options.setdefault("_paper_cb_failures", {})
    disabled = session._options.setdefault("_paper_cb_disabled", set())
    key = id(func)
    if key in disabled:
        return False
    try:
        func(*args)
    except Exception as exc:
        count = failures.get(key, 0) + 1
        failures[key] = count
        if count >= PAPER_CALLBACK_MAX_FAILURES:
            disabled.add(key)
            log.error(
                f"paper: {label} {getattr(func, '__name__', func)} failed {count} "
                f"times in a row — disabling it for the rest of the run. "
                f"Last error: {exc}"
            )
        else:
            log.warn(
                f"paper: {label} {getattr(func, '__name__', func)} raised "
                f"({count}/{PAPER_CALLBACK_MAX_FAILURES}): {exc}"
            )
        return False
    failures.pop(key, None)
    return True


def run_paper_trade(initialize_func, starting_cash=100000.0,
                    benchmark: str = "000300.XSHG", interval: int = 60):
    """Run a strategy in paper trading mode with live market data.

    Session semantics (declared behaviour):
      - Nothing is matched outside the 09:15–15:00 session window
        (``PAPER_SESSION_START``/``PAPER_SESSION_END``); the loop idles.
      - The first fill of a trading day waits for the open call auction to
        complete (``PAPER_FIRST_FILL_TIME``, 09:25) so fills use real traded
        prices rather than stale quotes.
      - ``before_trading_start`` hooks run before any scheduled function or
        ``handle_data`` of the day — including when the loop first wakes
        during the call auction (09:15–09:25), matching backtest ordering.
        Orders queued during the auction are matched the next trading day
        under the unified T→T+1 model (they do not participate in the
        09:25 auction match).
      - When no live price is available for a security the order stays
        pending (it is NOT cancelled); the order timeout governs expiry.
      - User callbacks (scheduled funcs / handle_data) are protected by a
        circuit breaker: after several consecutive failures the callback is
        disabled with an error log instead of killing the process.
    """
    from eqlib.objects import OrderCost

    session = BacktestSession()
    _set_session(session)
    object.__setattr__(session, '_preloaded', _preloaded_fallback)

    session._order_cost = OrderCost(
        open_tax=0,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5,
    )
    session._benchmark = benchmark
    session._options["_is_paper_trading"] = True

    now = datetime.datetime.now()
    context = Context(now.date(), now.date() + datetime.timedelta(days=365),
                      "daily", starting_cash)
    session._context = context

    import eqlib
    _g = eqlib.g
    for attr in list(_g.__dict__.keys()):
        delattr(_g, attr)
    session._g = GlobalObject()

    initialize_func(context)
    log.info(f"Paper trading started: capital={starting_cash:,.0f}, interval={interval}s")

    spot_cache: dict = {}
    prev_day: Optional[datetime.date] = None
    _warmup_done: bool = False  # True after the first iteration is complete
    _deferred_fill_day: Optional[datetime.date] = None  # day whose first fill waits for the auction to end
    _paper_day_checked: Optional[datetime.date] = None
    _paper_day_is_trading: bool = True
    try:
        while True:
            context.current_dt = datetime.datetime.now()

            # Non-trading days (weekends/holidays): no fills, no scheduled
            # funcs, no handle_data, no price fetch — just idle.
            today = context.current_dt.date()
            if today != _paper_day_checked:
                _paper_day_is_trading = _paper_is_trading_day(today)
                _paper_day_checked = today
                if not _paper_day_is_trading:
                    log.info(f"paper: {today} is not a trading day — idling")
            if not _paper_day_is_trading:
                time.sleep(max(interval, 300))
                continue

            # ── Market-hours gate (INFRA-P0-01) ──────────────────────────
            # No matching, callbacks, or price fetches outside the session
            # window.  Without this, the first poll after midnight matched
            # yesterday's orders against stale/empty quotes.
            phase = _paper_market_phase(context.current_dt)
            if phase in ("closed", "after"):
                # Fire after_trading_end hooks once, just after the close.
                if (phase == "after" and prev_day == today
                        and not session._after_trading_end_done):
                    context.current_dt = datetime.datetime.combine(
                        today, datetime.time(15, 0))
                    for func in session._after_trading_end_funcs:
                        _paper_run_callback(
                            session, func, context, _LazyData(context),
                            label="after_trading_end")
                    session._after_trading_end_done = True
                time.sleep(max(interval, 60))
                continue

            # Restrict live price fetch to only the securities in the user's
            # universe and current positions — avoids downloading all 5000+
            # A-share quotes for a small strategy.
            universe_bare: Optional[set] = None
            universe_all = list(context.universe or []) + list(context.portfolio.positions.keys())
            if universe_all:
                universe_bare = {
                    _bare_code(s) for s in universe_all
                }
            spot_cache = _fetch_live_prices(spot_cache, securities=universe_bare)

            today = context.current_dt.date()

            # Build a price map (bare code → price) from spot_cache for order fills.
            # akshare returns bare codes (e.g. "601390"); securities in pending orders
            # may have exchange suffixes, so _fill_pending_orders will strip them.
            live_prices = {k: v for k, v in spot_cache.items() if k != "_ts"}

            # On a new calendar day, unlock T+1 shares and fill yesterday's orders.
            # Skip the fill on the very first iteration — the strategy hasn't
            # produced any orders yet, and pre-filling an empty queue is
            # harmless now but would incorrectly fill persisted orders after a
            # restart (e.g., reloading yesterday's unfilled orders from SQLite).
            # The day-rollover block also runs during the open call auction
            # (09:15–09:25) so before_trading_start hooks always precede the
            # day's first scheduled function / handle_data — matching the
            # backtest loop's ordering.  Order matching still waits for the
            # continuous phase: the day's first fill happens once the auction
            # completes (09:25).
            if today != prev_day and phase in ("auction", "continuous"):
                if _warmup_done:
                    if phase == "continuous":
                        _t1_unlock(session)
                        _fill_pending_orders(session, today, exec_prices=live_prices)
                    else:
                        # Auction phase: hooks run now but nothing is matched
                        # yet — defer the day's first fill (and T+1 unlock)
                        # to the first continuous iteration.
                        _deferred_fill_day = today
                    # Call before_trading_start hooks at market open (09:30)
                    real_now = context.current_dt
                    context.current_dt = datetime.datetime.combine(today, datetime.time(9, 30))
                    for func in session._before_trading_start_funcs:
                        _paper_run_callback(
                            session, func, context, _LazyData(context),
                            label="before_trading_start")
                    # Restore the wall clock: the ±60s scheduled-time match
                    # below must compare against *now*, not the 09:30 hook
                    # timestamp — otherwise a day whose first in-market
                    # iteration is, say, 14:50 would wrongly fire the 09:30
                    # schedule (and skip the 14:50 one) on that iteration.
                    context.current_dt = real_now
                else:
                    _warmup_done = True
                # Reset after_trading_end flag for the new day
                session._after_trading_end_done = False
                prev_day = today

            # A day that rolled over during the call auction still needs its
            # first fill once continuous trading begins.
            if phase == "continuous" and _deferred_fill_day == today:
                _t1_unlock(session)
                _fill_pending_orders(session, today, exec_prices=live_prices)
                _deferred_fill_day = None

            prices = {sec: _resolve_live_price(spot_cache, sec, None)
                      for sec, pos in context.portfolio.positions.items()}

            # Run scheduled functions with precise time check
            for sched in session._scheduled_funcs:
                if _should_run_schedule(sched, today):
                    t = _get_sched_time(sched)
                    func = _get_sched_func(sched)
                    if t == "every_bar":
                        _paper_run_callback(session, func, context,
                                            label="scheduled(every_bar)")
                    else:
                        # Parse scheduled time and check if within ±60 seconds.
                        # Run at most once per (func, time) per day: the
                        # polling loop can hit the ±60s window 2-3 times.
                        sched_key = (id(func), t)
                        if session._sched_last_run.get(sched_key) == today:
                            continue
                        try:
                            hour, minute = map(int, t.split(":"))
                        except (ValueError, AttributeError, TypeError):
                            # Unparseable schedule time: run once today with a
                            # loud warning instead of silently retrying every
                            # iteration (previously this branch also re-ran
                            # user callbacks that had raised — INFRA-P1-03).
                            session._sched_last_run[sched_key] = today
                            log.warn(f"paper: unparseable schedule time {t!r} for "
                                     f"{getattr(func, '__name__', func)} — running once today")
                            _paper_run_callback(session, func, context,
                                                label="scheduled")
                            continue
                        scheduled_dt = datetime.datetime.combine(today, datetime.time(hour, minute))
                        current_dt = context.current_dt
                        if abs((current_dt - scheduled_dt).total_seconds()) <= 60:
                            session._sched_last_run[sched_key] = today
                            # User-callback exceptions are contained by the
                            # circuit breaker; they never reach the main loop.
                            _paper_run_callback(session, func, context,
                                                label="scheduled")

            if session._handle_data_func is not None:
                _paper_run_callback(session, session._handle_data_func,
                                    context, _LazyData(context),
                                    label="handle_data")

            context.portfolio._sync_total_value(prices)
            total = context.portfolio.total_value
            pnl = total - starting_cash
            pnl_pct = (pnl / starting_cash * 100) if starting_cash > 0 else 0.0
            log.info(f"[{context.current_dt:%H:%M:%S}] total={total:,.2f} "
                     f"PnL={pnl:+,.2f} ({pnl_pct:+.2f}%)")

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Paper trading stopped.")
    finally:
        _clear_session()

    return {
        "context": context,
        "trade_log": session._trade_log,
        "recorded_values": sorted(session._recorded_values.values(),
                                  key=lambda x: x["date"]),
        "session": session,
    }


def _resolve_live_price(spot_cache: dict, security: str, default: Optional[float]) -> Optional[float]:
    """Look up a live spot price from spot_cache for a security.

    akshare returns bare codes (e.g. "601390").  Securities in the portfolio
    may carry exchange suffixes (e.g. "601390.XSHG").  This helper tries
    both forms and falls back to ``default`` if neither is found.
    """
    price = spot_cache.get(security)
    if price is None:
        bare = _bare_code(security)
        price = spot_cache.get(bare)
    return price if price is not None else default


def _fetch_live_prices(cache: dict, max_age: int = 30,
                       securities: Optional[set] = None) -> dict:
    """Fetch A-share spot quotes and update the cache.

    For small universes (< 100 securities) fetches individual daily bars
    via ``ak.stock_zh_a_hist`` to avoid downloading the full A-share list
    (~5000 rows, ~1 MB).  For larger universes falls back to the bulk
    endpoint ``ak.stock_zh_a_spot_em``.

    Parameters:
        cache: previous cache dict (returned unchanged if still fresh).
        max_age: cache TTL in seconds (default 30).
        securities: optional set of bare security codes (e.g. ``{"601390"}``).
            When provided only those codes are retained in the cache,
            avoiding storing thousands of irrelevant quotes for a small
            universe.  If ``None``, the full A-share universe is cached.
    """
    import time as _time
    if _time.time() - cache.get("_ts", 0) < max_age:
        return cache
    try:
        import akshare as ak
        import datetime
        new_cache = {"_ts": _time.time()}

        if securities and len(securities) < 100:
            # MED-24: small universe — fetch individual daily bars to avoid
            # downloading the full 5000+ row A-share list.
            today = datetime.date.today().strftime("%Y%m%d")
            for code in securities:
                if code in cache and cache.get("_ts", 0) > _time.time() - max_age:
                    new_cache[code] = cache[code]
                    continue
                try:
                    # Fetch latest 5 days of daily data; use last bar's close
                    df = ak.stock_zh_a_hist(
                        symbol=code, period="daily",
                        start_date=today, end_date=today,
                        adjust=""
                    )
                    if df is not None and not df.empty:
                        price = float(df.iloc[-1]["收盘"])
                        new_cache[code] = price
                except Exception:
                    pass
            return new_cache

        # Large universe or no filter — use bulk endpoint
        df = ak.stock_zh_a_spot_em()
        if df.empty:
            return cache
        for _, row in df.iterrows():
            code = row.get("代码")
            price = row.get("最新价")
            if code and price is not None:
                if securities is not None and code not in securities:
                    continue
                try:
                    new_cache[code] = float(price)
                except (ValueError, TypeError):
                    pass
        return new_cache
    except Exception:
        return cache


# ── Convenience getters ────────────────────────────────────────────────────────

def get_context():
    return st.get_session()._context


def get_g():
    return st.get_session()._g


def get_trade_log():
    return st.get_session()._trade_log


def get_recorded_values():
    return sorted(st.get_session()._recorded_values.values(), key=lambda x: x["date"])


def context_universe():
    ctx = st.get_session()._context
    return ctx.universe if ctx else []
