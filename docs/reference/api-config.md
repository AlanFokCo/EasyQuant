# 配置 API

> 设置基准指数、交易手续费、滑点模型等回测参数。

---

## set_benchmark

设置回测基准。

```python
set_benchmark('000300.XSHG')   # 沪深300
```

## set_order_cost

设置交易手续费。

```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                         open_commission=0.00025, close_commission=0.00025,
                         min_commission=5))
```

### OrderCost

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `open_tax` | `0` | 买入印花税 |
| `close_tax` | `None` | 卖出印花税；`None` 时按法定税率（2023-08-28 起 0.05%，此前 0.1%），显式设置优先 |
| `open_commission` | `0.00025` | 买入佣金 |
| `close_commission` | `0.00025` | 卖出佣金 |
| `close_today_commission` | `0` | 今日卖出佣金 |
| `min_commission` | `5` | 最低佣金（元） |

## set_option

设置策略选项。

```python
set_option('use_real_price', True)
```

### 可用选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `check_price_limit` | `True` | 涨跌停成交限制（见下文「涨跌停规则」）。**2026-10 起默认从 `False` 翻转为 `True`** |
| `avoid_future_data` | `False` | 严格 PIT 模式：回测会话内调用非时点安全的快照类 API（如 `get_fundamentals`）时，从 `FutureWarning` 升级为 `ValueError` |
| `st_status_map` | `None` | ST 状态的时点映射：`{代码: bool \| (start, end) \| [(start, end), ...] \| callable(bare_code, date)}`。回测中无网络检测，不注入时按非 ST（主板 ±10%）处理 |
| `delist_gap_days` | `30` | 持仓超过 N 个交易日无行情即视为退市，按最后收盘价强制清算（`<= 0` 关闭） |
| `delisted_position_handling` | `"liquidate"` | 退市处理方式；`"keep"` 表示保留持仓（按最后价估值） |
| `delisted_liquidation_haircut` | `0.0` | 退市清算折价比例（0–1），如 `1.0` 模拟面值退市归零 |

### 涨跌停规则

`check_price_limit=True`（默认）时，以涨停价开盘的买单、以跌停价开盘的卖单会被取消并记录 `Order.cancel_reason`（`"limit-up"` / `"limit-down"`）。涨跌幅限制按板块与日期区分：

| 板块 | 幅度 |
|------|------|
| 主板（非 ST） | ±10% |
| 主板 ST / *ST | ±5%（需 `st_status_map` 提供时点状态） |
| 创业板（300xxx） | 2020-08-24 前 ±10%，之后 ±20%（注册制改革） |
| 科创板（688xxx） | ±20%（开板以来） |
| 北交所（83/87/43/92 开头） | ±30% |

限价按该证券**最近真实收盘价**（停牌期间不更新）计算并精确到分。新股上市无涨跌幅窗口未建模。停牌日订单当日取消并记录原因（`"no price data"`（缺行情）/ `"suspended"`（零成交）），不顺延。退市持仓超过 `delist_gap_days` 无行情后强制清算，`trade_log` 记录 `DELIST_LIQUIDATE`。

> **迁移说明（breaking）**：旧版本回测默认不检查涨跌停（`check_price_limit=False`），动量/打板类策略的旧回测结果会偏乐观。如需复现旧行为，显式 `set_option('check_price_limit', False)`。

## set_slippage

设置滑点模型。

| 类 | 说明 |
|-----|------|
| `SlippageModel` | 基类，不调整价格 |
| `FixedSlippage(pct=0.001)` | 固定比例滑点 |
| `VolumeSlippage(impact=0.05)` | 与成交量成比例的冲击成本 |

## BacktestSession 与 get_session

`BacktestSession` 封装单次回测的可变状态。普通策略不必使用，多线程并行回测时可为每线程创建独立会话。
