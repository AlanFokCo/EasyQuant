<p align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="240" alt="EasyQuant"/></a>
</p>

# EasyQuant 文档中心

!!! tip "在文档站阅读"

    若你正在 **GitHub Pages 文档站**，可用左上角 **搜索**、顶部 **导航栏** 切换「快速入门 / 用户手册 / API / 教程 / 示例」；站点首页为 [Home](../index.md)。

面向 **中国 A 股** 的本地回测与策略开发。核心包名为 **`eqlib`**（与仓库名 EasyQuant 对应）。

---

## 我是哪类读者？

| 你的情况 | 建议从这里开始 |
|----------|----------------|
| 第一次克隆仓库，想尽快跑通 | [用户手册](user_guide.md)（从 §0 新手四步起） |
| 跟着教程系统学 | [Tutorial 00 — 环境与第一次运行](../tutorials/00_environment_and_first_run.md) → [教程导读](../tutorials/README.md) |
| 查函数签名、参数、返回值 | [API 速查索引](api_index.md) 或 [完整 API 参考](api_reference.md) |
| 报告 / JSON 里指标看不懂 | [报告与指标 → §2.8 走读](reports_and_metrics.md#28-对照走读示例reports19_localdata--html) 或通读 [报告与指标](reports_and_metrics.md) |
| 安装失败、无数据、很慢、图表空白 | [常见问题 FAQ](FAQ.md) |
| 做参数搜索、审计日志 | [Tutorial 10](../tutorials/10_agent_optimization.md) 与 GitHub 上 [`agent/`](https://github.com/AlanFokCo/EasyQuant/tree/main/agent) 目录 |

!!! note "仓库名与包名"

    GitHub 仓库名是 **EasyQuant**，Python 包名是 **`eqlib`**。文档与示例中的 `pip install .` 均在**仓库根目录**执行。

---

## 建议阅读顺序

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [用户手册](user_guide.md) | 安装、策略骨架、`run_strategy` / `run_backtest`、数据与报告概览 |
| 2 | [环境、报告与指标详解](reports_and_metrics.md)（[§2.8 对照走读](reports_and_metrics.md#28-对照走读示例reports19_localdata--html)） | 打开 HTML/PNG、**HTML 逐屏对照**、`analyze_returns` 全字段 |
| 3 | [常见问题 FAQ](FAQ.md) | 安装失败、数据下载、回测无图、性能与排错 |
| 4 | [API 速查索引](api_index.md) | 按主题跳转 `api_reference.md` 章节 |
| 5 | [API 参考（完整）](api_reference.md) | 全部公开 API 的参数与示例 |
| 6 | [工具库参考](utils_reference.md) | `eqlib.utils` 指标与公式说明 |
| 7 | [PTrade/QMT 适配器](ptrade_adapter.md) | 导出到券商实盘环境 |

**教程（分步学习）：** 仓库根目录下 [`tutorials/`](../tutorials/README.md)，建议从「环境与第一次运行」开始。

**可运行示例：** [`examples/Examples.md`](../examples/Examples.md)。

**示例回测产物：** [`reports/README.md`](../reports/README.md)（说明 `reports/` 下 HTML/PNG 等与各 `examples/` 脚本的对应关系；目录内其它文件默认不提交 Git）。

---

## 新手 15 分钟验证清单

```bash
cd EasyQuant
pip install .
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

然后在 `reports/` 打开最新 `.html` 文件，确认：收益曲线、回撤曲线、交易记录都能显示。

若要做额外自检：

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```

---

## 快速命令

```bash
# Python 3.10+ 必填（见 pyproject.toml）
cd EasyQuant
pip install .
# 可选：pip install -e .   # 开发模式

python examples/03_run_backtest.py
# 在 reports/ 下查看生成的 .html / .png / .md / .json（说明见 reports/README.md）
```

---

## 相关链接

- 项目说明（中文）：[`README_zh.md`](../README_zh.md)
- 参数优化与审计（Tutorial 10）：[`tutorials/10_agent_optimization.md`](../tutorials/10_agent_optimization.md)
- 本地数据快速验证：[`tutorials/00_environment_and_first_run.md`](../tutorials/00_environment_and_first_run.md)

---

## 文档排版说明（GitHub Pages）

本站由 **MkDocs Material** 构建。教程与手册文首的 **「本篇导览」**、`!!! tip` 等块在 **GitHub 仓库内联预览** 中可能显示为纯文本；在 **[在线文档站](https://AlanFokCo.github.io/EasyQuant/)** 中渲染最佳。编写新文档时建议：先写 **一段摘要** + **读者 / 前置 / 预计时间**，再展开正文。
