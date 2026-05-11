# EasyQuant

一个面向 **中国 A 股市场** 的量化策略与回测工具。

本项目提供 `eqlib` Python 包——核心库，包含事件驱动回测引擎、数据 API 和分析工具。

[English](README.md) · [新手教程](tutorials/) · [**文档中心**](doc/README.md) · [用户手册](doc/user_guide.md) · [API 速查](doc/api_index.md) · [API 参考](doc/api_reference.md) · [示例](examples/Examples.md)

---

## 功能

- **事件驱动回测** — initialize、定时调度函数、日线、组合追踪
- **A 股数据** — 日线 OHLCV、分钟 K 线、Tick 数据、实时行情、财务摘要、资金流向
- **仓位管理** — 按股数 / 金额 / 目标值买卖；自动取整到 100 股、自动计算手续费
- **风险分析** — 夏普 / 索提诺 / 最大回撤 / alpha & beta / Brinson 归因 / Fama-French 因子分析
- **组合优化** — 最小方差、最大夏普、风险平价
- **模拟盘** — 使用实时行情运行策略
- **PTrade/QMT 适配器** — 将 EasyQuant 策略一键导出为 PTrade/QMT 平台格式，无缝上线实盘
- **工具库** — 技术指标（MA、MACD、RSI、KDJ、布林带、ATR）、统计分析、仓位管理（Kelly、ATR、固定比例）
- **报告输出** — 图表（PNG）、Markdown、JSON

---

## 安装

```bash
pip install akshare pandas numpy matplotlib scipy
# 可选：更快的磁盘缓存
pip install pyarrow
```

或从源码安装（任选其一，需在仓库根目录执行）：

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install .
# 开发时可选用 editable：pip install -e .
```

安装后可在任意目录 `import eqlib`。运行 `examples/` 下的脚本前，请在仓库根目录执行 `pip install .`（或 `pip install -e .`）。

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
    use_local=True,
)
```

---

## 示例

参见 [`examples/Examples.md`](examples/Examples.md) 索引；脚本位于 [`examples/`](examples/)：

| # | 文件 | 说明 |
|---|------|------|
| 01 | `01_fetch_data.py` | 下载股票数据 |
| 02 | `02_write_strategy.py` | 编写策略（均线交叉、RSI、多股轮动） |
| 03 | `03_run_backtest.py` | 运行完整回测 |
| 04 | `04_stock_screener.py` | 选股扫描 |
| 05 | `05_paper_trade.py` | 模拟盘交易 |
| 06 | `06_advanced_api.py` | 调度说明、组合优化、归因与因子分析 |
| 07 | `07_market_data.py` | 市场数据：财务、指数、分钟线、Tick |
| 08 | `08_lifecycle_callbacks.py` | 生命周期回调 |
| 09 | `09_attribution_analysis.py` | 归因分析 |
| 10 | `10_index_concept.py` | 指数与概念板块 |
| 11 | `11_utils_library.py` | 技术指标、统计分析、资金管理 |
| 12 | `12_portfolio_backtest.py` | 组合回测模式（StrategyConfig） |
| 13 | `13_ptrade_export.py` | 导出 PTrade/QMT 策略 |
| 14 | `14_bollinger_strategy.py` | 布林带均值回归策略 |
| 15 | `15_macd_volume_strategy.py` | MACD 趋势跟踪 + 成交量确认 |
| 16 | `16_multi_factor_strategy.py` | 多因子选股 + 每周轮动 |
| 17 | `17_grid_trading_strategy.py` | 网格交易策略 |
| 18 | `18_strategy_comparison.py` | 多策略横向对比 |
| 19 | `19_local_data_backtest.py` | 本地数据回测模式（下载一次，离线回测） |
| 20 | `20_sr_strategy/` | 支撑阻力位组合策略（完整实盘案例） |
| 21 | `21_combined_strategy/` | **全天候 Alpha** — 综合策略（多因子+行业轮动+RSI/MACD/布林带+ATR止损） |
| 22 | `22_stock_selection_strategy.py` | 定期选股调仓（run_selection / 因子筛选） |
| 23 | `23_small_cap_query_example.py` | 小市值 query/valuation 链式筛选示例 |
| 24 | `24_quick_report_test.py` | 快速验证报告输出（PNG/HTML/MD/JSON） |

---

## 文档

- [**新手教程**](tutorials/) — 从零基础到实盘部署，5 篇系列教程
- [**用户手册**](doc/user_guide.md) — 教程：编写策略、运行回测、解读报告
- [**API 参考**](doc/api_reference.md) — 完整 API：结构体、参数说明、用法
- [**工具库参考**](doc/utils_reference.md) — 计算工具：技术指标、统计分析、资金管理、支撑阻力位
- [**PTrade/QMT 适配器**](doc/ptrade_adapter.md) — 将 EasyQuant 策略导出为 PTrade/QMT 平台格式

---

## AI Agent — 自动化策略优化

EasyQuant 内置了由 **Claude Code** 驱动的 **AI Agent 工作流**。AI Agent（Claude Code 本身）直接读取策略文件、通过 `eqlib` API 运行回测、分析结果、编辑策略文件、调用代码审查子 Agent，并将每一步决策记录下来 —— 无需运行独立的优化脚本。

### Agent 能做什么

1. 你告诉 Claude Code 你的要求（例如"夏普 > 1.0，最大回撤 < 20%"）
2. Claude Code 读取 `CLAUDE.md` 和你的策略文件
3. 使用 `eqlib` API 运行回测并分析结果
4. 诊断问题并提出数据驱动的参数调整方案
5. 直接编辑策略文件应用参数变更
6. 调用专门的代码审查子 Agent 验证修改
7. 循环迭代直到满足所有要求
8. 将每一步决策记录到结构化审计日志（JSONL + Markdown）

完整工作流程详见 [`CLAUDE.md`](CLAUDE.md) 和 [`tutorials/10_agent_optimization.md`](tutorials/10_agent_optimization.md)。

### 快速上手

直接告诉 Claude Code 你的需求：

```
优化 agent/strategy_template.py，要求夏普比率 > 1.0，
最大回撤 < 20%，在 2021、2022、2023 三个年度分别验证。
```

Claude Code 会自动完成所有工作 —— 无需运行任何命令。

### 参考工具

[`agent/optimizer.py`](agent/optimizer.py) 提供了一个独立的规则基参数搜索工具，用于与 AI 驱动方法进行比较。它可以独立运行，但**不是**主要的优化驱动方式。

### Agent 相关文件

- **[`CLAUDE.md`](CLAUDE.md)** — Claude Code 可识别的 AI Agent 配置文件，包含完整的自优化工作流、参数调整规则、审计日志格式和代码审查要求
- **[`agent/audit_log.py`](agent/audit_log.py)** — 结构化审计日志（JSONL + Markdown）
- **[`agent/strategy_template.py`](agent/strategy_template.py)** — 参数化策略模板
- **[`agent/optimizer.py`](agent/optimizer.py)** — 参考用规则基优化器（可选，用于对比）
- **[Tutorial 10: AI Agent 自动化策略优化](tutorials/10_agent_optimization.md)** — 完整使用教程

### 审计日志

每次优化会话在 `audit_log/` 目录下生成两个文件：

```
audit_log/
├── session_<时间戳>.jsonl   # 机器可读，支持 jq 查询
└── session_<时间戳>.md      # 人类可读 Markdown 报告
```

每次参数调整都记录了：触发调整的具体指标数值、预期效果和代码审查结果。
用户可以追溯每一个决策的数据依据。

---

## 许可证

MIT
