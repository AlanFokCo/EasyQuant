# Examples（示例总览）

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 按编号快速定位 `examples/` 下脚本用途与推荐运行方式 |
    | **前置** | 在仓库根目录执行 `pip install .`（或 `pip install -e .`） |

本文件是 `examples/` 目录的准确导航与快速入口，按实际文件整理。

## 快速开始

在仓库根目录安装 `eqlib`（如未安装）：

```bash
pip install -e .
```

运行示例：

```bash
python examples/<file>.py
```

依赖：`akshare`、`pandas`、`numpy`、`matplotlib`、`scipy`（见项目 `pyproject.toml`）。多数回测示例使用 `use_local=True`：首次会下载并写入 `data/`，之后优先读本地 CSV。

## 示例清单

| # | 文件/目录 | 说明 | 运行命令 |
|---|---|---|---|
| 01 | `01_fetch_data.py` | 基础数据 API：历史行情、CSV、本地加载、市场扫描 | `python examples/01_fetch_data.py` |
| 02 | `02_write_strategy.py` | 策略编写模板（双均线、RSI、多股轮动） | 不直接运行 |
| 03 | `03_run_backtest.py` | 端到端回测 + 图表/报告输出 | `python examples/03_run_backtest.py` |
| 04 | `04_stock_screener.py` | 实时选股（价格/涨跌幅/PE + 金叉） | `python examples/04_stock_screener.py` |
| 05 | `05_paper_trade.py` | 模拟盘（实时行情轮询） | `python examples/05_paper_trade.py` |
| 06 | `06_advanced_api.py` | 调度、组合优化、归因分析 | `python examples/06_advanced_api.py` |
| 07 | `07_market_data.py` | 财务/行业/指数/分钟线/tick 数据接口 | `python examples/07_market_data.py` |
| 08 | `08_lifecycle_callbacks.py` | 生命周期回调、股票池管理 | `python examples/08_lifecycle_callbacks.py` |
| 09 | `09_attribution_analysis.py` | 绩效指标 + Brinson + 因子分析 | `python examples/09_attribution_analysis.py` |
| 10 | `10_index_concept.py` | 指数与概念策略 | `python examples/10_index_concept.py` |
| 11 | `11_utils_library.py` | `eqlib.utils` 全量工具示例 | `python examples/11_utils_library.py` |
| 12 | `12_portfolio_backtest.py` | `StrategyConfig` 组合回测 | `python examples/12_portfolio_backtest.py` |
| 13 | `13_ptrade_export.py` | 导出 PTrade/QMT 策略脚本 | `python examples/13_ptrade_export.py` |
| 14 | `14_bollinger_strategy.py` | 布林带均值回归策略 | `python examples/14_bollinger_strategy.py` |
| 15 | `15_macd_volume_strategy.py` | MACD + 成交量确认 + ATR 止损 | `python examples/15_macd_volume_strategy.py` |
| 16 | `16_multi_factor_strategy.py` | 多因子选股 + 周调仓 | `python examples/16_multi_factor_strategy.py` |
| 17 | `17_grid_trading_strategy.py` | 网格交易策略 | `python examples/17_grid_trading_strategy.py` |
| 18 | `18_strategy_comparison.py` | 多策略同标的同周期对比 | `python examples/18_strategy_comparison.py` |
| 19 | `19_local_data_backtest.py` | 本地数据回测（下载/列出/清理本地数据） | `python examples/19_local_data_backtest.py` |
| 20 | `20_sr_strategy/` | 支撑阻力位组合策略完整案例 | `python examples/20_sr_strategy/run_backtest.py` |
| 21 | `21_combined_strategy/` | 全天候 Alpha 综合策略 | `python examples/21_combined_strategy/run_backtest.py` |
| 22 | `22_stock_selection_strategy.py` | `run_selection` 选股接口（三种写法） | `python examples/22_stock_selection_strategy.py` |
| 23 | `23_small_cap_query_example.py` | 小市值选股（query/valuation 链式筛选） | `python examples/23_small_cap_query_example.py` |
| 24 | `24_quick_report_test.py` | 快速回测验证报告格式 | `python examples/24_quick_report_test.py` |

---

## 06 — 高级 API：调度、组合优化、归因分析

演示 eqlib 高级功能：策略调度（`run_weekly`/`run_monthly`）、组合优化（最小方差/最大夏普/风险平价）、归因分析（Brinson + Fama-French）。

**涉及 API：** `portfolio_optimizer`、`MinVariance`、`MaxSharpe`、`RiskParity`、`analyze_returns`、`brinson_attribution`、`fama_french_analysis`

## 07 — 扩展数据 API

财务摘要与报表、按财务指标筛选、指数成分股与权重、行业/概念板块、分钟线 K 线、Tick 数据。

**涉及 API：** `get_financial_abstract`、`get_financial_screen`、`get_index_stocks`、`get_industry_list`、`get_industry_stocks`、`fetch_minute_data`、`get_price_minute`、`get_tick_data`

## 08 — 生命周期回调与股票池管理

`before_trading_start`（开盘前回调）、`after_trading_end`（收盘后统计）、`set_universe` / `get_universe`（动态股票池）、`run_monthly`（每月调仓）。

**涉及 API：** `before_trading_start`、`after_trading_end`、`set_universe`、`get_universe`、`get_trade_days`、`run_monthly`、`get_extras`

## 09 — 绩效归因分析

多股票动量策略 + 完整的回测后分析：绩效指标、Brinson 归因、Fama-French 因子分析、报告生成。

**涉及 API：** `analyze_returns`、`brinson_attribution`、`fama_french_analysis`、`generate_chart`、`generate_report_md`、`generate_report_json`

## 10 — 指数与概念策略

从指数成分股构建策略股票池，探索概念/主题板块。

**涉及 API：** `get_index_stocks`、`get_index_weights`、`get_concept_list`、`get_concept_stocks`、`get_industry`

## 11 — 工具库

全面演示 `eqlib.utils`：技术指标（MA/EMA/MACD/RSI/KDJ/布林带/ATR/ADX/CCI/威廉指标/ROC/OBV）、统计分析（滚动夏普/Beta/Z-Score/VaR/CVaR/CAGR）、资金管理（Kelly/ATR 仓位/固定比例/风险平价）、支撑阻力位（枢轴点/斐波那契/唐奇安/成交量分布/缺口检测/追踪止损）。

**涉及 API：** `utils.ma`、`utils.ema`、`utils.macd`、`utils.rsi`、`utils.kdj`、`utils.boll`、`utils.atr`、`utils.adx`、`utils.rolling_sharpe`、`utils.value_at_risk`、`utils.max_drawdown`、`utils.cagr`、`utils.kelly_criterion`、`utils.atr_position_size`、`utils.fixed_fraction_size`、`utils.risk_parity_weights`、`utils.pivot_classic`、`utils.support_resistance_levels`、`utils.fibonacci_retracement`、`utils.donchian`、`utils.volume_profile_support_resistance`、`utils.trailing_stop`、`utils.gap_up_down`

## 12 — 组合回测模式

使用 `StrategyConfig` 和 `run_portfolio_backtest` 进行多股票组合回测，通过 `report_suffix` 参数区分不同版本。

**涉及 API：** `StrategyConfig`、`run_portfolio_backtest`、`context.universe`、`order_value`、`order_target`

## 13 — 导出 PTrade/QMT 策略

将 EasyQuant 策略一键转换为 PTrade/QMT 平台可运行的格式，自动转换股票代码格式，兼容全部 API。

**涉及 API：** `start`、`on_bar`、`export_ptrade_script`、`QMT_TEMPLATE`

## 14 — 布林带均值回归策略

价格触及下轨买入，触及上轨卖出，内置止损机制。适合震荡市中的高抛低吸操作。

**涉及 API：** `utils.boll`、`order_value`、`order_target`、`set_order_cost`

## 15 — MACD 趋势跟踪 + 成交量确认

MACD 金叉/死叉判断趋势方向，成交量放大确认信号，ATR 追踪止损。

**涉及 API：** `utils.macd`、`utils.atr`、`order_value`、`order_target`

## 16 — 多因子选股 + 每周轮动

动量因子 + 成交量因子 + 价格过滤，每周一调仓，等权配置排名前 N 的股票。

**涉及 API：** `run_weekly`、`attribute_history`、`context.universe`、`order_value`

## 17 — 网格交易策略

设定价格区间并划分为 N 个网格级别，价格下跌买入，价格上涨卖出。适合低波动、区间震荡的股票。

**涉及 API：** `order_value`、`order`、`attribute_history`

## 18 — 多策略对比

在同一只股票和同一时间段内，横向对比买入持有、均线交叉、RSI 均值回归、布林带四种策略表现。

**涉及 API：** `run_backtest`、`analyze_returns`、`record`

## 19 — 本地数据回测模式

首次运行从网络下载数据保存到本地 CSV，后续运行从本地加载无需网络。适合离线回测和批量预下载。

**涉及 API：** `use_local`、`has_local_data`、`list_local_stocks`、`save_stock_local`、`clear_all_local_data`

## 20 — 支撑阻力位组合策略（完整实盘案例）

基于支撑阻力位、RSI、MACD、ATR 和唐奇安通道的多股票组合策略，在 8 只不同行业的 A 股中进行交易。

**涉及 API：** `utils.support_resistance_levels`、`utils.rsi`、`utils.macd`、`utils.atr`、`utils.donchian`、`order_value`、`order_target`、`record`

## 21 — 全天候 Alpha 综合策略

多因子 + 行业轮动 + RSI/MACD/布林带 + ATR 止损的综合策略。

## 22 — 定期选股调仓

`run_selection` 选股接口：ST/PB/动量过滤 + 多因子打分 + Top-N 选股，支持普通函数、StockSelector 子类、`run_strategy` 参数三种方式。

**涉及 API：** `run_selection`、`filter_st_stocks`、`filter_paused_stocks`、`TopNSelector`、`MultiFactorSelector`、`fetch_factor_data`

## 23 — 小市值选股（query API）

演示 `query()` / `valuation` / `get_fundamentals()` 链式筛选 API。

**涉及 API：** `query`、`valuation`、`get_fundamentals`、`filter_paused_stocks`、`order_value`、`order_target_value`

## 24 — 快速回测验证

快速运行简单回测，验证 PNG/HTML/MD/JSON 四类报告输出格式是否正常。适合在修改报告代码后快速验证。

**涉及 API：** `run_backtest`、`generate_chart`、`generate_html_report`、`generate_report_md`、`generate_report_json`、`analyze_returns`

---

## 运行与行为说明

- 示例 04、07、05 依赖实时行情，建议交易时段运行。
- 示例 05、21 的模拟盘为持续运行脚本，使用 `Ctrl+C` 停止。
- 本地回测中，`order*` 是下单请求：先进入队列，再在下一交易日开盘价撮合成交。
- 回测报告通常输出到 `reports/` 目录。
- 多数回测示例带 `use_local=True`：配合 `examples/19_local_data_backtest.py` 预下载后，可显著减少重复请求。
