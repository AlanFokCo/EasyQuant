# 回测执行模型

EasyQuant 采用**事件驱动**的回测模型，与 JoinQuant / Zipline 一致。理解执行模型有助于避免常见错误（如前视偏差、内存溢出）。

---

## 策略骨架

每个策略由 **三个函数 + 一个全局对象** 组成：

| 组件 | 调用时机 | 职责 |
|------|----------|------|
| `initialize(context)` | 回测开始时一次 | 设置基准、手续费、注册定时函数、初始化变量 |
| `handle_data(context, data)` | 每个交易日一次 | 读取行情、判断信号、下单 |
| `market_open(context)` | 由 `run_daily` 注册 | 替代 `handle_data` 的自定义入口 |
| `g` | 跨交易日持久化 | 存储策略变量（如持仓天数、阈值） |

## 每日执行流程

```text
每个交易日:
  ┌─ before_trading_start(ctx, data)    ← 盘前回调（可选）
  │
  ├─ run_daily / run_weekly / run_monthly  ← 定时函数
  │
  ├─ handle_data(context, data)           ← 每日交易逻辑
  │
  └─ after_trading_end(ctx, data)         ← 盘后回调（可选）
```

## 关键约束

| 约束 | 说明 | 设计意图 |
|------|------|---------|
| **T+1** | 当天买入的股票次日才可卖出 | 符合 A 股交易制度，框架自动处理 |
| **100 股整数倍** | 买入数量自动向下取整到 100 的整数倍 | 符合 A 股最小交易单位 |
| **前视偏差防护** | 策略只能访问 `context.current_dt` 及之前的数据 | 确保回测结果可信 |
| **下一日成交** | `order*` 在当前回调入队，下一交易日开盘价成交 | 避免使用当日收盘价下单的偏差 |
| **内存限制** | 默认限制 1024 MB，可通过 `max_memory_mb` 调整 | 防止大回测 OOM |

## 订单执行语义

```python
def market_open(context):
    # 1. 当前时刻：只是下单，不立即成交
    order_value('601390', 50000)

    # 2. 下一交易日开盘：引擎按开盘价撮合
    #    - 检查可用资金
    #    - 取整到 100 股
    #    - 计算手续费
    #    - 更新持仓和现金
```

这意味着：
- **不能在下单后立即读取成交价** — 成交价在下一个回调中才能获取
- **当日买入不能当日卖出** — `closeable_amount` 在 T+1 日才大于 0
- **策略信号领先成交一天** — 这是刻意为之，确保回测结果保守可信

## g 全局对象

`g` 是策略级别的持久化存储，跨交易日有效。适合存储：

- 策略参数（均线周期、阈值等）
- 状态变量（持仓天数、上次信号等）
- 预计算的股票池

```python
def initialize(context):
    g.security = '601390'
    g.hold_days = 0
    g.last_signal = None

def market_open(context):
    g.hold_days += 1  # 跨日持久化
```

!!! warning "不要使用 Python 全局变量"

    使用 `g` 而非 Python `global` 变量。`g` 由框架管理，确保在回测和模拟盘中行为一致。
