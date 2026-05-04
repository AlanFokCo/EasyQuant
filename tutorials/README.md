# Tutorials

EasyQuant 量化策略入门教程系列，从零基础到实盘部署，涵盖趋势跟踪、均值回归、行业轮动和多因子选股四大策略方向。

---

## 教程列表

### 核心入门系列（建议按顺序学习）

| # | 教程 | 主题 | 预计阅读 |
|---|------|------|---------|
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

---

## 学习路径

根据你的背景和目标，选择最适合的学习路径：

### 路径 A：零基础入门（推荐新手）

```
01 量化基础 → 02 第一个策略 → 03 回测验证 → 04 策略优化 → 05 实盘部署
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

---

## 按策略类型查找

| 策略类型 | 教程 | 相关示例 |
|---------|------|---------|
| **趋势跟踪（双均线）** | [Tutorial 02](02_first_strategy.md)、[Tutorial 04](04_strategy_optimization.md) | [Example 02](../examples/02_write_strategy.py)、[Example 03](../examples/03_run_backtest.py) |
| **均值回归（RSI）** | [Tutorial 06](06_rsi_mean_reversion.md) | [Example 14](../examples/14_bollinger_strategy.py)、[Example 18](../examples/18_strategy_comparison.py) |
| **均值回归（布林带）** | [Tutorial 06 §8](06_rsi_mean_reversion.md#8-与布林带策略的对比) | [Example 14](../examples/14_bollinger_strategy.py) |
| **MACD 趋势确认** | [Tutorial 04 §3.4](04_strategy_optimization.md#34-macd-辅助确认) | [Example 15](../examples/15_macd_volume_strategy.py) |
| **行业轮动** | [Tutorial 07](07_sector_rotation.md) | [Example 10](../examples/10_index_concept.py) |
| **多因子选股** | [Tutorial 08](08_multi_factor.md) | [Example 16](../examples/16_multi_factor_strategy.py)、[Example 09](../examples/09_attribution_analysis.py) |
| **网格交易** | — | [Example 17](../examples/17_grid_trading_strategy.py) |
| **支撑阻力位** | — | [Example 11](../examples/11_utils_library.py)、[Example 20](../examples/20_sr_strategy/) |
| **组合回测** | [Tutorial 03 §8](03_backtesting.md#8-组合回测) | [Example 12](../examples/12_portfolio_backtest.py) |
| **模拟盘 / 实盘** | [Tutorial 05](05_live_trading.md) | [Example 05](../examples/05_paper_trade.py)、[Example 13](../examples/13_ptrade_export.py) |

---

## 前置要求

- Python 基础（变量、函数、循环、条件判断）
- 已安装 `eqlib`：`pip install akshare pandas numpy matplotlib scipy`
- 建议了解 pandas 的 DataFrame 基本操作

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
