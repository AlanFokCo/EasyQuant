"""Notification module for paper trading alerts.

Supports DingTalk (钉钉) and Feishu (飞书) webhook notifications.
When paper trading detects trading signals, this module sends actionable
alerts with specific trading recommendations including strategy name,
trigger point, price range, etc.

Usage in paper trading:
    from eqlib import *
    from eqlib.notification import notify_signal

    def initialize(context):
        # Configure DingTalk notification
        set_notification_webhook("dingtalk", "https://oapi.dingtalk.com/robot/send?access_token=xxx")
        enable_notification(["signal"])

    def handle_data(context, data):
        price = data.current(g.security, 'close')
        ma5 = data.attribute_history(g.security, 5, '1d', ['close']).mean()
        ma20 = data.attribute_history(g.security, 20, '1d', ['close']).mean()

        # 当策略判断需要买入时
        if ma5 > ma20 and g.prev_ma5 <= g.prev_ma20:
            notify_signal(
                security=g.security,
                side="buy",
                amount=1000,
                current_price=price,
                price_range=(price * 0.98, price * 1.02),
                strategy_name="双均线金叉策略",
                trigger_point=f"MA5={ma5:.2f} 上穿 MA20={ma20:.2f}, 金叉形成"
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
        """Send notification message. Returns True if successful."""
        raise NotImplementedError


class DingTalkSender(NotificationSender):
    """DingTalk (钉钉) webhook sender."""

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
            # F1: DingTalk API requires timestamp and sign as URL query parameters
            url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
        else:
            url = self.webhook_url

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("errcode", -1) == 0
            return False
        except Exception:
            return False


class FeishuSender(NotificationSender):
    """Feishu (飞书/Lark) webhook sender."""

    def send(self, message: str, title: str = "EasyQuant交易信号", **kwargs) -> bool:
        """Send notification to Feishu via webhook."""
        event_type = kwargs.get("event_type", "info")
        color_map = {"buy": "blue", "sell": "orange", "signal": "blue", "info": "blue"}
        card_color = color_map.get(event_type, "blue")

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": card_color
                },
                "elements": [{"tag": "markdown", "content": message}]
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
    strategy_name: Optional[str] = None,
    trigger_point: Optional[str] = None
) -> str:
    """Format actionable trade signal message.

    Parameters:
        security: Stock code (e.g., "601390")
        side: "buy" or "sell"
        amount: Number of shares to trade
        current_price: Current market price
        price_range: Tuple of (low, high) recommended execution price range
        context: Current context with portfolio info
        strategy_name: Name of the strategy (e.g., "双均线金叉策略")
        trigger_point: Detailed trigger condition (e.g., "MA5=5.25 上穿 MA20=4.80")

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

    side_label = "买入" if side == "buy" else "卖出"
    side_emoji = "📈" if side == "buy" else "📉"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"## {side_emoji} EasyQuant 操作建议", ""]

    # 策略名称（核心需求）
    if strategy_name:
        lines.append(f"**触发策略**: {strategy_name}")

    lines.append(f"**股票**: {security_display}")
    lines.append(f"**操作**: {side_label}")
    lines.append(f"**数量**: {amount:,} 股 ({amount // 100} 手)")

    if current_price:
        lines.append(f"**当前价格**: ¥{current_price:.3f}")

    if price_range:
        low, high = price_range
        lines.append(f"**建议价格区间**: ¥{low:.3f} ~ ¥{high:.3f}")
        if current_price and current_price > 0:
            pct_low = (low - current_price) / current_price * 100
            pct_high = (high - current_price) / current_price * 100
            lines.append(f"**区间幅度**: {pct_low:+.2f}% ~ {pct_high:+.2f}%")

    if current_price:
        lines.append(f"**预估金额**: ¥{current_price * amount:,.2f}")

    lines.append(f"**时间**: {now}")

    # 触发点（核心需求 - 详细触发条件）
    if trigger_point:
        lines.append("")
        lines.append(f"**触发点**: {trigger_point}")

    if context:
        portfolio = context.portfolio
        lines.append("")
        lines.append("---")
        lines.append("**账户信息**:")
        lines.append(f"- 可用资金: ¥{portfolio.available_cash:,.2f}")
        lines.append(f"- 持仓数量: {len(portfolio.positions)} 只")
        if portfolio.total_value:
            lines.append(f"- 总资产: ¥{portfolio.total_value:,.2f}")

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
    strategy_name: Optional[str] = None,
    trigger_point: Optional[str] = None
) -> bool:
    """Send actionable trade signal notification.

    Parameters:
        security: Stock code (e.g., "601390")
        side: "buy" or "sell"
        amount: Number of shares to trade
        current_price: Current market price
        price_range: Tuple of (low, high) recommended price range
        context: Current context
        strategy_name: 策略名称 (e.g., "双均线金叉策略")
        trigger_point: 触发点详情 (e.g., "MA5=5.25 上穿 MA20=4.80, 金叉形成")

    Returns:
        True if sent successfully.

    Example:
        notify_signal(
            security="601390",
            side="buy",
            amount=1000,
            current_price=5.85,
            price_range=(5.80, 5.90),
            strategy_name="双均线金叉策略",
            trigger_point="MA5=5.25 上穿 MA20=4.80, 金叉形成"
        )
    """
    import eqlib._state as st
    sess = st.get_session()

    sender = getattr(sess, '_notification_sender', None)
    if not sender:
        return False

    enabled_events = getattr(sess, '_notification_events', [])
    if "signal" not in enabled_events and "queued" not in enabled_events:
        return False

    message = format_signal_message(
        security, side, amount,
        current_price=current_price,
        price_range=price_range,
        context=context,
        strategy_name=strategy_name,
        trigger_point=trigger_point
    )

    side_emoji = "📈" if side == "buy" else "📉"
    title = f"{side_emoji} EasyQuant {side.upper()} 建议"

    return sender.send(message, title=title, event_type=side)