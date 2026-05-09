# Examples（示例总览）

本文件是 `examples/` 目录的准确导航与快速入口，按实际文件整理。

## 快速开始

在项目根目录执行：

```bash
python examples/<file>.py
```

安装依赖（如未安装）：

```bash
pip install -e ".[dev]"
```

---

## 示例清单（01-22）

| # | 文件/目录 | 说明 | 运行命令 |
|---|---|---|---|
| 01 | `01_fetch_data.py` | 基础数据 API：历史行情、CSV、本地加载、市场扫描 | `python examples/01_fetch_data.py` |
| 02 | `02_write_strategy.py` | 策略编写模板（双均线、RSI、多股轮动）；供其他示例导入 | 不直接运行 |
| 03 | `03_run_backtest.py` | 端到端回测 + 图表/报告输出 | `python examples/03_run_backtest.py` |
| 04 | `04_stock_screener.py` | 实时选股（价格/涨跌幅/PE + 金叉） | `python examples/04_stock_screener.py` |
| 05 | `05_paper_trade.py` | 模拟盘（实时行情轮询，不下真实单） | `python examples/05_paper_trade.py` |
| 06 | `06_advanced_api.py` | 调度、组合优化、归因分析 | `python examples/06_advanced_api.py` |
| 07 | `07_market_data.py` | 财务/行业/指数/分钟线/tick 数据接口演示 | `python examples/07_market_data.py` |
| 08 | `08_lifecycle_callbacks.py` | 生命周期回调、股票池管理 | `python examples/08_lifecycle_callbacks.py` |
| 09 | `09_attribution_analysis.py` | 绩效指标 + Brinson + 因子分析 | `python examples/09_attribution_analysis.py` |
| 10 | `10_index_concept.py` | 指数与概念策略 | `python examples/10_index_concept.py` |
| 11 | `11_utils_library.py` | `eqlib.utils` 全量工具示例（指标/统计/资金管理/支撑阻力） | `python examples/11_utils_library.py` |
| 12 | `12_portfolio_backtest.py` | `StrategyConfig` 组合回测 | `python examples/12_portfolio_backtest.py` |
| 13 | `13_ptrade_export.py` | 导出 PTrade/QMT 策略脚本 | `python examples/13_ptrade_export.py` |
| 14 | `14_bollinger_strategy.py` | 布林带均值回归策略 | `python examples/14_bollinger_strategy.py` |
| 15 | `15_macd_volume_strategy.py` | MACD + 成交量确认 + ATR 止损 | `python examples/15_macd_volume_strategy.py` |
| 16 | `16_multi_factor_strategy.py` | 多因子选股 + 周调仓 | `python examples/16_multi_factor_strategy.py` |
| 17 | `17_grid_trading_strategy.py` | 网格交易策略 | `python examples/17_grid_trading_strategy.py` |
| 18 | `18_strategy_comparison.py` | 多策略同标的同周期对比 | `python examples/18_strategy_comparison.py` |
| 19 | `19_local_data_backtest.py` | 本地数据回测（下载/列出/清理本地数据） | `python examples/19_local_data_backtest.py` |
| 20 | `20_sr_strategy/` | 支撑阻力位组合策略完整案例（含预生成报告） | `python examples/20_sr_strategy/run_backtest.py` |
| 21 | `21_combined_strategy/` | 全天候 Alpha 综合策略（回测+模拟盘） | `python examples/21_combined_strategy/run_backtest.py` |
| 22 | `22_stock_selection_strategy.py` | `run_selection` 选股接口（三种写法） | `python examples/22_stock_selection_strategy.py` |

---

## 常用命令（补充）

### 04 实时选股参数

```bash
python examples/04_stock_screener.py --min-price 15 --min-pct 2 --max-pct 6 --max-pe 40
```

### 05 模拟盘参数

```bash
python examples/05_paper_trade.py --strategy examples/02_write_strategy --cash 200000 --interval 120
```

### 19 本地数据管理

```bash
python examples/19_local_data_backtest.py --list
python examples/19_local_data_backtest.py --download-all
```

### 21 综合策略模拟盘

```bash
python examples/21_combined_strategy/run_paper_trade.py --cash 500000 --interval 60
```

---

## 运行与行为说明

- 示例 04、07、05 依赖实时行情，建议交易时段运行。
- 示例 05 为持续运行脚本，使用 `Ctrl+C` 停止。
- 本地回测中，`order*` 是下单请求：先进入队列，再在下一交易日开盘价撮合成交。
- 模拟盘（paper trade）使用实时价格进行模拟成交。
- 回测报告通常输出到 `reports/` 目录（具体以脚本参数为准）。

---

## 相关文档

- `examples/20_sr_strategy/README.md`
- `examples/21_combined_strategy/README.md`
- `tutorials/09_combined_strategy.md`
