"""Notification module for paper trading alerts.

Supports DingTalk (钉钉) and Feishu (飞书) webhook notifications.
When paper trading detects trading signals, this module sends actionable
alerts with specific trading recommendations (price range, amount, etc.).

Usage in paper trading:
    from eqlib import *
    from eqlib.notification import notify_signal

    def initialize(context):
        # Configure DingTalk notification
        set_notification_webhook("dingtalk", "https://oapi.dingtalk.com/robot/send?access_token=xxx")
        enable_notification(["signal"])

    def handle_data(context, data):
        price = data.current(g.security, 'close')
        # 当策略判断需要买入时
        if should_buy:
            # 发送通知，包含价格区间建议
            notify_signal(
                security=g.security,
                side="buy",
                amount=1000,
                current_price=price,
                price_range=(price * 0.98, price * 1.02)  # 建议在±2%区间内买入
            )
"""

import datetime
import requests
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from eqlib.context import Context
    import eqlib._state as st


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
        """Send notification to DingTalk via webhook."""
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": message
            }
        }

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
        except Exception:
            return False


class FeishuSender(NotificationSender):
    """Feishu (飞书/Lark) webhook sender.

    Feishu webhook API reference:
    https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
    """

    def send(self, message: str, title: str = "EasyQuant交易信号", **kwargs) -> bool:
        """Send notification to Feishu via webhook."""
        event_type = kwargs.get("event_type", "info")
        color_map = {
            "buy": "blue",
            "sell": "orange",
            "signal": "blue",
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
        except Exception:
            return False


def format_signal_message(
    security: str,
    side: str,
    amount: int,
    current_price: Optional[float] = None,
    price_range: Optional[Tuple[float, float]] = None,
    context: Optional["Context"] = None,
    reason: Optional[str] = None
) -> str:
    """Format actionable trade signal message.

    Parameters:
        security: Stock code (e.g., "601390")
        side: "buy" or "sell"
        amount: Number of shares to trade
        current_price: Current market price
        price_range: Tuple of (low, high) recommended execution price range
        context: Current context with portfolio info
        reason: Optional reason/strategy name for the signal

    Returns:
        Formatted markdown string for notification.
    """
    # Get security name if possible
    security_display = security.replace(".XSHG", "").replace(".XSHE", "")
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        bare = security.replace(".XSHG", "").replace(".XSHE", "")
        row = spot[spot["代码"] == bare]
        if len(row) > 0:
            security_name = row.iloc[0]["名称"]
            security_display = f"{bare} ({security_name})"
    except Exception:
        pass

    # Format side
    side_label = "买入" if side == "buy" else "卖出"
    side_emoji = "📈" if side == "buy" else "📉"

    # Get current time
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build actionable message
    lines = [
        f"## {side_emoji} EasyQuant 操作建议",
        "",
        f"**股票**: {security_display}",
        f"**操作**: {side_label}",
        f"**数量**: {amount:,} 股 ({amount // 100} 手)",
    ]

    # Add current price
    if current_price:
        lines.append(f"**当前价格**: ¥{current_price:.3f}")

    # Add recommended price range (核心需求)
    if price_range:
        low, high = price_range
        lines.append(f"**建议价格区间**: ¥{low:.3f} ~ ¥{high:.3f}")
        # 计算区间幅度
        if current_price and current_price > 0:
            pct_low = (low - current_price) / current_price * 100
            pct_high = (high - current_price) / current_price * 100
            lines.append(f"**区间幅度**: {pct_low:+.2f}% ~ {pct_high:+.2f}%")

    # Add estimated value
    if current_price:
        estimated_value = current_price * amount
        lines.append(f"**预估金额**: ¥{estimated_value:,.2f}")

    lines.append(f"**时间**: {now}")

    # Add reason if provided
    if reason:
        lines.append("")
        lines.append(f"**信号来源**: {reason}")

    # Add account info
    if context:
        portfolio = context.portfolio
        lines.append("")
        lines.append("---")
        lines.append("**账户信息**:")
        lines.append(f"- 可用资金: ¥{portfolio.available_cash:,.2f}")
        lines.append(f"- 持仓数量: {len(portfolio.positions)} 只")
        if portfolio.total_value:
            lines.append(f"- 总资产: ¥{portfolio.total_value:,.2f}")

    # Add actionable hint
    lines.append("")
    lines.append("> 💡 **操作建议**:")
    if side == "buy":
        if price_range:
            lines.append(f"> 建议在 ¥{price_range[0]:.3f} ~ ¥{price_range[1]:.3f} 区间内买入 {amount:,} 股")
        else:
            lines.append(f"> 建议买入 {amount:,} 股 ({amount // 100} 手)")
    else:
        if price_range:
            lines.append(f"> 建议在 ¥{price_range[0]:.3f} ~ ¥{price_range[1]:.3f} 区间内卖出 {amount:,} 股")
        else:
            lines.append(f"> 建议卖出 {amount:,} 股 ({amount // 100} 手)")

    return "\n".join(lines)


def notify_signal(
    security: str,
    side: str,
    amount: int,
    current_price: Optional[float] = None,
    price_range: Optional[Tuple[float, float]] = None,
    context: Optional["Context"] = None,
    reason: Optional[str] = None
) -> bool:
    """Send actionable trade signal notification.

    This is the main function to call when strategy generates a signal.
    It sends a notification with concrete trading advice including
    price range recommendations.

    Parameters:
        security: Stock code (e.g., "601390")
        side: "buy" or "sell"
        amount: Number of shares to trade
        current_price: Current market price
        price_range: Tuple of (low, high) recommended execution price range
            For example: (5.80, 6.00) means execute between ¥5.80 and ¥6.00
        context: Current context (optional)
        reason: Signal reason (optional, e.g., "MA金叉")

    Returns:
        True if notification was sent successfully, False otherwise.

    Example:

        notify_signal(
            security="601390",
            side="buy",
            amount=1000,
            current_price=5.85,
            price_range=(5.80, 5.90),  # 建议在5.80-5.90区间买入
            reason="MA5上穿MA20金叉"
        )
    """
    import eqlib._state as st
    sess = st.get_session()

    sender = getattr(sess, '_notification_sender', None)
    if not sender:
        return False

    # Check if signal event is enabled
    enabled_events = getattr(sess, '_notification_events', [])
    if "signal" not in enabled_events and "queued" not in enabled_events:
        return False

    # Format message
    message = format_signal_message(
        security, side, amount,
        current_price=current_price,
        price_range=price_range,
        context=context,
        reason=reason
    )

    # Determine title
    side_emoji = "📈" if side == "buy" else "📉"
    title = f"{side_emoji} EasyQuant {side.upper()} 建议"

    # Send
    return sender.send(message, title=title, event_type=side)