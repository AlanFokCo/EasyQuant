"""Stock query API for EasyQuant.

Provides `query()`, `valuation`, and `get_fundamentals()` for
fluent, chainable stock screening with market-cap, PE, PB and
other fundamental fields.

Usage:
    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.pe,
    ).filter(
        valuation.market_cap.between(20, 30),
        valuation.pe > 0,
    ).order_by(
        valuation.market_cap.asc(),
    ).limit(5)

    df = get_fundamentals(q)

Limitation (V1): valuation data comes from current akshare spot snapshots,
not historical reports. PE / PB / market_cap reflect the latest real-time
snapshot, not the value on the simulated backtest date.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Internal: column mapping between query field names and EasyQuant/akshare
# ---------------------------------------------------------------------------

# Mapping: query field name -> (akshare Chinese column, output column name)
_COLUMN_MAP: dict[str, tuple[str, str]] = {
    "code": ("代码", "code"),
    "market_cap": ("流通市值", "market_cap"),
    "total_value": ("总市值", "total_value"),
    "float_value": ("流通市值", "float_value"),
    "pe": ("市盈率-动态", "pe"),
    "pb": ("市净率", "pb"),
    "turnover": ("换手率", "turnover"),
    "price": ("最新价", "price"),
    "pct_change": ("涨跌幅", "pct_change"),
}

# Fields that need yuan -> 亿元 (divide by 1e8) conversion
_CAP_FIELDS = {"market_cap", "total_value", "float_value"}


# ---------------------------------------------------------------------------
# Filter / Order-by data classes
# ---------------------------------------------------------------------------


@dataclass
class FilterCondition:
    """A single filter condition produced by a field descriptor."""

    field: str
    op: str  # "=", ">", ">=", "<", "<=", "!=", "between", "in"
    value: Any


@dataclass
class OrderByClause:
    """An ORDER BY clause produced by .asc() / .desc() on a field descriptor."""

    field: str
    ascending: bool = True


# ---------------------------------------------------------------------------
# Field descriptor — enables `valuation.market_cap.between(...)` etc.
# ---------------------------------------------------------------------------


class _FieldDescriptor:
    """Represents a queryable field. Comparison operators produce FilterConditions."""

    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return FilterCondition(self.name, "=", other)

    def __ne__(self, other):
        return FilterCondition(self.name, "!=", other)

    def __gt__(self, other):
        return FilterCondition(self.name, ">", other)

    def __ge__(self, other):
        return FilterCondition(self.name, ">=", other)

    def __lt__(self, other):
        return FilterCondition(self.name, "<", other)

    def __le__(self, other):
        return FilterCondition(self.name, "<=", other)

    def between(self, low, high):
        return FilterCondition(self.name, "between", (low, high))

    def in_(self, values):
        return FilterCondition(self.name, "in", list(values))

    def asc(self):
        return OrderByClause(self.name, ascending=True)

    def desc(self):
        return OrderByClause(self.name, ascending=False)


# ---------------------------------------------------------------------------
# `valuation` namespace
# ---------------------------------------------------------------------------


class _ValuationFields:
    """Namespace for valuation fields used in query() expressions."""

    code = _FieldDescriptor("code")
    market_cap = _FieldDescriptor("market_cap")  # 流通市值, in 亿元
    total_value = _FieldDescriptor("total_value")  # 总市值, in 亿元
    float_value = _FieldDescriptor("float_value")  # 流通市值, in 亿元
    pe = _FieldDescriptor("pe")
    pb = _FieldDescriptor("pb")
    turnover = _FieldDescriptor("turnover")
    price = _FieldDescriptor("price")
    pct_change = _FieldDescriptor("pct_change")


valuation = _ValuationFields()


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


class Query:
    """Fluent query builder for chainable stock screening."""

    def __init__(self, fields: list[_FieldDescriptor]):
        self._fields = fields
        self._filters: list[FilterCondition] = []
        self._order_by: list[OrderByClause] = []
        self._limit_n: Optional[int] = None

    def filter(self, *conditions: FilterCondition) -> "Query":
        """Add filter conditions. Multiple conditions are AND-ed together."""
        self._filters.extend(conditions)
        return self

    def order_by(self, *clauses: OrderByClause) -> "Query":
        """Add ORDER BY clauses."""
        self._order_by.extend(clauses)
        return self

    def limit(self, n: int) -> "Query":
        """Limit the number of returned rows."""
        self._limit_n = n
        return self


def query(*fields: _FieldDescriptor) -> Query:
    """Create a new query for chainable field selection.

    Example:
        q = query(
            valuation.code,
            valuation.market_cap,
        ).filter(
            valuation.market_cap.between(20, 30),
        ).order_by(
            valuation.market_cap.asc(),
        )
    """
    return Query(list(fields))


# ---------------------------------------------------------------------------
# Query executor
# ---------------------------------------------------------------------------


def _execute_query(q: Query) -> pd.DataFrame:
    """Execute a Query object and return a DataFrame."""
    from eqlib.data import _get_spot_data

    spot = _get_spot_data()
    if spot.empty:
        return pd.DataFrame()

    # Build column rename map for all fields referenced in the query
    needed_fields: set[str] = set()
    for f in q._fields:
        needed_fields.add(f.name)
    for cond in q._filters:
        needed_fields.add(cond.field)
    for clause in q._order_by:
        needed_fields.add(clause.field)

    rename_dict: dict[str, str] = {}
    for field_name in needed_fields:
        if field_name in _COLUMN_MAP:
            cn_col, out_col = _COLUMN_MAP[field_name]
            rename_dict[cn_col] = out_col

    # Only keep columns we can rename, plus ensure 'code' is present
    keep_cn = [cn for cn, out in rename_dict.items() if cn in spot.columns]
    if keep_cn:
        df = spot[keep_cn].copy()
        for cn, out in rename_dict.items():
            if cn in df.columns:
                df.rename(columns={cn: out}, inplace=True)
    else:
        return pd.DataFrame()

    # Numeric conversion
    numeric_cols = [c for c in df.columns if c != "code"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Convert market-cap fields from yuan to 亿元
    for field in _CAP_FIELDS:
        if field in df.columns:
            df[field] = df[field] / 1e8

    # Apply filters
    for cond in q._filters:
        if cond.field not in df.columns:
            continue
        col = df[cond.field]
        if cond.op == "=":
            mask = col == cond.value
        elif cond.op == "!=":
            mask = col != cond.value
        elif cond.op == ">":
            mask = col > cond.value
        elif cond.op == ">=":
            mask = col >= cond.value
        elif cond.op == "<":
            mask = col < cond.value
        elif cond.op == "<=":
            mask = col <= cond.value
        elif cond.op == "between":
            low, high = cond.value
            mask = col.between(low, high)
        elif cond.op == "in":
            mask = col.isin(cond.value)
        else:
            continue
        df = df[mask]

    # Select requested columns (always include 'code')
    output_cols: list[str] = []
    for f in q._fields:
        if f.name in df.columns and f.name not in output_cols:
            output_cols.append(f.name)
    if "code" not in output_cols and "code" in df.columns:
        output_cols.insert(0, "code")
    df = df[output_cols]

    # Apply order_by
    for clause in q._order_by:
        if clause.field in df.columns:
            df = df.sort_values(by=clause.field, ascending=clause.ascending)

    # Apply limit
    if q._limit_n is not None:
        df = df.head(q._limit_n)

    # Ensure code column is string type
    if "code" in df.columns:
        df["code"] = df["code"].astype(str)

    df = df.reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# `get_fundamentals` — dual-signature (query or single code)
# ---------------------------------------------------------------------------


def get_fundamentals(query_or_code, date=None):
    """Get fundamentals data.

    Query object usage::

        q = query(valuation.code, valuation.market_cap).filter(
            valuation.market_cap.between(20, 30)
        )
        df = get_fundamentals(q)

    Single stock code usage (original EasyQuant API)::

        df = get_fundamentals('601390')

    Parameters:
        query_or_code: a Query object (from query()) or a stock code string
        date: optional date parameter (ignored in V1; spot data is always current)
    """
    if isinstance(query_or_code, Query):
        return _execute_query(query_or_code)
    # Fallback: original EasyQuant behavior
    from eqlib.data import get_financial_abstract
    return get_financial_abstract(query_or_code)


# ---------------------------------------------------------------------------
# `get_current_data_object` — stock data with .paused attribute
# ---------------------------------------------------------------------------


class _StockDataObj:
    """Stock data object with attribute access (e.g. data[code].paused).

    Returns dict mapping code -> _StockDataObj with attributes:
        code, name, price, paused, is_st, pe, pb, total_value, float_value, etc.
    """

    def __init__(self, code: str, name: str = "", price: float = 0.0,
                 open: float = 0.0, high: float = 0.0, low: float = 0.0,
                 prev_close: float = 0.0, volume: float = 0.0,
                 money: float = 0.0, turnover: float = 0.0,
                 pe: float = 0.0, pb: float = 0.0,
                 total_value: float = 0.0, float_value: float = 0.0,
                 pct_change: float = 0.0, paused: bool = False,
                 is_st: bool = False, **kwargs):
        self.code = code
        self.name = name
        self.price = price
        self.open = open
        self.high = high
        self.low = low
        self.prev_close = prev_close
        self.volume = volume
        self.money = money
        self.turnover = turnover
        self.pe = pe
        self.pb = pb
        self.total_value = total_value
        self.float_value = float_value
        self.pct_change = pct_change
        self.paused = paused
        self.is_st = is_st
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"_StockDataObj({self.code}, {self.name}, price={self.price}, paused={self.paused})"


def get_current_data_object() -> dict[str, _StockDataObj]:
    """Get current market snapshot as objects with attribute access.

    Returns dict mapping code -> _StockDataObj with .paused attribute.
    In backtest mode, checks preloaded volume to determine paused status.
    In live mode, checks spot volume == 0.
    """
    from eqlib.data import get_current_data as _get_current_data_eq

    eq_data = _get_current_data_eq()
    if not eq_data:
        return {}

    # Try to detect backtest mode for accurate paused detection
    paused_codes: set[str] = set()
    try:
        from eqlib.engine import _get_preloaded
        preloaded = _get_preloaded()
        if preloaded is not None and hasattr(preloaded, "_dates") and preloaded._dates:
            from eqlib._state import _context
            if _context is not None and hasattr(_context, "current_dt") and _context.current_dt:
                current_date = _context.current_dt.date()
                for code in eq_data:
                    bar = preloaded.get_bar(current_date, code)
                    if bar is not None and bar.get("volume", 0) == 0:
                        paused_codes.add(code)
    except Exception:
        pass

    result: dict[str, _StockDataObj] = {}
    for code, info in eq_data.items():
        paused = code in paused_codes or info.get("volume", 0) == 0
        result[code] = _StockDataObj(
            code=code,
            name=str(info.get("name", "")),
            price=float(info.get("price", 0) or 0),
            open=float(info.get("open", 0) or 0),
            high=float(info.get("high", 0) or 0),
            low=float(info.get("low", 0) or 0),
            prev_close=float(info.get("prev_close", 0) or 0),
            volume=float(info.get("volume", 0) or 0),
            money=float(info.get("money", 0) or 0),
            turnover=float(info.get("turnover", 0) or 0),
            pe=float(info.get("pe", 0) or 0),
            pb=float(info.get("pb", 0) or 0),
            total_value=float(info.get("total_value", 0) or 0),
            float_value=float(info.get("float_value", 0) or 0),
            pct_change=float(info.get("pct_change", 0) or 0),
            paused=paused,
            is_st="ST" in str(info.get("name", "")),
        )
    return result
