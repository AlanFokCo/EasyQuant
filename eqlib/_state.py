"""Global state shared across eqlib modules.

Provides:
- BacktestSession: encapsulates all per-backtest mutable state, enabling
  multiple concurrent backtests (e.g., walk-forward loops in parallel threads).
- Thread-local session management: each thread can have its own active session.
- Module-level proxy: backward-compatible ``st._context``-style access is
  transparently delegated to the active session via a module wrapper class.
"""

import sys
import threading
import types


# ── BacktestSession ────────────────────────────────────────────────────────────

class BacktestSession:
    """Encapsulates all mutable state for a single backtest run.

    Creating a fresh ``BacktestSession`` per ``run_backtest`` call (and
    registering it as the thread-local active session) lets multiple backtests
    execute concurrently in separate threads without sharing state.

    Attributes:
        _context: current Context object
        _g: user-facing GlobalObject (strategy variables)
        _order_cost: active OrderCost settings
        _benchmark: benchmark security code
        _options: strategy options dict
        _scheduled_funcs: list of (type, ..., func) schedules
        _recorded_values: date → dict of recorded metrics
        _trade_log: list of executed trade dicts
        _handle_data_func: optional per-bar callback
        _before_trading_start_funcs / _after_trading_end_funcs: lifecycle hooks
        _pending_orders: orders buffered during strategy execution,
            filled at the *next* trading day's open (look-ahead bias fix)
        _order_timestamps: dict mapping order_id to submission datetime
            (for timeout tracking in Phase 2.4)
        _order_timeout_seconds: timeout threshold for pending orders
            (default: 3600 for live/paper, 86400 for backtest)
        _t1_locked_amounts: {security: int} — new shares bought today that
            cannot be sold until the next trading day (T+1 enforcement)
        _slippage_model: SlippageModel instance or None
    """

    __slots__ = (
        '_context', '_g', '_order_cost', '_order_cost_config', '_benchmark',
        '_options', '_scheduled_funcs', '_recorded_values', '_trade_log',
        '_handle_data_func', '_before_trading_start_funcs', '_after_trading_end_funcs',
        '_pending_orders', '_order_timestamps', '_order_timeout_seconds', '_t1_locked_amounts',
        '_slippage_model', '_selection_func', '_selection_rebalance', '_preloaded',
        # Notification system (Phase 2.5)
        '_notification_sender', '_on_order_queued_funcs', '_on_order_filled_funcs',
        '_notification_events',
    )

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all fields to their initial (pre-backtest) state."""
        self._context = None
        self._g = None
        self._order_cost = None
        self._order_cost_config = None
        self._benchmark = None
        self._options: dict = {}
        self._scheduled_funcs: list = []
        self._recorded_values: dict = {}   # date -> entry dict (O(1) lookup)
        self._trade_log: list = []
        self._handle_data_func = None
        self._before_trading_start_funcs: list = []
        self._after_trading_end_funcs: list = []
        # Pending orders: buffered during strategy execution, filled next day
        self._pending_orders: list = []
        # Order timestamps: for timeout tracking (Phase 2.4)
        self._order_timestamps: dict = {}
        # Order timeout: default 1 day for backtest, 1 hour for live/paper
        self._order_timeout_seconds: int = None  # None means use mode-based default
        # T+1: maps security -> number of new shares bought today (unsellable)
        self._t1_locked_amounts: dict = {}
        # Slippage model (None = no slippage)
        self._slippage_model = None
        # Stock selection (set via run_selection or parameter)
        self._selection_func = None
        self._selection_rebalance = None
        # Preloaded data (set by engine)
        self._preloaded = None
        # Notification system (Phase 2.5)
        self._notification_sender = None  # NotificationSender instance
        self._on_order_queued_funcs: list = []  # Callbacks for signal generation
        self._on_order_filled_funcs: list = []  # Callbacks for order execution
        self._notification_events: list = []  # Enabled events, e.g., ["queued", "filled"]


# ── Thread-local session management ───────────────────────────────────────────

_thread_local = threading.local()
# MED-25: lazy initialization — avoid instantiating BacktestSession at import
# time.  The global session is created on first access via get_session().
_global_session: "BacktestSession | None" = None


def get_session() -> BacktestSession:
    """Return the active BacktestSession for the current thread.

    Returns the thread-local session when one has been registered via
    :func:`_set_session`, otherwise returns (lazily creating) the module-level
    global session.
    """
    global _global_session
    sess = getattr(_thread_local, 'session', None)
    if sess is not None:
        return sess
    if _global_session is None:
        _global_session = BacktestSession()
    return _global_session


def _set_session(session: BacktestSession):
    """Register *session* as the active session for the current thread."""
    _thread_local.session = session


def _clear_session():
    """Deactivate the thread-local session (reverts to global fallback)."""
    try:
        del _thread_local.session
    except AttributeError:
        pass


def reset_all():
    """Reset the active session's state for a fresh backtest run."""
    get_session().reset()


# ── Module-level proxy (backward compatibility) ────────────────────────────────
#
# Makes ``import eqlib._state as st`` followed by ``st._context`` (read) and
# ``st._context = ctx`` (write) transparently delegate to the active session.
# This preserves the existing public API without any call-site changes.

_DELEGATED: frozenset = frozenset(BacktestSession.__slots__)


class _StateModule(types.ModuleType):
    """Module wrapper: proxies delegated attributes to the active session."""

    def __getattr__(self, name: str):
        # Only invoked for names absent from __dict__ (non-delegated attrs are
        # stored in __dict__ by the normal import machinery and won't come here).
        if name in _DELEGATED:
            return getattr(get_session(), name)
        raise AttributeError(f"module 'eqlib._state' has no attribute {name!r}")

    def __setattr__(self, name: str, value):
        # _DELEGATED is defined at module scope; access it directly to avoid
        # the dict-lookup indirection used during module initialisation.
        if name in _DELEGATED:
            setattr(get_session(), name, value)
        else:
            object.__setattr__(self, name, value)


# Swap the module object with our proxy, copying all existing names.
_orig_module = sys.modules[__name__]
_proxy = _StateModule(__name__)
_proxy.__dict__.update({
    k: v for k, v in _orig_module.__dict__.items()
    if k not in ('__dict__', '__weakref__')
})
sys.modules[__name__] = _proxy
