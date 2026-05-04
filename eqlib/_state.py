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
        _t1_locked_amounts: {security: int} — new shares bought today that
            cannot be sold until the next trading day (T+1 enforcement)
        _slippage_model: SlippageModel instance or None
    """

    __slots__ = (
        '_context', '_g', '_order_cost', '_order_cost_config', '_benchmark',
        '_options', '_scheduled_funcs', '_recorded_values', '_trade_log',
        '_handle_data_func', '_before_trading_start_funcs', '_after_trading_end_funcs',
        '_pending_orders', '_t1_locked_amounts', '_slippage_model',
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
        # T+1: maps security -> number of new shares bought today (unsellable)
        self._t1_locked_amounts: dict = {}
        # Slippage model (None = no slippage)
        self._slippage_model = None


# ── Thread-local session management ───────────────────────────────────────────

_thread_local = threading.local()
_global_session = BacktestSession()   # fallback for single-threaded use


def get_session() -> BacktestSession:
    """Return the active BacktestSession for the current thread.

    Returns the thread-local session when one has been registered via
    :func:`_set_session`, otherwise returns the module-level global session.
    """
    return getattr(_thread_local, 'session', _global_session)


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
