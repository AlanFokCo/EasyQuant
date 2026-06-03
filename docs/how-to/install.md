# 安装与快速上手

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 安装 eqlib 并运行第一个回测 |
    | **预计用时** | 15 分钟 |

---
## 1. 新手四步

如果你是第一次接触 EasyQuant，请先完成以下最小闭环：

1. 安装：
   ```bash
   # PyPI 安装（推荐，无需克隆仓库）
   pip install easyquant-eqlib
   # 或从源码安装（开发者 / 贡献者，在仓库根目录）
   # pip install .
   ```
2. 验证导入：
   ```bash
   python -c "from eqlib import *; print('eqlib OK')"
   ```
3. 跑一次完整回测（需在仓库目录运行示例）：
   ```bash
   python examples/03_run_backtest.py
   ```
4. 打开 `reports/` 下最新 `.html`，确认图表和指标正常显示。

可选测试：

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```

> **替代方案：Web 策略工作室**
> 如果你更喜欢浏览器界面，可以使用 [Web 策略工作室](https://github.com/AlanFokCo/EasyQuant/tree/main/web_strategy_studio/)。
> 无需安装 Python 环境，打开浏览器即可编写策略、运行回测、查看报告和对比指标。
> 详见 [Web 工作室文档](web-studio.md)。

---

## 2. 简介与适用范围

`eqlib` 是一个面向 **中国 A 股市场** 的量化策略回测框架。它的数据源来自 `akshare`，采用事件驱动的策略 API 设计，支持完整的回测与模拟盘工作流。

**适用场景：**
- A 股日线 / 分钟线回测
- 策略开发验证
- 模拟盘交易
- 选股 / 行业轮动 / 资金流分析
- 投资组合优化

**不支持：**
- 港股、美股、期货、期权、加密货币等非 A 股品种
- 高频 T+0 策略（A 股为 T+1 交易制度）

---

## 3. 安装

**环境要求：Python 3.10 及以上**。

```bash
# PyPI 安装（推荐）
pip install easyquant-eqlib
# 开发时可选用（在仓库根目录）：pip install -e .
```

确认安装成功：

```python
from eqlib import *
print("eqlib OK")
```

更多排错见 [常见问题 FAQ](../project/faq.md)。

---

