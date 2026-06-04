<div align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="../assets/logo.svg" width="240" alt="EasyQuant"/></a>
</div>

# 教程导读（Tutorials）

本系列从零基础到实盘部署，涵盖趋势跟踪、均值回归、行业轮动和多因子选股等方向。**英文标题「Tutorials」仅作导航标识，正文以中文为主。**

!!! tip "阅读格式"

    自 Tutorial 00 起，每篇教程文首带有 **「本篇导览」** 表格，便于你快速判断**目标、预计用时与前置教程**；正文仍保留原有目录与深度讲解。

**第一次使用请先阅读：[Tutorial 00 — 环境与第一次运行 / 量化交易基础概念](00-getting-started.md)**（Python 3.10+、`pip install .`、运行 `examples/03_run_backtest.py`、打开 HTML 报告、量化基础概念）。**文档中心：** [指南总览](../how-to/index.md)（用户手册、API 索引、FAQ、报告指标详解）。

---

## 目录结构

```
docs/tutorials/
├── prerequisites/          ← 前置知识（按需阅读）
│   ├── index.md            ← 前置知识总览
│   ├── python-basics.md    ← Python 语法、pandas/numpy、虚拟环境
│   ├── technical-concepts.md  ← 均线、RSI、MACD、布林带、ATR、KDJ 等
│   └── ashare-knowledge.md ← A 股代码规则、T+1、涨跌停、指数、手续费
├── 00-getting-started.md   ← 环境安装、首跑回测、量化基础概念（必读）
├── 01-first-strategy.md    ← 编写双均线策略
├── 02-backtesting.md       ← 解读回测报告与指标
├── 03-optimization.md      ← 参数调优、组合优化、归因分析
├── 04-live-trading.md      ← 模拟盘到实盘部署
├── 05-rsi-mean-reversion.md  ← RSI 均值回归策略
├── 06-sector-rotation.md   ← 行业轮动策略
├── 07-multi-factor.md      ← 多因子选股
├── 08-combined-strategy.md ← 综合策略（全天候 Alpha）
├── 09-param-optimization.md  ← 策略参数优化与审计
└── 10-ashare-data-risk.md  ← A 股特色数据与风控
```

---

## 前置知识（按需阅读）

如果你在以下任一领域没有基础，建议先阅读对应的前置文件，再从 Tutorial 00 开始：

| 文件 | 内容 | 适合谁 |
|------|------|--------|
| [Python 基础与环境配置](prerequisites/python-basics.md) | 语法速查、pandas/numpy 核心用法、虚拟环境 | 没有写过 Python |
| [技术分析基础概念](prerequisites/technical-concepts.md) | OHLCV、均线、RSI、MACD、布林带、ATR、KDJ、ADX、支撑阻力 | 没接触过技术指标 |
| [A 股市场基础知识](prerequisites/ashare-knowledge.md) | 股票代码、T+1、涨跌停、主要指数、ST 股、手续费与税、基本面数据 | 没有 A 股投资经验 |

→ 前置知识完整索引：[prerequisites/index.md](prerequisites/index.md)

---

## 新手首日打卡（建议按顺序）

1. 安装并验证：
   ```bash
   # PyPI 安装（推荐，无需克隆仓库）
   pip install easyquant-eqlib
   # 或从源码安装（仓库根目录）
   # pip install .
   python -c "from eqlib import *; print('eqlib OK')"
   ```
2. 跑第一份完整报告（需在仓库目录运行）：
   ```bash
   python examples/03_run_backtest.py
   ```
3. 打开 `reports/*.html` 看指标卡片、回撤曲线、交易记录。
4. 需要离线快速验证时，先跑本地数据示例（可选）：
   ```bash
   python examples/06_local_data.py --download-all
   python examples/06_local_data.py
   ```
5. 做最小功能验证（可选）：
   ```bash
   python examples/01_fetch_data.py
   pip install -e ".[dev]"
   python -m pytest tests/
   ```

> **替代方案：Web 策略工作室**
> 如果你更喜欢浏览器界面，可以使用 [Web 策略工作室](https://github.com/AlanFokCo/EasyQuant/tree/main/web_strategy_studio/)。
> 无需安装 Python 环境或克隆仓库，打开浏览器即可编写策略、运行回测、查看报告。
> 适合不想折腾环境配置的用户。详见 [Web 工作室文档](../how-to/web-studio.md)。

完成后继续阅读 [Tutorial 01](01-first-strategy.md) 与 [Tutorial 02](02-backtesting.md)。

---

## 教程列表

### 前置知识（可选，按需阅读）

| 文件 | 内容摘要 | 预计阅读 |
|------|---------|---------|
| [Python 基础与环境配置](prerequisites/python-basics.md) | 变量、函数、pandas/numpy 核心操作、虚拟环境 | 20 min |
| [技术分析基础概念](prerequisites/technical-concepts.md) | OHLCV、MA / RSI / MACD / 布林带 / ATR / KDJ / ADX、支撑阻力 | 25 min |
| [A 股市场基础知识](prerequisites/ashare-knowledge.md) | 股票代码格式、T+1、涨跌停、常用指数、ST 股、手续费与税 | 20 min |

### 环境与入门

| # | 教程 | 主题 | 预计阅读 |
|---|------|------|---------|
| 00 | [**环境与量化基础**](00-getting-started.md) | 环境安装、首跑回测、量化基础概念、策略要素、常见错误 | 25 min |
| 01 | [写第一个策略](01-first-strategy.md) | 编写双均线策略、运行回测 | 20 min |
| 02 | [回测验证](02-backtesting.md) | 解读报告、风险指标、组合回测 | 20 min |
| 03 | [策略优化与改进](03-optimization.md) | 参数调优、组合优化、归因分析 | 20 min |
| 04 | [模拟盘到实盘](04-live-trading.md) | 模拟盘验证、PTrade/QMT 导出部署 | 15 min |

### 策略专项教程（按兴趣选读）

| # | 教程 | 策略类型 | 核心技术 | 预计阅读 |
|---|------|---------|---------|---------|
| 05 | [RSI 均值回归策略](05-rsi-mean-reversion.md) | 均值回归 | RSI、布林带二次确认、止损 | 20 min |
| 06 | [行业轮动策略](06-sector-rotation.md) | 行业轮动 | 动量打分、等权调仓、行业 API | 20 min |
| 07 | [多因子选股](07-multi-factor.md) | 因子选股 | Z-Score 标准化、因子合成、IC 检验 | 25 min |
| 08 | [全天候 Alpha 综合策略](08-combined-strategy.md) | 综合策略 | 多因子+行业轮动+RSI/布林/MACD+ATR止损 | 30 min |
| 09 | [策略参数优化与审计](09-param-optimization.md) | 参数化与工具 | PARAMS、`optimizer.py`、审计日志、审查清单 | 20 min |
| 10 | [A 股数据与风控](10-ashare-data-risk.md) | A 股特色数据 | 北向资金、融资融券、涨跌停、限售股解禁、组合风控 | 25 min |

---

## 学习路径

根据你的背景和目标，选择最适合的学习路径：

### 路径 A：零基础入门（推荐新手）

```
00 环境与量化基础 → 01 第一个策略 → 02 回测验证 → 03 策略优化 → 04 实盘部署
```

适合：第一次接触量化交易，想系统了解整个流程

### 路径 B：趋势跟踪策略方向

```
01 第一个策略（双均线）→ 02 回测验证 → 03 策略优化（止损/大盘过滤）→ 06 行业轮动
```

适合：想做趋势交易，关注动量、均线突破的用户

### 路径 C：均值回归策略方向

```
01 第一个策略 → 02 回测验证 → 05 RSI 均值回归 → 03 策略优化
```

适合：想做震荡行情中的高抛低吸，关注 RSI、布林带的用户

### 路径 D：选股与组合方向

```
01 第一个策略 → 02 回测验证 → 07 多因子选股 → 06 行业轮动 → 03 策略优化
```

适合：想构建多股票组合策略，关注量化选股的用户

### 路径 E：快速上手实盘

```
01 第一个策略 → 02 回测验证 → 04 模拟盘到实盘
```

适合：有一定基础，想尽快把策略部署到 PTrade/QMT 的用户

### 路径 F：综合策略实战（推荐进阶用户）

```
05 RSI 均值回归 → 06 行业轮动 → 07 多因子选股 → 08 综合策略
```

适合：已掌握单一策略，希望将所有技术融合到一个生产级策略的用户

### 路径 G：参数优化与审计（推荐有一定基础的用户）

```
01 第一个策略 → 02 回测验证 → 03 策略优化 → 09 参数优化与审计
```

适合：希望用脚本或自建流程调参、并保留可审计记录的用户

---

## 按策略类型查找

| 策略类型 | 教程 | 相关示例 |
|---------|------|---------|
| **趋势跟踪（双均线）** | [Tutorial 01](01-first-strategy.md)、[Tutorial 03](03-optimization.md) | [Example 02](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/02_write_strategy.py)、[Example 03](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/03_run_backtest.py) |
| **均值回归（RSI）** | [Tutorial 05](05-rsi-mean-reversion.md) | [Example 14](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py)、[Example 18](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/18_strategy_comparison.py) |
| **均值回归（布林带）** | [Tutorial 05 第 8 节](05-rsi-mean-reversion.md#8-与布林带策略的对比) | [Example 14](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/15_bollinger_strategy.py) |
| **MACD 趋势确认** | [Tutorial 03 第 3.4 节](03-optimization.md#34-macd-辅助确认) | [Example 15](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/16_macd_volume.py) |
| **行业轮动** | [Tutorial 06](06-sector-rotation.md) | [Example 10](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/10_index_concept.py) |
| **多因子选股** | [Tutorial 07](07-multi-factor.md) | [Example 16](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/17_multi_factor.py)、[Example 09](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/09_attribution.py) |
| **综合策略（全天候 Alpha）** | [Tutorial 08](08-combined-strategy.md) | [Example 21](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md) |
| **网格交易** | — | [Example 17](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/18_grid_trading.py) |
| **支撑阻力位** | — | [Example 11](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/08_utils_library.py)、[Example 20](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md) |
| **组合回测** | [Tutorial 02 第 8 节](02-backtesting.md#8-组合回测) | [Example 12](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/11_portfolio_backtest.py) |
| **参数优化与审计** | [Tutorial 09](09-param-optimization.md) | [agent/optimizer.py](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/optimizer.py)、[agent/strategy_template.py](https://github.com/AlanFokCo/EasyQuant/blob/main/agent/strategy_template.py) |
| **模拟盘 / 实盘** | [Tutorial 04](04-live-trading.md) | [Example 05](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/12_paper_trade.py)、[Example 13](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/12_paper_trade.py) |
| **A 股特色数据与风控** | [Tutorial 10](10-ashare-data-risk.md) | — |

---

## 前置要求

- Python **3.10+**（见 [Tutorial 00](00-getting-started.md)）
- 已安装 eqlib：`pip install easyquant-eqlib`（PyPI）或 `pip install .` / `pip install -e .`（源码）
- Python 基础（变量、函数、循环、条件判断） → 没有基础？见 [Python 基础与环境配置](prerequisites/python-basics.md)
- 技术指标基础（均线、RSI 等） → 没有基础？见 [技术分析基础概念](prerequisites/technical-concepts.md)
- A 股市场常识（T+1、涨跌停、股票代码等） → 没有基础？见 [A 股市场基础知识](prerequisites/ashare-knowledge.md)

**排错与 API 速查：** [FAQ](../project/faq.md)、[API 参考](../reference/index.md)。

---

## 与示例的区别

| | 教程 (docs/tutorials/) | 示例 (examples/) |
|--|-------------------|-----------------|
| 形式 | Markdown 文档 + 代码片段 | 可运行的 Python 脚本 |
| 目标 | 系统学习概念和方法 | 快速参考和复制运行 |
| 内容 | 讲解"为什么"和"怎么做" | 展示"具体代码长什么样" |

建议：先用教程学习概念，再运行示例加深理解。

---

## 实战案例

完成教程后，查看以下真实策略案例：

### 全天候 Alpha 综合策略（完整生产级案例）

**[Tutorial 08: 全天候 Alpha 综合策略](08-combined-strategy.md)** —
将所有教程的策略技术融合为一个完整的生产级综合策略，包含多因子选股、行业轮动、
RSI/布林带/MACD/ATR 技术信号、支撑阻力位和生命周期回调，配有完整的回测和模拟盘代码。

**[Example 21: 全天候 Alpha 综合策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/20_all_weather_alpha/README.md)** —
完整可运行的综合策略代码，包含策略模块、回测脚本和模拟盘脚本。

### 支撑阻力位组合策略（完整实盘案例）

**[Example 20: 支撑阻力位组合策略](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** —
一个完整的多股票组合策略实战案例，包含预生成的回测报告（HTML/PNG/Markdown/JSON），
可以直接打开浏览器查看策略表现，也可以运行回测验证。

**策略亮点：** 8 只不同行业 A 股，结合支撑阻力位 + RSI + MACD + ATR 止损，
回测期间（2020–2026）总收益 +137%。

### 多策略横向对比

**[Example 18: 多策略对比](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/18_strategy_comparison.py)** —
在同一只股票、同一时间段内，横向对比买入持有、双均线、RSI 均值回归、布林带四种策略。
这是检验你对不同策略理解是否到位的最好工具。
