# Notification API

!!! tip "Paper Trading Notifications"

    During paper trading, receive trade signal notifications via DingTalk or Feishu webhooks.
    Upon receiving a notification, you can manually execute the trade in your live account.

---

## set_notification_webhook

Configure a webhook for sending trade signal notifications.

```python
# DingTalk (supports signature verification)
set_notification_webhook("dingtalk", 
    "https://oapi.dingtalk.com/robot/send?access_token=xxx",
    secret="SECxxx")

# Feishu (Lark)
set_notification_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/xxx")

# Disable notifications
set_notification_webhook(None, None)
```

| Parameter | Description |
|-----------|-------------|
| `platform` | `"dingtalk"` or `"feishu"` |
| `url` | Webhook URL |
| `secret` | DingTalk signing secret (optional) |

!!! warning "Obtaining a Webhook"

    - **DingTalk**: Group Settings → Smart Group Assistant → Add Robot → Custom
    - **Feishu**: Group Settings → Group Bots → Add Bot → Custom Bot

## enable_notification

Enable notification event types.

```python
# Enable signal notifications (recommended)
enable_notification(["signal"])

# Enable all notifications
enable_notification(["signal", "filled"])

# Disable notifications
enable_notification([])
```

| Event | Description |
|-------|-------------|
| `"signal"` | Notify when the strategy triggers a trade signal (recommended) |
| `"filled"` | Notify when an order is filled |
| `"queued"` | Notify when an order is generated |

## notify_signal

Send a trade signal notification. Call when the strategy detects a trading signal.

```python
def handle_data(context, data):
    price = data.current(g.security, 'close')
    ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
    ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()
    
    # Golden cross signal - send notification
    if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),  # ±2% range
            strategy_name="Dual MA Golden Cross Strategy",
            trigger_point=f"MA5={ma5:.2f} crosses above MA20={ma20:.2f}"
        )
        order(g.security, 1000)
```

| Parameter | Description |
|-----------|-------------|
| `security` | Stock ticker |
| `side` | `"buy"` or `"sell"` |
| `amount` | Quantity (shares), must be a multiple of 100 |
| `current_price` | Current price |
| `price_range` | Suggested price range `(low, high)` |
| `strategy_name` | Strategy name |
| `trigger_point` | Trigger point details |

### Notification Message Format

```
## 📈 EasyQuant Trade Recommendation

**Strategy**: Dual MA Golden Cross Strategy
**Stock**: 601390 (China Railway)
**Action**: Buy
**Quantity**: 1,000 shares (10 lots)
**Current Price**: ¥5.850
**Suggested Price Range**: ¥5.800 ~ ¥5.900
**Range**: -0.85% ~ +0.85%
**Estimated Amount**: ¥5,850.00
**Time**: 2024-01-15 09:30:00

**Trigger**: MA5=5.25 crosses above MA20=4.80, golden cross formed

> 💡 **Recommendation**:
> Buy 1,000 shares within the ¥5.800 ~ ¥5.900 range
```
