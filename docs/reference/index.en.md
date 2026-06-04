# API Reference

> This document describes all public APIs of the `eqlib` core library.
> **Note: This tool only supports the China A-share market.**

!!! tip "Reading Tip"

    Use browser search (`Ctrl+F` / `⌘F`) to find function names. Beginners should complete the [How-to Guides](../how-to/index.md) before jumping into this chapter.

## Find by Scenario

| Scenario | Jump to |
|----------|---------|
| Write your first strategy | [Structures](structures.md) → [Trading API](api-trading.md) |
| Fetch market data | [Data API](api-data.md) |
| Run a backtest | [Backtest Engine](api-backtest.md) |
| Set commission/slippage | [Configuration API](api-config.md) |
| Paper trading notifications | [Notification API](api-notification.md) |
| Generate reports / calculate metrics | [Reports & Analysis](api-analysis.md) |
| Stock selection / sector rotation | [Selection Strategies](api-selection.md) |
| Optimize portfolio weights | [Reports & Analysis — Portfolio Optimization](api-analysis.md) |
| A-share specific data | [Data API — A-Share Specific](api-data.md#a-share-specific-data) |
| Portfolio risk monitoring | [Portfolio Risk API](api-risk.md) |
| Walk-forward validation / overfitting detection | [Scientific Validation API](api-scientific.md) |

**Naming Conventions:**

- Stock codes are 6-digit numbers, e.g., `'601390'`; benchmarks may include exchange suffix, e.g., `'000300.XSHG'`
- Date format is `'YYYY-MM-DD'` or `date` objects
- `context` is automatically passed by the framework, containing current time, portfolio, universe, etc.
- `g` is a strategy-level global object that persists across trading days

**Minimal Runnable Strategy:**

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist['close'].iloc[-1] > hist['close'].mean() * 1.02:
        order_value(g.security, context.portfolio.available_cash)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390'],
)
```

---

## Complete Import List

```python
from eqlib import (
    # Lifecycle
    run_backtest, run_strategy, run_portfolio_backtest,
    run_daily, run_weekly, run_monthly, run_selection,
    set_handle_data, record, run_paper_trade,
    # Configuration
    set_benchmark, set_option, set_order_cost, set_slippage,
    OrderCost, SlippageModel, FixedSlippage, VolumeSlippage,
    # Trading
    order, order_target, order_value, order_target_value,
    # Data
    get_price, history, attribute_history, get_all_securities,
    fetch_stock_data, download_stock_data, load_csv, clear_cache,
    scan_market, check_golden_cross, get_financial_screen,
    get_index_stocks, get_industry_list, get_industry_stocks,
    get_concept_list, get_concept_stocks, get_industry,
    fetch_minute_data, get_price_minute, get_tick_data,
    get_current_data, get_security_info, get_trade_days,
    get_fundamentals, get_financial_abstract, get_money_flow,
    get_billboard_list, get_valuation, get_index_weights, get_extras,
    query, valuation, get_current_data_object,
    set_universe, get_universe,
    before_trading_start, after_trading_end,
    # A-share specific data
    get_north_money_flow, get_margin_data,
    get_limit_up_down_stats, get_restriction_release,
    # Logging
    log,
    # Objects
    g, GlobalObject, Context, Portfolio, Position,
    StrategyConfig,
    # Reports
    generate_chart, generate_report_md, generate_report_json, generate_html_report,
    # Portfolio optimization
    portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity,
    # Analysis
    analyze_returns, brinson_attribution, simple_factor_analysis,
    # Portfolio risk (experimental)
    PortfolioRiskMonitor, RiskThresholds, RiskReport, AlertLevel,
    check_kill_switch,
    # Walk-forward validation (experimental)
    walk_forward, WFAResult,
    # Scientific validation (experimental)
    ValidationConfig,
    # Stock selection
    StockSelector, TopNSelector, MultiFactorSelector,
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
    fetch_factor_data,
    # Caching
    set_cache_dir, set_local_data_dir, fetch_cached, estimate_memory_mb,
    save_stock_local, load_stock_local, has_local_data,
    list_local_stocks, remove_local_data, clear_all_local_data,
    BacktestSession, get_session,
)
```
