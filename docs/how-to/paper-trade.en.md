# Paper Trading

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Run strategies on live market data, push signals to DingTalk/Feishu, and execute real trades manually |
    | **Prerequisite** | [Running a Backtest](run-backtest.md) |

---
## 1. Paper Trading

Paper trading runs a strategy continuously on live market data with the same matching logic as the backtest. It never places real orders — signals are pushed to you via webhook, and you execute the live trade manually.

### 1. Basic Usage

```python
from eqlib import run_paper_trade, set_benchmark, run_daily, g

def initialize(context):
    g.security = '601398.XSHG'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    pass  # strategy logic

result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,   # quote polling interval in seconds
)
```

Press `Ctrl+C` to stop. On stop it returns a dict with `context`, `trade_log`, `recorded_values`, and `session`.

Scheduled callbacks take only `context` — writing `def market_open(context, data)` raises a TypeError and trips the callback circuit breaker (see §3). Fetch data with the module-level `attribute_history()` / `get_current_data()`.

### 2. Trade Signal Notifications

Receive signal notifications through a DingTalk or Feishu webhook, then place orders manually using the suggested price range.

#### 2.1 Configure the Webhook

```python
from eqlib import set_notification_webhook, enable_notification

def initialize(context):
    # DingTalk (secret is optional — the robot's signing key)
    set_notification_webhook(
        "dingtalk",
        "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
        secret="SECxxxxxxxx",
    )
    # Feishu
    # set_notification_webhook(
    #     "feishu",
    #     "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
    # )
    enable_notification(["signal"])  # default; may be omitted
```

`set_notification_webhook(platform, url, secret=None)`: `platform` is `"dingtalk"` or `"feishu"`; pass `None` to disable notifications. DingTalk signing is handled internally (HMAC-SHA256, URL-encoded onto the webhook URL).

`enable_notification(events=None)`: `events` accepts `"signal"` / `"queued"` / `"filled"` and defaults to `["signal"]`. `"signal"` fires when the strategy calls `notify_signal`; `"queued"` (order queued) and `"filled"` (order filled, with price, amount, commission and partial-fill flag) are pushed automatically by the engine in paper/live sessions. No notification is ever sent during a backtest, regardless of configuration.

!!! tip "Getting a Webhook URL"

    - **DingTalk**: Group Settings → Smart Group Assistant → Add Robot → Custom. If you enable "Sign" in the security settings, pass the key as `secret`.
    - **Feishu**: Group Settings → Group Bots → Add Bot → Custom Bot.

#### 2.2 Sending Signals from a Strategy

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
    g.strategy_name = "Dual MA crossover"
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
            trigger_point=f"MA5={fast_ma:.2f} crossed above MA20={slow_ma:.2f} (golden cross)",
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
                trigger_point=f"MA5={fast_ma:.2f} crossed below MA20={slow_ma:.2f} (death cross)",
            )
            order_target(g.security, 0)
```

`notify_signal(security, side, amount, current_price=None, price_range=None, strategy_name=None, trigger_point=None)`: `side` is `"buy"` or `"sell"`; `amount` should be a multiple of 100 (A-share round lots); returns `True` when the message was sent. Without a configured webhook or with the `"signal"` event disabled, it returns `False` immediately without disturbing the strategy.

### 3. Session Gating

Paper trading follows the A-share session (China Standard Time). Outside the session the main loop idles:

| Time | Phase | Behavior |
|------|-------|----------|
| Before 09:15 | closed | No price fetches, no matching, no callbacks |
| 09:15–09:25 | auction (open call auction) | Callbacks may run and queue orders; nothing is matched |
| 09:25–15:00 | continuous | Normal matching; the day's first fill waits for the 09:25 auction close |
| After 15:00 | after | `after_trading_end` hooks fire once, then the loop idles |

Detailed rules:

- **Non-trading days** (weekends/holidays): the loop idles all day — no fetches, no matching, no callbacks.
- **Orders queued during the auction** do not participate in the 09:25 auction match; under the unified T→T+1 model they fill the next trading day.
- **No-quote orders are not cancelled**: if no live price is available for a security, its order stays pending.
- **Callback circuit breaker**: after 3 consecutive exceptions, a callback (scheduled function or `handle_data`) is disabled for the rest of the run with an error log. The process survives, but that callback dies silently — handle your own exceptions inside callbacks.
- **Scheduled times**: a fixed-time callback like `run_daily(f, time="09:45")` matches the wall clock within ±60 seconds, at most once per day per time slot. An `interval` well above 60 seconds can miss the window; `time="every_bar"` runs on every poll and is unaffected.
- `before_trading_start` hooks run before any scheduled function or `handle_data` of the day (with `context.current_dt` fixed at 09:30), matching the backtest ordering.

---

See the [Backtest Engine API Reference](../reference/api-backtest.md) and the [Notification API Reference](../reference/api-notification.md) for full parameter documentation. The end-to-end demo is `examples/12_paper_trade.py`.
