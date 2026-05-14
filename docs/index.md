---
hide:
  - navigation.path
---

# EasyQuant

面向中国 A 股的事件驱动回测与策略开发框架。

<div class="hero-cards">
<div class="hero-card" markdown>
### 快速入门

从安装到运行第一个回测，15 分钟即可上手。

[开始阅读](doc/user_guide.md#0-新手四步)
</div>
<div class="hero-card" markdown>
### 用户手册

编写策略、运行回测、解读报告的完整指南。

[阅读手册](doc/user_guide.md)
</div>
<div class="hero-card" markdown>
### 分步教程

从零到实盘的系列教程，含真实策略案例。

[浏览教程](tutorials/README.md)
</div>
<div class="hero-card" markdown>
### API 参考

`eqlib` 全部公开 API 的参数与示例。

[查看 API](doc/api_reference.md)
</div>
</div>

---

## 常用入口

| 我想… | 建议阅读 |
|------|----------|
| 第一次安装并验证环境 | [用户手册 §0](doc/user_guide.md#0-新手四步) |
| 看懂 HTML 报告里的图表和指标 | [报告与指标](doc/reports_and_metrics.md) |
| 查 `order` / `run_backtest` 等 API | [API 参考](doc/api_reference.md) |
| 排查数据下载、无交易等问题 | [常见问题](doc/FAQ.md) |

## 快速验证

```bash
pip install .
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

在 `reports/` 目录打开最新生成的 `.html` 报告。

---

!!! info

    本文档仅供学习研究，不构成投资建议。
