# EasyQuant 文档中心

面向 **中国 A 股** 的本地回测与策略开发。核心包名为 **`eqlib`**。

!!! note "仓库名与包名"

    GitHub 仓库名是 **EasyQuant**，Python 包名是 **`eqlib`**。文档与示例中的 `pip install .` 均在**仓库根目录**执行。

---

## 我是哪类读者？

| 你的情况 | 建议从这里开始 |
|----------|----------------|
| 第一次克隆仓库，想尽快跑通 | [用户手册](user_guide.md)（从 §0 新手四步起） |
| 跟着教程系统学 | [Tutorial 00](../tutorials/00_environment_and_first_run.md) → [教程导读](../tutorials/README.md) |
| 查函数签名、参数、返回值 | [API 参考](api_reference.md) |
| 报告 / JSON 里指标看不懂 | [报告与指标](reports_and_metrics.md) |
| 安装失败、无数据、很慢 | [常见问题 FAQ](FAQ.md) |

---

## 建议阅读顺序

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [用户手册](user_guide.md) | 安装、策略骨架、回测与报告概览 |
| 2 | [报告与指标详解](reports_and_metrics.md) | HTML 报告逐屏解读 |
| 3 | [API 参考](api_reference.md) | 全部公开 API 的参数与示例 |
| 4 | [常见问题 FAQ](FAQ.md) | 安装、数据、性能与排错 |

**教程（分步学习）：** [教程导读](../tutorials/README.md)，建议从「环境与第一次运行」开始。

**可运行示例：** [示例索引](../examples/Examples.md)。

---

## 快速验证

```bash
cd EasyQuant
pip install .
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

然后在 `reports/` 打开最新 `.html` 文件。
