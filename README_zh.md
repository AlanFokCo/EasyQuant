<div align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="250" alt="EasyQuant logo"/></a>
<p><strong>EasyQuant</strong> - 面向 <strong>中国 A 股市场</strong> 的量化策略与回测工具。</p>
<p>核心 Python 包为 <code>eqlib</code>：事件驱动回测引擎、数据 API 与分析工具。</p>
<p>
<a href="https://github.com/AlanFokCo/EasyQuant/blob/main/README.md">English</a> · <a href="https://AlanFokCo.github.io/EasyQuant/">在线文档站</a> · <a href="tutorials/README.md">新手教程</a> · <a href="doc/README.md"><b>文档中心</b></a> · <a href="doc/user_guide.md">用户手册</a> · <a href="doc/api_index.md">API 速查</a> · <a href="doc/api_reference.md">API 参考</a> · <a href="examples/Examples.md">示例</a>
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
- **选股** — 按因子定期调仓（ST/PB/PE/动量过滤、Top-N、多因子评分）
- **工具库** — 技术指标（MA、MACD、RSI、KDJ、布林带、ATR）、统计分析、仓位管理（Kelly、ATR、固定比例）
- **报告输出** — 交互式 HTML 报告（可在浏览器打开）、图表（PNG）、Markdown、JSON，包含 20+ 风险/收益指标
- **直接查询股票** — 链式 API（`query` / `valuation` / `get_fundamentals`）用于基本面筛选

---

## 报告预览

`run_strategy` 生成**交互式 HTML 报告**（可在任意浏览器打开），同时输出 PNG、Markdown 和 JSON 文件。以下为真实回测结果截图——布局相同，数据不同。

### 盈利策略

| **MACD 趋势 + 成交量** (600536) | **布林带均值回归** (601088) | **支撑/阻力位** (8 只股票) |
|:---:|:---:|:---:|
| **+103.48%** · 16 笔 | **+57.77%** · 8 笔 | **+119.97%** · 171 笔 |
| [![MACD+Volume](tutorials/assets/example_report_macd_volume.png)](tutorials/assets/example_report_macd_volume.png) | [![Bollinger](tutorials/assets/example_report_bollinger.png)](tutorials/assets/example_report_bollinger.png) | [![S/R](tutorials/assets/example_report_sr_strategy.png)](tutorials/assets/example_report_sr_strategy.png) |
| HTML 报告: [![HTML](tutorials/assets/example_report_html_macd_volume.png)](tutorials/assets/example_report_html_macd_volume.png) | HTML 报告: [![HTML](tutorials/assets/example_report_html_bollinger.png)](tutorials/assets/example_report_html_bollinger.png) | HTML 报告: [![HTML](tutorials/assets/example_report_html_sr_strategy.png)](tutorials/assets/example_report_html_sr_strategy.png) |

| **网格交易** (601857) | **多因子** (10 只股票) | **选股策略** (14 只股票) |
|:---:|:---:|:---:|
| **+30.25%** · 10 笔 | **+5.19%** · 135 笔 | **+16.96%** · 5 只持仓 |
| [![Grid](tutorials/assets/example_report_grid.png)](tutorials/assets/example_report_grid.png) | [![Multi-Factor](tutorials/assets/example_report_multifactor.png)](tutorials/assets/example_report_multifactor.png) | [![Stock Selection](tutorials/assets/example_report_stock_selection.png)](tutorials/assets/example_report_stock_selection.png) |
| HTML 报告: [![HTML](tutorials/assets/example_report_html_grid.png)](tutorials/assets/example_report_html_grid.png) | HTML 报告: [![HTML](tutorials/assets/example_report_html_multifactor.png)](tutorials/assets/example_report_html_multifactor.png) | HTML 报告: [![HTML](tutorials/assets/example_report_html_stock_selection.png)](tutorials/assets/example_report_html_stock_selection.png) |

### 亏损策略（用于学习）

| **动量组合** (5 只股票) | **本地数据** (000768) |
|:---:|:---:|
| **−25.69%** · 52 笔 | **−33.28%** · 16 笔 |
| [![Portfolio](tutorials/assets/example_report_portfolio.png)](tutorials/assets/example_report_portfolio.png) | [![Local Data](tutorials/assets/example_report_19_localdata.png)](tutorials/assets/example_report_19_localdata.png) |
| HTML 报告: [![HTML](tutorials/assets/example_report_html_portfolio.png)](tutorials/assets/example_report_html_portfolio.png) | HTML 报告: [![HTML](tutorials/assets/example_report_html_19_localdata.png)](tutorials/assets/example_report_html_19_localdata.png) |

> **如何阅读报告：** 每个 HTML 页面依次展示：头部摘要 → 指标卡片（夏普、最大回撤、alpha 等）→ K 线图 → 累计收益 vs 基准 → 回撤曲线 → 每日盈亏 → 交易/持仓标签页。字段详解见 [**报告与指标说明**](doc/reports_and_metrics.md)。

---

---

## 性能

- **内存感知数据加载** — 从磁盘缓存（parquet）或本地 CSV 文件预加载数据，
  自动限制内存用量（默认 1 GB）。超出限制时引擎自动切换为紧凑切片模式——
  结果完全一致，只是略慢。
- **快速 I/O** — `attribute_history` 直接读取内存中的数据，避免每次调用都访问
  磁盘或网络，将典型的 6 年以上回测时间从约 20 分钟缩短至约 1 分钟。
- **并行数据加载** — 多线程预加载，加快启动速度。

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

完整索引见 [`examples/Examples.md`](examples/Examples.md)，脚本位于 [`examples/`](examples/)。

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

- [**新手教程**](tutorials/) — 从零基础到实盘部署的入门指南，以及参数调优（教程 10）
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

## 选股

EasyQuant 支持通过选股接口实现定期调仓。你无需硬编码股票池，只需定义一个选股函数，按周、按月或以任意自定义频率运行。

### 快速开始

```python
from eqlib import *

def my_selection(context):
    """返回本期要交易的股票列表。"""
    # 过滤 ST 股，然后按 PE 最低取前 5
    candidates = filter_st_stocks(["601390", "600519", "000858", "600036"])
    df = fetch_factor_data(candidates, fields=["pe"])
    df = df.dropna(subset=["pe"]).sort_values("pe", ascending=True)
    return df.head(5).index.tolist()

def initialize(context):
    context.universe = ["601390"]  # 初始股票池
    run_selection(my_selection, rebalance="monthly:1")  # 每月 1 日运行
    run_daily(trade, time="every_bar")

def trade(context):
    selected = context.universe
    # ... 卖出不在 selected 的股票，买入 selected 中的股票 ...
```

### 调仓频率

| 值 | 含义 | 示例 |
|-------|---------|---------|
| `"monthly:N"` | 每月第 N 日（1-31） | `"monthly:1"`（1 日），`"monthly:15"`（15 日） |
| `"weekly:N"` | 每周第 N 个工作日（0=周一，4=周五） | `"weekly:0"`（周一），`"weekly:4"`（周五） |
| `"daily"` | 每个交易日 | `"daily"` |

### 三种定义选股的方式

**1. 普通函数**（最简单）：

```python
def simple_selection(context):
    candidates = filter_st_stocks(CANDIDATE_POOL)
    return TopNSelector(factor="pe", top_n=5).rank(candidates, context)
```

**2. StockSelector 子类**（复杂逻辑）：

```python
class MySelector(StockSelector):
    def filter(self, candidates, context):
        candidates = filter_st_stocks(candidates)
        return filter_high_pe_stocks(candidates, max_pe=50)
    def rank(self, securities, context):
        return MultiFactorSelector(
            factors={"pe": -0.4, "pb": -0.3, "pct_change": 0.3},
            top_n=5
        ).rank(securities, context)
```

**3. 通过 `run_strategy` 参数传入**：

```python
result = run_strategy(
    initialize_func=initialize,
    selection_func=my_selection,
    selection_rebalance="weekly:0",
)
```

### 可用过滤器与选择器

| API | 说明 |
|-----|-------------|
| `filter_st_stocks(securities)` | 移除 ST / *ST 股票 |
| `filter_paused_stocks(securities, context)` | 移除停牌股票 |
| `filter_low_price_stocks(securities, min_price)` | 移除低于价格阈值的股票 |
| `filter_high_pe_stocks(securities, max_pe)` | 移除 PE 高于阈值的股票 |
| `fetch_factor_data(securities, fields)` | 获取多维度数据（PE/PB/动量/MA/RSI） |
| `TopNSelector(factor, top_n, ascending)` | 按单因子排名 |
| `MultiFactorSelector(factors, top_n)` | 按加权综合评分排名 |

完整示例见 [`examples/22_stock_selection_strategy.py`](examples/22_stock_selection_strategy.py)。

---

## 目录结构

| 目录 | 用途 |
|-----------|---------|
| `data/` | 日线 OHLCV 本地 CSV 缓存。当 `use_local=True` 或调用 `save_stock_local()` 时自动创建。删除后将从网络重新下载。 |
| `reports/` | 回测报告输出目录（PNG 图表、HTML、Markdown、JSON）。由 `run_strategy()` 和 `generate_chart()` 自动创建。 |

---

## 许可证

MIT
