# Examples（示例总览）

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 按编号快速定位 `examples/` 下脚本用途与推荐运行方式 |
    | **前置** | 在仓库根目录执行 `pip install -e .` |

20 个示例，三层递进式学习路径：基础（01-07）→ 进阶（08-14）→ 实战（15-20），并扩展 ML 层（21-24）。

## 快速开始

在仓库根目录安装 `eqlib`（如未安装）：

```bash
pip install -e .
```

运行示例：

```bash
python examples/<file>.py
```

所有示例使用相对日期和统一的交易成本配置（`examples/_defaults.py`）。

---

## 基础层（01-07）：入门必学

| # | 文件 | 说明 | 运行命令 |
|---|------|------|----------|
| 01 | `01_fetch_data.py` | 数据 API：历史行情、CSV 下载、市场扫描 | `python examples/01_fetch_data.py` |
| 02 | `02_write_strategy.py` | 策略模板：双均线交叉、`initialize`/`run_daily`/`g` 对象 | `python examples/02_write_strategy.py` |
| 03 | `03_run_backtest.py` | 底层回测：`run_backtest`、交易日志、`analyze_returns` | `python examples/03_run_backtest.py` |
| 04 | `04_stock_screener.py` | 选股工具：`scan_market`、金叉检测、解禁过滤、`query()` API | `python examples/04_stock_screener.py` |
| 05 | `05_reports.py` | 报告生成：PNG/HTML/MD/JSON 四种格式 + 指标字典参考 | `python examples/05_reports.py` |
| 06 | `06_local_data.py` | 本地数据：下载缓存、`use_local=True` 回测 | `python examples/06_local_data.py` |
| 07 | `07_lifecycle.py` | 生命周期：`before_trading_start`、ST 检测、月度调仓 | `python examples/07_lifecycle.py` |

---

## 进阶层（08-14）：分析工具与 A 股特色

| # | 文件 | 说明 | 运行命令 |
|---|------|------|----------|
| 08 | `08_utils_library.py` | `utils.*` 工具库：技术指标、统计、资金管理 | `python examples/08_utils_library.py` |
| 09 | `09_attribution.py` | 绩效归因：`brinson_attribution`、`simple_factor_analysis` | `python examples/09_attribution.py` |
| 10 | `10_index_concept.py` | 指数/概念/行业：成分股、板块轮动 | `python examples/10_index_concept.py` |
| 11 | `11_portfolio_backtest.py` | 组合回测：`StrategyConfig`、`PortfolioRiskMonitor` | `python examples/11_portfolio_backtest.py` |
| 12 | `12_paper_trade.py` | 模拟盘：`run_paper_trade`、Webhook 通知 | `python examples/12_paper_trade.py` |
| 13 | `13_ashare_sentiment.py` | A 股情绪：北向资金、融资融券、涨跌停、综合情绪 | `python examples/13_ashare_sentiment.py` |
| 14 | `14_portfolio_risk.py` | 组合风控：VaR、相关性、集中度、熔断机制 | `python examples/14_portfolio_risk.py` |

---

## 实战层（15-20）：完整策略项目

| # | 文件/目录 | 策略 | 核心技术 | 运行命令 |
|---|-----------|------|----------|----------|
| 15 | `15_bollinger_strategy.py` | 布林带均值回归 | `utils.boll()`、ATR 追踪止损 | `python examples/15_bollinger_strategy.py` |
| 16 | `16_macd_volume.py` | MACD 趋势跟踪 | `utils.macd()`、成交量确认 | `python examples/16_macd_volume.py` |
| 17 | `17_multi_factor.py` | 多因子选股 | Z-Score 打分、北向资金门控 | `python examples/17_multi_factor.py` |
| 18 | `18_grid_trading.py` | 网格交易 | 价格网格、区间震荡检测 | `python examples/18_grid_trading.py` |
| 19 | `19_sr_portfolio/` | 支撑阻力位组合 | S/R 水平、RSI/MACD 确认 | `python examples/19_sr_portfolio/run_backtest.py` |
| 20 | `20_all_weather_alpha/` | 全天候 Alpha | 多因子 + 行业轮动 + 风控 | `python examples/20_all_weather_alpha/run_backtest.py` |

---

## 机器学习层（21-24）：ML 驱动选股

| # | 文件 | 策略 | 核心技术 | 运行命令 |
|---|------|------|----------|----------|
| 21 | `21_ml_selector.py` | ML 选股 | `MLSelector`、`past_return_5d` 标签、随机森林 | `python examples/21_ml_selector.py` |
| 22 | `22_feature_pipeline.py` | 特征管道独立使用 | `FeaturePipeline`、RSI/MACD/ATR 工程 | `python examples/22_feature_pipeline.py` |
| 23 | `23_model_comparison.py` | 模型对比 | RandomForest vs LogisticRegression | `python examples/23_model_comparison.py` |
| 24 | `24_custom_features.py` | 自定义特征 | 价格/MA 比率、成交量激增注入 pipeline | `python examples/24_custom_features.py` |

!!! warning "ML 单日训练局限"

    `MLSelector` 默认使用**单日横截面数据**训练。当 universe 较小
    （<50 只）时样本量不足，模型无法学到有意义的模式。如需稳健训练，
    请通过 `label_data` 传入 panel DataFrame。详见
    [ML 选股教程](../tutorials/11-ml-selection.md)。

---

## 交易成本标准

所有示例使用统一的 2024 年费率（`examples/_defaults.py`）：

| 费用 | 费率 | 说明 |
|------|------|------|
| 印花税 | 0.05% | 仅卖出收取（2023年8月起减半） |
| 佣金 | 0.025% | 买卖双向（含规费） |
| 最低佣金 | 5 元 | 每笔交易 |

---

## 共享基础设施

- **`examples/_defaults.py`** — 统一的交易成本、股票代码、相对日期、数据验证
- **`tests/test_examples_smoke.py`** — 冒烟测试：语法检查、导入检查、代码规范

---

## 运行说明

- 回测示例输出报告到 `reports/` 目录
- 示例 12 的模拟盘为持续运行脚本，使用 `Ctrl+C` 停止
- 本地回测中，`order*` 是下单请求：在下一交易日开盘价撮合成交（T+1）
- 首次运行建议使用 `python examples/06_local_data.py --download` 预下载数据
