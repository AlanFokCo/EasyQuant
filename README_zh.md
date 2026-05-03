# EasyQuant

一个面向 **中国 A 股市场** 的量化策略与回测工具。

本项目提供 `eqlib` Python 包——核心库，包含事件驱动回测引擎、数据 API 和分析工具。

[English](README.md) · [用户手册](doc/user_guide.md) · [API 参考](doc/api_reference.md) · [示例](examples/)

---

## 功能

- **事件驱动回测** — initialize、定时调度函数、日线、组合追踪
- **A 股数据** — 日线 OHLCV、分钟 K 线、Tick 数据、实时行情、财务摘要、资金流向
- **仓位管理** — 按股数 / 金额 / 目标值买卖；自动取整到 100 股、自动计算手续费
- **风险分析** — 夏普 / 索提诺 / 最大回撤 / alpha & beta / Brinson 归因 / Fama-French 因子分析
- **组合优化** — 最小方差、最大夏普、风险平价
- **模拟盘** — 使用实时行情运行策略
- **工具库** — 技术指标（MA、MACD、RSI、KDJ、布林带、ATR）、统计分析、仓位管理（Kelly、ATR、固定比例）
- **报告输出** — 图表（PNG）、Markdown、JSON

---

## 安装

```bash
pip install akshare pandas numpy matplotlib scipy
# 可选：更快的磁盘缓存
pip install pyarrow
```

或从源码安装：

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install -e .
```

---

## 快速开始

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        order_target(g.security, 0)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    securities=['601390'],
)
```

---

## 示例

参见 [`examples/`](examples/) 目录中的完整脚本：

| # | 文件 | 说明 |
|---|------|------|
| 01 | `01_fetch_data.py` | 下载股票数据 |
| 02 | `02_write_strategy.py` | 编写策略（均线交叉、RSI、多股轮动） |
| 03 | `03_run_backtest.py` | 运行完整回测 |
| 04 | `04_stock_screener.py` | 选股扫描 |
| 05 | `05_paper_trade.py` | 模拟盘交易 |
| 06 | `06_advanced_api.py` | 高级数据 API |
| 07 | `07_market_data.py` | 市场数据：财务、指数、分钟线、Tick |
| 08 | `08_lifecycle_callbacks.py` | 生命周期回调 |
| 09 | `09_attribution_analysis.py` | 归因分析 |
| 10 | `10_index_concept.py` | 指数与概念板块 |
| 11 | `11_utils_library.py` | 技术指标、统计分析、资金管理 |

---

## 文档

- [**用户手册**](doc/user_guide.md) — 教程：编写策略、运行回测、解读报告
- [**API 参考**](doc/api_reference.md) — 完整 API：结构体、参数说明、用法
- [**工具库参考**](doc/utils_reference.md) — 计算工具：技术指标、统计分析、资金管理、支撑阻力位

---

## 许可证

MIT
