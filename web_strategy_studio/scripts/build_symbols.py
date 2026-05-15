#!/usr/bin/env python3
"""Generate backend/studio_api/data/eqlib_symbols.json from the eqlib public API.

Usage:
    python scripts/build_symbols.py

Writes 80-120 completion items covering the most useful eqlib symbols,
including lifecycle hooks, trading functions, data access, indicators,
and stock selection utilities.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so eqlib can be imported when running
# from the web_strategy_studio/ directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import eqlib  # noqa: F401 — side-effect: populates eqlib namespace
    import eqlib.utils.indicators as _indicators
except ImportError as exc:  # pragma: no cover
    print(
        f"[build_symbols] ERROR: cannot import eqlib ({exc}).\n"
        "Run `pip install -e .` from the repo root first.",
        file=sys.stderr,
    )
    sys.exit(1)

_OUT = Path(__file__).resolve().parent.parent / "backend" / "studio_api" / "data" / "eqlib_symbols.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_doc(obj: object) -> str:
    """Return the first paragraph of obj's docstring, stripped."""
    doc = inspect.getdoc(obj)
    if not doc:
        return ""
    # Return only the first non-empty paragraph (up to 300 chars)
    para = doc.split("\n\n")[0].replace("\n", " ").strip()
    return para[:300]


def _sig(obj: object) -> str:
    """Return a readable signature string, or '' on failure."""
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "()"


def _fn(name: str, obj: object, kind: str = "Function") -> dict:
    sig = _sig(obj)
    doc = _clean_doc(obj)
    return {
        "label": name,
        "kind": kind,
        "insert_text": f"{name}{sig}",
        "documentation": doc or f"eqlib.{name}",
    }


def _cls(name: str, obj: type) -> dict:
    doc = _clean_doc(obj)
    try:
        init_sig = _sig(obj.__init__).replace("(self, ", "(").replace("(self)", "()")
    except Exception:
        init_sig = "()"
    return {
        "label": name,
        "kind": "Class",
        "insert_text": f"{name}{init_sig}",
        "documentation": doc or f"eqlib.{name}",
    }


def _var(name: str, documentation: str) -> dict:
    return {
        "label": name,
        "kind": "Variable",
        "insert_text": name,
        "documentation": documentation,
    }


# ---------------------------------------------------------------------------
# Symbol definitions
# ---------------------------------------------------------------------------

def _collect() -> list[dict]:
    symbols: list[dict] = []
    eq = eqlib

    # ── Lifecycle callbacks ──────────────────────────────────────────────────
    lifecycle_snippets = [
        ("initialize", "def initialize(context):\n    \"\"\"Called once before backtest starts.\"\"\"\n    pass"),
        ("handle_data", "def handle_data(context, data):\n    \"\"\"Called on every bar (if set_handle_data is used).\"\"\"\n    pass"),
        ("before_trading_start", "def before_trading_start(context, data):\n    \"\"\"Called each day before market open.\"\"\"\n    pass"),
        ("after_trading_end", "def after_trading_end(context, data):\n    \"\"\"Called each day after market close.\"\"\"\n    pass"),
    ]
    for name, snippet in lifecycle_snippets:
        symbols.append({
            "label": name,
            "kind": "Function",
            "insert_text": snippet,
            "documentation": f"eqlib lifecycle callback: {name}",
        })

    # ── Schedule helpers ─────────────────────────────────────────────────────
    for name in ("run_daily", "run_weekly", "run_monthly", "run_selection"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Backtest entry point ─────────────────────────────────────────────────
    obj = getattr(eq, "run_backtest", None)
    if callable(obj):
        symbols.append(_fn("run_backtest", obj))

    # ── Trading ──────────────────────────────────────────────────────────────
    for name in ("order", "order_target", "order_value", "order_target_value"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Data access ──────────────────────────────────────────────────────────
    for name in (
        "get_price", "attribute_history", "history",
        "get_all_securities", "get_index_stocks",
        "get_current_data", "get_security_info", "get_trade_days",
        "get_fundamentals", "get_valuation",
        "get_industry_list", "get_industry_stocks",
        "get_concept_list", "get_concept_stocks",
        "fetch_stock_data", "download_stock_data",
        "set_universe", "get_universe",
    ):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Configuration ────────────────────────────────────────────────────────
    for name in ("set_benchmark", "set_order_cost", "set_slippage", "set_option", "record"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Classes ──────────────────────────────────────────────────────────────
    for name in ("OrderCost", "SlippageModel", "FixedSlippage", "VolumeSlippage",
                 "StockSelector", "TopNSelector", "MultiFactorSelector",
                 "BacktestSession", "StrategyConfig"):
        obj = getattr(eq, name, None)
        if obj is not None and isinstance(obj, type):
            symbols.append(_cls(name, obj))

    # ── Special variables ────────────────────────────────────────────────────
    symbols.append(_var("g", "Global object for storing user-defined state across bars. Access as g.my_var = ..."))
    symbols.append(_var("context", "Passed to every lifecycle callback. Holds portfolio, current_dt, universe, etc."))
    symbols.append(_var("context.portfolio", "Portfolio object: available_cash, total_value, positions, etc."))
    symbols.append(_var("context.portfolio.positions", "Dict[security, Position] of current positions."))
    symbols.append(_var("context.portfolio.available_cash", "Current available cash balance (float)."))

    # ── log methods ──────────────────────────────────────────────────────────
    log_obj = getattr(eq, "log", None)
    for method in ("info", "warn", "error", "debug"):
        m = getattr(log_obj, method, None) if log_obj is not None else None
        doc = _clean_doc(m) if callable(m) else f"Log at {method} level."
        symbols.append({
            "label": f"log.{method}",
            "kind": "Method",
            "insert_text": f"log.{method}",
            "documentation": doc or f"eqlib log.{method}",
        })

    # ── Indicators from eqlib.utils.indicators ───────────────────────────────
    for name in ("ma", "ema", "sma", "smma", "wma", "macd", "rsi", "kdj", "boll", "atr",
                 "dmi", "cci", "roc", "obv", "vwap", "golden_cross", "death_cross", "stoch"):
        obj = getattr(_indicators, name, None)
        if callable(obj):
            sym = _fn(name, obj)
            sym["documentation"] = f"Indicator: {sym['documentation']}"
            symbols.append(sym)

    # ── Selection helpers ────────────────────────────────────────────────────
    for name in ("filter_st_stocks", "filter_paused_stocks",
                 "filter_low_price_stocks", "filter_high_pe_stocks",
                 "fetch_factor_data"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Analytics ────────────────────────────────────────────────────────────
    for name in ("analyze_returns", "brinson_attribution", "simple_factor_analysis",
                 "portfolio_optimizer", "walk_forward"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # ── Report ───────────────────────────────────────────────────────────────
    for name in ("generate_html_report", "generate_report_json", "generate_report_md", "generate_chart"):
        obj = getattr(eq, name, None)
        if callable(obj):
            symbols.append(_fn(name, obj))

    # Deduplicate by label (keep first occurrence)
    seen: set[str] = set()
    unique: list[dict] = []
    for s in symbols:
        lbl = s["label"]
        if lbl not in seen:
            seen.add(lbl)
            unique.append(s)

    return unique


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    symbols = _collect()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(symbols, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_symbols] Wrote {len(symbols)} symbols → {_OUT.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
