# Tutorial 05: 模拟盘到实盘

> 回测通过后，用实时行情验证策略，再导出到 PTrade/QMT 进行实盘部署。

---

## 目录

1. [从回测到实盘的流程](#1-从回测到实盘的流程)
2. [模拟盘交易](#2-模拟盘交易)
3. [导出到 PTrade/QMT](#3-导出到-ptradeqmt)
4. [实盘注意事项](#4-实盘注意事项)
5. [常见问题](#5-常见问题)
6. [完整示例](#6-完整示例)

---

## 1. 从回测到实盘的流程

```
回测验证（历史数据）
    ↓  通过
模拟盘（实时行情，虚拟资金）
    ↓  通过
PTrade/QMT 模拟运行（真实交易接口，虚拟环境）
    ↓  通过
PTrade/QMT 实盘（真实资金）
```

每一步的目标不同：
- **回测**：验证策略逻辑是否正确、历史表现如何
- **模拟盘**：验证实时数据流是否稳定、信号是否及时
- **PTrade/QMT 模拟**：验证交易接口是否正常、委托成交是否符合预期
- **实盘**：最终验证——真金白银

---

## 2. 模拟盘交易

### 2.1 基本用法

```python
from eqlib import *

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return

    price = hist['close'].iloc[-1]
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
            log.info('买入 %s @ %.3f' % (g.security, price))
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
            log.info('卖出 %s @ %.3f' % (g.security, price))

# 启动模拟盘，每 60 秒刷新
run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,  # 轮询间隔（秒）
)
```

### 2.2 模拟盘输出

```
[09:30:00] total_value=100,000.00  PnL=+0.00 (+0.00%)
[09:31:00] total_value=100,000.00  PnL=+0.00 (+0.00%)
[09:32:00] 买入 601390 @ 5.230
[09:32:00] total_value=100,234.56  PnL=+234.56 (+0.23%)
...
```

### 2.3 模拟盘 vs 回测的差异

| | 回测 | 模拟盘 |
|--|------|--------|
| 数据源 | akshare 历史数据 | akshare 实时行情 |
| 速度 | 几秒钟跑完一年 | 持续运行，实时更新 |
| 交易 | 模拟成交（使用当日收盘价） | 模拟成交（使用实时价格） |
| 用途 | 验证策略逻辑 | 验证实时数据流和信号及时性 |

### 2.4 模拟盘注意事项

- 在交易时段运行才能获得实时行情
- 使用 `Ctrl+C` 停止
- 模拟盘不会产生真实委托，不会真正买卖股票
- 建议至少运行 1-2 周，观察信号是否合理

---

## 3. 导出到 PTrade/QMT

模拟盘验证通过后，可以导出策略到 PTrade/QMT 平台进行实盘。

### 3.1 使用导出工具

```bash
python examples/13_ptrade_export.py
```

这会生成 `ptrade_strategy.py` 文件。

### 3.2 自定义策略导出

修改 `examples/13_ptrade_export.py` 中的 `STRATEGY_CODE` 变量，替换为你自己的策略：

```python
# 在 examples/13_ptrade_export.py 中
STRATEGY_CODE = '''
# 你的策略代码（去掉 from eqlib import * 这一行）

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')
    run_daily(market_open, time='every_bar')

def market_open(context):
    # ... 你的策略逻辑 ...
    pass
'''
```

### 3.3 手动迁移步骤

**Step 1**：在 QMT 策略编辑器中新建策略文件。

**Step 2**：写入以下内容：

```python
from eqlib.ptrade_adapter import *

# === 全局变量 ===
g.security = '601390'
g.fast_period = 5
g.slow_period = 20

# === 初始化函数（与回测完全一致） ===
def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')  # 你的 QMT 账号
    run_daily(market_open, time='every_bar')

# === 策略逻辑（与回测完全一致） ===
def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < g.slow_period:
        return

    price = hist['close'].iloc[-1]
    ma_fast = hist['close'].tail(g.fast_period).mean()
    ma_slow = hist['close'].mean()

    if price > ma_fast > ma_slow:
        if g.security not in context.portfolio.positions or \
           context.portfolio.positions[g.security].amount == 0:
            order_value(g.security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f' % (g.security, price))
    elif price < ma_fast < ma_slow:
        if g.security in context.portfolio.positions and \
           context.portfolio.positions[g.security].amount > 0:
            order_target(g.security, 0)
            log.info('SELL %s @ %.3f' % (g.security, price))

# === QMT 入口函数（固定写法） ===
def init(ContextInfo):
    set_account('6000000248')  # 你的 QMT 账号
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

**Step 3**：在 QMT 中设置账号 → 运行回测或实盘。

### 3.4 迁移差异总结

从 EasyQuant 回测到 PTrade/QMT 实盘，只有 3 处差异：

| # | 差异 | 回测 | PTrade/QMT |
|---|------|------|-----------|
| 1 | 导入语句 | `from eqlib import *` | `from eqlib.ptrade_adapter import *` |
| 2 | 账号设置 | `run_strategy(starting_cash=...)` | `set_account('你的QMT账号')` |
| 3 | 入口函数 | `run_strategy(initialize, ...)` | `def init(ContextInfo): start(ContextInfo)` |

策略逻辑本身**完全不变**。

### 3.5 代码自动转换

适配器自动处理以下内容，你不需要手动改：

- **股票代码**：`601390` → `601390.SH`
- **指数代码**：`000300.XSHG` → `000300.SH`
- **交易函数**：`order_value()` → QMT 原生 `order_value()`
- **数据函数**：`attribute_history()` → QMT 原生 `get_market_data()`

---

## 4. 实盘注意事项

### 4.1 回测模式 vs 实盘模式

| | 回测模式 | 实盘模式 |
|--|---------|---------|
| 数据 | QMT 本地历史数据 | 实时行情 |
| 交易 | 虚拟账号执行，产生买卖点 | 真实委托，实际成交 |
| 滑点 | 无 | 有（券商实际成交价可能有偏差） |
| 手续费 | 按设置费率模拟 | 券商实际费率 |

### 4.2 资金管理

- 先用**小仓位**开始实盘（如总资金的 10%-20%）
- 观察 1-2 周，确认策略行为与回测一致
- 逐步增加仓位，不要一步到位

### 4.3 风控建议

```python
# 实盘建议增加的风控条件

# 1. 单股最大仓位限制
def market_open(context):
    max_position_pct = 0.30  # 单股不超过 30%
    max_value = context.portfolio.total_value * max_position_pct
    buy_value = min(context.portfolio.available_cash, max_value)
    order_value(g.security, buy_value)

# 2. 组合最大回撤限制
    if context.portfolio.returns < -0.15:  # 总亏损超过 15%
        # 清仓所有持仓
        for sec in list(context.portfolio.positions.keys()):
            order_target(sec, 0)
        log.warn('最大回撤触发，清仓所有持仓')
        return

# 3. 每日最大交易次数限制
    g.daily_trades = getattr(g, 'daily_trades', 0)
    if g.daily_trades >= 5:  # 每天最多 5 笔交易
        return
```

### 4.4 日志记录

实盘中日志很重要，建议记录关键操作：

```python
def market_open(context):
    log.info('当前总资产: %.2f, 可用现金: %.2f, 收益率: %.2f%%' % (
        context.portfolio.total_value,
        context.portfolio.available_cash,
        context.portfolio.returns * 100,
    ))

    # 每次买卖都记录
    if signal_buy:
        order_value(security, buy_value)
        log.info('BUY %s, amount=%d, price=%.3f' % (security, amount, price))
```

### 4.5 监控

- 定期检查日志，确认策略运行正常
- 关注买卖点是否与预期一致
- 对比实际收益与回测预期，如果偏差过大，需要排查原因

---

## 5. 常见问题

### Q: 模拟盘和回测结果不一致？

可能原因：
- 回测用收盘价，模拟盘用实时价格（可能有滑点）
- 回测期间和模拟盘期间的市场环境不同
- 模拟盘运行时间不足，信号不够

### Q: QMT 中报 `ModuleNotFoundError: No module named 'eqlib'`？

在 QMT 环境中需要确保 `eqlib` 可访问：
- 把 `eqlib` 目录复制到 QMT 的 Python 路径中
- 或者在 QMT 策略代码开头添加：
  ```python
  import sys
  sys.path.insert(0, '/path/to/your/EasyQuant')
  ```

### Q: 实盘交易不成交？

可能原因：
- 价格偏离市场价太多（如涨跌停）
- 流动性不足，成交量太低
- 账号未设置或未授权
- 非交易时段（不在 9:30-11:30 或 13:00-15:00 内）

### Q: 如何同时运行多个策略？

每个策略需要在 QMT 中创建独立的策略文件，分别设置账号和股票池。

### Q: 如何从 PTrade/QMT 同步真实持仓？

适配器内置了 `Portfolio.update_from_qmt()` 方法，会在每根 bar 开始时自动同步 QMT 真实账户状态。详见 [PTrade/QMT 适配器文档](../doc/ptrade_adapter.md)。

---

## 6. 完整示例

以下是从回测到实盘的完整流程：

### 6.1 本地回测

```python
# ma_strategy.py — 本地回测用
from eqlib import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)

result = run_strategy(
    initialize, '2024-01-01', '2024-12-31',
    starting_cash=100000, securities=['601390'],
)
```

### 6.2 模拟盘验证

```python
# 同一个文件，改为模拟盘运行
# python ma_strategy.py --paper-trade

import sys

if '--paper-trade' in sys.argv:
    run_paper_trade(
        initialize,
        starting_cash=100000,
        benchmark='000300.XSHG',
        interval=60,
    )
else:
    result = run_strategy(
        initialize, '2024-01-01', '2024-12-31',
        starting_cash=100000, securities=['601390'],
    )
```

### 6.3 QMT 实盘

```python
# ma_strategy_ptrade.py — QMT 策略编辑器中运行
from eqlib.ptrade_adapter import *

g.security = '601390'

def initialize(context):
    set_benchmark('000300.XSHG')
    set_account('6000000248')
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash)
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)

def init(ContextInfo):
    set_account('6000000248')
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
```

---

## 恭喜

你已经完成了从策略概念到实盘部署的完整流程！

### 进一步学习

- **[Tutorial 06: RSI 均值回归策略](../tutorials/06_rsi_mean_reversion.md)** — 学习与趋势跟踪截然不同的均值回归策略思路
- **[Tutorial 07: 行业轮动策略](../tutorials/07_sector_rotation.md)** — 利用 A 股行业轮动构建超额收益策略
- **[Tutorial 08: 多因子选股](../tutorials/08_multi_factor.md)** — 系统性量化选股方法
- [PTrade/QMT 适配器文档](../doc/ptrade_adapter.md) — 适配器 API 详解
- [API 参考](../doc/api_reference.md) — 完整的 API 列表
- [工具库参考](../doc/utils_reference.md) — 技术指标、统计工具、资金管理
- [示例代码](../examples/) — 20 个可直接运行的示例
- **[Example 20: 支撑阻力位组合策略](../examples/20_sr_strategy/)** — 一个完整的多股票组合策略实战案例，包含预生成的回测报告
