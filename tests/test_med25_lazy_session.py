"""Tests for MED-25: lazy BacktestSession initialization.

Before this fix, eqlib/_state.py eagerly created a BacktestSession at import
time.  After the fix, the global session is created lazily on first access.
"""

from __future__ import annotations

import inspect


def test_no_eager_instantiation_in_source():
    """The module source must not eagerly instantiate BacktestSession.

    Structural guard: the line `_global_session = BacktestSession()` must not
    appear before the `def get_session` definition.  The correct pattern is
    `_global_session = None` (lazy) with instantiation inside get_session().
    """
    import eqlib._state as state_mod
    src = inspect.getsource(state_mod)
    # Split at the definition of get_session
    before_get_session = src.split("def get_session")[0]
    assert "BacktestSession()" not in before_get_session, (
        "Found eager BacktestSession() call before get_session() definition — "
        "MED-25 lazy init is broken"
    )
    assert (
        "_global_session = None" in before_get_session
        or "_global_session: " in before_get_session
    ), (
        "_global_session should be initialized to None (lazy)"
    )


def test_get_session_returns_valid_session():
    """get_session() must return a BacktestSession instance."""
    from eqlib._state import get_session, BacktestSession
    sess = get_session()
    assert sess is not None
    assert isinstance(sess, BacktestSession)


def test_get_session_creates_lazily(monkeypatch):
    """get_session() lazily creates the session on first call if not set."""
    from eqlib._state import get_session, BacktestSession, _clear_session

    # Access the actual globals dict where _global_session lives
    func_globals = get_session.__globals__
    original = func_globals.get("_global_session")
    # Reset to None to simulate a fresh import
    func_globals["_global_session"] = None

    # Clear thread-local to force the global path
    from eqlib._state import _thread_local
    had_tl = hasattr(_thread_local, "session")
    tl_session = getattr(_thread_local, "session", None)
    if had_tl:
        del _thread_local.session

    created = []
    original_init = BacktestSession.__init__

    def _tracking(self):
        created.append(1)
        original_init(self)

    monkeypatch.setattr(BacktestSession, "__init__", _tracking)

    try:
        assert func_globals["_global_session"] is None
        sess = get_session()
        assert sess is not None
        assert len(created) >= 1, (
            "get_session() should have lazily created BacktestSession"
        )
    finally:
        # Restore original state
        func_globals["_global_session"] = original
        if had_tl:
            _thread_local.session = tl_session


def test_thread_local_session_bypasses_global():
    """Thread-local sessions override the global session."""
    from eqlib._state import get_session, BacktestSession, _set_session, _clear_session

    new_sess = BacktestSession()
    _set_session(new_sess)
    try:
        result = get_session()
        assert result is new_sess, "get_session() should return the thread-local session"
    finally:
        _clear_session()
