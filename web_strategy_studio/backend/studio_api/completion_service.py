"""Load eqlib symbol hints for POST /completion (MVP)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def _symbols_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "eqlib_symbols.json"


@lru_cache
def _load_symbols() -> list[dict]:
    p = _symbols_path()
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def suggest(source: str, cursor_line: int, cursor_col: int) -> list[dict]:
    lines = source.splitlines()
    if cursor_line < 1 or cursor_line > len(lines):
        line = ""
        prefix = ""
    else:
        line = lines[cursor_line - 1]
        prefix = line[:cursor_col] if cursor_col <= len(line) else line

    # crude token: last word-ish segment
    token = prefix.strip().split()[-1] if prefix.strip() else ""
    token = token.replace("(", "").replace(".", "")

    syms = _load_symbols()
    if not token:
        return syms[:30]
    tlow = token.lower()
    return [s for s in syms if tlow in s.get("label", "").lower()][:40]
