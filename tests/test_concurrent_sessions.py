"""Tests for BLOCKER-2 (engine._preloaded thread-safety) and
BLOCKER-3 (g singleton shared across threads).

BLOCKER-2: run_backtest writes to module-level engine._preloaded (line 595).
When two threads run backtests concurrently, thread A's preloaded data gets
overwritten by thread B's, corrupting results.

BLOCKER-3: eqlib.g is a module-level GlobalObject singleton. run_backtest
clears it (delattr on every attribute) at start, so concurrent backtests
destroy each other's strategy state (e.g., g.security, g.fast_period).
"""

import datetime
import threading
import pandas as pd
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_preloaded(bars: dict[str, dict[datetime.date, dict]]) -> "PreloadedData":
    """Build a minimal PreloadedData instance from a nested dict."""
    from eqlib.data_cache import PreloadedData

    pd_frames = {}
    for sec, day_bars in bars.items():
        rows = []
        for d, bar in sorted(day_bars.items()):
            rows.append({**bar, "date": pd.Timestamp(d)})
        df = pd.DataFrame(rows).set_index("date")
        pd_frames[sec] = df

    pre = PreloadedData()
    pre.panel = pd.concat(pd_frames, axis=1)
    pre.panel.columns = pd.MultiIndex.from_tuples(
        [(sec, col) for sec in pd_frames for col in pd_frames[sec].columns],
        names=["security", "field"],
    )
    pre._securities = sorted(pd_frames.keys())
    pre._dates = pre.panel.index

    for sec, df in pd_frames.items():
        if "close" in df.columns:
            pre._close_dict[sec] = dict(zip(df.index, df["close"]))
        fields = ["open", "high", "low", "close", "volume"]
        pre._bar_cache[sec] = df.reindex(columns=fields, fill_value=0).to_dict("index")
        pre._field_series[sec] = {f: df[f] for f in df.columns if f in df}

    return pre


def _activate_preloaded(pre):
    """Install *pre* as the active session's preloaded data."""
    from eqlib._state import get_session
    import eqlib.engine as eng
    sess = get_session()
    object.__setattr__(sess, "_preloaded", pre)
    # Also set on engine module-level for tests that read it directly
    eng._preloaded = pre


def _clear_preloaded():
    """Remove any preloaded data from the active session."""
    from eqlib._state import get_session
    import eqlib.engine as eng
    sess = get_session()
    object.__setattr__(sess, "_preloaded", None)
    eng._preloaded = eng._preloaded_fallback


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-2: Concurrent backtests must not share _preloaded
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker2PreloadedIsolation:
    """Verify that _get_preloaded() reads from the thread's session, not a
    shared module-level global.

    The bug: run_backtest writes engine._preloaded (module global). When two
    threads call run_backtest, thread A's data is overwritten by thread B.
    The fix: remove the module-level write at engine.py:595; all reads go
    through _get_preloaded() which reads from session._preloaded.
    """

    def teardown_method(self):
        _clear_preloaded()

    def test_get_preloaded_reads_from_session_not_module_global(self):
        """_get_preloaded() must return the session's data, not a stale global."""
        from eqlib._state import BacktestSession, _set_session, get_session
        from eqlib.engine import _get_preloaded

        # Set up session A with preloaded data
        pre_a = _make_preloaded({
            "A": {datetime.date(2024, 1, 2): {"open": 10, "high": 10, "low": 10,
                                               "close": 10, "volume": 100}}
        })
        sess_a = BacktestSession()
        object.__setattr__(sess_a, "_preloaded", pre_a)
        _set_session(sess_a)

        assert _get_preloaded()._securities == ["A"], (
            "_get_preloaded should return session A's data"
        )

        # Now switch to session B with different data
        pre_b = _make_preloaded({
            "B": {datetime.date(2024, 1, 2): {"open": 20, "high": 20, "low": 20,
                                               "close": 20, "volume": 200}}
        })
        sess_b = BacktestSession()
        object.__setattr__(sess_b, "_preloaded", pre_b)
        _set_session(sess_b)

        # Session B's data should be returned
        assert _get_preloaded()._securities == ["B"], (
            "_get_preloaded should now return session B's data"
        )

        # Session A's _preloaded must be unchanged (not overwritten by session B)
        assert sess_a._preloaded._securities == ["A"], (
            "Session A's _preloaded should be unchanged after switching sessions"
        )

    def test_concurrent_get_preloaded_isolation(self):
        """Two threads must see their own _preloaded, not the other's."""
        from eqlib._state import BacktestSession, _set_session, get_session
        from eqlib.engine import _get_preloaded

        pre_a = _make_preloaded({
            "STOCK_A": {datetime.date(2024, 1, 2): {"open": 10, "high": 10, "low": 10,
                                                     "close": 10, "volume": 100}}
        })
        pre_b = _make_preloaded({
            "STOCK_B": {datetime.date(2024, 1, 2): {"open": 20, "high": 20, "low": 20,
                                                     "close": 20, "volume": 200}}
        })

        results = {}
        barrier = threading.Barrier(2)

        def worker(label, preloaded, other_preloaded):
            sess = BacktestSession()
            object.__setattr__(sess, "_preloaded", preloaded)
            _set_session(sess)

            # Both threads reach this point simultaneously
            barrier.wait()

            # Small delay to increase chance of detecting race condition
            import time; time.sleep(0.05)

            got = _get_preloaded()
            results[label] = list(got._securities) if got else []

        t1 = threading.Thread(target=worker, args=("A", pre_a, pre_b))
        t2 = threading.Thread(target=worker, args=("B", pre_b, pre_a))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results.get("A") == ["STOCK_A"], (
            f"Thread A should see only STOCK_A, got {results.get('A')}"
        )
        assert results.get("B") == ["STOCK_B"], (
            f"Thread B should see only STOCK_B, got {results.get('B')}"
        )

    def test_engine_no_module_level_preloaded_write(self):
        """After fix, run_backtest must NOT write to engine._preloaded.

        The bug: run_backtest does `global _preloaded; _preloaded = preloaded`
        (engine.py:577,595), overwriting a module-level global that other
        threads may be reading.
        """
        import eqlib.engine as eng
        import inspect

        source = inspect.getsource(eng.run_backtest)
        assert "_preloaded =" not in source or "_preloaded_fallback" in source, (
            "run_backtest should NOT assign to module-level _preloaded; "
            "it already attaches to session._preloaded which is thread-safe"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-3: g must be session-scoped, not a module-level singleton
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlocker3GlobalGIsolation:
    """Verify that eqlib.g is a proxy that delegates to the active session's
    _g, so concurrent backtests don't clobber each other's strategy state.

    The bug: g = GlobalObject() is a module-level singleton. run_backtest
    clears it (delattr on all attrs), so concurrent backtests destroy each
    other's g.security, g.fast_period, etc.
    """

    def teardown_method(self):
        from eqlib._state import _clear_session
        _clear_session()

    def test_g_proxy_delegates_to_session_g(self):
        """g.attr reads/writes must go through the active session's _g."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session, get_session
        from eqlib.objects import GlobalObject

        # Create and activate a session with its own GlobalObject
        sess = BacktestSession()
        sess._g = GlobalObject()  # sessions start with _g=None
        _set_session(sess)

        # Write via g proxy
        eqlib.g.test_attr = "hello"

        # Read from session's _g directly
        assert sess._g.test_attr == "hello", (
            "g proxy should write to session's _g"
        )

        # Read back via g proxy
        assert eqlib.g.test_attr == "hello", (
            "g proxy should read from session's _g"
        )

    def test_g_proxy_different_sessions_different_values(self):
        """Two sessions must have independent g state."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session
        from eqlib.objects import GlobalObject

        sess_a = BacktestSession()
        sess_a._g = GlobalObject()
        sess_b = BacktestSession()
        sess_b._g = GlobalObject()

        # Session A: set g.x = 1
        _set_session(sess_a)
        eqlib.g.x = 1

        # Session B: set g.x = 2
        _set_session(sess_b)
        eqlib.g.x = 2

        # Session A should still have x = 1
        _set_session(sess_a)
        assert eqlib.g.x == 1, (
            f"Session A's g.x should be 1, got {eqlib.g.x} — sessions share g"
        )

        # Session B should still have x = 2
        _set_session(sess_b)
        assert eqlib.g.x == 2, (
            f"Session B's g.x should be 2, got {eqlib.g.x} — sessions share g"
        )

    def test_g_concurrent_isolation(self):
        """Two threads must be able to set g.x to different values independently."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session
        from eqlib.objects import GlobalObject
        import time

        results = {}
        barrier = threading.Barrier(2)

        def worker(label, value):
            sess = BacktestSession()
            sess._g = GlobalObject()
            _set_session(sess)
            barrier.wait()
            time.sleep(0.05)  # Increase race window
            eqlib.g.x = value
            time.sleep(0.05)
            results[label] = eqlib.g.x

        t1 = threading.Thread(target=worker, args=("A", 1))
        t2 = threading.Thread(target=worker, args=("B", 2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see its own value
        assert results.get("A") == 1, (
            f"Thread A should see g.x=1, got {results.get('A')}"
        )
        assert results.get("B") == 2, (
            f"Thread B should see g.x=2, got {results.get('B')}"
        )

    def test_g_proxy_supports_del(self):
        """del g.attr must work through the proxy."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session
        from eqlib.objects import GlobalObject

        sess = BacktestSession()
        sess._g = GlobalObject()
        _set_session(sess)

        eqlib.g.temp = "delete_me"
        assert hasattr(eqlib.g, "temp")

        del eqlib.g.temp
        assert not hasattr(eqlib.g, "temp"), "del g.attr should work"

    def test_g_proxy_contains(self):
        """'attr' in g must work through the proxy."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session
        from eqlib.objects import GlobalObject

        sess = BacktestSession()
        sess._g = GlobalObject()
        _set_session(sess)

        eqlib.g.foo = 42
        assert "foo" in eqlib.g
        assert "nonexistent" not in eqlib.g

    def test_g_proxy_keys_items(self):
        """g.keys() and g.items() must work through the proxy."""
        import eqlib
        from eqlib._state import BacktestSession, _set_session
        from eqlib.objects import GlobalObject

        sess = BacktestSession()
        sess._g = GlobalObject()
        _set_session(sess)

        eqlib.g.a = 1
        eqlib.g.b = 2

        keys = list(eqlib.g.keys())
        assert "a" in keys
        assert "b" in keys
