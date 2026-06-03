# 模拟盘交易

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 使用实时行情运行策略，接收交易信号通知 |
    | **前置** | [运行回测](run-backtest.md) |

---
## 1. 模拟盘交易

模拟盘使用实时行情数据持续运行策略。

### 1. 基本用法

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

### 2. 交易信号通知

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

完整参数说明见 [回测引擎 API 参考](../reference/api-backtest.md)。通知消息格式见 [通知 API 参考](../reference/api-notification.md)。
