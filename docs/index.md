---
hide:
  - navigation.path
---

# EasyQuant — 事件驱动回测，面向中国 A 股

**EasyQuant** 是围绕 Python 包 **`eqlib`** 构建的量化回测与策略开发框架：聚宽风格 API、AKShare 行情、HTML 交互式报告与常用风险指标。

<div class="grid" markdown>

-   **:material-rocket-launch: 15 分钟跑通**

    安装 `eqlib`、运行示例回测、在浏览器中打开 HTML 报告。

    [:octicons-arrow-right-24: 用户手册](doc/user_guide.md){ .md-button .md-button--primary }

-   **:material-school: 系统学习**

    从环境配置到参数优化与审计的分步教程。

    [:octicons-arrow-right-24: 教程导读](tutorials/README.md){ .md-button }

-   **:material-file-document-outline: 示例代码**

    双均线、RSI、多因子、组合策略等可运行脚本。

    [:octicons-arrow-right-24: 示例索引](examples/Examples.md){ .md-button }

-   **:material-book-open-variant: API 参考**

    完整 API 文档：结构体、参数说明、用法示例。

    [:octicons-arrow-right-24: API 参考](doc/api_reference.md){ .md-button }

</div>

## 常用入口

| 我想… | 建议阅读 |
|------|----------|
| 第一次安装并验证环境 | [用户手册 §0–§2](doc/user_guide.md#0-新手四步) |
| 弄懂 HTML 报告里每张图、每个指标 | [报告与指标](doc/reports_and_metrics.md) |
| 查 `order` / `run_backtest` 等 API | [API 参考](doc/api_reference.md) |
| 排查数据下载、无交易、无图等问题 | [常见问题 FAQ](doc/FAQ.md) |

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
- **仓库**：[github.com/AlanFokCo/EasyQuant](https://github.com/AlanFokCo/EasyQuant)

---

!!! info

    本报告与文档仅供学习研究，不构成投资建议。市场有风险，决策需谨慎。
