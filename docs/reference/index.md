# API 参考

> 本文档描述 `eqlib` 核心库的全部公开 API。
> **注意：本工具仅支持中国 A 股市场。**

!!! tip "阅读提示"

    函数名可用浏览器页内查找（`Ctrl+F` / `⌘F`）。新手请先完成 [操作指南](../how-to/index.md) 再按需跳转本章。

## 按场景查找

| 场景 | 跳转 |
|------|------|
| 写第一个策略 | [结构体](structures.md) → [交易 API](api-trading.md) |
| 拉取行情数据 | [数据 API](api-data.md) |
| 运行回测 | [回测引擎](api-backtest.md) |
| 设置手续费/滑点 | [配置 API](api-config.md) |
| 模拟盘通知 | [通知 API](api-notification.md) |
| 生成报告/计算指标 | [报告与分析](api-analysis.md) |
| 选股/行业轮动 | [选股策略](api-selection.md) |
| 优化仓位权重 | [报告与分析 — 组合优化](api-analysis.md) |
| A 股特色数据 | [数据 API — A 股特色](api-data.md#a-股特色数据) |
| 组合风控监测 | [组合风控 API](api-risk.md) |
| 滚动验证 / 过拟合检测 | [科学验证 API](api-scientific.md) |

**命名约定：**

- 股票代码格式为 6 位数字，如 `'601390'`；基准可带交易所后缀，如 `'000300.XSHG'`
- 日期格式统一为 `'YYYY-MM-DD'` 或 `date` 对象
- `context` 由框架自动传入，包含当前时间、投资组合、股票池等
- `g` 为策略级别全局对象，跨交易日持久化

**最小可运行策略：**

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

## 完整导入清单

```python
from eqlib import (
    # 生命周期
    run_backtest, run_strategy, run_portfolio_backtest,
    run_daily, run_weekly, run_monthly, run_selection,
    set_handle_data, record, run_paper_trade,
    # 配置
    set_benchmark, set_option, set_order_cost, set_slippage,
    OrderCost, SlippageModel, FixedSlippage, VolumeSlippage,
    # 交易
    order, order_target, order_value, order_target_value,
    # 数据
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
    # A 股特色数据
    get_north_money_flow, get_margin_data,
    get_limit_up_down_stats, get_restriction_release,
    # 日志
    log,
    # 对象
    g, GlobalObject, Context, Portfolio, Position,
    StrategyConfig,
    # 报告
    generate_chart, generate_report_md, generate_report_json, generate_html_report,
    # 组合优化
    portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity,
    # 分析
    analyze_returns, brinson_attribution, simple_factor_analysis,
    # 组合风控（实验性）
    PortfolioRiskMonitor, RiskThresholds, RiskReport, AlertLevel,
    check_kill_switch,
    # 滚动验证（实验性）
    walk_forward, WFAResult,
    # 科学验证（实验性）
    ValidationConfig,
    # 选股
    StockSelector, TopNSelector, MultiFactorSelector,
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
    fetch_factor_data,
    # 缓存
    set_cache_dir, set_local_data_dir, fetch_cached, estimate_memory_mb,
    save_stock_local, load_stock_local, has_local_data,
    list_local_stocks, remove_local_data, clear_all_local_data,
    BacktestSession, get_session,
)
```
