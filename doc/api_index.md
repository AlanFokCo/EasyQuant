# eqlib API 速查索引

> 一页看清「能做什么、去哪查细节」。完整签名与边界条件以 [**api_reference.md**](api_reference.md) 为准；工具函数见 [**utils_reference.md**](utils_reference.md)；链式选股见 api_reference **第 3.14 节**。

!!! tip "第一次使用？"

    若尚未跑通安装与示例回测，请先完成 [**用户手册 §0～§3**](user_guide/index.md)（从 [§0](user_guide/00_first_steps.md) 读到 [§3](user_guide/03_quickstart_strategy.md)），再回到本页按「场景」查 API。

---

## 按使用场景跳转

| 我想… | 优先看 |
|--------|--------|
| 第一次跑通回测 + 出报告 | [用户手册 §9](user_guide/09_backtest.md)；[API 参考第 4 章 `run_strategy`](api_reference.md#4-回测与模拟盘引擎)（在章节内搜索函数名） |
| 只要回测结果、自己后处理 | [API 参考第 4 章 `run_backtest`](api_reference.md#4-回测与模拟盘引擎) |
| 多标的固定规则组合 | [API 参考第 4 章 `run_portfolio_backtest`](api_reference.md#4-回测与模拟盘引擎) |
| 读懂 HTML/指标含义 | [**reports_and_metrics.md**](reports_and_metrics.md) |
| 安装/数据/无图报错 | [**FAQ.md**](FAQ.md) |
| 导出 PTrade/QMT | [**ptrade_adapter.md**](ptrade_adapter.md) |
| 模拟盘 | [API 参考第 4 章 `run_paper_trade`](api_reference.md#4-回测与模拟盘引擎) |

---

## 公开符号一览（与 `eqlib.__all__` 对齐）

下列符号均可 `from eqlib import ...` 导入（`run_strategy` 在包内 `__init__.py` 定义，亦属公开 API）。

### 生命周期与调度

| 符号 | 文档 |
|------|------|
| `run_backtest`, `run_strategy`, `run_paper_trade` | [第4章](api_reference.md#4-回测与模拟盘引擎) |
| `run_daily`, `run_weekly`, `run_monthly`, `run_selection` | [第4章](api_reference.md#4-回测与模拟盘引擎) |
| `set_handle_data`, `record` | [第4章](api_reference.md#4-回测与模拟盘引擎) |
| `before_trading_start`, `after_trading_end` | [第4章](api_reference.md#4-回测与模拟盘引擎) |

### 配置与成本

| 符号 | 文档 |
|------|------|
| `set_benchmark`, `set_option`, `set_order_cost`, `OrderCost` | [第5章](api_reference.md#5-配置-api) |
| `set_slippage`, `SlippageModel`, `FixedSlippage`, `VolumeSlippage` | [第5章](api_reference.md#5-配置-api)（滑点模型） |

### 交易

| 符号 | 文档 |
|------|------|
| `order`, `order_target`, `order_value`, `order_target_value` | [第2章 交易 API](api_reference.md#2-交易-api) |

### 数据（行情与基础信息）

| 符号 | 文档 |
|------|------|
| `get_price`, `history`, `attribute_history` | [第3章 数据 API](api_reference.md#3-数据-api) |
| `fetch_stock_data`, `download_stock_data`, `load_csv`, `clear_cache` | [第3章](api_reference.md#3-数据-api) |
| `get_all_securities`, `scan_market`, `check_golden_cross` | [第3章](api_reference.md#3-数据-api) |
| `get_financial_abstract`, `get_financial_screen` | [第3章](api_reference.md#3-数据-api) |
| `get_index_stocks`, `get_industry_list`, `get_industry_stocks`, `get_industry` | [第3章](api_reference.md#3-数据-api) |
| `get_concept_list`, `get_concept_stocks` | [第3章](api_reference.md#3-数据-api) |
| `fetch_minute_data`, `get_price_minute` | [第3章](api_reference.md#3-数据-api) |
| `get_tick_data` | [第3章](api_reference.md#3-数据-api) |
| `get_current_data`, `get_security_info`, `get_trade_days` | [第3章](api_reference.md#3-数据-api) |
| `get_money_flow`, `get_billboard_list`, `get_valuation`, `get_index_weights`, `get_extras` | [第3章](api_reference.md#3-数据-api) |
| `set_universe`, `get_universe` | [第3章](api_reference.md#3-数据-api) |
| `get_fundamentals` | [第3章](api_reference.md#3-数据-api)（链式选股见 **第 3.14 节**） |

### 链式选股（Screening）

| 符号 | 文档 |
|------|------|
| `query`, `valuation`, `get_current_data_object` | [第 3.14 节 链式选股](api_reference.md#314-链式选股-api) |

### 报告与风险分析

| 符号 | 文档 |
|------|------|
| `generate_chart`, `generate_report_md`, `generate_report_json`, `generate_html_report` | [第6章 报告与分析](api_reference.md#6-报告与分析-api) |
| `analyze_returns`, `brinson_attribution`, `fama_french_analysis` | [第6章](api_reference.md#6-报告与分析-api) |

### 组合优化

| 符号 | 文档 |
|------|------|
| `portfolio_optimizer`, `Bound`, `MinVariance`, `MaxSharpe`, `RiskParity` | [第7章](api_reference.md#7-组合优化-api) |

### 缓存与本地 CSV 仓库

| 符号 | 文档 |
|------|------|
| `set_cache_dir`, `fetch_cached`, `estimate_memory_mb` | [第8章](api_reference.md#8-缓存-api) |
| `set_local_data_dir`, `save_stock_local`, `load_stock_local`, `has_local_data`, `list_local_stocks`, `remove_local_data`, `clear_all_local_data` | [第8章](api_reference.md#8-缓存-api) |

### 选股策略框架

| 符号 | 文档 |
|------|------|
| `StockSelector`, `TopNSelector`, `MultiFactorSelector` | [第11章](api_reference.md#11-选股策略-api) |
| `filter_st_stocks`, `filter_paused_stocks`, `filter_low_price_stocks`, `filter_high_pe_stocks`, `fetch_factor_data` | [第11章](api_reference.md#11-选股策略-api) |

### 对象与类型

| 符号 | 文档 |
|------|------|
| `g`, `GlobalObject`, `Context`, `Portfolio`, `Position` | [第1章](api_reference.md#1-策略生命周期结构体) |
| `StrategyConfig`（组合回测配置） | [第4章](api_reference.md#4-回测与模拟盘引擎) |

### 日志与进阶

| 符号 | 文档 |
|------|------|
| `log` | [第9章](api_reference.md#9-日志-api) |
| `engine`（模块）、`BacktestSession`, `get_session` | [第10章](api_reference.md#10-辅助工具-api)；会话与滑点见 [第5章](api_reference.md#5-配置-api) |

### 工具子包

| 符号 | 文档 |
|------|------|
| `utils` | [**utils_reference.md**](utils_reference.md) |

### 券商适配（子模块，避免与回测 API 命名冲突）

```python
from eqlib.ptrade_adapter import *  # 按需导入
```

说明见 [**ptrade_adapter.md**](ptrade_adapter.md)。

---

## 附录导入块（复制用）

与 `api_reference.md` 附录一致，便于在 IDE 中一次性粘贴：

```python
from eqlib import (
    run_backtest, run_strategy, run_portfolio_backtest,
    run_daily, run_weekly, run_monthly, run_selection,
    set_handle_data, record, run_paper_trade,
    set_benchmark, set_option, set_order_cost, set_slippage,
    OrderCost, SlippageModel, FixedSlippage, VolumeSlippage,
    order, order_target, order_value, order_target_value,
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
    log, g, GlobalObject, Context, Portfolio, Position, StrategyConfig,
    generate_chart, generate_report_md, generate_report_json, generate_html_report,
    portfolio_optimizer, Bound, MinVariance, MaxSharpe, RiskParity,
    analyze_returns, brinson_attribution, fama_french_analysis,
    StockSelector, TopNSelector, MultiFactorSelector,
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
    fetch_factor_data,
    set_cache_dir, set_local_data_dir, fetch_cached, estimate_memory_mb,
    save_stock_local, load_stock_local, has_local_data,
    list_local_stocks, remove_local_data, clear_all_local_data,
    BacktestSession, get_session,
)
```

> 注：若某环境未声明全部导出，以 `from eqlib import X` 单符号导入最稳妥。
