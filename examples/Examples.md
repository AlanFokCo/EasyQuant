# Examples

每个示例都是一个可独立运行的脚本。在项目根目录下执行：

```bash
python examples/<示例文件名>.py
```

---

## 01_fetch_data.py — 数据获取基础

演示 eqlib 的基础数据 API：获取历史 OHLCV 行情、下载并保存到 CSV、从本地 CSV 加载数据，以及市场扫描筛选。

**涉及 API：** `get_price`、`fetch_stock_data`、`get_all_securities`、`download_stock_data`、`load_csv`、`scan_market`

**运行方式：**
```bash
python examples/01_fetch_data.py
```

---

## 02_write_strategy.py — 编写交易策略

演示如何用 eqlib API 编写事件驱动的交易策略。包含三个策略：

- **双均线策略** — 金叉买入、死叉卖出
- **RSI 超买超卖策略** — 基于 RSI 指标的均值回归
- **多股票轮动策略** — 等权重每周一调仓

**涉及 API：** `initialize`、`run_daily`、`run_weekly`、`attribute_history`、`order_value`、`order_target`、`record`、`set_benchmark`、`set_order_cost`

**注意：** 这是一个策略模块，不直接运行，被其他示例（如 03、05）导入使用。

---

## 03_run_backtest.py — 运行回测

完整的端到端回测示例。运行双均线策略回测一年，并生成图表（PNG）、报告（Markdown）和数据（JSON）。

**涉及 API：** `run_strategy`、`run_backtest`、`generate_chart`、`generate_report_md`、`generate_report_json`

**运行方式：**
```bash
python examples/03_run_backtest.py
```

**输出：** 报告保存在 `reports/` 目录下。

---

## 04_stock_screener.py — 实时选股

扫描全 A 股市场，按股价、涨跌幅、市盈率筛选，再通过金叉技术指标确认买入信号。支持命令行参数自定义筛选阈值。

**涉及 API：** `scan_market`、`check_golden_cross`

**运行方式：**
```bash
# 使用默认参数
python examples/04_stock_screener.py

# 自定义筛选条件
python examples/04_stock_screener.py --min-price 15 --min-pct 2 --max-pct 6 --max-pe 40
```

---

## 05_paper_trade.py — 模拟盘交易

使用实时行情数据运行策略模拟交易。模拟成交但不会发送真实订单。持续运行直到按 Ctrl+C 停止。

**涉及 API：** `run_paper_trade`

**运行方式：**
```bash
# 使用内置双均线策略
python examples/05_paper_trade.py

# 加载自定义策略文件
python examples/05_paper_trade.py --strategy examples/02_write_strategy

# 自定义资金和刷新间隔
python examples/05_paper_trade.py --cash 200000 --interval 120
```

---

## 06_advanced_api.py — 高级 API：调度、组合优化、归因分析

演示 eqlib 高级功能：

- **策略调度** — `run_weekly` 按周调仓、`run_monthly` 按月调仓
- **组合优化** — 最小方差、最大夏普、风险平价三种优化方式
- **归因分析** — 风险收益指标、Brinson 归因分解、Fama-French 因子分析

**涉及 API：** `portfolio_optimizer`、`MinVariance`、`MaxSharpe`、`RiskParity`、`analyze_returns`、`brinson_attribution`、`fama_french_analysis`

**运行方式：**
```bash
python examples/06_advanced_api.py
```

---

## 07_market_data.py — 扩展数据 API

演示高级数据获取能力：

- 财务摘要与财务报表
- 按财务指标（P/E、P/B）筛选股票
- 指数成分股与权重
- 行业板块及其成分股
- 分钟级 K 线数据（1分钟、5分钟、15分钟）
- 当日分笔成交 Tick 数据

**涉及 API：** `get_financial_abstract`、`get_financial_screen`、`get_index_stocks`、`get_industry_list`、`get_industry_stocks`、`fetch_minute_data`、`get_price_minute`、`get_tick_data`

**运行方式：**
```bash
python examples/07_market_data.py
```

---

## 08_lifecycle_callbacks.py — 生命周期回调与股票池管理

演示如何使用生命周期钩子和动态股票池管理：

- `before_trading_start` — 每个交易日开盘前回调（如 ST 股检测）
- `after_trading_end` — 收盘后组合统计
- `set_universe` / `get_universe` — 动态设置和获取股票池
- `get_trade_days` — 交易日历查询
- `run_monthly` — 每月调仓

**涉及 API：** `before_trading_start`、`after_trading_end`、`set_universe`、`get_universe`、`get_trade_days`、`run_monthly`、`get_extras`

**运行方式：**
```bash
python examples/08_lifecycle_callbacks.py
```

---

## 09_attribution_analysis.py — 绩效归因分析

多股票动量策略 + 完整的回测后分析：

- **绩效指标** — 夏普比率、索提诺比率、最大回撤、Calmar 比率、Alpha、Beta、日胜率
- **Brinson 归因** — 配置效应、选股效应、交互效应
- **因子分析** — 市场 Beta、Alpha、动量相关性、残差波动率
- **报告生成** — 图表、Markdown 报告、JSON 数据

**涉及 API：** `analyze_returns`、`brinson_attribution`、`fama_french_analysis`、`generate_chart`、`generate_report_md`、`generate_report_json`

**运行方式：**
```bash
python examples/09_attribution_analysis.py
```

---

## 10_index_concept.py — 指数与概念策略

从指数成分股构建策略股票池，探索概念/主题板块：

- 获取指数成分股及权重
- 概念板块及其成分股查询
- 运行基于动量的指数策略，每周调仓

**涉及 API：** `get_index_stocks`、`get_index_weights`、`get_concept_list`、`get_concept_stocks`、`get_industry`

**运行方式：**
```bash
python examples/10_index_concept.py
```

---

## 11_utils_library.py — 工具库：技术指标 / 统计 / 资金管理 / 支撑阻力位

全面演示 `eqlib.utils` 中的计算工具：

- **技术指标** — 均线（MA/EMA/SMA/WMA）、MACD、RSI、KDJ、布林带、ATR、CCI、威廉指标、ROC、OBV、ADX、金叉/死叉检测
- **统计分析** — 滚动夏普比率、滚动 Beta、Z-Score、百分位排名、线性回归、最大回撤、VaR/CVaR、CAGR
- **资金管理** — Kelly Criterion、固定比例风险仓位、ATR 仓位管理、波动率目标、马丁格尔/反马丁格尔、风险平价权重
- **支撑阻力位** — 五种枢轴点（Classic/Fibonacci/Woodie/Camarilla/DeMark）、摆动高低点聚类、斐波那契回撤、唐奇安通道、成交量分布（POC/VAH/VAL）、整数心理价位、ATR 追踪止损、缺口检测

**涉及 API：** `utils.ma`、`utils.ema`、`utils.macd`、`utils.rsi`、`utils.kdj`、`utils.boll`、`utils.atr`、`utils.adx`、`utils.rolling_sharpe`、`utils.value_at_risk`、`utils.max_drawdown`、`utils.cagr`、`utils.kelly_criterion`、`utils.atr_position_size`、`utils.fixed_fraction_size`、`utils.risk_parity_weights`、`utils.pivot_classic`、`utils.support_resistance_levels`、`utils.fibonacci_retracement`、`utils.donchian`、`utils.volume_profile_support_resistance`、`utils.trailing_stop`、`utils.gap_up_down`

**运行方式：**
```bash
python examples/11_utils_library.py
```

---

## 12_portfolio_backtest.py — 组合回测模式

使用 `StrategyConfig` 和 `run_portfolio_backtest` 进行多股票组合回测：

- 定义初始资金、股票池、每只股票的仓位比例
- 策略函数遍历 `context.universe`，从股票池中选择标的交易
- 自动生成包含每只股票操作明细、整体盈亏、与大盘对比的综合报告
- 通过 `report_suffix` 参数区分不同版本或参数的回测结果

**涉及 API：** `StrategyConfig`、`run_portfolio_backtest`、`context.universe`、`order_value`、`order_target`

**运行方式：**
```bash
python examples/12_portfolio_backtest.py
```

---

## 13_ptrade_export.py — 导出 PTrade/QMT 策略

将 EasyQuant 策略一键转换为 PTrade/QMT 平台可运行的格式：

- 自动生成 QMT 所需的 `init()` / `handlebar()` 入口函数
- 透明转换股票代码格式（`601390` → `601390.SH`）
- 兼容 EasyQuant 的全部 API：`attribute_history`、`order_value`、`run_daily` 等
- 提供 `start()` / `on_bar()` 生命周期桥接

**涉及 API：** `start`、`on_bar`、`export_ptrade_script`、`QMT_TEMPLATE`

**运行方式：**
```bash
# 生成 QMT 策略文件
python examples/13_ptrade_export.py

# 输出 ptrade_strategy.py，复制到 QMT 编辑器即可运行
```

---

## 14_bollinger_strategy.py — 布林带均值回归策略

演示经典的布林带均值回归策略：

- 价格触及下轨买入，触及上轨卖出
- 内置止损机制（亏损超过设定比例强制平仓）
- 适合震荡市中的高抛低吸操作

**涉及 API：** `utils.boll`、`order_value`、`order_target`、`set_order_cost`

**运行方式：**
```bash
python examples/14_bollinger_strategy.py
```

---

## 15_macd_volume_strategy.py — MACD 趋势跟踪 + 成交量确认

演示结合 MACD 和成交量的趋势跟踪策略：

- MACD 金叉/死叉判断趋势方向
- 成交量放大确认信号有效性
- ATR 追踪止损，根据波动率动态调整止损位

**涉及 API：** `utils.macd`、`utils.atr`、`order_value`、`order_target`

**运行方式：**
```bash
python examples/15_macd_volume_strategy.py
```

---

## 16_multi_factor_strategy.py — 多因子选股 + 每周轮动

演示多因子量化选股策略：

- 动量因子：过去 20 天收益率
- 成交量因子：短期成交量与长期均值的比值
- 价格过滤：排除低价股和高价股
- 每周一调仓，等权配置排名前 N 的股票

**涉及 API：** `run_weekly`、`attribute_history`、`context.universe`、`order_value`

**运行方式：**
```bash
python examples/16_multi_factor_strategy.py
```

---

## 17_grid_trading_strategy.py — 网格交易策略

演示适用于震荡市的网格交易策略：

- 设定价格区间并划分为 N 个网格级别
- 价格下跌到网格级别时买入一批
- 价格上涨到网格级别时卖出一批
- 从价格的上下波动中获利

适合低波动、区间震荡的股票（如银行股）。

**涉及 API：** `order_value`、`order`、`attribute_history`

**运行方式：**
```bash
python examples/17_grid_trading_strategy.py
```

---

## 18_strategy_comparison.py — 多策略对比

在同一只股票和同一时间段内，横向对比多种策略的表现：

- 买入持有（基准）
- 均线交叉（趋势跟踪）
- RSI 均值回归（反向交易）
- 布林带（均值回归）

输出格式化的对比表格，按夏普比率排序，便于客观评估哪种方法更有效。

**涉及 API：** `run_backtest`、`analyze_returns`、`record`

**运行方式：**
```bash
python examples/18_strategy_comparison.py
```

---

## 19_local_data_backtest.py — 本地数据回测模式

演示 `use_local` 参数的用法：

- 首次运行：从网络下载数据，保存到本地 CSV
- 后续运行：从本地 CSV 加载数据，无需网络
- 手动管理：列出、下载、删除本地数据文件

适合以下场景：
- 离线回测（无网络环境）
- 节省重复下载的时间
- 管理自己的历史数据版本
- 批量预下载数据

**涉及 API：** `use_local`、`has_local_data`、`list_local_stocks`、`save_stock_local`、`clear_all_local_data`

**运行方式：**
```bash
# 首次运行 — 下载数据并回测
python examples/19_local_data_backtest.py

# 再次运行 — 使用本地数据（无网络请求）
python examples/19_local_data_backtest.py

# 查看本地数据列表
python examples/19_local_data_backtest.py --list

# 批量预下载数据
python examples/19_local_data_backtest.py --download-all
```

---

## 21_combined_strategy/ — 全天候 Alpha 综合策略（生产级综合案例）

将所有教程和示例的策略技术融合为一个完整的、可投入实盘的综合策略：

策略逻辑（四层架构）：
- **第一层**：多因子选股 — 动量（35%）+ 成交量（30%）+ 反转修正（15%）+ 低波动率（20%）
  四因子经 Z-Score 标准化后加权合成，每周选出 Top 5 股票
- **第二层**：行业轮动加成 — 对各行业代表股计算 10 日动量，以 +10% 权重加成综合得分
- **第三层**：技术指标入场/离场 — RSI + 布林带（入场超卖确认）、MACD 金叉/死叉（趋势确认）、
  成交量确认（量比 ≥ 1.2×）、支撑阻力位（精确位置确认）、ATR 追踪止损 + 唐奇安通道
- **第四层**：风险管理 — 硬止损 -8%、每股最大仓位 20%（最多 5 只）、生命周期回调集成

**股票池（12 只，覆盖 8 个行业）：**
  601398（工商银行）、600519（贵州茅台）、002594（比亚迪）、601857（中国石油）、
  601088（中国神华）、601390（中国中铁）、600276（恒瑞医药）、000333（美的集团）、
  600916（中国黄金）、000858（五粮液）、601318（中国平安）、600887（伊利股份）

**涉及 API：** `utils.rsi`、`utils.boll`、`utils.macd`、`utils.atr`、`utils.donchian`、
`utils.support_resistance_levels`、`before_trading_start`、`after_trading_end`、
`run_weekly`、`run_daily`、`order_value`、`order_target`、`record`、`analyze_returns`

**运行方式：**
```bash
# 回测（约 60 秒）
python examples/21_combined_strategy/run_backtest.py

# 模拟盘（持续运行，按 Ctrl+C 停止）
python examples/21_combined_strategy/run_paper_trade.py
```

**配套教程：** [Tutorial 09: 全天候 Alpha 综合策略](../tutorials/09_combined_strategy.md)

---

## 20_sr_strategy/ — 支撑阻力位组合策略（完整实盘案例）

一个真实的多股票组合策略实战案例：基于支撑阻力位、RSI、MACD、ATR 和唐奇安通道，
在 8 只不同行业的 A 股中进行交易。

策略逻辑：
- **买入**：价格接近支撑位 + RSI 超卖 或 MACD 金叉
- **卖出**：价格接近阻力位 + RSI 超买 或 MACD 死叉
- **止损**：ATR 追踪止损
- **仓位**：每只股票最多 25% 资金，等权配置

回测结果（2020-01-01 至 2026-03-30）：
- 初始资金：1,000,000
- 最终价值：2,371,889.70
- 总收益率：+137.19%
- 交易次数：226 笔

本目录包含完整的策略代码、回测脚本和预生成的报告文件（PNG、HTML、Markdown、JSON），
用户可以查看报告了解策略表现，也可以直接运行回测验证。

**涉及 API：** `utils.support_resistance_levels`、`utils.rsi`、`utils.macd`、`utils.atr`、`utils.donchian`、`order_value`、`order_target`、`record`

**运行方式：**
```bash
# 查看预生成的报告
# 打开 examples/20_sr_strategy/sr_backtest.html（浏览器）

# 运行回测（需要 data/ 目录中的本地数据）
python examples/20_sr_strategy/run_backtest.py
```

---

## 速查表

| # | 文件 | 主题 | 运行时间 |
|---|------|------|---------|
| 01 | `01_fetch_data.py` | 数据获取基础 | ~10s |
| 02 | `02_write_strategy.py` | 策略编写（模块，不直接运行） | N/A |
| 03 | `03_run_backtest.py` | 完整回测 + 报告生成 | ~15s |
| 04 | `04_stock_screener.py` | 市场扫描选股 | ~30s |
| 05 | `05_paper_trade.py` | 实时模拟盘 | 持续运行，按 Ctrl+C 停止 |
| 06 | `06_advanced_api.py` | 组合优化 + 归因分析 | ~30s |
| 07 | `07_market_data.py` | 扩展数据 API | ~30s |
| 08 | `08_lifecycle_callbacks.py` | 生命周期回调 + 股票池 | ~15s |
| 09 | `09_attribution_analysis.py` | 绩效归因 | ~15s |
| 10 | `10_index_concept.py` | 指数与概念策略 | ~30s |
| 11 | `11_utils_library.py` | 工具库：技术指标 / 统计 / 资金管理 / 支撑阻力位 | ~5s |
| 12 | `12_portfolio_backtest.py` | 组合回测模式（StrategyConfig） | ~15s |
| 13 | `13_ptrade_export.py` | 导出 PTrade/QMT 策略 | ~1s |
| 14 | `14_bollinger_strategy.py` | 布林带均值回归策略 | ~15s |
| 15 | `15_macd_volume_strategy.py` | MACD 趋势跟踪 + 成交量确认 | ~15s |
| 16 | `16_multi_factor_strategy.py` | 多因子选股 + 每周轮动 | ~30s |
| 17 | `17_grid_trading_strategy.py` | 网格交易策略 | ~15s |
| 18 | `18_strategy_comparison.py` | 多策略横向对比（同股同时段） | ~30s |
| 19 | `19_local_data_backtest.py` | 本地数据回测模式（下载一次，离线回测） | ~15s |
| 20 | `20_sr_strategy/` | 支撑阻力位组合策略（完整实盘案例） | ~30s |
| 21 | `21_combined_strategy/` | 全天候 Alpha 综合策略（多因子+行业轮动+RSI/MACD/布林+ATR） | ~60s |

## 环境要求

```bash
pip install akshare pandas numpy matplotlib scipy
```

## 注意事项

- 示例 04 和 07 需要连接实时行情，建议在交易时段运行以获得完整结果。
- 示例 05 持续运行，按 Ctrl+C 停止。
- 回测报告（03、08、09、10）保存到 `reports/` 目录。
- 所有示例的日志和输出均使用英文。底层 akshare API 的中文列名在内部转换，不影响用户输出。
