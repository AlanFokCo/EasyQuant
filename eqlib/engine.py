"""Backtest engine: drives the strategy lifecycle
(initialize -> handle_data / run_daily -> report)."""

import datetime
import time
import pandas as pd
from typing import Optional
from eqlib.context import Context
from eqlib.data import fetch_stock_data, get_price, _get_trading_days_range
from eqlib.data_cache import PreloadedData
from eqlib.objects import GlobalObject
import eqlib._state as st
from eqlib._state import BacktestSession, _set_session, _clear_session, reset_all
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
        bar = _get_preloaded().get_bar(day, key)
        if bar is not None:
            result = SecurityBar(bar)
            self[key] = result
            return result
        return None


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


def _get_price_limit_ratio(security: str) -> float:
    """Return the daily price-limit ratio (one-sided) for a security.

    Board classification:
        688xxx.XSHG  → STAR Market: ±20 %
        300xxx.XSHE  → ChiNext: ±20 %
        All others   → Main board / SME: ±10 %

    ST stocks have a ±5 % limit but their current ST status is not reliably
    known in the preloaded OHLCV panel, so they are treated as main-board here.
    Users who need precise ST handling should override with ``set_option``.
    """
    bare = security.replace(".XSHG", "").replace(".XSHE", "")
    if bare.startswith("688") or bare.startswith("300"):
        return 0.20
    return 0.10


def _fill_pending_orders(sess: BacktestSession, day: datetime.date,
                         exec_prices: Optional[dict] = None):
    """Fill all pending orders at today's open price.

    Orders buffered during yesterday's strategy execution are executed here,
    eliminating look-ahead bias.  Slippage is applied to each fill.
    After a buy is filled, the new shares are registered as T+1-locked
    (``closeable_amount`` is NOT increased for those shares until tomorrow).

    Parameters:
        sess: the active BacktestSession
        day: the fill date (used for preloaded price lookup)
        exec_prices: optional dict mapping security code (bare or full) to
            execution price.  When provided (e.g. for live/paper trading),
            these prices take precedence over preloaded data.  The suspension
            check is skipped for securities whose price is found in this dict.
    """
    from eqlib.context import Position
    from eqlib.objects import OrderCost
    from eqlib.data import _is_etf

    pending = list(sess._pending_orders)
    sess._pending_orders.clear()

    if not pending:
        return

    slippage = sess._slippage_model
    cost_cfg: OrderCost = sess._order_cost or OrderCost()
    portfolio = sess._context.portfolio

    for order_req in pending:
        security = order_req["security"]
        action = order_req["action"]

        # ── Resolve target amount ──────────────────────────────────────────
        if action == "ORDER":
            delta = order_req["amount"]
        elif action == "ORDER_TARGET":
            current = portfolio.positions[security].amount if security in portfolio.positions else 0
            delta = order_req["target_amount"] - current
        elif action == "ORDER_VALUE":
            open_px = _get_open_fast(security, day)
            if not open_px:
                log.warn(f"fill_pending: no open price for {security} on {day} (ORDER_VALUE skipped)")
                continue
            raw = int(order_req["value"] / open_px)
            delta = (_round_lot(raw) if order_req["value"] > 0 else raw)
            if order_req["value"] < 0:
                delta = -abs(delta)
        elif action == "ORDER_TARGET_VALUE":
            open_px = _get_open_fast(security, day)
            if not open_px:
                log.warn(f"fill_pending: no open price for {security} on {day} (ORDER_TARGET_VALUE skipped)")
                continue
            target_sh = _round_lot(int(order_req["target_value"] / open_px)) if order_req["target_value"] > 0 else 0
            current = portfolio.positions[security].amount if security in portfolio.positions else 0
            delta = target_sh - current
        else:
            continue

        if delta == 0:
            continue

        is_buy = delta > 0

        # ── Resolve execution price ────────────────────────────────────────
        # When exec_prices is provided (paper/live trading), use it first.
        base_price = None
        if exec_prices is not None:
            bare_code = security.replace(".XSHG", "").replace(".XSHE", "")
            base_price = exec_prices.get(security) or exec_prices.get(bare_code)
        if not base_price:
            base_price = _get_open_fast(security, day)
        if not base_price:
            log.warn(f"fill_pending: no open price for {security} on {day} — order skipped")
            continue

        # ── HIGH-13: warn on large price gaps for ORDER_VALUE / ORDER_TARGET_VALUE ──
        # A significant gap between yesterday's close and today's open suggests
        # a limit-hit or suspension scenario; shares-based orders (order())
        # handle this more predictably than value-based ones.
        if exec_prices is None and action in ("ORDER_VALUE", "ORDER_TARGET_VALUE"):
            preloaded = _get_preloaded()
            if preloaded is not None and preloaded._dates is not None:
                prev_day = preloaded.get_prev_trading_day(day)
                if prev_day is not None:
                    prev_close = _get_price_fast(security, prev_day)
                    if prev_close and prev_close > 0:
                        gap_ratio = base_price / prev_close
                        if gap_ratio > 1.1 or gap_ratio < 0.9:
                            log.warn(
                                f"fill_pending {action} {security}: today's open ({base_price:.3f}) "
                                f"has a large gap vs yesterday's close ({prev_close:.3f}, "
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
            continue
        elif vol == 0 and treat_missing_as_suspended:
            log.warn(f"fill_pending: {security} volume=0 on {day} (appears suspended) — order skipped")
            continue

        # ── Price-limit check (optional, A-share circuit breaker) ─────────
        # Enabled via set_option('check_price_limit', True).
        # Buys at limit-up open are typically unfillable; sells at limit-down
        # open are also blocked.  Skip for live/paper trading (exec_prices)
        # where the broker already applies the rule.
        if exec_prices is None and sess._options.get("check_price_limit", False):
            prev_day_date = None
            preloaded = _get_preloaded()
            if preloaded is not None and preloaded._dates is not None:
                prev_day_date = preloaded.get_prev_trading_day(day)
            if prev_day_date is not None:
                prev_close = _get_price_fast(security, prev_day_date)
                if prev_close:
                    ratio = _get_price_limit_ratio(security)
                    limit_up = prev_close * (1 + ratio)
                    limit_down = prev_close * (1 - ratio)
                    # A small tolerance (0.1%) absorbs floating-point rounding
                    # in price data (e.g. adjusted-price inaccuracies) so that
                    # a price of 10.999 is not incorrectly treated as exactly
                    # limit-up (11.000).  The same tolerance is applied to both
                    # sides for symmetry.
                    _LIMIT_TOL = 0.001
                    if is_buy and base_price >= limit_up * (1 - _LIMIT_TOL):
                        log.warn(
                            f"fill_pending BUY {security}: open {base_price:.3f} hit "
                            f"limit-up ({limit_up:.3f}) on {day} — order skipped"
                        )
                        continue
                    if not is_buy and base_price <= limit_down * (1 + _LIMIT_TOL):
                        log.warn(
                            f"fill_pending SELL {security}: open {base_price:.3f} hit "
                            f"limit-down ({limit_down:.3f}) on {day} — order skipped"
                        )
                        continue

        if slippage:
            exec_price = slippage.get_execution_price(
                base_price, abs(int(delta)), is_buy, daily_volume=vol
            )
        else:
            exec_price = base_price

        # ── Execute ────────────────────────────────────────────────────────
        if is_buy:
            rounded = _round_lot(delta)
            if rounded <= 0:
                continue
            commission = cost_cfg.calc_open_cost(exec_price, rounded)
            total_cost = exec_price * rounded + commission

            if total_cost > portfolio.available_cash:
                # HIGH-11: use base_price (before slippage) plus a conservative
                # buffer that covers both maximum expected slippage and commission.
                slippage_max_pct = getattr(sess._slippage_model, "max_pct", _DEFAULT_SLIPPAGE_MAX_PCT) \
                    if sess._slippage_model is not None else 0.0
                commission_rate = cost_cfg.open_tax + cost_cfg.open_commission
                effective_rate = 1.0 + slippage_max_pct + commission_rate
                max_affordable = int(portfolio.available_cash / (base_price * effective_rate) // 100) * 100
                rounded = max_affordable
                if rounded <= 0:
                    log.warn(f"fill_pending BUY {security}: insufficient cash")
                    continue
                commission = cost_cfg.calc_open_cost(exec_price, rounded)
                total_cost = exec_price * rounded + commission
                # Guard against min_commission pushing total_cost over budget
                while total_cost > portfolio.available_cash and rounded > 0:
                    rounded -= 100
                    if rounded <= 0:
                        break
                    commission = cost_cfg.calc_open_cost(exec_price, rounded)
                    total_cost = exec_price * rounded + commission
                if rounded <= 0:
                    log.warn(f"fill_pending BUY {security}: insufficient cash (after min_commission)")
                    continue

            portfolio.available_cash -= total_cost

            if security not in portfolio.positions:
                portfolio.positions[security] = Position(security)

            pos = portfolio.positions[security]
            total_cb = pos.avg_cost * pos.amount + exec_price * rounded
            pos.amount += rounded
            # T+1: newly bought shares are not sellable today
            locked = sess._t1_locked_amounts.get(security, 0) + rounded
            sess._t1_locked_amounts[security] = locked
            pos.closeable_amount = pos.amount - locked

            pos.avg_cost = total_cb / pos.amount if pos.amount > 0 else 0

            log.info(f"FILL BUY {security}: {rounded} @ {exec_price:.3f} "
                     f"(open={base_price:.3f}), comm={commission:.2f}")
            sess._trade_log.append({
                "type": "BUY",
                "date": day,
                "security": security,
                "price": exec_price,
                "amount": rounded,
                "commission": commission,
            })

        else:
            # Sell
            sell_amount = abs(delta)
            if security not in portfolio.positions:
                continue
            pos = portfolio.positions[security]
            sell_amount = min(sell_amount, int(pos.closeable_amount))
            if sell_amount <= 0:
                log.warn(f"fill_pending SELL {security}: closeable_amount=0 (T+1 or no position)")
                continue

            is_etf_sec = _is_etf(security.replace(".XSHG", "").replace(".XSHE", ""))
            commission = cost_cfg.calc_close_cost(exec_price, sell_amount, is_etf=is_etf_sec,
                                                  trade_date=day)
            net = exec_price * sell_amount - commission

            portfolio.available_cash += net
            pos.amount -= sell_amount
            pos.closeable_amount = max(0, pos.closeable_amount - sell_amount)

            if pos.amount <= 0:
                del portfolio.positions[security]

            log.info(f"FILL SELL {security}: {sell_amount} @ {exec_price:.3f} "
                     f"(open={base_price:.3f}), comm={commission:.2f}")
            sess._trade_log.append({
                "type": "SELL",
                "date": day,
                "security": security,
                "price": exec_price,
                "amount": sell_amount,
                "commission": commission,
            })


def _round_lot(amount) -> int:
    """Round down to nearest 100 shares (A-share lot size)."""
    return int(amount // 100) * 100


def run_backtest(initialize_func, start_date, end_date,
                 starting_cash=100000.0, frequency: str = "daily",
                 benchmark: str = "000300.XSHG", securities=None,
                 use_local: bool = False, max_memory_mb: int = 1024,
                 selection_func=None, selection_rebalance: str = "monthly:1"):
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

    preloaded = PreloadedData()
    # Attach to session so concurrent threads each have their own PreloadedData.
    # NOTE: do NOT write to any module-level alias — that would break
    # thread-safety.  All code should read via _get_preloaded().
    object.__setattr__(session, '_preloaded', preloaded)

    session._order_cost = OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
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
        _clear_session()
        return None

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

    # ── Main trading loop ──────────────────────────────────────────────────
    for idx, day in enumerate(trading_days, start=1):
        context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))

        # ── T+1 unlock: restore closeable_amount for yesterday's buys ──────
        _t1_unlock(session)

        # ── Fill pending orders from previous day at today's open ──────────
        _fill_pending_orders(session, day)

        # ── Portfolio pre-update with open prices (item 17) ────────────────
        open_prices = {}
        for sec in context.portfolio.positions:
            op = _get_open_fast(sec, day)
            open_prices[sec] = op if op is not None else context.portfolio.positions[sec].avg_cost
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
            close_prices[sec] = (price if price is not None
                                 else context.portfolio.positions[sec].avg_cost)
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

    _clear_session()
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


def _get_trading_days(start, end, preloaded: PreloadedData = None) -> list[datetime.date]:
    """Get list of trading days between start and end.

    Priority:
    1. Preloaded panel dates (fastest, no network call).
    2. ``ak.tool_trade_date_hist_sina()`` — the canonical A-share trading
       calendar, used by data.py:get_trade_days().  This avoids the previous
       stock-history approach (601390 is listed since 2007, so early dates
       were incomplete; the stock could also be suspended or delisted).
    3. Weekday approximation fallback.
    """
    if preloaded is not None and preloaded._dates is not None and len(preloaded._dates) > 0:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        return sorted(
            (pd.Timestamp(d).date() for d in preloaded._dates
             if start_ts <= pd.Timestamp(d) <= end_ts)
        )

    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if not df.empty:
            col = df.columns[0]
            dates = pd.to_datetime(df[col])
            result = [
                d.date() for d in dates
                if start <= d.date() <= end
            ]
            if result:
                return sorted(result)
    except Exception:
        pass

    # Legacy fallback: fetch from single stock (less reliable)
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="601390", period="daily",
                                start_date=start.strftime("%Y%m%d"),
                                end_date=end.strftime("%Y%m%d"),
                                adjust="qfq")
        if not df.empty:
            df["日期"] = pd.to_datetime(df["日期"])
            return sorted(df["日期"].dt.date.unique().tolist())
    except Exception:
        pass

    return list(_get_trading_days_range(start, end))


# ── Paper trading ──────────────────────────────────────────────────────────────

def run_paper_trade(initialize_func, starting_cash=100000.0,
                    benchmark: str = "000300.XSHG", interval: int = 60):
    """Run a strategy in paper trading mode with live market data."""
    from eqlib.objects import OrderCost

    session = BacktestSession()
    _set_session(session)
    object.__setattr__(session, '_preloaded', _preloaded_fallback)

    session._order_cost = OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    )
    session._benchmark = benchmark

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
    try:
        while True:
            context.current_dt = datetime.datetime.now()

            # Restrict live price fetch to only the securities in the user's
            # universe and current positions — avoids downloading all 5000+
            # A-share quotes for a small strategy.
            universe_bare: Optional[set] = None
            universe_all = list(context.universe or []) + list(context.portfolio.positions.keys())
            if universe_all:
                universe_bare = {
                    s.replace(".XSHG", "").replace(".XSHE", "") for s in universe_all
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
            if today != prev_day:
                if _warmup_done:
                    _t1_unlock(session)
                    _fill_pending_orders(session, today, exec_prices=live_prices)
                else:
                    _warmup_done = True
                prev_day = today

            prices = {sec: _resolve_live_price(spot_cache, sec, pos.avg_cost)
                      for sec, pos in context.portfolio.positions.items()}
            for sched in session._scheduled_funcs:
                if _should_run_schedule(sched, today):
                    t = _get_sched_time(sched)
                    if t == "every_bar":
                        _get_sched_func(sched)(context)

            if session._handle_data_func is not None:
                session._handle_data_func(context, _LazyData(context))

            context.portfolio._sync_total_value(prices)
            total = context.portfolio.total_value
            pnl = total - starting_cash
            pnl_pct = (pnl / starting_cash * 100) if starting_cash > 0 else 0.0
            log.info(f"[{context.current_dt:%H:%M:%S}] total={total:,.2f} "
                     f"PnL={pnl:+,.2f} ({pnl_pct:+.2f}%)")

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Paper trading stopped.")

    return {
        "context": context,
        "trade_log": session._trade_log,
        "recorded_values": sorted(session._recorded_values.values(),
                                  key=lambda x: x["date"]),
        "session": session,
    }


def _resolve_live_price(spot_cache: dict, security: str, default: float) -> float:
    """Look up a live spot price from spot_cache for a security.

    akshare returns bare codes (e.g. "601390").  Securities in the portfolio
    may carry exchange suffixes (e.g. "601390.XSHG").  This helper tries
    both forms and falls back to ``default`` if neither is found.
    """
    price = spot_cache.get(security)
    if price is None:
        bare = security.replace(".XSHG", "").replace(".XSHE", "")
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
