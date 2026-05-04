"""Backtest engine: drives the strategy lifecycle
(initialize -> handle_data / run_daily -> report)."""

import datetime
import time
import pandas as pd
from typing import Optional
from eqlib.context import Context
from eqlib.data import fetch_stock_data, get_price, _iter_days
from eqlib.data_cache import PreloadedData
from eqlib._state import (
    _scheduled_funcs, _recorded_values, _trade_log, _handle_data_func,
    _before_trading_start_funcs, _after_trading_end_funcs,
    reset_all,
)
from eqlib.logger import log


# Global preloaded data instance — set by run_backtest, used by _LazyData and trade
_preloaded = PreloadedData()


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
    import eqlib._state as st
    from eqlib.objects import OrderCost
    st._order_cost_config = cost
    st._order_cost = OrderCost(
        open_tax=cost.open_tax,
        close_tax=cost.close_tax,
        open_commission=cost.open_commission,
        close_commission=cost.close_commission,
        close_today_commission=cost.close_today_commission,
        min_commission=cost.min_commission,
    )


def set_benchmark(security):
    """Set benchmark security."""
    import eqlib._state as st
    st._benchmark = security


def set_option(name, value):
    """Set strategy option."""
    import eqlib._state as st
    st._options[name] = value


def run_daily(func, time="every_bar"):
    """Schedule a function to run every trading day.

    Parameters:
        func: callable taking (context) as argument
        time: execution time, e.g., '09:30', '14:50', 'every_bar'
    """
    import eqlib._state as st
    st._scheduled_funcs.append(("daily", time, func))


def run_weekly(func, day_of_week: int = 1, time="09:30"):
    """Schedule a function to run weekly.

    Parameters:
        func: callable taking (context) as argument
        day_of_week: 0=Monday, 1=Tuesday, ..., 4=Friday
        time: execution time, e.g., '09:30'
    """
    import eqlib._state as st
    st._scheduled_funcs.append(("weekly", day_of_week, time, func))


def run_monthly(func, day_of_month: int = 1, time="09:30"):
    """Schedule a function to run monthly.

    Parameters:
        func: callable taking (context) as argument
        day_of_month: day of month, 1-31
        time: execution time, e.g., '09:30'
    """
    import eqlib._state as st
    st._scheduled_funcs.append(("monthly", day_of_month, time, func))


def _should_run_schedule(sched, day) -> bool:
    """Check if a scheduled function should run on the given date."""
    t = sched[0]
    if t == "daily":
        return True
    if t == "weekly":
        return day.weekday() == sched[1]
    if t == "monthly":
        return day.day == sched[1]
    return False


def _get_sched_time(sched) -> str:
    """Get the time string from a schedule entry."""
    return sched[2 if sched[0] != "daily" else 1]


def _get_sched_func(sched):
    """Get the function from a schedule entry."""
    return sched[3 if sched[0] != "daily" else 2]


def _register_before_start(func):
    """Register a before_trading_start callback."""
    import eqlib._state as st
    st._before_trading_start_funcs.append(func)


def _register_after_end(func):
    """Register an after_trading_end callback."""
    import eqlib._state as st
    st._after_trading_end_funcs.append(func)


def record(**kwargs):
    """Record a data point for charting."""
    import eqlib._state as st
    entry = {"date": st._context.current_dt.date()}
    entry.update(kwargs)
    # O(1) dict write — replaces O(N) list append + linear scan
    st._recorded_values[st._context.current_dt.date()] = entry


def _get_price_fast(security, day) -> Optional[float]:
    """Get closing price for a security on a given day.

    When data is preloaded (normal backtest), this is a pure dict lookup.
    No fallback to network/disk I/O — if preload is set, it's authoritative.
    """
    return _preloaded.get_close(day, security)


def set_handle_data(func):
    """Register the user's handle_data function."""
    import eqlib._state as st
    st._handle_data_func = func


class _LazyData(dict):
    """Lazy data dict: when you access data[security], it fetches the latest bar."""

    def __init__(self, context):
        super().__init__()
        self._context = context

    def __missing__(self, key):
        day = self._context.current_dt.date()
        bar = _preloaded.get_bar(day, key)
        if bar is not None:
            result = SecurityBar(bar)
            self[key] = result
            return result
        # No fallback to network/disk — preloaded data is authoritative
        return None


def run_backtest(initialize_func, start_date, end_date,
                 starting_cash=100000.0, frequency: str = "daily",
                 benchmark: str = "000300.XSHG", securities=None,
                 use_local: bool = False, max_memory_mb: int = 1024):
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
                   Downloads and saves to local CSV if not found.
                   Subsequent runs will use the saved local data,
                   avoiding network requests.
        max_memory_mb: memory limit in MB for in-memory dict caches.
                       Default 1024 (1 GB). If estimated memory exceeds
                       this, falls back to compact panel slicing (slower
                       but memory-safe). Results are identical either way.
    """
    global _preloaded

    import eqlib._state as st
    from eqlib.objects import OrderCost

    reset_all()
    _preloaded.clear()

    st._order_cost = OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    )
    st._benchmark = benchmark

    # Preload data first (if securities provided)
    if securities:
        log.info(f"Preloading data for {len(securities)} securities{' (local)' if use_local else ''}...")
        # Add warmup period for indicator lookback (e.g. 110 bars needs ~280 calendar days)
        warmup_start = start_date - datetime.timedelta(days=365) if isinstance(start_date, datetime.date) else start_date
        _preloaded.load(securities, warmup_start, end_date, adjust="qfq", use_local=use_local, max_memory_mb=max_memory_mb)
        log.info("Data preloaded.")

    # Get trading days from preloaded data index (no network call)
    trading_days = _get_trading_days(start_date, end_date)
    if not trading_days:
        log.error("No trading days found")
        return None

    _context = Context(start_date, end_date, frequency, starting_cash)
    st._context = _context

    import eqlib
    _g = eqlib.g
    for attr in list(_g.__dict__.keys()):
        delattr(_g, attr)
    st._g = _g

    initialize_func(_context)

    log.info(f"Backtest started: {start_date} to {end_date}, "
             f"{len(trading_days)} trading days, cash={starting_cash:,.0f}")

    # Main trading loop
    data = None
    for day in trading_days:
        _context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))
        data = _LazyData(_context)

        # Before trading start callbacks
        for func in st._before_trading_start_funcs:
            func(_context, data)

        # Update portfolio prices (pure dict lookup, no I/O)
        prices = {}
        for sec in _context.portfolio.positions:
            price = _get_price_fast(sec, day)
            prices[sec] = price if price is not None else _context.portfolio.positions[sec].avg_cost

        # Run scheduled funcs
        for sched in st._scheduled_funcs:
            if _should_run_schedule(sched, day):
                t = _get_sched_time(sched)
                func = _get_sched_func(sched)
                if t == "every_bar":
                    func(_context)
                else:
                    hour, minute = map(int, t.split(":"))
                    _context.current_dt = datetime.datetime.combine(day, datetime.time(hour, minute))
                    func(_context)
                    _context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))

        # Run handle_data if defined
        if st._handle_data_func is not None:
            st._handle_data_func(_context, data)

        # Update portfolio values
        _context.portfolio._sync_total_value(prices)

        # Record daily portfolio value — O(1) dict lookup/insert
        day_entry = _recorded_values.get(day)
        if day_entry is None:
            day_entry = {"date": day}
            _recorded_values[day] = day_entry
        day_entry["total_value"] = _context.portfolio.total_value
        day_entry["cash"] = _context.portfolio.available_cash

        # After trading end callbacks
        _context.current_dt = datetime.datetime.combine(day, datetime.time(15, 0))
        for func in st._after_trading_end_funcs:
            func(_context, data)
        _context.current_dt = datetime.datetime.combine(day, datetime.time(9, 30))

    log.info(f"Backtest finished: final_value={_context.portfolio.total_value:,.2f}")

    return {
        "context": _context,
        "trade_log": st._trade_log,
        "recorded_values": sorted(_recorded_values.values(), key=lambda x: x["date"]),
        "benchmark": st._benchmark,
    }


def _get_trading_days(start, end) -> list[datetime.date]:
    """Get list of trading days between start and end.

    If PreloadedData has been populated, uses its index directly (no network call).
    """
    if _preloaded._dates is not None and len(_preloaded._dates) > 0:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        return sorted(
            (pd.Timestamp(d).date() for d in _preloaded._dates
             if start_ts <= pd.Timestamp(d) <= end_ts)
        )

    # Fallback: try akshare or simple weekday filter
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="601390", period="daily",
                                start_date=start.strftime("%Y%m%d"),
                                end_date=end.strftime("%Y%m%d"),
                                adjust="qfq")
        if df.empty:
            return []
        df["日期"] = pd.to_datetime(df["日期"])
        return sorted(df["日期"].dt.date.unique().tolist())
    except Exception:
        return [d for d in _iter_days(start, end) if d.weekday() < 5]


# Re-export for external access
def get_context():
    """Get the current backtest context."""
    import eqlib._state as st
    return st._context


def get_g():
    """Get the global object."""
    import eqlib._state as st
    return st._g


def get_trade_log():
    import eqlib._state as st
    return st._trade_log


def get_recorded_values():
    import eqlib._state as st
    return sorted(st._recorded_values.values(), key=lambda x: x["date"])


def run_paper_trade(initialize_func, starting_cash=100000.0,
                    benchmark: str = "000300.XSHG", interval: int = 60):
    """Run a strategy in paper trading mode with live market data.

    Parameters:
        initialize_func: user's initialize(context) function
        starting_cash: initial capital
        benchmark: benchmark security code
        interval: polling interval in seconds
    """
    import eqlib._state as st
    from eqlib.objects import OrderCost

    reset_all()
    st._order_cost = OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    )
    st._benchmark = benchmark

    now = datetime.datetime.now()
    _context = Context(now.date(), now.date() + datetime.timedelta(days=365),
                       "daily", starting_cash)
    st._context = _context

    import eqlib
    _g = eqlib.g
    for attr in list(_g.__dict__.keys()):
        delattr(_g, attr)
    st._g = _g

    initialize_func(_context)

    log.info(f"Paper trading started: initial capital={starting_cash:,.0f}, interval={interval}s")
    log.info(f"Universe: {context_universe()}")

    # Cache live prices to avoid redundant spot API calls
    spot_cache: dict = {}

    try:
        while True:
            _context.current_dt = datetime.datetime.now()
            spot_cache = _fetch_live_prices(spot_cache)

            prices = {}
            for sec in _context.portfolio.positions:
                prices[sec] = spot_cache.get(sec) or _context.portfolio.positions[sec].avg_cost

            today = _context.current_dt.date()
            for sched in st._scheduled_funcs:
                if _should_run_schedule(sched, today):
                    t = _get_sched_time(sched)
                    if t == "every_bar":
                        _get_sched_func(sched)(_context)

            if st._handle_data_func is not None:
                st._handle_data_func(_context, _LazyData(_context))

            _context.portfolio._sync_total_value(prices)

            total = _context.portfolio.total_value
            pnl = total - starting_cash
            pnl_pct = (pnl / starting_cash) * 100 if starting_cash else 0
            log.info(f"[{_context.current_dt:%H:%M:%S}] total_value={total:,.2f}  "
                     f"PnL={pnl:+,.2f} ({pnl_pct:+.2f}%)")

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Paper trading stopped.")

    return {
        "context": _context,
        "trade_log": st._trade_log,
        "recorded_values": sorted(st._recorded_values.values(), key=lambda x: x["date"]),
    }


def _fetch_live_prices(cache: dict, max_age: int = 30) -> dict:
    """Fetch all A-share quotes once and update the cache.

    Returns updated dict mapping code -> price.
    Cache is reused to avoid fetching on every poll cycle.
    """
    import time as _time
    ts = cache.get("_ts", 0)
    if _time.time() - ts < max_age:
        return cache

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df.empty:
            return cache

        new_cache = {"_ts": _time.time()}
        for _, row in df.iterrows():
            code = row.get("代码")
            price = row.get("最新价")
            if code and price is not None:
                try:
                    new_cache[code] = float(price)
                except (ValueError, TypeError):
                    pass
        return new_cache
    except Exception:
        return cache


def context_universe():
    """Get the current strategy universe from context."""
    import eqlib._state as st
    if st._context:
        return st._context.universe
    return []
