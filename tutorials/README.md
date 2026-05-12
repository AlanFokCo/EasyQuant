# Tutorials

EasyQuant 量化策略入门教程系列，从零基础到实盘部署，涵盖趋势跟踪、均值回归、行业轮动和多因子选股四大策略方向。

**第一次使用请先阅读：[Tutorial 00 — 环境与第一次运行](00_environment_and_first_run.md)**（Python 3.10+、`pip install .`、运行 `examples/03_run_backtest.py`、打开 HTML 报告）。**文档中心：** [`doc/README.md`](../doc/README.md)（用户手册、API 索引、FAQ、报告指标详解）。

---

## 目录结构

```
tutorials/
├── prerequisites/          ← 前置知识（按需阅读）
│   ├── README.md           ← 前置知识总览
│   ├── python_basics.md    ← Python 语法、pandas/numpy、虚拟环境
│   ├── technical_concepts.md  ← 均线、RSI、MACD、布林带、ATR、KDJ 等
│   └── ashare_knowledge.md ← A 股代码规则、T+1、涨跌停、指数、手续费
├── 00_environment_and_first_run.md   ← 安装、首跑回测（必读）
├── 01_quant_basics.md      ← 量化基础概念、策略要素、常见错误
├── 02_first_strategy.md    ← 编写双均线策略
├── 03_backtesting.md       ← 解读回测报告与指标
├── 04_strategy_optimization.md  ← 参数调优、组合优化、归因分析
├── 05_live_trading.md      ← 模拟盘到实盘部署
├── 06_rsi_mean_reversion.md  ← RSI 均值回归策略
├── 07_sector_rotation.md   ← 行业轮动策略
├── 08_multi_factor.md      ← 多因子选股
├── 09_combined_strategy.md ← 综合策略（全天候 Alpha）
└── 10_agent_optimization.md  ← AI Agent 自动化策略优化
```

---

## 前置知识（按需阅读）

如果你在以下任一领域没有基础，建议先阅读对应的前置文件，再从 Tutorial 00 开始：

| 文件 | 内容 | 适合谁 |
|------|------|--------|
| [Python 基础与环境配置](prerequisites/python_basics.md) | 语法速查、pandas/numpy 核心用法、虚拟环境 | 没有写过 Python |
| [技术分析基础概念](prerequisites/technical_concepts.md) | OHLCV、均线、RSI、MACD、布林带、ATR、KDJ、ADX、支撑阻力 | 没接触过技术指标 |
| [A 股市场基础知识](prerequisites/ashare_knowledge.md) | 股票代码、T+1、涨跌停、主要指数、ST 股、手续费与税、基本面数据 | 没有 A 股投资经验 |

→ 前置知识完整索引：[prerequisites/README.md](prerequisites/README.md)

---

## 新手首日打卡（建议按顺序）

1. 安装并验证：
   ```bash
   pip install .
   python -c "from eqlib import *; print('eqlib OK')"
   ```
2. 跑第一份完整报告：
   ```bash
   python examples/03_run_backtest.py
   ```
3. 打开 `reports/*.html` 看指标卡片、回撤曲线、交易记录。
4. 需要离线快验时，先跑本地数据示例（可选）：
   ```bash
   python examples/19_local_data_backtest.py --download-all
   python examples/19_local_data_backtest.py
   ```
5. 做最小功能验证（可选）：
   ```bash
   python examples/01_fetch_data.py
   pip install -e ".[dev]"
   python -m pytest tests/
   ```

完成后继续阅读 [Tutorial 01](01_quant_basics.md) 与 [Tutorial 02](02_first_strategy.md)。

---

## 教程列表

### 前置知识（可选，按需阅读）

| 文件 | 内容摘要 | 预计阅读 |
|------|---------|---------|
| [Python 基础与环境配置](prerequisites/python_basics.md) | 变量、函数、pandas/numpy 核心操作、虚拟环境 | 20 min |
| [技术分析基础概念](prerequisites/technical_concepts.md) | OHLCV、MA / RSI / MACD / 布林带 / ATR / KDJ / ADX、支撑阻力 | 25 min |
| [A 股市场基础知识](prerequisites/ashare_knowledge.md) | 股票代码格式、T+1、涨跌停、常用指数、ST 股、手续费与税 | 20 min |

### 环境与入门

| # | 教程 | 主题 | 预计阅读 |
|---|------|------|---------|
| 00 | [**环境与第一次运行**](00_environment_and_first_run.md) | Python 版本、安装、首跑回测、打开报告 | 10 min |
| 01 | [什么是量化交易策略](01_quant_basics.md) | 量化交易基础、策略要素、常见错误 | 15 min |
| 02 | [写第一个策略](02_first_strategy.md) | 编写双均线策略、运行回测 | 20 min |
| 03 | [回测验证](03_backtesting.md) | 解读报告、风险指标、组合回测 | 20 min |
| 04 | [策略优化与改进](04_strategy_optimization.md) | 参数调优、组合优化、归因分析 | 20 min |
| 05 | [模拟盘到实盘](05_live_trading.md) | 模拟盘验证、PTrade/QMT 导出部署 | 15 min |

### 策略专项教程（按兴趣选读）

| # | 教程 | 策略类型 | 核心技术 | 预计阅读 |
|---|------|---------|---------|---------|
| 06 | [RSI 均值回归策略](06_rsi_mean_reversion.md) | 均值回归 | RSI、布林带二次确认、止损 | 20 min |
| 07 | [行业轮动策略](07_sector_rotation.md) | 行业轮动 | 动量打分、等权调仓、行业 API | 20 min |
| 08 | [多因子选股](08_multi_factor.md) | 因子选股 | Z-Score 标准化、因子合成、IC 检验 | 25 min |
| 09 | [全天候 Alpha 综合策略](09_combined_strategy.md) | 综合策略 | 多因子+行业轮动+RSI/布林/MACD+ATR止损 | 30 min |
| 10 | [AI Agent 自动化策略优化](10_agent_optimization.md) | Agent 工作流 | 自优化循环、数据驱动调参、审计日志 | 25 min |

---

## 学习路径

根据你的背景和目标，选择最适合的学习路径：

### 路径 A：零基础入门（推荐新手）

```
00 环境与第一次运行 → 01 量化基础 → 02 第一个策略 → 03 回测验证 → 04 策略优化 → 05 实盘部署
```

适合：第一次接触量化交易，想系统了解整个流程

### 路径 B：趋势跟踪策略方向

```
02 第一个策略（双均线）→ 03 回测验证 → 04 策略优化（止损/大盘过滤）→ 07 行业轮动
```

适合：想做趋势交易，关注动量、均线突破的用户

### 路径 C：均值回归策略方向

```
02 第一个策略 → 03 回测验证 → 06 RSI 均值回归 → 04 策略优化
```

适合：想做震荡行情中的高抛低吸，关注 RSI、布林带的用户

### 路径 D：选股与组合方向

```
02 第一个策略 → 03 回测验证 → 08 多因子选股 → 07 行业轮动 → 04 策略优化
```

适合：想构建多股票组合策略，关注量化选股的用户

### 路径 E：快速上手实盘

```
02 第一个策略 → 03 回测验证 → 05 模拟盘到实盘
```

适合：有一定基础，想尽快把策略部署到 PTrade/QMT 的用户

### 路径 F：综合策略实战（推荐进阶用户）

```
06 RSI 均值回归 → 07 行业轮动 → 08 多因子选股 → 09 综合策略
```

适合：已掌握单一策略，希望将所有技术融合到一个生产级策略的用户

### 路径 G：AI Agent 自动化优化（推荐有一定基础的用户）

```
02 第一个策略 → 03 回测验证 → 04 策略优化 → 10 AI Agent 自动化优化
```

适合：想用 AI 工具自动调参、无需人工干预完成策略优化闭环的用户

---

## 按策略类型查找

| 策略类型 | 教程 | 相关示例 |
|---------|------|---------|
| **趋势跟踪（双均线）** | [Tutorial 02](02_first_strategy.md)、[Tutorial 04](04_strategy_optimization.md) | [Example 02](../examples/02_write_strategy.py)、[Example 03](../examples/03_run_backtest.py) |
| **均值回归（RSI）** | [Tutorial 06](06_rsi_mean_reversion.md) | [Example 14](../examples/14_bollinger_strategy.py)、[Example 18](../examples/18_strategy_comparison.py) |
| **均值回归（布林带）** | [Tutorial 06 第 8 节](06_rsi_mean_reversion.md#8-与布林带策略的对比) | [Example 14](../examples/14_bollinger_strategy.py) |
| **MACD 趋势确认** | [Tutorial 04 第 3.4 节](04_strategy_optimization.md#34-macd-辅助确认) | [Example 15](../examples/15_macd_volume_strategy.py) |
| **行业轮动** | [Tutorial 07](07_sector_rotation.md) | [Example 10](../examples/10_index_concept.py) |
| **多因子选股** | [Tutorial 08](08_multi_factor.md) | [Example 16](../examples/16_multi_factor_strategy.py)、[Example 09](../examples/09_attribution_analysis.py) |
| **综合策略（全天候 Alpha）** | [Tutorial 09](09_combined_strategy.md) | [Example 21](../examples/21_combined_strategy/) |
| **网格交易** | — | [Example 17](../examples/17_grid_trading_strategy.py) |
| **支撑阻力位** | — | [Example 11](../examples/11_utils_library.py)、[Example 20](../examples/20_sr_strategy/) |
| **组合回测** | [Tutorial 03 第 8 节](03_backtesting.md#8-组合回测) | [Example 12](../examples/12_portfolio_backtest.py) |
| **AI Agent 自动化优化** | [Tutorial 10](10_agent_optimization.md) | [agent/optimizer.py](../agent/optimizer.py)、[agent/strategy_template.py](../agent/strategy_template.py) |
| **模拟盘 / 实盘** | [Tutorial 05](05_live_trading.md) | [Example 05](../examples/05_paper_trade.py)、[Example 13](../examples/13_ptrade_export.py) |

---

## 前置要求

- Python **3.10+**（见 [Tutorial 00](00_environment_and_first_run.md)）
- 已在仓库根目录执行 **`pip install .`** 或 **`pip install -e .`**
- Python 基础（变量、函数、循环、条件判断） → 没有基础？见 [Python 基础与环境配置](prerequisites/python_basics.md)
- 技术指标基础（均线、RSI 等） → 没有基础？见 [技术分析基础概念](prerequisites/technical_concepts.md)
- A 股市场常识（T+1、涨跌停、股票代码等） → 没有基础？见 [A 股市场基础知识](prerequisites/ashare_knowledge.md)

**排错与 API 速查：** [`doc/FAQ.md`](../doc/FAQ.md)、[`doc/api_index.md`](../doc/api_index.md)。

---

## 与示例的区别

| | 教程 (tutorials/) | 示例 (examples/) |
|--|-------------------|-----------------|
| 形式 | Markdown 文档 + 代码片段 | 可运行的 Python 脚本 |
| 目标 | 系统学习概念和方法 | 快速参考和复制运行 |
| 内容 | 讲解"为什么"和"怎么做" | 展示"具体代码长什么样" |

建议：先用教程学习概念，再运行示例加深理解。

---

## 实战案例

完成教程后，查看以下真实策略案例：

### 全天候 Alpha 综合策略（完整生产级案例）

**[Tutorial 09: 全天候 Alpha 综合策略](09_combined_strategy.md)** —
将所有教程的策略技术融合为一个完整的生产级综合策略，包含多因子选股、行业轮动、
RSI/布林带/MACD/ATR 技术信号、支撑阻力位和生命周期回调，配有完整的回测和模拟盘代码。

**[Example 21: 全天候 Alpha 综合策略](../examples/21_combined_strategy/)** —
完整可运行的综合策略代码，包含策略模块、回测脚本和模拟盘脚本。

### 支撑阻力位组合策略（完整实盘案例）

**[Example 20: 支撑阻力位组合策略](../examples/20_sr_strategy/)** —
一个完整的多股票组合策略实战案例，包含预生成的回测报告（HTML/PNG/Markdown/JSON），
可以直接打开浏览器查看策略表现，也可以运行回测验证。

**策略亮点：** 8 只不同行业 A 股，结合支撑阻力位 + RSI + MACD + ATR 止损，
回测期间（2020–2026）总收益 +137%。

### 多策略横向对比

**[Example 18: 多策略对比](../examples/18_strategy_comparison.py)** —
在同一只股票、同一时间段内，横向对比买入持有、双均线、RSI 均值回归、布林带四种策略。
这是检验你对不同策略理解是否到位的最好工具。
