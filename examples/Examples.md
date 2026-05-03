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

## 环境要求

```bash
pip install akshare pandas numpy matplotlib scipy
```

## 注意事项

- 示例 04 和 07 需要连接实时行情，建议在交易时段运行以获得完整结果。
- 示例 05 持续运行，按 Ctrl+C 停止。
- 回测报告（03、08、09、10）保存到 `reports/` 目录。
- 所有示例的日志和输出均使用英文。底层 akshare API 的中文列名在内部转换，不影响用户输出。
