"""Test that all public APIs are importable."""

import pytest


def test_import_eqlib():
    import eqlib
    assert hasattr(eqlib, "__all__")


def test_import_lifecycle():
    from eqlib import (
        run_backtest, run_daily, run_weekly, run_monthly,
        set_handle_data, record, run_paper_trade,
    )
    assert callable(run_backtest)
    assert callable(run_daily)
    assert callable(run_weekly)
    assert callable(run_monthly)


def test_import_config():
    from eqlib import set_benchmark, set_option, set_order_cost, OrderCost
    assert callable(set_benchmark)
    assert callable(set_option)
    assert callable(set_order_cost)
    assert callable(OrderCost)


def test_import_trading():
    from eqlib import order, order_target, order_value, order_target_value
    assert callable(order)
    assert callable(order_target)
    assert callable(order_value)
    assert callable(order_target_value)


def test_import_data():
    from eqlib import (
        get_price, history, attribute_history, get_all_securities,
        download_stock_data, load_csv,
        scan_market, check_golden_cross,
        fetch_stock_data, clear_cache,
        get_financial_abstract, get_financial_screen,
        get_index_stocks, get_industry_list, get_industry_stocks,
        get_concept_list, get_concept_stocks, get_industry,
        fetch_minute_data, get_price_minute,
        get_tick_data,
        get_current_data, get_security_info, get_trade_days,
        get_fundamentals, get_money_flow, get_billboard_list,
        get_valuation, get_index_weights, get_extras,
        set_universe, get_universe,
        before_trading_start, after_trading_end,
    )
    assert callable(get_price)
    assert callable(history)
    assert callable(attribute_history)


def test_import_objects():
    from eqlib import g, GlobalObject, Context, Portfolio, Position
    assert g is not None
    assert callable(GlobalObject)


def test_import_reporting():
    from eqlib import generate_chart, generate_report_md, generate_report_json
    assert callable(generate_chart)
    assert callable(generate_report_md)
    assert callable(generate_report_json)


def test_import_optimizer():
    from eqlib import portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity
    assert callable(portfolio_optimizer)
    assert callable(MinVariance)
    assert callable(MaxSharpe)
    assert callable(RiskParity)


def test_import_attribution():
    from eqlib import analyze_returns, brinson_attribution, fama_french_analysis
    assert callable(analyze_returns)
    assert callable(brinson_attribution)
    assert callable(fama_french_analysis)


def test_import_utils():
    from eqlib import utils
    # Indicators
    assert callable(utils.ma)
    assert callable(utils.sma)
    assert callable(utils.smma)
    assert callable(utils.macd)
    assert callable(utils.rsi)
    assert callable(utils.boll)
    assert callable(utils.atr)
    # Stats
    assert callable(utils.max_drawdown)
    assert callable(utils.cagr)
    assert callable(utils.rolling_sharpe)
    # Money management
    assert callable(utils.kelly_criterion)
    assert callable(utils.atr_position_size)
    # Levels
    assert callable(utils.pivot_classic)
    assert callable(utils.fibonacci_retracement)


def test_import_cache():
    from eqlib import set_cache_dir, fetch_cached
    assert callable(set_cache_dir)


def test_run_strategy():
    from eqlib import run_strategy
    assert callable(run_strategy)
