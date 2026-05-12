# reports/ 目录说明

本目录存放 **`run_strategy` / `run_portfolio_backtest` 等生成的回测产物**（HTML、PNG、Markdown、JSON）。默认被 `.gitignore` 忽略（避免把大量二进制与重复结果提交进 Git），**仅本说明文件 `README.md` 会纳入版本库**。

你在自己机器上跑示例后，会得到与下列**相同类型**的文件；文件名中的时间戳每次运行都会变化。

---

## 示例结果（供对照教程与文档）

以下文件来自仓库维护者最近一次本地运行（2026-05-11/12），**便于你在教程里对照「长什么样」**；你本地路径仍为 `reports/backtest_<时间戳>_*`。

| 文件前缀（示例） | 来源示例 | 标的 | 收益 | 说明 |
|------------------|----------|------|------|------|
| `backtest_*_14_bollinger.*` | [`examples/14_bollinger_strategy.py`](../examples/14_bollinger_strategy.py) | 601088 中国神华 | +57.77% | 布林带均值回归 |
| `backtest_*_15_macd_volume.*` | [`examples/15_macd_volume_strategy.py`](../examples/15_macd_volume_strategy.py) | 600536 中国软件 | +103.48% | MACD + 成交量确认 |
| `backtest_*_17_grid.*` | [`examples/17_grid_trading_strategy.py`](../examples/17_grid_trading_strategy.py) | 601857 中国石油 | +30.25% | 网格交易 |
| `backtest_*_16_multifactor.*` | [`examples/16_multi_factor_strategy.py`](../examples/16_multi_factor_strategy.py) | 10 只股票池 | +5.19% | 多因子选股 |
| `backtest_*_22_stockselection.*` | [`examples/22_stock_selection_strategy.py`](../examples/22_stock_selection_strategy.py) | 14 只股票池 | +16.96% | 选股策略界面 |
| `backtest_*_20_sr.*` | [`examples/20_sr_strategy/run_backtest.py`](../examples/20_sr_strategy/README.md) | 8 只股票池 | +119.97% | 支撑/阻力位组合 |
| `backtest_*_19_localdata.*` | [`examples/19_local_data_backtest.py`](../examples/19_local_data_backtest.py) | 000768 中航光电 | -33.28% | 本地 CSV 模式（亏损示例，适合读报告） |
| `backtest_*_12_portfolio.*` | [`examples/12_portfolio_backtest.py`](../examples/12_portfolio_backtest.py) | 5 只股票池 | -25.69% | 组合回测模式 |
| `backtest_*_momentum_v2.*` | [`examples/12_portfolio_backtest.py`](../examples/12_portfolio_backtest.py)（旧版） | — | — | 中间调试版本 |

**推荐打开对照阅读：**

- **盈利策略**：`*_15_macd_volume.html`（+103%）、`*_14_bollinger.html`（+58%）、`*_20_sr.html`（+120%）
- **亏损策略**（用于学习如何识别问题）：`*_19_localdata.html`（-33%）、`*_12_portfolio.html`（-26%）
- 打开后对照 [教程 03 — 报告逐层解读](../tutorials/03_backtesting.md#35-html-交互式报告逐层解读) 与 [报告与指标详解](../doc/reports_and_metrics.md)

> 若你克隆仓库后没有这些文件，运行对应脚本即可生成：  
> `python examples/14_bollinger_strategy.py`  
> `python examples/15_macd_volume_strategy.py`  
> `python examples/19_local_data_backtest.py`  
> ……依此类推。

---

## 如何打开 HTML

在资源管理器或终端中双击 / 用浏览器「打开文件」选中 `reports/backtest_*.html` 即可，**无需**启动 HTTP 服务器。

**注意：**报告页内 **K 线、累计收益等交互图**依赖 CDN 加载图表库；**离线或内网拦截**时图区可能空白，页眉与指标卡片通常仍可用。详见 [FAQ — HTML 图表空白](../doc/FAQ.md#faq-html-blank) 与 [`doc/reports_and_metrics.md`](../doc/reports_and_metrics.md) 第 2.8 节对照走读。

---

## 与教程中图片的关系

[`tutorials/assets/README.md`](../tutorials/assets/README.md) 提供了教程配图索引；其中列出的 `example_report_*.png` 与上表中的对应 `.png` 为同一次示例运行的副本，纳入 Git 后方便在 GitHub 等环境直接预览教程配图。**你本地学习时以本机 `reports/` 下最新生成的为准。**

| 教程截图 | 对应报告 |
|---------|---------|
| `tutorials/assets/example_report_19_localdata.png` | `*_19_localdata.png` |
| `tutorials/assets/example_report_bollinger.png` | `*_14_bollinger.png` |
| `tutorials/assets/example_report_macd_volume.png` | `*_15_macd_volume.png` |
| `tutorials/assets/example_report_grid.png` | `*_17_grid.png` |
| `tutorials/assets/example_report_multifactor.png` | `*_16_multifactor.png` |
| `tutorials/assets/example_report_stock_selection.png` | `*_22_stockselection.png` |
| `tutorials/assets/example_report_portfolio.png` | `*_12_portfolio.png` |
