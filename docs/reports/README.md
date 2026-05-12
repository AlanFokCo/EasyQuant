# `reports/` 回测产物索引

运行 `run_strategy()`、`run_backtest()` 后配合 `generate_html_report` / `generate_chart` 等，默认会在**仓库根目录**下的 `reports/` 中写入带时间戳的：

- `backtest_*.html` — 交互式报告（浏览器打开）
- `backtest_*.png` — Matplotlib 汇总图
- `backtest_*.md` / `backtest_*.json` — 文本与结构化结果

这些生成文件通常被 [.gitignore](https://github.com/AlanFokCo/EasyQuant/blob/main/.gitignore) 忽略，**不会**出现在 Git 克隆里；本页说明各 **示例脚本** 与报告命名的对应关系，便于你对照本地输出。

仓库根目录另有一份简短入口：[`reports/README.md`](https://github.com/AlanFokCo/EasyQuant/blob/main/reports/README.md)（与本文同步维护）。

---

## 示例脚本与报告命名（推荐对照组）

| 示例 / 场景 | 脚本路径（仓库内） | 报告文件名常见片段 / 说明 |
|-------------|---------------------|---------------------------|
| 本地数据回测 | `examples/19_local_data_backtest.py` | `*_19_localdata*`；教程 PNG/HTML 截图与之同源 |
| 布林带 | `examples/14_bollinger_strategy.py` | 标的如 601088；教程 `example_report_bollinger*` |
| MACD + 成交量 | `examples/15_macd_volume_strategy.py` | 标的如 600536；教程 `example_report_macd_volume*` |
| 网格交易 | `examples/17_grid_trading_strategy.py` | 601857 等；教程 `example_report_grid*` |
| 多因子 | `examples/16_multi_factor_strategy.py` | 教程 `example_report_multifactor*` |
| 选股 | `examples/22_stock_selection_strategy.py` | 教程 `example_report_stock_selection*` |
| 组合回测 | `examples/12_*.py`（组合示例） | 教程 `example_report_portfolio*` |
| 支撑/阻力 | `examples/20_sr_strategy/` | 教程 `example_report_sr_strategy*` |

教程配图目录说明：[Tutorial assets](../tutorials/assets/README.md)。

报告字段逐项解读：[Reports & Metrics](../doc/reports_and_metrics.md)。HTML 空白排错：[FAQ](../doc/FAQ.md#faq-html-blank)。

---

## 在 GitHub 上浏览示例代码

[examples 目录](https://github.com/AlanFokCo/EasyQuant/tree/main/examples) · [tutorials 目录](https://github.com/AlanFokCo/EasyQuant/tree/main/tutorials)
