---
hide:
  - navigation.path
---

<div class="eq-hero" markdown="1">

<p class="eq-hero-logo" markdown="1">
[![EasyQuant](assets/logo.svg){ width="220" .eq-hero-img loading=lazy }](https://github.com/AlanFokCo/EasyQuant)
</p>

# 事件驱动回测，面向中国 A 股

**EasyQuant** 是围绕 Python 包 **`eqlib`** 构建的量化回测与策略开发框架：聚宽风格 API、AKShare 行情、HTML 交互式报告与常用风险指标。本站为 **官方文档站**（GitHub Pages），与仓库内容同步更新。

!!! tip "阅读提示"

    绝大多数教程与手册为 **中文**；首页与导航保留少量英文标签，便于在双语环境下检索。侧边栏 **搜索** 支持中文关键词。

</div>

## 从这里开始

<div class="grid cards eq-cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __15 分钟跑通__

    ---

    安装 `eqlib`、运行示例回测、在浏览器中打开 HTML 报告。

    [:octicons-arrow-right-24: 安装与用户手册](doc/user_guide/index.md){ .md-button .md-button--primary }

-   :material-school-outline:{ .lg .middle } __系统学习__

    ---

    从环境配置（Tutorial 00）到参数优化与审计（Tutorial 10）的分步教程。

    [:octicons-arrow-right-24: 教程导读](tutorials/README.md){ .md-button }

-   :material-file-document-outline:{ .lg .middle } __文档索引__

    ---

    建议阅读顺序、FAQ、报告与指标说明、API 速查入口。

    [:octicons-arrow-right-24: 文档中心](doc/README.md){ .md-button }

-   :material-code-braces:{ .lg .middle } __示例代码__

    ---

    双均线、RSI、多因子、组合策略等可运行脚本索引。

    [:octicons-arrow-right-24: 示例索引](examples/Examples.md){ .md-button }

</div>

## 常用入口

| 我想… | 建议阅读 |
|------|----------|
| 第一次安装并验证环境 | [环境与第一次运行](tutorials/00_environment_and_first_run.md) → [用户手册总览](doc/user_guide/index.md) |
| 弄懂 HTML 报告里每张图、每个指标 | [报告与指标](doc/reports_and_metrics.md) |
| 查 `order` / `run_backtest` 等 API | [API 速查索引](doc/api_index.md) 或 [完整 API 参考](doc/api_reference.md) |
| 排查数据下载、无交易、无图等问题 | [常见问题 FAQ](doc/FAQ.md) |
| 规划 Web 端策略编辑与回测服务 | [Design Spec — Web 策略工作室](doc/design_spec_web_strategy_studio.md) |

## 本地快速验证

=== "最小验证"

    ```bash
    pip install .
    python -c "from eqlib import *; print('eqlib OK')"
    python examples/03_run_backtest.py
    ```

    然后在仓库的 `reports/` 目录打开最新生成的 `.html` 报告。

=== "含开发依赖"

    ```bash
    pip install -e ".[dev]"
    python -m pytest tests/
    ```

## 版本与环境

- **Python**：3.10+（见仓库根目录 `pyproject.toml`）
- **数据**：默认通过 [AKShare](https://akshare.akfamily.xyz/) 获取 A 股行情（需网络）
- **仓库**：[github.com/AlanFokCo/EasyQuant](https://github.com/AlanFokCo/EasyQuant) · 中文说明见 [README_zh.md](https://github.com/AlanFokCo/EasyQuant/blob/main/README_zh.md)

---

<div class="eq-footer-note" markdown="1">

:octicons-info-24: 本报告与文档仅供学习研究，不构成投资建议。市场有风险，决策需谨慎。

</div>
