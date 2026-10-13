# 选股策略框架

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 用选择器定期更新股票池，驱动组合调仓 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 选股策略框架

选股由两部分组成：

- **选择器**：`filter()` 剔除不合格股票，`rank()` 排序并取前 N 只。
- **调度**：`run_strategy(..., selection_func=..., selection_rebalance=...)` 决定选股函数多久跑一次。跑出的名单写入 `context.universe`，策略按新名单调仓。

### 1.1 TopNSelector：单因子排名

按单个因子列排序，取前 N 只。`factor` 是 `fetch_factor_data` 返回的列名（字符串），不是函数。

```python
from eqlib import TopNSelector

# PE 最低的 5 只（ascending=True = 升序，越小越好）
sel = TopNSelector(factor="pe", top_n=5, ascending=True)
selected = sel.rank(context.universe, context)

# 当日涨幅最高的 3 只（降序，越大越好）
sel = TopNSelector(factor="pct_change", top_n=3, ascending=False)
selected = sel.rank(context.universe, context)
```

签名：`TopNSelector(factor: str = "pe", top_n: int = 5, ascending: bool = True)`。

可用的 `factor` 列名：

| 列名 | 含义 | 回测中可用 |
|------|------|-----------|
| `pct_change` | 当日涨跌幅 | 是 |
| `turnover` | 换手率 | 是 |
| `ma5` / `ma10` / `ma20` | 均线值 | 是 |
| `rsi14` | RSI(14) | 是 |
| `price` / `open` / `high` / `low` / `close` / `volume` / `money` | 行情字段 | 是 |
| `pe` / `pb` / `total_value` | 估值字段 | 否，回测中恒为 NaN（见 §1.6） |

### 1.2 MultiFactorSelector：多因子加权

对每列因子做 z-score 标准化，按权重加总成综合得分，取前 N 只。权重为负表示"越小越好"。

```python
from eqlib import MultiFactorSelector

selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},  # 不传时的默认值
    top_n=5,
)
selected = selector.rank(context.universe, context)
```

签名：`MultiFactorSelector(factors: Optional[dict] = None, top_n: int = 5)`。

`factors` 只接受 `{内置因子列名: 权重}` 的映射，不接受自定义因子函数。要算自己的因子，见 §1.5。

### 1.3 调仓调度

两种注册方式，二选一：

```python
# 方式一：run_strategy 参数
result = run_strategy(
    initialize,
    start_date="2024-01-01",
    end_date="2024-12-31",
    selection_func=my_selection,
    selection_rebalance="monthly:1",
)

# 方式二：在 initialize 里声明
def initialize(context):
    run_selection(my_selection, rebalance="weekly:0")
```

`selection_rebalance` 格式：

| 格式 | 含义 |
|------|------|
| `"monthly:N"` | 每月首个 `日期 >= N` 的交易日（N 取 1-31） |
| `"weekly:N"` | 每周第 N 个工作日（0=周一，4=周五） |
| `"daily"` | 每个交易日 |

选股函数签名固定为 `def my_selection(context) -> list[str]`，返回股票代码列表。引擎在调仓日的盘前调用它，用返回名单替换 `context.universe`，当天后续回调看到的就是新名单。返回空列表时引擎静默跳过（名单不变）；抛异常时名单不变并记一条警告，回测继续。

### 1.4 过滤器

```python
from eqlib import (
    filter_st_stocks, filter_paused_stocks,
    filter_low_price_stocks, filter_high_pe_stocks,
)

candidates = filter_st_stocks(context.universe)                # 剔除 ST/*ST
candidates = filter_paused_stocks(candidates, context)         # 剔除停牌
candidates = filter_low_price_stocks(candidates, 2.0, context) # 剔除 2 元以下
```

各过滤器在回测中的行为不同，用之前看清楚：

- `filter_paused_stocks`、`filter_low_price_stocks` 用预加载数据按 `context.current_dt` 过滤，无前视偏差。
- `filter_st_stocks` 用的是**真实当前日期**的 ST 名单（akshare 快照），不是历史时点。回测中调用会发 `UserWarning`，有幸存者偏差：当年是 ST、如今摘帽的票会被错误保留，反之被错误剔除。
- `filter_high_pe_stocks` 在回测中拿不到历史 PE，原样返回全部候选并记一条警告——等于不过滤。

### 1.5 自定义因子：子类化 StockSelector

内置选择器只能用 `fetch_factor_data` 的现成列。要算自己的因子（比如 20 日动量），继承 `StockSelector` 并实现 `rank()`：

```python
from eqlib import StockSelector, attribute_history

class MomentumSelector(StockSelector):
    """20 日动量：区间涨幅最高的前 N 只。"""

    def __init__(self, top_n: int = 3, lookback: int = 20):
        self.top_n = top_n
        self.lookback = lookback

    def rank(self, securities, context):
        momentum = {}
        for sec in securities:
            hist = attribute_history(sec, self.lookback + 1, "1d", ["close"])
            if hist is None or len(hist) < self.lookback + 1:
                continue
            close = hist["close"]
            momentum[sec] = close.iloc[-1] / close.iloc[0] - 1
        ranked = sorted(momentum, key=momentum.get, reverse=True)
        return ranked[: self.top_n]
```

`filter()` 默认原样返回候选，`rank()` 默认原样返回输入顺序，按需覆盖。

### 1.6 回测中估值因子不可用

`fetch_factor_data` 在回测模式下把 `pe`、`pb`、`total_value` 返回为 NaN——历史估值快照没有 PIT 数据源，给 NaN 是为了避免未来函数。连锁后果：

- `TopNSelector(factor="pe")` 在回测中会把所有行 dropna 掉，`rank()` 返回空列表，`context.universe` 保持不变。
- `get_valuation(code)` 返回键是 `pe`（另有 `pb`、`total_value`、`float_value`、`turnover`、`pct_change`），但回测中它给的是**真实当前**快照，触发 `FutureWarning`；`set_option('avoid_future_data', True)` 时直接抛 `ValueError`。

回测里做估值选股没有干净的数据源。务实的选择：用行情派生因子（`pct_change`、`turnover`、均线、RSI），或按 §1.5 自己写 `rank()` 并用历史行情算因子。

### 1.7 完整示例

每月首个交易日从股票池选出当日涨幅前 3 名，等权持有到下个月：

```python
from eqlib import (
    run_strategy, set_benchmark, set_order_cost, set_slippage,
    run_daily, order_target, order_target_value,
    TopNSelector, filter_paused_stocks, g,
)
from examples._defaults import DEFAULT_ORDER_COST, DEFAULT_SLIPPAGE

STOCK_POOL = ["601398", "601318", "600519", "002594", "000725", "600276"]


def initialize(context):
    set_benchmark("000300.XSHG")
    set_order_cost(DEFAULT_ORDER_COST)
    set_slippage(DEFAULT_SLIPPAGE)
    context.universe = STOCK_POOL
    g.held_universe = None
    run_daily(rebalance, time="every_bar")


def my_selection(context):
    active = filter_paused_stocks(context.universe, context)
    sel = TopNSelector(factor="pct_change", top_n=3, ascending=False)
    return sel.rank(active, context)


def rebalance(context):
    # 名单没变就不动
    if context.universe == g.held_universe:
        return
    g.held_universe = list(context.universe)

    for sec in list(context.portfolio.positions):
        if sec.split(".")[0] not in {s.split(".")[0] for s in context.universe}:
            order_target(sec, 0)
    if not context.universe:
        return
    target = context.portfolio.total_value / len(context.universe)
    for sec in context.universe:
        order_target_value(sec, target)


result = run_strategy(
    initialize,
    start_date="2024-01-01",
    end_date="2024-12-31",
    securities=STOCK_POOL,
    selection_func=my_selection,
    selection_rebalance="monthly:1",
)
```

注意订单在次日开盘价成交（T→T+1），调仓日看到的名单次日才变成持仓。

---

完整参数说明见 [选股策略 API 参考](../reference/api-selection.md)。
