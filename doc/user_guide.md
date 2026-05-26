# EasyQuant 用户手册

`eqlib` 是面向中国 A 股市场的事件驱动量化回测框架。本手册涵盖从安装、编写策略、运行回测到报告解读的完整工作流。

---

## 核心概念：策略如何运行

在编写代码之前，先理解 EasyQuant 的执行模型。这有助于避免常见错误（如前视偏差、内存溢出）。

### 策略骨架

每个策略由 **三个函数 + 一个全局对象** 组成：

| 组件 | 调用时机 | 职责 |
|------|----------|------|
| `initialize(context)` | 回测开始时一次 | 设置基准、手续费、注册定时函数、初始化变量 |
| `handle_data(context, data)` | 每个交易日一次 | 读取行情、判断信号、下单 |
| `market_open(context)` | 由 `run_daily` 注册 | 替代 `handle_data` 的自定义入口 |
| `g` | 跨交易日持久化 | 存储策略变量（如持仓天数、阈值） |

### 关键约束

| 约束 | 说明 |
|------|------|
| **T+1** | 当天买入的股票次日才可卖出，框架自动处理 |
| **100 股整数倍** | 买入数量自动向下取整到 100 的整数倍 |
| **前视偏差** | 策略只能访问 `context.current_dt` 及之前的数据 |
| **内存** | 默认限制 1024 MB，可通过 `max_memory_mb` 调整 |

### 阅读指南

- **快速上手** → 从 §0 新手四步开始，跳过理论直接跑通流程
- **系统学习** → 从 §1 简介读至 §14，理解每个模块的设计意图
- **查阅参考** → 跳转至 [API 参考](api_reference.md) 查看完整参数表

---

## 0. 新手四步

如果你是第一次接触 EasyQuant，请先完成以下最小闭环：

1. 安装：
   ```bash
   # PyPI 安装（推荐，无需克隆仓库）
   pip install easyquant-eqlib
   # 或从源码安装（开发者 / 贡献者，在仓库根目录）
   # pip install .
   ```
2. 验证导入：
   ```bash
   python -c "from eqlib import *; print('eqlib OK')"
   ```
3. 跑一次完整回测（需在仓库目录运行示例）：
   ```bash
   python examples/03_run_backtest.py
   ```
4. 打开 `reports/` 下最新 `.html`，确认图表和指标正常显示。

可选测试：

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```

> **替代方案：Web 策略工作室**
> 如果你更喜欢浏览器界面，可以使用 [Web 策略工作室](../web_strategy_studio/)。
> 无需安装 Python 环境，打开浏览器即可编写策略、运行回测、查看报告和对比指标。
> 详见 [Web 工作室文档](web_studio.md)。

---

## 1. 简介与适用范围

`eqlib` 是一个面向 **中国 A 股市场** 的量化策略回测框架。它的数据源来自 `akshare`，采用事件驱动的策略 API 设计，支持完整的回测与模拟盘工作流。

**适用场景：**
- A 股日线 / 分钟线回测
- 策略开发验证
- 模拟盘交易
- 选股 / 行业轮动 / 资金流分析
- 投资组合优化

**不支持：**
- 港股、美股、期货、期权、加密货币等非 A 股品种
- 高频 T+0 策略（A 股为 T+1 交易制度）

---

## 2. 安装

**环境要求：Python 3.10 及以上**。

```bash
# PyPI 安装（推荐）
pip install easyquant-eqlib
# 开发时可选用（在仓库根目录）：pip install -e .
```

确认安装成功：

```python
from eqlib import *
print("eqlib OK")
```

更多排错见 [常见问题 FAQ](FAQ.md)。

---

## 3. 快速开始：编写并运行一个策略

一个可运行的策略至少包含：**`initialize(context)`**（初始化），以及用 **`run_daily`** 注册的交易函数。

```python
from eqlib import *

def initialize(context):
    g.security = '601390'          # 工商银行
    set_benchmark('000300.XSHG')   # 沪深300 作为基准
    set_option('use_real_price', True)
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    current_price = hist['close'].iloc[-1]

    if current_price > ma20 * 1.02:
        order_value(g.security, context.portfolio.available_cash)
    elif current_price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        order_target(g.security, 0)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390'],
    report_dir='reports',
)
```

运行后会输出 PNG、HTML、Markdown、JSON 四类报告文件。优先在浏览器打开 `.html` 查看完整报告。

> 订单执行模型：`order*` 系列 API 在当前回调里只是下单，实际按**下一个交易日开盘价**成交。

---

## 4. 策略生命周期

```
initialize(context)          ← 回测开始时调用一次
    |
    v
before_trading_start(ctx, data)   ← 每个交易日开盘前调用（可选注册）
    |
    v
run_daily / run_weekly / run_monthly 定时函数
    |
    v
handle_data(context, data)   ← 每个交易日调用一次
    |
    v
after_trading_end(ctx, data) ← 每个交易日收盘后调用（可选注册）
```

### 4.1 `initialize(context)`

策略入口，每个策略必须定义。

```python
def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')
```

### 4.2 `handle_data(context, data)`

每日交易逻辑。也可以用 `run_daily` 代替。

```python
def handle_data(context, data):
    bar = data.get(g.security)
    if bar:
        log.info("%s 今日收盘: %.2f" % (g.security, bar.close))
```

### 4.3 盘前/盘后回调

```python
from eqlib import before_trading_start, after_trading_end

def before_start(context, data):
    log.info("盘前检查...")

def after_end(context, data):
    log.info("盘后统计: 持仓 %d 只" % len(context.portfolio.positions))

before_trading_start(before_start)
after_trading_end(after_end)
```

### 4.4 `g` 全局对象

`g` 是策略级别的持久化存储，跨交易日有效。

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0

def market_open(context):
    g.hold_days += 1
```

---

## 5. 资金管理与仓位控制

### 5.1 设置初始资金

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=500000,   # 50 万元初始资金
)
```

### 5.2 读取账户状态

```python
def market_open(context):
    cash = context.portfolio.available_cash
    total = context.portfolio.total_value
    positions = context.portfolio.positions
    returns = context.portfolio.returns
```

### 5.3 仓位控制方式

| 方式 | 函数 | 说明 |
|------|------|------|
| **全仓买入** | `order_value(sec, context.portfolio.available_cash)` | 用全部可用现金买入 |
| **按比例买入** | `order_value(sec, context.portfolio.available_cash * 0.5)` | 用 50% 现金买入 |
| **按固定金额** | `order_value(sec, 50000)` | 买入 5 万元 |
| **按固定股数** | `order(sec, 1000)` | 买入 1000 股（自动取整到 100 的整数倍） |
| **调到目标股数** | `order_target(sec, 5000)` | 调整持仓到 5000 股 |
| **调到目标市值** | `order_target_value(sec, 100000)` | 调整持仓市值到 10 万 |
| **清仓** | `order_target(sec, 0)` | 全部卖出 |

A 股最小交易单位为 **100 股（1 手）**，所有买入会自动向下取整到 100 的整数倍。

### 5.4 多股等权配置示例

```python
def market_open(context):
    stocks = ['601390', '600519', '000858']
    weight = context.portfolio.available_cash / len(stocks)
    for sec in stocks:
        order_value(sec, weight)
```

---

## 6. 交易 API

> 重要：`order` / `order_value` / `order_target` / `order_target_value` 在回测中是**先入队**，统一按**下一交易日开盘价**成交。

### 6.1 `order(security, amount)`

按股数买卖，正数买入，负数卖出。

```python
order('601390', 1000)     # 买入 1000 股
order('601390', -500)     # 卖出 500 股
```

### 6.2 `order_value(security, value)`

按金额买卖。

```python
order_value('601390', 50000)   # 买入 5 万元
```

### 6.3 `order_target(security, amount)`

调整持仓到目标股数。

```python
order_target('601390', 5000)   # 持仓调到 5000 股
order_target('601390', 0)      # 清仓
```

### 6.4 `order_target_value(security, value)`

调整持仓到目标市值。

```python
order_target_value('601390', 100000)  # 持仓市值调到 10 万
```

---

## 7. 数据拉取

### 7.1 历史日线数据

```python
# 方式一：history()
close = history(20, '1d', 'close', security='601390')

# 方式二：attribute_history（更灵活）
hist = attribute_history('601390', 30, '1d',
                         fields=['open', 'close', 'volume', 'high', 'low'])

# 方式三：get_price（支持指定日期范围）
df = get_price('601390',
               start_date='2024-01-01',
               end_date='2024-06-30',
               fields=['open', 'high', 'low', 'close', 'volume'])
```

### 7.2 实时行情快照

```python
data = get_current_data()
info = get_security_info('601390')
val = get_valuation('601390')
```

### 7.3 选股与扫描

```python
candidates = scan_market(min_price=10, min_pct_change=3, max_pct_change=5, max_pe=50)
screened = get_financial_screen(min_pe=5, max_pe=30, min_roe=0.1)
```

### 7.4 指数与行业成分股

```python
constituents = get_index_stocks('000300.XSHG')   # 沪深300 成分股
industries = get_industry_list()                  # 所有行业板块
stocks = get_industry_stocks('白酒')              # 白酒行业成分股
concepts = get_concept_list()                     # 所有概念板块
concept_stocks = get_concept_stocks('人工智能')    # 人工智能概念股
```

### 7.5 分钟线数据

```python
df_5m = fetch_minute_data('601390', period='5m')
# 支持的周期：1m, 5m, 15m, 30m, 60m
```

### 7.6 Tick 数据

```python
df_tick = get_tick_data('601390')
```

### 7.7 资金流向与龙虎榜

```python
flow = get_money_flow('601390', count=30)
billboard = get_billboard_list(date='20241201')
weights = get_index_weights('000300.XSHG')
```

### 7.8 交易日历

```python
days = get_trade_days(start_date='2024-01-01', end_date='2024-12-31')
recent_days = get_trade_days(count=10)
```

### 7.9 本地数据缓存

```python
from eqlib import set_local_data_dir, save_stock_local, has_local_data

set_local_data_dir('/path/to/eqlib_data')

for sec in ['601390', '600519', '000300.XSHG']:
    path = save_stock_local(sec, '2020-01-01', '2024-12-31')

result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390', '600519'],
    use_local=True,
)
```

建议：先确认 `has_local_data(code)` 为 `True` 再跑回测；大范围回测先用较短日期区间做冒烟测试。

---

## 8. 计算工具库

`eqlib.utils` 提供了技术指标、统计分析、资金管理和支撑阻力位计算工具。

### 8.1 技术指标

```python
from eqlib import utils

ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
rsi14 = utils.rsi(close, 14)
k, d, j = utils.kdj(high, low, close, period=9)
upper, mid, lower = utils.boll(close, period=20)
atr14 = utils.atr(high, low, close, 14)
```

### 8.2 统计分析

```python
sharpe = utils.rolling_sharpe(daily_returns, window=20)
max_dd, dd_start, dd_end = utils.max_drawdown(equity_curve)
var_5 = utils.value_at_risk(daily_returns, confidence=0.05)
```

### 8.3 资金管理

```python
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
shares = utils.atr_position_size(capital=100000, risk_pct=0.02, atr=0.30, n_atr=2.0)
weights = utils.risk_parity_weights([0.15, 0.25, 0.20])
```

### 8.4 支撑阻力位

```python
pp, r1, s1, r2, s2, r3, s3 = utils.pivot_classic(high, low, close)
sr = utils.support_resistance_levels(high, low, close)
fib = utils.fibonacci_retracement(high, low, close)
```

详细说明见 [工具库参考](utils_reference.md)。

---

## 9. 运行回测

### 9.1 `run_strategy`（推荐）

一站式运行回测并生成所有报告。

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601390', '600519'],
    report_dir='reports',
)
```

### 9.2 `run_backtest`（精细控制）

只运行回测，不生成报告。

```python
result = run_backtest(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
)
```

### 9.3 `run_portfolio_backtest`（组合回测）

面向多股票组合的高层接口。

```python
from eqlib import StrategyConfig, run_portfolio_backtest

config = StrategyConfig(
    starting_cash=200000,
    securities=["601390", "600519", "000858"],
    benchmark="000300.XSHG",
    position_pct=0.33,
    start_date="2024-01-01",
    end_date="2024-12-31",
    report_suffix="momentum_v1",
)

def my_strategy(context):
    for sec in context.universe:
        hist = attribute_history(sec, 25, "1d", ["close"])
        if hist.empty:
            continue
        ma20 = hist["close"].tail(20).mean()
        price = hist["close"].iloc[-1]
        if price > ma20 * 1.02:
            order_value(sec, context.portfolio.available_cash)
        elif price < ma20 * 0.98 and context.portfolio.positions.get(sec):
            order_target(sec, 0)

result = run_portfolio_backtest(config, my_strategy, report_dir="reports")
```

### 9.4 基准对比

通过 `benchmark` 参数设置基准（默认 `000300.XSHG` 沪深300）。结果会自动计算 alpha、beta 和 information ratio。

---

## 10. 回测报告与图表解读

### 10.1 图表（PNG）

图表文件：`reports/backtest_YYYYMMDD_HHMMSS.png`

- **灰色线 (Close)**：股票每日收盘价
- **蓝色线 (MA5)**：5 日均线（短期趋势）
- **橙色线 (MA20)**：20 日均线（中期趋势）
- **绿色圆圈 (BUY)**：买入点
- **红色圆圈 (SELL)**：卖出点
- **绿色阴影区域**：持仓期间
- **绿色线 (右侧轴)**：投资组合总资产价值

### 10.2 交互式 HTML 报告

文件：`reports/backtest_YYYYMMDD_HHMMSS.html`，用浏览器打开。

页面自上而下分为：

1. **页头摘要** — 回测标的、时间区间、初始/最终资金，一眼判断盈亏
2. **核心指标卡片** — 年化收益、超额收益、夏普比率、最大回撤、胜率、卡玛比率
3. **详细指标行** — 年化波动率、索提诺比率、Alpha、Beta、信息比率、日胜率、盈亏比
4. **K 线与技术指标图** — 价格线 + 均线 + 买卖点标记 + 成交量
5. **累计收益率** — 叠加沪深300与上证综指两条宽基累计收益曲线
6. **回撤曲线** — 策略回撤 vs 两指数回撤
7. **每日盈亏** — 每个交易日的盈亏柱状图
8. **标签页** — 成交明细、持仓状态

**完整阅读流程：** 页头（赚钱了吗）→ 指标卡片（夏普/回撤合格吗）→ 累计收益图（相对大盘位置）→ 回撤曲线 → 成交表。

### 10.3 Markdown 报告

文件：`reports/backtest_YYYYMMDD_HHMMSS.md`，包含摘要、交易记录、持仓信息。

### 10.4 JSON 报告

文件：`reports/backtest_YYYYMMDD_HHMMSS.json`，机器可读的结构化数据。

```python
import json
with open('reports/backtest_20240101_120000.json') as f:
    report = json.load(f)
print("总收益: %.2f%%" % report['pnl_pct'])
```

---

## 11. 风险与归因分析

### 11.1 `analyze_returns`：综合风险指标

```python
from eqlib import analyze_returns
metrics = analyze_returns(result, risk_free_rate=0.03)
```

| 指标 | 说明 | 好值 |
|------|------|------|
| `total_return` | 总收益率 | 正数越大越好 |
| `annual_return` | 年化收益率 | 正数越大越好 |
| `annual_volatility` | 年化波动率 | 低一些更好 |
| `sharpe_ratio` | 夏普比率 | > 1 为好，> 2 为优秀 |
| `sortino_ratio` | 索提诺比率 | 只考虑下行风险，> 1 为好 |
| `max_drawdown` | 最大回撤 | 接近 0 越好 |
| `calmar_ratio` | 卡玛比率 | > 1 为好 |
| `alpha` | 超额收益（年化） | 正数为跑赢基准 |
| `beta` | 市场敏感度 | 1 表示与大盘同步 |
| `information_ratio` | 信息比率 | > 0.5 为好 |
| `win_rate_daily` | 日胜率 | > 0.5 为好 |
| `win_rate_trade` | 配对交易胜率 | 与日胜率含义不同 |

### 11.2 `brinson_attribution`：归因分析

```python
from eqlib import brinson_attribution
attr = brinson_attribution(result)
print("配置效应: %.4f" % attr['allocation_effect'])
print("选股效应: %.4f" % attr['selection_effect'])
```

### 11.3 `fama_french_analysis`：因子分析

```python
from eqlib import fama_french_analysis
ff = fama_french_analysis(result)
print("市场 Beta: %.3f" % ff['market_beta'])
```

---

## 12. 模拟盘交易

模拟盘使用实时行情数据持续运行策略。

### 12.1 基本用法

```python
from eqlib import run_paper_trade

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    pass  # 策略逻辑

result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,
)
```

按 `Ctrl+C` 停止。

### 12.2 交易信号通知

模拟盘运行时，可通过钉钉或飞书 Webhook 接收交易信号通知，
收到通知后手动执行实盘操作。

```python
from eqlib import *
from eqlib.notification import notify_signal

def initialize(context):
    # 配置钉钉通知
    set_notification_webhook("dingtalk", 
        "https://oapi.dingtalk.com/robot/send?access_token=xxx")
    enable_notification(["signal"])
    
    g.security = '601390'
    g.strategy_name = "双均线金叉策略"
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context, data):
    price = data.current(g.security, 'close')
    ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
    ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()
    
    # 金叉信号
    if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
        # 发送通知
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),
            strategy_name=g.strategy_name,
            trigger_point=f"MA5={ma5:.2f} 上穿 MA20={ma20:.2f}"
        )
        order(g.security, 1000)
    
    # 死叉信号
    if ma5 < ma20 and g.prev_ma5 >= g.prev_ma20:
        notify_signal(
            security=g.security,
            side="sell",
            amount=context.portfolio.positions[g.security].amount,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),
            strategy_name=g.strategy_name,
            trigger_point=f"MA5={ma5:.2f} 下穿 MA20={ma20:.2f}"
        )
        order_target(g.security, 0)
    
    g.prev_ma5 = ma5
    g.prev_ma20 = ma20
```

收到钉钉通知后，可根据建议的价格区间手动执行实盘操作。

!!! tip "获取 Webhook"

    - **钉钉**: 群设置 → 智能群助手 → 添加机器人 → 自定义
    - **飞书**: 群设置 → 群机器人 → 添加机器人 → 自定义机器人

---

## 13. 参数优化与审计

### 13.1 参数化策略

策略须定义 `PARAMS` 与 `PARAM_RANGES`：

```python
PARAMS = {
    'fast_period':      5,
    'slow_period':      20,
    'stop_loss_pct':    0.08,
    'position_pct':     1.0,
    'vol_confirm_mul':  1.5,
}

PARAM_RANGES = {
    'fast_period':      (2,   15,   1),
    'slow_period':      (10,  60,   5),
    'stop_loss_pct':    (0.03, 0.15, 0.01),
    'position_pct':     (0.3,  1.0,  0.1),
    'vol_confirm_mul':  (1.0,  3.0,  0.25),
}

def initialize(context):
    g.fast_period    = PARAMS['fast_period']
    g.slow_period    = PARAMS['slow_period']
    g.stop_loss_pct  = PARAMS['stop_loss_pct']
    g.position_pct   = PARAMS['position_pct']
    g.vol_confirm_mul = PARAMS['vol_confirm_mul']
```

### 13.2 运行 optimizer.py

```bash
python agent/optimizer.py \
  --strategy agent/strategy_template.py \
  --min-sharpe 1.0 \
  --max-drawdown 0.20 \
  --periods "2022-01-01:2022-12-31" "2023-01-01:2023-12-31"
```

### 13.3 审计日志

使用 `audit_log.py` 时，会话产物示例：

```
audit_log/
├── session_<时间戳>.jsonl
└── session_<时间戳>.md
```

详细说明见 [Tutorial 10](../tutorials/10_agent_optimization.md)。

---

## 14. 常见问题

更完整的排错见 [FAQ.md](FAQ.md)。

### Q: 如何设置手续费？

```python
set_order_cost(OrderCost(
    open_tax=0,
    close_tax=0.001,
    open_commission=0.0003,
    close_commission=0.0003,
    min_commission=5,
))
```

### Q: 如何做多只股票？

```python
def initialize(context):
    g.stocks = ['601390', '600519', '000858']
    run_daily(rebalance, time='every_bar')

def rebalance(context):
    n = len(g.stocks)
    weight = context.portfolio.total_value / n
    for sec in g.stocks:
        order_target_value(sec, weight)
```

### Q: 如何加速大回测？

```python
# 1. 预加载数据
result = run_backtest(initialize, '2020-01-01', '2024-12-31',
                      securities=['601390', '600519'])

# 2. 设置磁盘缓存
from eqlib import set_cache_dir
set_cache_dir('/path/to/cache')

# 3. 清除缓存
from eqlib import clear_cache
clear_cache()
```

### Q: 策略报错 "no price data" 怎么办？

检查股票代码是否正确。A 股代码格式为 6 位数字（如 `'601390'`），不需要带交易所后缀。基准可以使用后缀如 `'000300.XSHG'`。

### Q: A 股 T+1 限制如何处理？

`eqlib` 内部自动处理 T+1 限制：当天买入的股票当天不能卖出。
