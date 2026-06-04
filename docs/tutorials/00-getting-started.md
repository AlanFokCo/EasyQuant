# Tutorial 00: 环境与量化基础

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 配好 Python 环境、安装 `eqlib`、跑通一次回测并在浏览器中打开 HTML 报告 |
    | **预计用时** | 约 30 分钟 |
    | **前置** | 无（零基础可先读下方「前置知识」链接） |

> 在按顺序阅读后续量化基础概念之前，请先完成本节：保证 Python 环境、`eqlib` 安装与一次成功回测，避免后续教程中的代码无法运行。

**没有 Python 基础？** 先阅读 [前置知识：Python 基础与环境配置](prerequisites/python-basics.md)。  
**不了解技术指标？** 阅读 [前置知识：技术分析基础概念](prerequisites/technical-concepts.md)。  
**不熟悉 A 股规则？** 阅读 [前置知识：A 股市场基础知识](prerequisites/ashare-knowledge.md)。

---

## 1. 你需要什么环境？

| 项目 | 要求 |
|------|------|
| Python | **3.10、3.11 或 3.12**（`eqlib` 在 `pyproject.toml` 中声明 `requires-python >= 3.10`） |
| 操作系统 | macOS / Linux / Windows 均可 |
| 网络 | 首次拉取行情依赖 `akshare` 在线接口，需能访问外网或数据源 |

---

## 2. 安装 eqlib（推荐）

在克隆下来的仓库**根目录**执行（会一并安装 `akshare`、`pandas` 等依赖）：

```bash
cd EasyQuant
python3 -m venv .venv          # 可选，但强烈推荐
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 方式一：从源码安装（在仓库根目录）
pip install .
# 开发调试可选用：pip install -e .

# 方式二：PyPI 安装（无需克隆仓库）
# pip install easyquant-eqlib
```

验证：

```bash
python -c "from importlib.metadata import version; print('eqlib', version('eqlib'))"
```

若 `pip install .` 报错，请先阅读 [**常见问题 FAQ**](../project/faq.md) 中的「安装与环境」。

---

## 3. 第一次跑示例回测

在仓库根目录执行：

```bash
python examples/03_run_backtest.py
```

脚本会下载（或更新）数据并运行回测。结束后终端会打印 `reports/` 下的 **PNG、HTML、Markdown、JSON** 路径。

用浏览器打开其中的 **`.html` 文件`**，从上到下浏览：指标卡片 → 图表 → 成交与持仓。各字段含义见 [**报告与指标详解**](../reference/reports-format.md)。

与 **`reports/`** 中已保存的示例导出如何对照，见 **[`reports/README.md`](../how-to/read-reports.md)**（推荐与 [`example_report_html_19_localdata.png`](../assets/tutorials/example_report_html_19_localdata.png) 及 Tutorial 02 配图一起阅读）。

---

## 4. 可选：只测数据接口

若你想先确认网络与数据是否正常，可运行：

```bash
python examples/01_fetch_data.py
```

该脚本侧重演示 `get_price`、`fetch_stock_data` 等数据 API，不涉及完整回测报告。

---

## 5. 推荐：先下载目标股票到本地，再做快速回测验证

如果你已经有明确的研究标的，建议先把数据下载到本地，再用 `use_local=True` 做快速回测，这样可以显著减少网络波动带来的不确定性。

```bash
python - <<'PY'
from eqlib import set_local_data_dir, save_stock_local, list_local_stocks

set_local_data_dir('/home/user/eqlib_data')  # 推荐绝对路径，便于多项目复用
targets = ['601390', '600519', '000858', '000300.XSHG']  # 含基准

for sec in targets:
    path = save_stock_local(sec, start_date='2020-01-01', end_date='2024-12-31')
    print(sec, '->', path)

print('local files:', list_local_stocks())
PY
```

然后运行任一回测脚本时开启本地模式：

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390'],
    use_local=True,
)
```

建议先跑 [`examples/19_local_data_backtest.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_local_data_backtest.py) 做离线流程验证。

> 提示：本地已下载数据的日期区间应覆盖你的回测区间；若回测起止超出本地文件范围，请先补齐对应日期数据再运行。

更多接口说明见：

- [如何拉取与加载本地 CSV](../how-to/fetch-data.md)
- [API 参考：缓存 API](../reference/api-backtest.md)
- [FAQ：首次回测慢或卡住](../project/faq.md)

---

## 6. 教程、示例与「正式文档」怎么配合？

| 资源 | 用途 |
|------|------|
| `docs/tutorials/`（本目录） | 按主题循序渐进：**为什么这样写、常见坑** |
| `examples/` | **可复制运行的脚本**，对照 [`Examples.md`](../examples/index.md) 索引 |
| `docs/README.md` | **文档中心**：用户手册、API 全表、FAQ、报告解读的入口 |

---

## 7. 下一步

当你已能成功运行 `examples/03_run_backtest.py` 并打开 HTML 报告后，请继续阅读下方的量化交易基础概念，随后进入：

- **[Tutorial 01: 写第一个策略](01-first-strategy.md)**
- **[Tutorial 02: 回测验证](02-backtesting.md)**

---

## 量化交易基础概念

> 从零开始理解量化交易，了解策略开发的基本思路和注意事项。

| 项目 | 说明 |
|------|------|
| **目标** | 建立量化交易与策略开发的基本概念，了解完整流程与常见误区 |
| **预计用时** | 45～60 分钟（可按目录跳读） |
| **前置** | 请先完成上方的环境配置与第一次运行 |

---

## 1. 什么是量化交易

量化交易（Quantitative Trading）是用**数学模型和计算机程序**来制定和执行交易决策的方法。与主观交易（凭经验、直觉判断）不同，量化交易把投资逻辑写成明确的规则，让计算机自动执行。

### 1.1 一个简单的例子

主观交易思路：
> "我觉得工商银行最近涨得不错，均线看起来要金叉了，买点试试。"

量化交易思路：
> "当 601390 的 5 日均线向上穿越 20 日均线，且当日收盘价高于 5 日均线 2% 以上时，用全部可用现金买入；当 5 日均线下穿 20 日均线时，全部卖出。"

两者的核心区别在于：**可验证、可复制、可回溯**。

### 1.2 为什么用 Python

Python 是量化交易领域最主流的语言，原因在于：
- 语法简洁，上手门槛低
- 拥有最完整的金融生态库（pandas、numpy、scipy、matplotlib）
- 有丰富且免费的数据源（akshare、tushare 等）

### 1.3 EasyQuant 的定位

EasyQuant（`eqlib`）是一个面向 **中国 A 股市场** 的轻量级量化策略框架，它提供：
- 一套简单直观的策略 API（事件驱动模式）
- 免费的 A 股数据源（akshare）
- 完整的回测、报告生成、模拟盘功能
- 可以导出到 PTrade/QMT 平台进行实盘

---

## 2. 量化策略的核心要素

任何一个可运行的量化策略，都包含以下 5 个要素：

### 2.1 股票池（Universe）

确定你要操作哪些股票。常见的选择方式：
- **固定列表**：事先选定几只股票（如 `'601390', '600519', '000858'`）
- **指数成分股**：沪深 300、中证 500 的成分股
- **行业板块**：某个行业的成分股（如白酒、新能源）
- **动态筛选**：按财务指标（PE/PB/ROE）、技术指标（均线排列）、资金流向等条件实时筛选

### 2.2 入场条件（Entry Signal）

什么时候买入？这就是你的**信号**。常见类型：

| 类型 | 例子 |
|------|------|
| 趋势跟踪 | 短期均线上穿长期均线（金叉） |
| 均值回归 | 价格偏离均线超过 N 个标准差，赌它回归 |
| 动量策略 | 过去 N 天涨幅排名前 10% 的股票 |
| 事件驱动 | 财报发布、分红派息、龙虎榜等 |
| 资金流向 | 主力资金连续 N 日净流入 |

### 2.3 出场条件（Exit Signal）

什么时候卖出？出场和入场同样重要：

| 类型 | 例子 |
|------|------|
| 信号反转 | 金叉买入 → 死叉卖出 |
| 止损 | 亏损超过 5% 无条件卖出 |
| 止盈 | 盈利超过 20% 后回落 5% 卖出 |
| 时间止损 | 持仓超过 20 个交易日仍不盈利则卖出 |
| 调仓换股 | 定期（如每周一）重新评估，替换为更好的标的 |

### 2.4 仓位管理（Position Sizing）

决定每次买多少：

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| 全仓 | 所有资金买入一只股票 | 单股策略 |
| 等权 | 多只股票平分资金 | 组合轮动 |
| 固定比例 | 每次投入可用资金的固定百分比 | 渐进建仓 |
| Kelly 公式 | 根据胜率和盈亏比计算最优仓位 | 有历史数据的成熟策略 |
| ATR 仓位 | 根据波动率动态调整仓位大小 | 风控严格的策略 |

### 2.5 风控规则（Risk Management）

- **单只股票最大仓位**（不超过总资金的 30%）
- **最大回撤阈值**（回撤超过 15% 暂停策略）
- **止损线**（单只亏损超过 8% 强制卖出）
- **行业集中度限制**（同一行业不超过 40%）

---

## 3. 策略开发的完整流程

```
想法 → 规则化 → 回测验证 → 优化 → 模拟盘 → 实盘
```

### 3.1 第一步：形成想法

来源可以是：
- 阅读经典的交易书籍（《海龟交易法则》《技术分析》《量化投资》）
- 研究市场现象（如"一月效应"、"周一效应"）
- 观察他人的成功经验
- 自己交易中的体会和总结

### 3.2 第二步：规则化

把模糊的想法变成**明确的、可计算的规则**：

```
模糊想法："低价股更容易涨"
规则化：
  1. 选择股价低于 10 元的 A 股
  2. 排除 ST 股
  3. 每周一等权买入符合条件的全部股票
  4. 每周五全部卖出
  5. 回测期间：2023-01-01 至 2024-12-31
```

### 3.3 第三步：回测验证

用历史数据运行你的规则，看结果如何。

**回测能告诉你什么：**
- 策略是否盈利？年化收益多少？
- 最大回撤有多大？能接受吗？
- 夏普比率如何？风险调整后是否优秀？
- 与大盘相比，是跑赢还是跑输？

### 3.4 第四步：优化（小心过拟合）

调整参数，让策略表现更好。

**但必须警惕过拟合**——在历史数据上表现完美，实盘却亏钱。避免过拟合的方法：
- **样本外验证**：用 2020-2023 年调参，用 2024 年验证
- **参数稳定性检验**：参数微调后结果不应剧烈变化
- **避免过多参数**：参数越多，过拟合风险越大
- **逻辑驱动而非数据驱动**：参数要有经济学或行为金融学的支撑

### 3.5 第五步：模拟盘

回测通过后，用实时行情跑模拟盘（paper trading），在不花真金白银的情况下验证策略在"真实环境"中的表现。

### 3.6 第六步：实盘

模拟盘验证后，可以小仓位开始实盘交易，逐步增加仓位。

---

## 4. 新手常犯的 10 个错误

### 4.1 忽略交易成本

```python
# 错误：没考虑手续费
# 一天交易 5 次，每次佣金 0.025% + 印花税 0.05%，一年累积成本巨大

# 正确做法：设置合理的交易成本
set_order_cost(OrderCost(
    open_tax=0,
    close_tax=0.0005,          # 印花税 0.05%（2023年8月起减半）
    open_commission=0.00025,   # 买入佣金 0.025%
    close_commission=0.00025,
    min_commission=5,         # 最低佣金 5 元
))
```

### 4.2 未来函数（Look-ahead Bias）

```python
# 错误：使用了当天收盘价做决策，但决策是在开盘时做的
def market_open(context):
    # 在开盘时就拿到了当天收盘价——这是不可能的！
    today_close = get_today_close('601390')
    if today_close > ma20:
        order(...)

# 正确做法：只用历史数据做决策
def market_open(context):
    # 用昨天及之前的数据
    hist = attribute_history('601390', 20, '1d', ['close'])
    # hist 只包含昨天及之前的 20 天数据
```

### 4.3 幸存者偏差

```python
# 错误：只测试当前还在上市的股票，忽略了已退市/ST 的股票
# 这会导致回测结果虚高

# 正确做法：使用历史成分股列表，或 scan_market 获取当时的全市场股票
```

### 4.4 忽视流动性

```python
# 错误：对小盘股用大资金回测，实际成交量无法支撑
# 每天成交 100 万，你回测要买入 500 万——不可能成交

# 正确做法：检查股票日均成交量，确保你的下单金额合理
vol = attribute_history(sec, 20, '1d', ['volume'])
avg_volume = vol['volume'].mean()
# 你的下单股数不应超过日均成交量的 5-10%
```

### 4.5 过拟合（过度优化）

```python
# 错误：在回测中不断调参直到曲线完美
# MA5/MA20 效果不好 → 试 MA7/MA23 → 试 MA3/MA17 → ...
# 最终找到一组参数回测年化 50%，实盘大概率亏损

# 正确做法：
# 1. 参数要有逻辑支撑（为什么是 20 而不是 23？）
# 2. 检验参数稳定性（MA18/MA22 和 MA20/MA25 结果应该接近）
# 3. 留出样本外数据做最终验证
```

### 4.6 忽略滑点

```python
# 错误：假设你能以收盘价成交
# 实际下单时，价格可能已经变动

# EasyQuant 中的处理：
# 回测中订单会先入队，在下一交易日开盘价成交
# 但实际交易中会有滑点，通常估计为 0.1%-0.3%
```

### 4.7 忽视 A 股的 T+1 制度

```python
# 错误：今天买入，今天就想卖出
# A 股实行 T+1 交易制度，当天买入的股票下一交易日才能卖出

# EasyQuant 内部自动处理 T+1 限制
# 通过 Position.closeable_amount 控制可卖数量
```

### 4.8 只看收益不看风险

```python
# 错误：策略 A 年化 30%，最大回撤 40%
#       策略 B 年化 15%，最大回撤 8%
# 只看收益选 A，但看夏普比率可能 B 更好

# 正确做法：关注风险调整后的指标
# - 夏普比率（Sharpe Ratio）
# - 最大回撤（Max Drawdown）
# - 索提诺比率（Sortino Ratio）
```

### 4.9 不设置止损

```python
# 错误：只有买入条件，没有卖出/止损条件
# "跌了就拿着，总会涨回来"——有些股票不会

# 正确做法：每个买入信号都应该配套对应的卖出规则
# 信号止损 / 固定比例止损 / ATR 追踪止损 / 时间止损
```

### 4.10 一次性上实盘

```python
# 错误：回测跑完就直接满仓实盘
# 正确做法：
# 1. 回测验证（历史数据）
# 2. 模拟盘（实时行情，虚拟资金）
# 3. 小仓位实盘（真实资金，但控制风险）
# 4. 逐步增加仓位
```

---

## 5. 你需要掌握哪些知识

以下三个前置知识文件提供了更完整的学习材料，可在需要时深入阅读：

| 前置文件 | 涵盖内容 | 链接 |
|---------|---------|------|
| **Python 基础与环境配置** | 语法速查、pandas/numpy 核心操作、虚拟环境 | [prerequisites/python-basics.md](prerequisites/python-basics.md) |
| **技术分析基础概念** | OHLCV、均线、RSI、MACD、布林带、ATR、KDJ、ADX | [prerequisites/technical-concepts.md](prerequisites/technical-concepts.md) |
| **A 股市场基础知识** | 股票代码格式、T+1、涨跌停、常用指数、ST 股、手续费与税 | [prerequisites/ashare-knowledge.md](prerequisites/ashare-knowledge.md) |

### 5.1 必备（开始写策略前）

| 领域 | 内容 | 学习建议 |
|------|------|---------|
| Python 基础 | 变量、函数、循环、条件判断 | 1-2 周；或直接查 [前置文件](prerequisites/python-basics.md) |
| pandas | DataFrame、Series、索引、聚合 | 1-2 周；核心用法见 [前置文件 §4](prerequisites/python-basics.md#4-pandas-核心用法) |
| 技术指标 | 均线、MACD、RSI、布林带 | 边学边用；系统介绍见 [前置文件](prerequisites/technical-concepts.md) |
| A 股基础规则 | T+1、涨跌停、手续费 | 半天；详见 [前置文件](prerequisites/ashare-knowledge.md) |

### 5.2 推荐（深入优化策略时）

| 领域 | 内容 |
|------|------|
| 风险管理 | Kelly 公式、VaR、最大回撤 |
| 投资组合理论 | 有效前沿、风险平价 |
| 绩效归因 | Brinson 归因、Fama-French 因子 |
| 数据可视化 | matplotlib 基础图表 |

### 5.3 加分项

| 领域 | 内容 |
|------|------|
| 机器学习 | 分类、回归、特征工程 |
| 时间序列分析 | ARIMA、GARCH |
| 数据库 | SQLite、PostgreSQL |
| 系统编程 | 多进程、定时任务 |

---

## 6. 下一步

完成了基础概念的学习，接下来：

- **[Tutorial 01: 写第一个策略](01-first-strategy.md)** — 用 EasyQuant 编写并运行你的第一个量化策略
- **[Tutorial 02: 回测验证](02-backtesting.md)** — 深入理解回测，检验策略的历史表现
- **[Tutorial 03: 策略优化与改进](03-optimization.md)** — 参数调优、避免过拟合、组合策略
- **[Tutorial 04: 模拟盘到实盘](04-live-trading.md)** — 从模拟盘到 PTrade/QMT 实盘部署
- **[Tutorial 05: RSI 均值回归策略](05-rsi-mean-reversion.md)** — 深入学习均值回归这一经典策略类型
- **[Tutorial 06: 行业轮动策略](06-sector-rotation.md)** — 利用 A 股行业轮动特性赚取超额收益
- **[Tutorial 07: 多因子选股](07-multi-factor.md)** — 系统化地用多个因子组合选出优质股票
