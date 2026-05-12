"""Professional logging facility with progress/step helpers."""

from __future__ import annotations

import logging
from typing import Any


_LEVEL_ICONS = {
    "DEBUG": "🔎",
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "ERROR": "❌",
    "CRITICAL": "🛑",
}


class _CleanFormatter(logging.Formatter):
    """Compact, readable logger formatter."""

    def format(self, record):
        ts = self.formatTime(record, self.datefmt)
        level = record.levelname.upper()
        icon = _LEVEL_ICONS.get(level, "•")
        msg = record.getMessage()
        return f"{ts} | {icon} {level:<8} | {msg}"


def _fmt_value(value: Any) -> str:
    """Format values into concise log-friendly text."""
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _fmt_fields(fields: dict[str, Any]) -> str:
    """Format key-value metadata fields."""
    clean = {k: v for k, v in fields.items() if v is not None}
    if not clean:
        return ""
    text = ", ".join(f"{k}={_fmt_value(v)}" for k, v in clean.items())
    return f" | {text}"


def _to_level(level: str | int) -> int:
    """Normalize level from int/string."""
    if isinstance(level, int):
        return level
    name = str(level).upper()
    if name in ("WARN", "WARNING"):
        return logging.WARNING
    return getattr(logging, name, logging.INFO)


# Internal logger
_logger = logging.getLogger("eqlib")
# Prevent duplicate logs when host apps configure root logging handlers.
# eqlib emits through its own dedicated handler for stable output layout.
_logger.propagate = False
_handler = logging.StreamHandler()
_handler.setFormatter(_CleanFormatter(datefmt="%H:%M:%S"))
if not _logger.handlers:
    _logger.addHandler(_handler)
_logger.setLevel(logging.INFO)


class Logger:
    """User-facing logger (mirrors EasyQuant's log object)."""

    @staticmethod
    def info(msg, *args):
        _logger.info(msg, *args)

    @staticmethod
    def debug(msg, *args):
        _logger.debug(msg, *args)

    @staticmethod
    def warn(msg, *args):
        """Log a warning.  Alias: ``warning``."""
        _logger.warning(msg, *args)

    # Python stdlib-compatible alias for warn
    warning = warn

    @staticmethod
    def error(msg, *args):
        _logger.error(msg, *args)

    @staticmethod
    def set_level(level: str | int):
        """Set logger verbosity, e.g. 'DEBUG'/'INFO'/'WARNING'."""
        _logger.setLevel(_to_level(level))

    @staticmethod
    def set_quiet(enabled: bool = True):
        """Enable/disable quiet mode (WARNING+ only)."""
        _logger.setLevel(logging.WARNING if enabled else logging.INFO)

    @staticmethod
    def section(title: str, **fields):
        """High-level section marker for a major stage."""
        _logger.info(f"━━ {title} ━━{_fmt_fields(fields)}")

    @staticmethod
    def step(name: str, status: str = "RUN", **fields):
        """Single process step marker."""
        _logger.info(f"[{status}] {name}{_fmt_fields(fields)}")

    @staticmethod
    def action(name: str, target: str | None = None, **fields):
        """Action-oriented operation log."""
        target_text = f" -> {target}" if target else ""
        _logger.info(f"{name}{target_text}{_fmt_fields(fields)}")

    @staticmethod
    def progress(current: int, total: int, label: str = "Progress", **fields):
        """Progress indicator with normalized percent."""
        total_safe = max(int(total), 1)
        current_safe = max(0, min(int(current), total_safe))
        pct = current_safe / total_safe * 100.0
        _logger.info(f"{label}: {current_safe}/{total_safe} ({pct:.1f}%){_fmt_fields(fields)}")


log = Logger()
