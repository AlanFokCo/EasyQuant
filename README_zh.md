# EasyQuant

一个面向 **中国 A 股市场** 的量化策略与回测工具。

本项目提供 `eqlib` Python 包——核心库，包含事件驱动回测引擎、数据 API 和分析工具。

[English](README.md) · [新手教程](tutorials/) · [用户手册](doc/user_guide.md) · [API 参考](doc/api_reference.md) · [示例](examples/)

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

---

## 文档

- [**新手教程**](tutorials/) — 从零基础到实盘部署，5 篇系列教程
- [**用户手册**](doc/user_guide.md) — 教程：编写策略、运行回测、解读报告
- [**API 参考**](doc/api_reference.md) — 完整 API：结构体、参数说明、用法
- [**工具库参考**](doc/utils_reference.md) — 计算工具：技术指标、统计分析、资金管理、支撑阻力位
- [**PTrade/QMT 适配器**](doc/ptrade_adapter.md) — 将 EasyQuant 策略导出为 PTrade/QMT 平台格式

---

## AI Agent — 自动化策略优化

EasyQuant 内置了 **AI Agent 工作流**，可让 Claude Code（或任何兼容的 AI 编码智能体）执行完整的无人值守策略优化循环。

### Agent 能做什么

1. 加载你的策略及其可调参数（`PARAMS` / `PARAM_RANGES`）
2. 在多个历史时段运行回测
3. 使用 `analyze_returns` 分析结果（夏普、回撤、胜率、alpha 等）
4. 生成**数据驱动**的参数调整方案，并记录每次调整的依据
5. 每次调参后执行代码审查
6. 循环迭代，直到满足你的所有要求（或达到最大迭代次数）
7. 将每一步决策记录到结构化审计日志（JSONL + Markdown）

### 快速上手

```bash
# 使用内置模板策略和默认要求
python agent/optimizer.py

# 使用自定义策略和自定义目标
python agent/optimizer.py \
    --strategy my_strategy.py \
    --min-sharpe 1.0 \
    --max-drawdown 0.20 \
    --max-iterations 15 \
    --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31" "2024-01-01:2024-12-31" \
    --output-strategy my_strategy_optimized.py
```

### Agent 相关文件

- **[`CLAUDE.md`](CLAUDE.md)** — Claude Code 可识别的 AI Agent 配置文件，包含完整的自优化工作流、参数调整规则、审计日志格式和代码审查要求
- **[`agent/optimizer.py`](agent/optimizer.py)** — 自优化循环编排器
- **[`agent/audit_log.py`](agent/audit_log.py)** — 结构化审计日志（JSONL + Markdown）
- **[`agent/strategy_template.py`](agent/strategy_template.py)** — 参数化策略模板
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
