# Paper Trading

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Run strategies on live market data and receive trade signal notifications |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Paper Trading

Paper trading continuously runs a strategy on real-time market data.

### 1. Basic Usage

```python
from eqlib import run_paper_trade

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    pass  # strategy logic

result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,
)
```

Press `Ctrl+C` to stop.

### 2. Trade Signal Notifications

While paper trading is running, you can receive trade signal notifications via DingTalk or Feishu webhooks.
After receiving a notification, manually execute the trade on your live account.

```python
from eqlib import *
from eqlib.notification import notify_signal

def initialize(context):
    # Configure DingTalk notification
    set_notification_webhook("dingtalk",
        "https://oapi.dingtalk.com/robot/send?access_token=xxx")
    enable_notification(["signal"])

    g.security = '601390'
    g.strategy_name = "Dual MA Golden Cross Strategy"
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context, data):
    price = data.current(g.security, 'close')
    ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
    ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()

    # Golden cross signal
    if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
        # Send notification
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),
            strategy_name=g.strategy_name,
            trigger_point=f"MA5={ma5:.2f} crosses above MA20={ma20:.2f}"
        )
        order(g.security, 1000)

    # Death cross signal
    if ma5 < ma20 and g.prev_ma5 >= g.prev_ma20:
        notify_signal(
            security=g.security,
            side="sell",
            amount=context.portfolio.positions[g.security].amount,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),
            strategy_name=g.strategy_name,
            trigger_point=f"MA5={ma5:.2f} crosses below MA20={ma20:.2f}"
        )
        order_target(g.security, 0)

    g.prev_ma5 = ma5
    g.prev_ma20 = ma20
```

After receiving a DingTalk notification, you can manually execute the trade on your live account using the suggested price range.

!!! tip "Getting a Webhook URL"

    - **DingTalk**: Group Settings → Smart Group Assistant → Add Robot → Custom
    - **Feishu**: Group Settings → Group Bots → Add Bot → Custom Bot

---

See the [Backtest Engine API Reference](../reference/api-backtest.md) for full parameter documentation. See the [Notification API Reference](../reference/api-notification.md) for the notification message format.
