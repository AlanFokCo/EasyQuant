<div align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="250" alt="EasyQuant logo"/></a>
<p><strong>EasyQuant</strong> - 面向 <strong>中国 A 股市场</strong> 的量化策略与回测工具。</p>
<p>核心 Python 包为 <code>eqlib</code>：事件驱动回测引擎、数据 API 与分析工具。</p>
<p>
<a href="https://github.com/AlanFokCo/EasyQuant/blob/main/README.md">English</a> · <a href="tutorials/README.md">新手教程</a> · <a href="doc/README.md"><b>文档中心</b></a> · <a href="doc/user_guide.md">用户手册</a> · <a href="doc/api_index.md">API 速查</a> · <a href="doc/api_reference.md">API 参考</a> · <a href="examples/Examples.md">示例</a>
</p>
</div>

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

## 新手上手（前 30 分钟）

如果你是第一次使用 EasyQuant，建议按以下顺序执行：

1. **验证安装是否成功**
   ```bash
   python -c "from eqlib import *; print('eqlib OK')"
   ```
2. **运行第一条完整回测链路**
   ```bash
   python examples/03_run_backtest.py
   ```
3. **打开 `reports/` 下生成的 HTML 报告**（可交互图表 + 指标卡片）。
4. **做两项快速检查**
   ```bash
   python examples/01_fetch_data.py
   # 可选：运行测试
   pip install -e ".[dev]"
   python -m pytest tests/
   ```

建议先阅读 [Tutorial 00：环境与第一次运行](tutorials/00_environment_and_first_run.md) 再继续后续教程。

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

可将以上代码保存为 `my_first_strategy.py`，然后执行：

```bash
python my_first_strategy.py
```

> 订单执行模型：`order*` 系列 API 在当前回调里只是下单，实际按**下一个交易日开盘价**成交（避免未来函数偏差）。
>
> **输出结果：** 运行后会在 `reports/` 生成 `.png`、`.html`、`.md`、`.json` 四类文件。优先在浏览器打开 `.html` 查看完整报告。

---

## 示例

参见 [`examples/Examples.md`](examples/Examples.md) 索引；脚本位于 [`examples/README.md`](examples/README.md)：

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

- [**新手教程**](tutorials/README.md) — 从零基础到实盘部署，5 篇系列教程
- [**用户手册**](doc/user_guide.md) — 教程：编写策略、运行回测、解读报告
- [**API 参考**](doc/api_reference.md) — 完整 API：结构体、参数说明、用法
- [**工具库参考**](doc/utils_reference.md) — 计算工具：技术指标、统计分析、资金管理、支撑阻力位
- [**PTrade/QMT 适配器**](doc/ptrade_adapter.md) — 将 EasyQuant 策略导出为 PTrade/QMT 平台格式

---

## 策略参数优化与审计

EasyQuant 提供 **`PARAMS` / `PARAM_RANGES`** 约定、可参考运行的 **`agent/optimizer.py`** 规则搜索，以及 **`agent/audit_log.py`** 审计日志。你可以在脚本、Notebook 或 CI 中自行调用 `eqlib` API 完成「回测 → 分析 → 改参 → 再回测」闭环；**不依赖**任何特定编辑器或商业 AI 产品。

### 延伸阅读

- **[Tutorial 10：参数优化与审计](tutorials/10_agent_optimization.md)** — 参数化、`optimizer.py`、审计与审查清单（中文）
- **[`agent/optimizer.py`](agent/optimizer.py)** — 可选命令行规则搜索，用于基线对比
- **[`agent/audit_log.py`](agent/audit_log.py)** — 结构化审计日志
- **[`agent/strategy_template.py`](agent/strategy_template.py)** — 参数化策略模板

### 审计日志目录

每次优化会话可在 `audit_log/` 写入：

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
