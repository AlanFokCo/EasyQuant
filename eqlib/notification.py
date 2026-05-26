"""Notification module for paper trading alerts.

Supports DingTalk (钉钉) and Feishu (飞书) webhook notifications.
When paper trading detects trading signals, this module can send
alerts to configured webhooks, allowing users to manually execute
live trades based on the notifications.

Usage:
    from eqlib import set_notification_webhook, enable_notification

    def initialize(context):
        # Configure DingTalk notification
        set_notification_webhook("dingtalk", "https://oapi.dingtalk.com/robot/send?access_token=xxx")
        enable_notification(["queued"])  # Notify on signal generation
"""

import datetime
import requests
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from eqlib.objects import Order
    from eqlib.context import Context


class NotificationSender:
    """Base class for notification senders."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str, title: str = "EasyQuant交易信号", **kwargs) -> bool:
        """Send notification message.

        Returns:
            True if successful, False otherwise.
        """
        raise NotImplementedError


class DingTalkSender(NotificationSender):
    """DingTalk (钉钉) webhook sender.

    DingTalk webhook API reference:
    https://open.dingtalk.com/document/robots/custom-robot-access

    The webhook URL format:
    https://oapi.dingtalk.com/robot/send?access_token=xxx

    For security, you can enable signature verification by passing
    secret parameter when creating the sender.
    """

    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        super().__init__(webhook_url)
        self.secret = secret

    def _compute_sign(self, timestamp: int) -> str:
        """Compute signature for secure webhook access."""
        if not self.secret:
            return None
        import hmac
        import hashlib
        import base64
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign

    def send(self, message: str, title: str = "EasyQuant交易信号", **kwargs) -> bool:
        """Send notification to DingTalk via webhook.

        Uses markdown message type for rich formatting.
        """
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": message
            }
        }

        # Add signature if secret is configured
        if self.secret:
            sign = self._compute_sign(timestamp)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("errcode", -1) == 0
            return False
        except Exception as e:
            # Log error but don't raise - notification failures shouldn't break trading
            return False


class FeishuSender(NotificationSender):
    """Feishu (飞书/Lark) webhook sender.

    Feishu webhook API reference:
    https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN

    The webhook URL format:
    https://open.feishu.cn/open-apis/bot/v2/hook/xxx

    Uses interactive card message type for rich formatting.
    """

    def __init__(self, webhook_url: str):
        super().__init__(webhook_url)

    def send(self, message: str, title: str = "EasyQuant交易信号", **kwargs) -> bool:
        """Send notification to Feishu via webhook.

        Uses interactive card message type for rich formatting.
        """
        # Determine card color based on event type
        event_type = kwargs.get("event_type", "info")
        color_map = {
            "buy": "blue",
            "sell": "orange",
            "queued": "blue",
            "filled": "green",
            "timeout": "red",
            "info": "blue"
        }
        card_color = color_map.get(event_type, "blue")

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": card_color
                },
                "elements": [
                    {"tag": "markdown", "content": message}
                ]
            }
        }

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("code", -1) == 0
            return False
        except Exception as e:
            return False


def format_order_message(order: "Order", context: "Context", event_type: str,
                         trade_info: Optional[Dict] = None) -> str:
    """Format order details into notification message.

    Parameters:
        order: Order object with details
        context: Current context with portfolio info
        event_type: "queued", "filled", "timeout", etc.
        trade_info: Additional trade execution info (price, amount, etc.)

    Returns:
        Formatted markdown string for notification.
    """
    from eqlib.objects import Order

    # Get security name if possible
    security = order.security
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        bare = security.replace(".XSHG", "").replace(".XSHE", "")
        row = spot[spot["代码"] == bare]
        if len(row) > 0:
            security_name = row.iloc[0]["名称"]
            security_display = f"{bare} ({security_name})"
        else:
            security_display = bare
    except Exception:
        security_display = security.replace(".XSHG", "").replace(".XSHE", "")

    # Format event type
    event_labels = {
        "queued": "信号生成",
        "filled": "订单成交",
        "partial_fill": "部分成交",
        "timeout": "订单超时",
        "cancelled": "订单取消"
    }
    event_label = event_labels.get(event_type, event_type)

    # Format side
    side_label = "买入" if order.side == "buy" else "卖出"
    side_emoji = "📈" if order.side == "buy" else "📉"

    # Format amount
    amount = order.amount
    filled_amount = order.filled_amount if hasattr(order, 'filled_amount') else 0

    # Get current time
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build message
    lines = [
        f"### {side_emoji} EasyQuant {event_label}",
        "",
        f"**类型**: {side_label}{event_label}",
        f"**股票**: {security_display}",
        f"**数量**: {amount:,} 股",
    ]

    # Add filled info for filled/partial events
    if event_type in ("filled", "partial_fill") and trade_info:
        price = trade_info.get("price", 0)
        filled = trade_info.get("amount", filled_amount)
        commission = trade_info.get("commission", 0)
        lines.append(f"**成交价**: ¥{price:.3f}")
        lines.append(f"**成交数量**: {filled:,} 股")
        if commission > 0:
            lines.append(f"**手续费**: ¥{commission:.2f}")

    # Add status info
    status_labels = {
        Order.STATUS_PENDING: "待执行",
        Order.STATUS_SUBMITTED: "已提交",
        Order.STATUS_PARTIAL_FILL: "部分成交",
        Order.STATUS_FILLED: "已成交",
        Order.STATUS_CANCELLED: "已取消",
        Order.STATUS_EXPIRED: "已超时",
        Order.STATUS_REJECTED: "已拒绝"
    }
    status_label = status_labels.get(order.status, order.status)
    lines.append(f"**状态**: {status_label}")
    lines.append(f"**时间**: {now}")

    # Add portfolio summary
    if context:
        portfolio = context.portfolio
        lines.append("")
        lines.append("---")
        lines.append(f"**账户余额**: ¥{portfolio.available_cash:,.2f}")
        if portfolio.total_value:
            lines.append(f"**总资产**: ¥{portfolio.total_value:,.2f}")

    # Add hint for queued orders
    if event_type == "queued":
        lines.append("")
        lines.append("> 信号已生成，订单将在下一交易日开盘执行。")
        lines.append("> 请关注实盘操作机会。")

    return "\n".join(lines)


def send_notification(sess, order: "Order", context: "Context",
                      event_type: str, trade_info: Optional[Dict] = None) -> bool:
    """Send notification via configured webhook.

    Parameters:
        sess: BacktestSession with notification configuration
        order: Order object
        context: Current context
        event_type: "queued", "filled", etc.
        trade_info: Additional trade info for filled events

    Returns:
        True if notification was sent successfully, False otherwise.
    """
    sender = getattr(sess, '_notification_sender', None)
    if not sender:
        return False

    # Check if this event is enabled
    enabled_events = getattr(sess, '_notification_events', [])
    if event_type not in enabled_events:
        return False

    # Format message
    message = format_order_message(order, context, event_type, trade_info)

    # Determine title and event type for card color
    side_emoji = "📈" if order.side == "buy" else "📉"
    title = f"{side_emoji} EasyQuant {order.side.upper()} {event_type}"

    # Send
    return sender.send(message, title=title, event_type=f"{order.side}_{event_type}")