# 策略生命周期结构体

> 策略执行过程中框架自动传入的核心数据结构。

---

## Context

策略执行上下文，由框架在回调时自动传入。

| 属性 | 类型 | 说明 |
|------|------|------|
| `current_dt` | `datetime` | 当前模拟时间 |
| `start_date` | `date` | 回测开始日期 |
| `end_date` | `date` | 回测结束日期 |
| `frequency` | `str` | `'daily'` 或 `'minute'` |
| `portfolio` | `Portfolio` | 投资组合对象 |
| `universe` | `list[str]` | 当前策略股票池 |
| `run_params` | `dict` | 回测参数字典 |

## Portfolio

投资组合状态，通过 `context.portfolio` 访问。

| 属性 | 说明 | 用户输入 |
|------|------|----------|
| `starting_cash` | 初始资金 | 由 `starting_cash` 参数设定 |
| `available_cash` | 可用现金 | 框架自动维护 |
| `positions` | 持仓字典，key 为股票代码 | 框架自动维护 |
| `total_value` | 总资产 = 现金 + 持仓市值 | 框架自动计算 |
| `returns` | 总收益率 | 只读 |

## Position

单只股票持仓，通过 `context.portfolio.positions[code]` 访问。

| 属性 | 说明 | 用户输入 |
|------|------|----------|
| `security` | 股票代码 | 框架自动设定 |
| `amount` | 持仓数量（股） | 框架自动维护 |
| `closeable_amount` | 今日可卖数量（T+1 限制） | 框架自动维护 |
| `avg_cost` | 持仓均价 | 框架自动计算 |
| `total_value` | 持仓市值 | 框架自动计算 |
| `price` | 当前价 | 只读 |
| `price_stale` | `bool`：最新报价缺失/无效时为 `True`，估值沿用上一有效价；收到新报价恢复 `False` | 框架自动维护 |

## Order

单笔订单，由 `order()` 等下单函数返回。

| 属性 | 类型 | 说明 |
|------|------|------|
| `order_id` | `str` | 订单唯一标识（自动生成） |
| `security` | `str` | 股票代码 |
| `amount` | `int` | 委托股数（恒为正，买卖方向看 `side`） |
| `side` | `str` | `"buy"` / `"sell"`（目标订单在首次撮合前可为 `None`） |
| `style` | — | `MarketOrder()` 或 `LimitOrder(price)` |
| `status` | `str` | 订单状态（见下） |
| `filled_amount` | `int` | 已成交股数 |
| `avg_cost` | `float` | 成交均价 |
| `commission` | `float` | 已付佣金 |
| `datetime` | `datetime` | 创建时间 |
| `submit_time` | `datetime \| None` | 提交时间 |
| `fill_time` | `datetime \| None` | 成交时间 |
| `reject_reason` | `str \| None` | 拒绝原因（状态为 `rejected` 时写入） |
| `cancel_reason` | `str \| None` | 取消/过期原因（状态为 `cancelled` / `expired` 时写入，取值见下表） |

方法：`is_complete()`（仅 `filled` 返回 `True`）；`remaining_amount()`（未成交股数；金额/目标订单在首次撮合解析股数前返回 `None`）。

### 订单状态

`pending` → `submitted` →（可经 `partial_fill`）→ `filled`；终止态还有 `rejected`、`cancelled`、`expired`。

### cancel_reason 取值

| 值 | 含义 |
|------|------|
| `"limit-up"` / `"limit-down"` | 买单遇涨停 / 卖单遇跌停，无法成交 |
| `"suspended"` | 停牌（当日有行情但零成交） |
| `"zero volume"` | 当日零成交量，滑点模型无法给出成交价 |
| `"no bar data"` | 当日无 K 线数据 |
| `"no open price"` | 金额/目标订单缺开盘价，无法换算股数 |
| `"no price data"` | 缺少行情数据 |
| `"sub-lot"` | 数量向下取整后不足 100 股 |
| `"insufficient cash"` | 可用资金不足 |
| `"no position"` | 卖出时无可卖持仓 |
| `"no position change needed"` | 目标持仓与当前持仓一致 |
| `"unknown action"` | 未知订单动作 |
| `"delisted"` | 退市强制清算 |
| `"timeout"` | 订单过期（状态为 `expired`） |

## g — GlobalObject

策略级别的全局对象，用于跨交易日存储自定义变量。

```python
from eqlib import g

def initialize(context):
    g.security = '601390'
    g.ma_period = 20

def market_open(context):
    hist = attribute_history(g.security, g.ma_period, '1d', ['close'])
```

!!! warning "⚠️ 重要提示：run_backtest 启动时会清空 ``g``"
    `run_backtest`（以及 `run_strategy`）在每次调用时都会**清空 `g` 对象**。因此：

    - **不要**在 `run_backtest` 调用之前设置 `g.xxx`，这些值会在回测启动时被清空。
    - **应该**在 `initialize(context)` 内部设置 `g.xxx`，这样值会在回测开始时写入。
    - 对于需要在回测外部共享的配置（如常量、参数），使用 Python 模块级变量而非 `g`。

    ```python
    # ❌ 错误：run_backtest 会清空 g.universe
    g.universe = ['601398', '600519']
    run_backtest(initialize, ...)

    # ✅ 正确：在 initialize 内部设置
    def initialize(context):
        g.universe = ['601398', '600519']
    ```
