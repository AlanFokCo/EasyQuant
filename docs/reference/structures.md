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
