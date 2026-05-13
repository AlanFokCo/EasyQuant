!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §2](02_install.md) · [下一章 §4](04_lifecycle.md)

---

## 3. 快速开始：5 分钟写一个策略

一个可运行的策略**至少**包含：**`initialize(context)`**（初始化），以及 **用 `run_daily` / `run_weekly` / `run_monthly` 等注册的交易函数**（本节示例为 `market_open`）。你也可以在 `initialize` 里通过 **`set_handle_data`** 注册全局 **`handle_data`**，引擎会在每个交易日调用它；**调度函数与 `handle_data` 的先后关系见 [§4](04_lifecycle.md#4-策略生命周期)**。新手可先只掌握下面的 `run_daily(market_open)` 写法。

```python
from eqlib import *

# ========== 初始化函数 ==========
def initialize(context):
    # 设置要操作的股票
    g.security = '601390'          # 工商银行
    set_benchmark('000300.XSHG')   # 沪深300 作为基准
    set_option('use_real_price', True)

    # 设置初始资金（在 run_backtest 中也指定，这里仅作策略内参考）
    # context.portfolio.starting_cash 可读取

    # 每天开盘时运行
    run_daily(market_open, time='every_bar')

# ========== 每日交易逻辑 ==========
def market_open(context):
    # 获取过去 20 天的收盘价
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()

    # 获取当前价格（最近一根 bar 的收盘价）
    current_price = hist['close'].iloc[-1]

    # 金叉买入，死叉卖出（简化示例）
    if current_price > ma20 * 1.02:
        # 用可用现金全仓买入
        order_value(g.security, context.portfolio.available_cash)
        log.info("买入 %s，价格 %.3f" % (g.security, current_price))

    elif current_price < ma20 * 0.98 and context.portfolio.positions.get(g.security):
        # 清仓卖出
        order_target(g.security, 0)
        log.info("卖出 %s，价格 %.3f" % (g.security, current_price))

# ========== 运行回测 ==========
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,          # 初始资金 10 万元
    benchmark='000300.XSHG',       # 对比基准
    securities=['601390'],         # 预加载数据
    report_dir='reports',
)
```

运行后会输出（时间戳每次不同）：
- `reports/backtest_YYYYMMDD_HHMMSS.png` — 价格与交易标记图
- `reports/backtest_YYYYMMDD_HHMMSS.html` — **交互式报告**（浏览器直接打开）
- `reports/backtest_YYYYMMDD_HHMMSS.md` — 回测摘要报告
- `reports/backtest_YYYYMMDD_HHMMSS.json` — 结构化数据

HTML 各区块与指标含义见 [**报告与指标详解**](../reports_and_metrics.md)。
