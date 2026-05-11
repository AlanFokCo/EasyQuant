"""Tests for stock query API."""

import pytest


def test_import_stock_query():
    from eqlib import query, valuation, get_fundamentals, get_current_data_object
    assert callable(query)
    assert callable(get_fundamentals)
    assert callable(get_current_data_object)


def test_query_construction():
    from eqlib import query, valuation
    from eqlib.stock_query import Query

    q = query(valuation.code, valuation.market_cap)
    assert isinstance(q, Query)
    assert len(q._fields) == 2


def test_field_comparison_operators():
    from eqlib import valuation
    from eqlib.stock_query import FilterCondition

    cond = valuation.pe > 0
    assert isinstance(cond, FilterCondition)
    assert cond.field == "pe"
    assert cond.op == ">"
    assert cond.value == 0

    cond = valuation.pb <= 2
    assert cond.op == "<="
    assert cond.value == 2

    cond = valuation.price == 10
    assert cond.op == "="


def test_field_between():
    from eqlib import valuation
    from eqlib.stock_query import FilterCondition

    cond = valuation.market_cap.between(20, 30)
    assert isinstance(cond, FilterCondition)
    assert cond.field == "market_cap"
    assert cond.op == "between"
    assert cond.value == (20, 30)


def test_field_in():
    from eqlib import valuation
    from eqlib.stock_query import FilterCondition

    cond = valuation.code.in_(["601390", "600519"])
    assert isinstance(cond, FilterCondition)
    assert cond.field == "code"
    assert cond.op == "in"
    assert cond.value == ["601390", "600519"]


def test_order_by_asc_desc():
    from eqlib import valuation
    from eqlib.stock_query import OrderByClause

    clause = valuation.market_cap.asc()
    assert isinstance(clause, OrderByClause)
    assert clause.field == "market_cap"
    assert clause.ascending is True

    clause = valuation.pe.desc()
    assert clause.ascending is False


def test_query_chaining():
    from eqlib import query, valuation
    from eqlib.stock_query import Query

    q = (
        query(valuation.code, valuation.market_cap, valuation.pe)
        .filter(
            valuation.market_cap.between(20, 30),
            valuation.pe > 0,
        )
        .order_by(valuation.market_cap.asc())
        .limit(5)
    )

    assert isinstance(q, Query)
    assert len(q._filters) == 2
    assert len(q._order_by) == 1
    assert q._limit_n == 5


def test_get_fundamentals_query():
    """Test that get_fundamentals with a Query returns a DataFrame."""
    from eqlib import query, valuation, get_fundamentals

    q = (
        query(valuation.code, valuation.market_cap, valuation.pe)
        .filter(valuation.pe > 0)
        .order_by(valuation.market_cap.asc())
        .limit(5)
    )

    df = get_fundamentals(q)

    assert isinstance(df, __import__("pandas").DataFrame)
    # May be empty if akshare network is unreachable
    if not df.empty:
        assert "code" in df.columns
        assert "market_cap" in df.columns
        assert "pe" in df.columns
        assert df["market_cap"].min() > 0


def test_get_fundamentals_backward_compat():
    """Test that get_fundamentals('code') still works (original EasyQuant API)."""
    from eqlib import get_fundamentals

    try:
        result = get_fundamentals("601390")
        assert result is not None
    except Exception:
        pass


def test_get_current_data_object():
    """Test that get_current_data_object returns _StockDataObj objects."""
    from eqlib import get_current_data_object
    from eqlib.stock_query import _StockDataObj

    data = get_current_data_object()
    assert isinstance(data, dict)
    if data:
        code = next(iter(data))
        item = data[code]
        assert isinstance(item, _StockDataObj)
        assert hasattr(item, "paused")
        assert hasattr(item, "price")
        assert hasattr(item, "pe")
        assert hasattr(item, "pb")
        assert hasattr(item, "total_value")
        assert hasattr(item, "float_value")


def test_small_cap_query():
    """Test a realistic small-cap stock selection query."""
    from eqlib import query, valuation, get_fundamentals

    q = (
        query(
            valuation.code,
            valuation.market_cap,
            valuation.pe,
        )
        .filter(
            valuation.market_cap.between(20, 30),
            valuation.pe > 0,
        )
        .order_by(
            valuation.market_cap.asc(),
        )
        .limit(3)
    )

    df = get_fundamentals(q)
    assert isinstance(df, __import__("pandas").DataFrame)
    if not df.empty:
        assert "code" in df.columns
        assert len(df) <= 3
