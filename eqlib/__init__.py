"""eqlib — EasyQuant-like API library for local quantitative backtesting.

Data source: akshare
Usage:
    from eqlib import *

    def initialize(context):
        g.security = '601390'
        set_benchmark('000300.XSHG')
        set_option('use_real_price', True)
        run_daily(market_open, time='every_bar')

    def market_open(context):
        close_data = attribute_history(g.security, 5, '1d', ['close'])
        MA5 = close_data['close'].mean()
        current_price = close_data['close'][-1]

        if current_price > 1.01 * MA5:
            order_value(g.security, context.portfolio.available_cash)
            log.info("Buying %s" % g.security)
        elif current_price < MA5 and context.portfolio.positions.get(g.security):
            order_target(g.security, 0)
            log.info("Selling %s" % g.security)

        record(price=current_price, cash=context.portfolio.available_cash)

    # Run backtest
    result = run_backtest(initialize,
                          start_date='2024-01-01',
                          end_date='2025-01-01',
                          starting_cash=100000)
"""

# Strategy lifecycle
from eqlib.engine import (
    run_backtest,
    run_daily,
    run_weekly,
    run_monthly,
    run_selection,
    set_handle_data,
    record,
    run_paper_trade,
)

# Configuration
from eqlib.engine import set_benchmark, set_option, set_order_cost, set_slippage
from eqlib.objects import OrderCost

# Slippage models
from eqlib.slippage import SlippageModel, FixedSlippage, VolumeSlippage

# Session management (for advanced / concurrent usage)
from eqlib._state import BacktestSession, get_session

# Trading
from eqlib.trade import order, order_target, order_value, order_target_value

# Data
from eqlib.data import (
    get_price, history, attribute_history, get_all_securities,
    download_stock_data, load_csv,
    scan_market, check_golden_cross,
    fetch_stock_data, clear_cache,
    # Financial data
    get_financial_abstract, get_financial_screen,
    # Index / industry / concept
    get_index_stocks, get_industry_list, get_industry_stocks,
    get_concept_list, get_concept_stocks, get_industry,
    # Minute-level data
    fetch_minute_data, get_price_minute,
    # Tick data
    get_tick_data,
    # P0: Market snapshot, security info, trading calendar
    get_current_data, get_security_info, get_trade_days,
    # P1: Fundamentals, money flow, valuation, extras
    get_fundamentals, get_money_flow, get_billboard_list,
    get_valuation, get_index_weights, get_extras,
    # Universe management
    set_universe, get_universe,
    # P0: Lifecycle callbacks
    before_trading_start, after_trading_end,
)

# Logging
from eqlib.logger import log

# Global object (user-facing) — always available like EasyQuant's g
from eqlib.objects import GlobalObject
g = GlobalObject()

# Context is provided at runtime
from eqlib.context import Context, Portfolio, Position

# Reporting
from eqlib.report import generate_chart, generate_report_md, generate_report_json, generate_html_report

# Engine internals (for internal use)
from eqlib import engine

# Data cache (disk caching + preloaded data)
from eqlib.data_cache import (
    set_cache_dir, fetch_cached, estimate_memory_mb,
    # Local CSV data store
    set_local_data_dir, save_stock_local, load_stock_local,
    has_local_data, list_local_stocks, remove_local_data,
    clear_all_local_data,
)

# Portfolio optimization
from eqlib.optimizer import (
    portfolio_optimizer,
    Bound, MinVariance, MaxSharpe, RiskParity,
)

# Attribution analysis
from eqlib.attribution import (
    analyze_returns,
    brinson_attribution,
    fama_french_analysis,
)

# Stock selection
from eqlib.selection import (
    StockSelector,
    TopNSelector,
    MultiFactorSelector,
    filter_st_stocks,
    filter_paused_stocks,
    filter_low_price_stocks,
    filter_high_pe_stocks,
    fetch_factor_data,
)

# Utilities: indicators, statistics, money management
from eqlib import utils

# Portfolio backtest mode
from eqlib.portfolio import StrategyConfig, run_portfolio_backtest

# PTrade/QMT adapter — imported as a submodule to avoid shadowing backtest functions:
#   from eqlib.ptrade_adapter import *
# See doc/ptrade_adapter.md for usage instructions.

__all__ = [
    # Lifecycle
    "run_backtest", "run_daily", "run_weekly", "run_monthly", "run_selection",
    "set_handle_data", "record", "run_paper_trade",
    # Config
    "set_benchmark", "set_option", "set_order_cost", "set_slippage", "OrderCost",
    # Slippage models
    "SlippageModel", "FixedSlippage", "VolumeSlippage",
    # Session management
    "BacktestSession", "get_session",
    # Trading
    "order", "order_target", "order_value", "order_target_value",
    # Data
    "get_price", "history", "attribute_history", "get_all_securities",
    "download_stock_data", "load_csv",
    "scan_market", "check_golden_cross",
    "fetch_stock_data", "clear_cache",
    # Financial data
    "get_financial_abstract", "get_financial_screen",
    # Index / industry / concept
    "get_index_stocks", "get_industry_list", "get_industry_stocks",
    "get_concept_list", "get_concept_stocks", "get_industry",
    # Minute-level data
    "fetch_minute_data", "get_price_minute",
    # Tick data
    "get_tick_data",
    # P0: Market snapshot, security info, trading calendar
    "get_current_data", "get_security_info", "get_trade_days",
    # P1: Fundamentals, money flow, valuation, extras
    "get_fundamentals", "get_money_flow", "get_billboard_list",
    "get_valuation", "get_index_weights", "get_extras",
    # Universe management
    "set_universe", "get_universe",
    # P0: Lifecycle callbacks
    "before_trading_start", "after_trading_end",
    # Logging
    "log",
    # Objects
    "g", "GlobalObject", "Context", "Portfolio", "Position",
    # Reporting
    "generate_chart", "generate_report_md", "generate_report_json", "generate_html_report",
    "run_strategy",
    # Engine internals
    "engine",
    # Portfolio optimization
    "portfolio_optimizer", "Bound", "MinVariance", "MaxSharpe", "RiskParity",
    # Attribution analysis
    "analyze_returns", "brinson_attribution", "fama_french_analysis",
    # Stock selection
    "StockSelector", "TopNSelector", "MultiFactorSelector",
    "filter_st_stocks", "filter_paused_stocks",
    "filter_low_price_stocks", "filter_high_pe_stocks",
    "fetch_factor_data",
    # Data cache
    "set_cache_dir", "fetch_cached", "estimate_memory_mb",
    # Local CSV data store
    "set_local_data_dir", "save_stock_local", "load_stock_local",
    "has_local_data", "list_local_stocks", "remove_local_data",
    "clear_all_local_data",
    # Utilities
    "utils",
    # Portfolio backtest
    "StrategyConfig", "run_portfolio_backtest",
]


def run_strategy(initialize_func, start_date=None, end_date=None,
                  starting_cash=100000.0, benchmark="000300.XSHG",
                  handle_data=None, securities=None,
                  report_dir="reports", use_local: bool = False,
                  max_memory_mb: int = 1024,
                  selection_func=None, selection_rebalance: str = "monthly:1"):
    """
    High-level strategy runner. Runs backtest and generates all reports.

    Parameters:
        initialize_func: user's initialize(context)
        start_date: 'YYYY-MM-DD' or datetime.date
        end_date: 'YYYY-MM-DD' or datetime.date
        starting_cash: initial capital
        benchmark: benchmark code
        handle_data: optional handle_data(context, data) function
        securities: list of stock codes to preload. Passing all stocks
            you'll trade significantly speeds up large backtests.
        report_dir: directory for output reports
        use_local: if True, load data from local CSV files first.
                   Downloads and saves to local CSV if not found.
                   Subsequent runs will use the saved local data.
        max_memory_mb: memory limit in MB for in-memory dict caches.
                       Default 1024 (1 GB). Results are identical
                       regardless of whether dict caches are used.
        selection_func: optional callable taking (context) and returning
            a list of selected security codes.  Runs periodically on
            rebalance days to update context.universe.
        selection_rebalance: when to run selection_func.  Format:
            - "monthly:N" — Nth day of month (1-31), default "monthly:1"
            - "weekly:N" — Nth weekday (0=Mon, 4=Fri), default "weekly:0"
            - "daily" — every trading day

    Returns:
        Backtest result dict
    """
    import datetime as _dt
    import os as _os

    if start_date is None:
        start_date = _dt.date.today() - _dt.timedelta(days=365)
    if isinstance(start_date, str):
        start_date = _dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date is None:
        end_date = _dt.date.today()
    if isinstance(end_date, str):
        end_date = _dt.datetime.strptime(end_date, "%Y-%m-%d").date()

    # Register handle_data if provided
    if handle_data is not None:
        set_handle_data(handle_data)

    # Run backtest
    result = run_backtest(
        initialize_func, start_date, end_date,
        starting_cash=starting_cash, benchmark=benchmark,
        securities=securities, use_local=use_local,
        max_memory_mb=max_memory_mb,
        selection_func=selection_func,
        selection_rebalance=selection_rebalance,
    )

    if result is None:
        print("Backtest failed: no result returned.")
        return None

    # Generate reports
    _os.makedirs(report_dir, exist_ok=True)
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    chart_path = f"{report_dir}/backtest_{timestamp}.png"
    report_html_path = f"{report_dir}/backtest_{timestamp}.html"
    report_md_path = f"{report_dir}/backtest_{timestamp}.md"
    report_json_path = f"{report_dir}/backtest_{timestamp}.json"

    generate_chart(result, chart_path)
    generate_html_report(result, report_html_path)
    generate_report_md(result, report_md_path)
    generate_report_json(result, report_json_path)

    ctx = result["context"]
    pnl = ctx.portfolio.total_value - ctx.portfolio.starting_cash
    pnl_pct = (pnl / ctx.portfolio.starting_cash) * 100

    print(f"\nFinal value: {ctx.portfolio.total_value:,.2f}")
    print(f"P&L: {pnl:,.2f} ({pnl_pct:+.2f}%)")
    print(f"Trades: {len(result['trade_log'])}")
    print(f"\nChart:  {chart_path}")
    print(f"HTML:   {report_html_path}")
    print(f"Report: {report_md_path}")
    print(f"Data:   {report_json_path}")

    return result
