"""Tests for enhanced logging helpers."""

import io

from eqlib.logger import _handler, log


def _with_capture(fn):
    stream = io.StringIO()
    old_stream = _handler.stream
    _handler.setStream(stream)
    try:
        fn(stream)
    finally:
        _handler.flush()
        _handler.setStream(old_stream)
        log.set_quiet(False)
        log.set_level("INFO")


def test_logger_structured_helpers():
    def run(stream):
        log.section("Backtest started", start="2024-01-01", end="2024-12-31")
        log.step("Preloading market data", status="RUN", securities=3)
        log.progress(1, 4, label="Backtest progress", date="2024-01-02")
        log.action("Queue order", "601390", amount="+100")
        text = stream.getvalue()
        assert "🧭 ━━ Backtest started ━━" in text
        assert "🔄 [RUN] Preloading market data" in text
        assert "📍 Backtest progress: 1/4 (25.0%)" in text
        assert "📝 Queue order -> 601390" in text
        assert "start=2024-01-01" in text

    _with_capture(run)


def test_logger_progress_clamps_values():
    def run(stream):
        log.progress(20, 10, label="Run")
        text = stream.getvalue()
        assert "📍 Run: 10/10 (100.0%)" in text
        assert "Progress clamped: current=20 total=10 -> current=10" in text

    _with_capture(run)


def test_logger_quiet_mode():
    def run(stream):
        log.set_quiet(True)
        log.info("this should be suppressed")
        log.warn("this warning should appear")
        text = stream.getvalue()
        assert "this should be suppressed" not in text
        assert "this warning should appear" in text

    _with_capture(run)


def test_logger_set_propagate():
    import eqlib.logger as logger_mod
    old = logger_mod._logger.propagate
    try:
        log.set_propagate(True)
        assert logger_mod._logger.propagate is True
        log.set_propagate(False)
        assert logger_mod._logger.propagate is False
    finally:
        logger_mod._logger.propagate = old
