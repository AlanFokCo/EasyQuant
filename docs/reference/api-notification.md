# 通知 API

!!! tip "模拟盘通知"

    在模拟盘运行时，通过钉钉或飞书 Webhook 接收交易信号通知，
    收到通知后可手动执行实盘操作。

---

## set_notification_webhook

配置 Webhook 用于发送交易信号通知。

```python
# 钉钉（支持签名验证）
set_notification_webhook("dingtalk", 
    "https://oapi.dingtalk.com/robot/send?access_token=xxx",
    secret="SECxxx")

# 飞书
set_notification_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/xxx")

# 关闭通知
set_notification_webhook(None, None)
```

| 参数 | 说明 |
|------|------|
| `platform` | `"dingtalk"` 或 `"feishu"` |
| `url` | Webhook URL |
| `secret` | 钉钉签名密钥（可选） |

!!! warning "获取 Webhook"

    - **钉钉**: 群设置 → 智能群助手 → 添加机器人 → 自定义
    - **飞书**: 群设置 → 群机器人 → 添加机器人 → 自定义机器人

## enable_notification

启用通知事件类型。

```python
# 启用信号通知（推荐）
enable_notification(["signal"])

# 启用所有通知
enable_notification(["signal", "filled"])

# 关闭通知
enable_notification([])
```

| 事件 | 说明 |
|------|------|
| `"signal"` | 策略触发交易信号时通知（推荐） |
| `"filled"` | 订单成交时通知 |
| `"queued"` | 订单生成时通知 |

## notify_signal

发送交易信号通知。在策略检测到交易信号时调用。

```python
def handle_data(context, data):
    price = data.current(g.security, 'close')
    ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
    ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()
    
    # 金叉信号 - 发送通知
    if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
        notify_signal(
            security=g.security,
            side="buy",
            amount=1000,
            current_price=price,
            price_range=(price * 0.98, price * 1.02),  # ±2%区间
            strategy_name="双均线金叉策略",
            trigger_point=f"MA5={ma5:.2f} 上穿 MA20={ma20:.2f}"
        )
        order(g.security, 1000)
```

| 参数 | 说明 |
|------|------|
| `security` | 股票代码 |
| `side` | `"buy"` 或 `"sell"` |
| `amount` | 数量（股），须为100的整数倍 |
| `current_price` | 当前价格 |
| `price_range` | 建议价格区间 `(low, high)` |
| `strategy_name` | 策略名称 |
| `trigger_point` | 触发点详情 |

### 通知消息格式

```
## 📈 EasyQuant 操作建议

**触发策略**: 双均线金叉策略
**股票**: 601390 (中国中铁)
**操作**: 买入
**数量**: 1,000 股 (10 手)
**当前价格**: ¥5.850
**建议价格区间**: ¥5.800 ~ ¥5.900
**区间幅度**: -0.85% ~ +0.85%
**预估金额**: ¥5,850.00
**时间**: 2024-01-15 09:30:00

**触发点**: MA5=5.25 上穿 MA20=4.80, 金叉形成

> 💡 **操作建议**:
> 建议在 ¥5.800 ~ ¥5.900 区间内买入 1,000 股
```
