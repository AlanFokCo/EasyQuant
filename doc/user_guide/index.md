# EasyQuant 用户手册

> EasyQuant 是一个面向中国 A 股市场的量化策略与回测工具。核心库为 `eqlib` Python 包，通过 `from eqlib import *` 导入使用。

!!! abstract "如何使用本手册"

    - **第一次使用**：完成 **[§0 新手四步](00_first_steps.md#0-新手先完成这-4-步)** 即可跑通并打开 HTML 报告（约 **15 分钟**）。
    - **写法提示**：多数官方示例用 **`run_daily(market_open, …)`** 注册每日逻辑；**`handle_data`** 是另一种「每 bar 自动调用」的入口，可与调度函数组合使用，完整顺序见 **[§4 策略生命周期](04_lifecycle.md#4-策略生命周期)**。
    - **按需跳读**：目录较长时，可用浏览器搜索（`Ctrl+F` / `⌘F`）或文档站左上角 **搜索** 定位关键词（如 `use_local`、`OrderCost`）。

---


## 章节目录

以下各章为**独立页面**，便于侧边栏导航、打印与深度链接。

<div class="grid cards eq-cards" markdown>

-   :material-book-open-page-variant: **§0** — 新手先完成这 4 步

    ---

    [:octicons-arrow-right-24: 打开本章](00_first_steps.md){ .md-button }

-   :material-book-open-page-variant: **§1** — 简介与适用范围

    ---

    [:octicons-arrow-right-24: 打开本章](01_intro_scope.md){ .md-button }

-   :material-book-open-page-variant: **§2** — 安装

    ---

    [:octicons-arrow-right-24: 打开本章](02_install.md){ .md-button }

-   :material-book-open-page-variant: **§3** — 快速开始：5 分钟写一个策略

    ---

    [:octicons-arrow-right-24: 打开本章](03_quickstart_strategy.md){ .md-button }

-   :material-book-open-page-variant: **§4** — 策略生命周期

    ---

    [:octicons-arrow-right-24: 打开本章](04_lifecycle.md){ .md-button }

-   :material-book-open-page-variant: **§5** — 资金管理：设置初始资金与仓位控制

    ---

    [:octicons-arrow-right-24: 打开本章](05_capital_position.md){ .md-button }

-   :material-book-open-page-variant: **§6** — 交易 API：买入与卖出

    ---

    [:octicons-arrow-right-24: 打开本章](06_trading_api.md){ .md-button }

-   :material-book-open-page-variant: **§7** — 数据拉取

    ---

    [:octicons-arrow-right-24: 打开本章](07_data.md){ .md-button }

-   :material-book-open-page-variant: **§8** — 计算工具库

    ---

    [:octicons-arrow-right-24: 打开本章](08_utils.md){ .md-button }

-   :material-book-open-page-variant: **§9** — 运行回测

    ---

    [:octicons-arrow-right-24: 打开本章](09_backtest.md){ .md-button }

-   :material-book-open-page-variant: **§10** — 回测报告与图表解读

    ---

    [:octicons-arrow-right-24: 打开本章](10_reports.md){ .md-button }

-   :material-book-open-page-variant: **§11** — 风险与归因分析

    ---

    [:octicons-arrow-right-24: 打开本章](11_risk_attribution.md){ .md-button }

-   :material-book-open-page-variant: **§12** — 模拟盘交易

    ---

    [:octicons-arrow-right-24: 打开本章](12_paper_trading.md){ .md-button }

-   :material-book-open-page-variant: **§13** — 参数优化、审计与参考脚本

    ---

    [:octicons-arrow-right-24: 打开本章](13_optimization.md){ .md-button }

-   :material-book-open-page-variant: **§14** — 常见问题

    ---

    [:octicons-arrow-right-24: 打开本章](14_faq.md){ .md-button }

</div>

---

## 子节速查（§9～§10）

| 章节 | 说明 |
|------|------|
| [§9 运行回测](09_backtest.md) | `run_strategy` / `run_backtest` / 组合回测 / 基准 |
| [§10 报告解读](10_reports.md) | PNG / HTML / Markdown / JSON 报告结构 |
