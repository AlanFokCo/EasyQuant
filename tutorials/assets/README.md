# 教程配图目录

## matplotlib 图表（PNG，`generate_chart` 输出）

- **`sample_equity_vs_benchmark.svg`**：轻量示意图，说明「策略 vs 基准」累计收益曲线的读法。
- **`example_report_19_localdata.png`**：与仓库根 [`reports/`](../../reports/README.md) 中一次 **`examples/19_local_data_backtest.py`** 运行导出的 PNG **内容一致**（副本纳入 Git，便于在线预览教程）。
- **`example_report_bollinger.png`**：Example 14 布林带策略报告（601088，+57.77%）。
- **`example_report_macd_volume.png`**：Example 15 MACD+成交量策略报告（600536，+103.48%）。
- **`example_report_grid.png`**：Example 17 网格交易策略报告（601857，+30.25%）。
- **`example_report_multifactor.png`**：Example 16 多因子选股策略报告（+5.19%）。
- **`example_report_stock_selection.png`**：Example 22 选股策略界面报告（+16.96%）。
- **`example_report_portfolio.png`**：Example 12 组合回测报告（-25.69%）。
- **`example_report_sr_strategy.png`**：Example 20 支撑/阻力位组合策略报告（+119.97%）。

## HTML 报告截图（`example_report_html_*`）

与上方各 PNG 同源，但展示**完整的交互式 HTML 报告**——包括页头指标卡片、详细指标行、K 线图、累计收益曲线、回撤曲线、每日盈亏、成交持仓等全部区块。

- **`example_report_html_19_localdata.png`**：本地数据回测（000768，-33.28%）
- **`example_report_html_bollinger.png`**：Example 14 布林带（601088，+57.77%）
- **`example_report_html_macd_volume.png`**：Example 15 MACD+成交量（600536，+103.48%）
- **`example_report_html_grid.png`**：Example 17 网格交易（601857，+30.25%）
- **`example_report_html_multifactor.png`**：Example 16 多因子选股（+5.19%）
- **`example_report_html_stock_selection.png`**：Example 22 选股策略（+16.96%）
- **`example_report_html_portfolio.png`**：Example 12 组合回测（-25.69%）
- **`example_report_html_sr_strategy.png`**：Example 20 支撑/阻力位（+119.97%）

> **HTML 上指标与页眉如何逐项对照：** 见 [`doc/reports_and_metrics.md`](../../doc/reports_and_metrics.md) **第 2 节**；图区空白见 [FAQ](../../doc/FAQ.md#faq-html-blank)。
>
> **重新生成截图：** 运行 `python screenshot_reports.py`（需先 `pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple` + `playwright install chromium`）。

**更多真实样例：** 见 [`reports/README.md`](../../reports/README.md) 中的示例对照表；自行跑示例后在 `reports/` 下会生成带新时间戳的 HTML/PNG。
