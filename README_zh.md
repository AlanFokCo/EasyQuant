<div align="center">

<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="280" alt="EasyQuant logo"/></a>

# EasyQuant

面向中国 A 股市场的事件驱动量化回测框架。

[![Tests](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/test.yml?label=Tests)](https://github.com/AlanFokCo/EasyQuant/actions/workflows/test.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/AlanFokCo/EasyQuant/deploy-docs.yml?label=Docs)](https://AlanFokCo.github.io/EasyQuant/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/AlanFokCo/EasyQuant/blob/main/LICENSE)

<p>
<a href="README.md">English</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/">文档站</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/tutorials/">教程</a> ·
<a href="https://AlanFokCo.github.io/EasyQuant/reference/">API 参考</a>
</p>

</div>

---

## 功能特性

- **事件驱动回测** — `initialize` → `run_daily` → `handle_data`，与 JoinQuant / Zipline 一致
- **A 股数据** — 日线/分钟线/Tick、财务摘要、资金流向、北向资金、涨跌停统计
- **风险分析** — Sharpe / Sortino / 最大回撤 / Alpha & Beta / Brinson 归因
- **组合风控** — VaR、策略相关性、集中度风险、Kill Switch 熔断
- **模拟盘** — 实时行情运行策略 + 钉钉/飞书通知
- **PTrade/QMT 适配** — 一键导出券商平台
- **Web 工作室** — 浏览器端策略开发，无需安装 Python

---

## 快速开始

```bash
pip install easyquant-eqlib

python -c "from eqlib import *; print('eqlib OK')"
```

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist['close'].iloc[-1] > hist['close'].mean() * 1.02:
        order_value(g.security, context.portfolio.available_cash)

result = run_strategy(initialize, start_date='2024-01-01',
                      end_date='2024-12-31', securities=['601390'])
```

---

## 文档

| 资源 | 说明 |
|------|------|
| [**文档站**](https://AlanFokCo.github.io/EasyQuant/) | 完整文档，支持搜索和暗色主题 |
| [**教程**](https://AlanFokCo.github.io/EasyQuant/tutorials/) | 从零到实盘，11 篇分步教程 |
| [**操作指南**](https://AlanFokCo.github.io/EasyQuant/how-to/) | 按场景定位的实用指南 |
| [**API 参考**](https://AlanFokCo.github.io/EasyQuant/reference/) | 全部公开 API 的参数与示例 |
| [**示例**](examples/) | 26 个可运行脚本 |
| [**常见问题**](https://AlanFokCo.github.io/EasyQuant/project/faq/) | 排错与常见疑问 |

---

## 安装

```bash
# PyPI 安装（推荐）
pip install easyquant-eqlib

# 从源码安装（贡献者）
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install -e ".[dev]"
python -m pytest tests/
```

**环境要求：** Python 3.10+ · macOS / Linux / Windows

---

## 贡献

请参阅 [贡献指南](docs/project/contributing.md)。

## 许可证

[MIT 许可证](LICENSE)

> **免责声明：** 本项目仅供学习研究使用，不构成投资建议。
