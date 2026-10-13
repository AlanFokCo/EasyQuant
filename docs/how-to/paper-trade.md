# 模拟盘交易

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 用实时行情运行策略，信号推送到钉钉/飞书，人工执行实盘 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 模拟盘交易

模拟盘用实时行情持续运行策略，撮合逻辑与回测一致。它不下真实订单——信号通过 Webhook 推送给你，实盘手动执行。

### 1. 基本用法

```python
from eqlib import run_paper_trade, set_benchmark, run_daily, g

def initialize(context):
    g.security = '601398.XSHG'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    pass  # 策略逻辑

result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,   # 行情轮询间隔（秒）
)
```

按 `Ctrl+C` 停止。停止后返回一个 dict：`context`、`trade_log`、`recorded_values`、`session`。

定时回调只接收 `context` 一个参数——写成 `def market_open(context, data)` 会抛 TypeError，而且触发回调熔断（见 §3）。取数用模块级的 `attribute_history()` / `get_current_data()`。

### 2. 交易信号通知

通过钉钉或飞书 Webhook 接收信号通知，按通知里的价格区间手动下单。

#### 2.1 配置 Webhook

```python
from eqlib import set_notification_webhook, enable_notification

def initialize(context):
    # 钉钉（secret 可选，对应机器人"加签"密钥）
    set_notification_webhook(
        "dingtalk",
        "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
        secret="SECxxxxxxxx",
    )
    # 飞书
    # set_notification_webhook(
    #     "feishu",
    #     "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
    # )
    enable_notification(["signal"])  # 默认值，可省略
```

`set_notification_webhook(platform, url, secret=None)`：`platform` 取 `"dingtalk"` 或 `"feishu"`；传 `None` 关闭通知。钉钉加签由库内自动完成（HMAC-SHA256 签名并 URL 编码后拼到 webhook 上）。

`enable_notification(events=None)`：`events` 接受 `"signal"` / `"queued"` / `"filled"`，默认 `["signal"]`。当前版本只在策略主动调用 `notify_signal` 时发送通知，引擎不会为挂单、成交自动推送。

!!! tip "获取 Webhook"

    - **钉钉**：群设置 → 智能群助手 → 添加机器人 → 自定义。安全设置选"加签"则把密钥传给 `secret`。
    - **飞书**：群设置 → 群机器人 → 添加机器人 → 自定义机器人。

#### 2.2 在策略里发信号

```python
from eqlib import (
    run_paper_trade, set_benchmark, run_daily,
    attribute_history, order_value, order_target,
    set_notification_webhook, enable_notification, notify_signal,
    g,
)

def initialize(context):
    set_notification_webhook(
        "dingtalk",
        "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
        secret="SECxxxxxxxx",
    )
    enable_notification(["signal"])

    g.security = "601398.XSHG"
    g.fast = 5
    g.slow = 20
    g.strategy_name = "双均线金叉策略"
    set_benchmark("000300.XSHG")
    run_daily(market_open, time="every_bar")

def market_open(context):
    hist = attribute_history(g.security, g.slow + 5, "1d", ["close"])
    if hist is None or len(hist) < g.slow + 1:
        return
    close = hist["close"]
    price = close.iloc[-1]
    fast_ma = close.tail(g.fast).mean()
    slow_ma = close.tail(g.slow).mean()
    prev_fast = close.tail(g.fast + 1).head(g.fast).mean()
    prev_slow = close.tail(g.slow + 1).head(g.slow).mean()

    if prev_fast <= prev_slow and fast_ma > slow_ma:
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),
            strategy_name=g.strategy_name,
            trigger_point=f"MA5={fast_ma:.2f} 上穿 MA20={slow_ma:.2f}, 金叉形成",
        )
        order_value(g.security, context.portfolio.available_cash)
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        pos = context.portfolio.positions.get(g.security)
        if pos is not None and pos.amount > 0:
            notify_signal(
                security=g.security,
                side="sell",
                amount=pos.amount,
                current_price=price,
                price_range=(price * 0.98, price * 1.02),
                strategy_name=g.strategy_name,
                trigger_point=f"MA5={fast_ma:.2f} 下穿 MA20={slow_ma:.2f}, 死叉形成",
            )
            order_target(g.security, 0)
```

`notify_signal(security, side, amount, current_price=None, price_range=None, strategy_name=None, trigger_point=None)`：`side` 取 `"buy"` / `"sell"`；`amount` 应为 100 的整数倍（A 股整手）；返回 `True` 表示发送成功。未配置 webhook 或未启用 `"signal"` 事件时直接返回 `False`，不影响策略运行。

### 3. 时段门控

模拟盘严格按 A 股交易时段（北京时间）运行，时段外主循环空转：

| 时段 | 阶段 | 行为 |
|------|------|------|
| 09:15 之前 | closed | 不取数、不撮合、不跑回调 |
| 09:15–09:25 | auction（集合竞价） | 回调可运行、可挂单，但不撮合 |
| 09:25–15:00 | continuous（连续竞价） | 正常撮合；当日首笔成交等 09:25 竞价结束 |
| 15:00 之后 | after | `after_trading_end` 钩子跑一次，随后空转 |

规则细节：

- **非交易日**（周末/节假日）整天空转，连行情都不拉。
- **竞价期挂单**：09:15–09:25 期间挂的订单不参与 09:25 的竞价撮合，按统一的 T→T+1 模型次日成交。
- **无行情不砍单**：拿不到报价的股票，订单保持 pending，不会被取消。
- **回调熔断**：同一回调（定时函数或 `handle_data`）连续抛异常 3 次，本次运行内禁用该回调并记 error 日志。进程不会死，但那个回调"安静死亡"——回调里自己兜好异常。
- **调度时刻**：`run_daily(f, time="09:45")` 这类定点回调按真实时钟 ±60 秒匹配，每天每个时间点最多跑一次。`interval` 设得明显大于 60 秒可能错过匹配窗口；`time="every_bar"` 每次轮询都跑，不受此影响。
- `before_trading_start` 钩子在每天任何定时函数和 `handle_data` 之前运行（`context.current_dt` 固定为当天 09:30），与回测的顺序一致。

---

完整参数说明见 [回测引擎 API 参考](../reference/api-backtest.md) 与 [通知 API 参考](../reference/api-notification.md)。端到端示例见 `examples/12_paper_trade.py`。
