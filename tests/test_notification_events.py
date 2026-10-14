"""Tests for automatic order-event notifications (queued / filled).

``enable_notification(["queued", "filled"])`` must actually fire webhook
messages in paper/live sessions, and must stay completely silent during
backtests.
"""

from types import SimpleNamespace

import pytest

import eqlib._state as st
from eqlib.notification import (
    format_order_message,
    notify_order_event,
)
from eqlib.objects import Order


class _StubSender:
    """Records send() calls instead of hitting a real webhook."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def send(self, message, title="", **kwargs):
        if self.fail:
            raise RuntimeError("webhook down")
        self.calls.append({"message": message, "title": title, **kwargs})
        return True


@pytest.fixture
def sess():
    session = st.get_session()
    saved = (
        session._notification_sender,
        list(session._notification_events),
        dict(session._options),
        session._context,
        list(session._pending_orders),
    )
    yield session
    (session._notification_sender, session._notification_events,
     session._options, session._context, session._pending_orders) = (
        saved[0], saved[1], saved[2], saved[3], saved[4],
    )


def _paper_session(sess, events, sender):
    sess._notification_sender = sender
    sess._notification_events = list(events)
    sess._options["_is_paper_trading"] = True


def test_filled_event_sends_webhook_in_paper_mode(sess):
    sender = _StubSender()
    _paper_session(sess, ["filled"], sender)
    order = Order("601390.XSHG", 1000)
    trade_info = {"type": "BUY", "price": 5.85, "amount": 1000,
                  "commission": 1.46, "partial": False}

    assert notify_order_event("filled", order, trade_info) is True
    assert len(sender.calls) == 1
    message = sender.calls[0]["message"]
    assert "订单已成交" in message
    assert "601390" in message
    assert "5.850" in message
    assert "1,000" in message


def test_queued_event_sends_webhook_in_paper_mode(sess):
    sender = _StubSender()
    _paper_session(sess, ["queued"], sender)

    assert notify_order_event("queued", Order("000001.XSHE", -500)) is True
    message = sender.calls[0]["message"]
    assert "订单已排队" in message
    assert "卖出" in message


def test_event_not_enabled_stays_silent(sess):
    sender = _StubSender()
    _paper_session(sess, ["signal"], sender)

    assert notify_order_event("filled", Order("601390.XSHG", 1000),
                              {"type": "BUY", "price": 5.0, "amount": 1000,
                               "commission": 1.0, "partial": False}) is False
    assert sender.calls == []


def test_backtest_never_sends_order_events(sess):
    sender = _StubSender()
    sess._notification_sender = sender
    sess._notification_events = ["queued", "filled"]
    # No "_is_paper_trading" flag — this is a backtest session.

    assert notify_order_event("queued", Order("601390.XSHG", 1000)) is False
    assert notify_order_event("filled", Order("601390.XSHG", 1000),
                              {"type": "BUY", "price": 5.0, "amount": 1000,
                               "commission": 1.0, "partial": False}) is False
    assert sender.calls == []


def test_no_webhook_configured_returns_false(sess):
    sess._notification_events = ["filled"]
    sess._options["_is_paper_trading"] = True

    assert notify_order_event("filled", Order("601390.XSHG", 1000),
                              {"type": "BUY", "price": 5.0, "amount": 1000,
                               "commission": 1.0, "partial": False}) is False


def test_sender_failure_never_raises(sess):
    sender = _StubSender(fail=True)
    _paper_session(sess, ["filled"], sender)

    assert notify_order_event("filled", Order("601390.XSHG", 1000),
                              {"type": "BUY", "price": 5.0, "amount": 1000,
                               "commission": 1.0, "partial": False}) is False


def test_target_order_side_falls_back_to_amount_sign(sess):
    sender = _StubSender()
    _paper_session(sess, ["queued"], sender)
    order = Order("601390.XSHG", 1000, side=None)  # target-order style

    assert notify_order_event("queued", order) is True
    assert "买入" in sender.calls[0]["message"]


def test_partial_fill_is_marked_in_message():
    message = format_order_message(
        "filled", Order("601390.XSHG", 1000),
        {"type": "SELL", "price": 5.0, "amount": 400,
         "commission": 0.5, "partial": True},
    )
    assert "部分成交" in message
    assert "卖出" in message


def test_buffer_order_triggers_queued_notification(sess):
    """Integration: trade._buffer_order fires the queued webhook."""
    from eqlib.trade import _buffer_order

    sender = _StubSender()
    _paper_session(sess, ["queued"], sender)
    sess._context = SimpleNamespace(
        current_dt=None,
        portfolio=SimpleNamespace(positions={}),
    )

    order = _buffer_order("buy", security="601390.XSHG", amount=1000)

    assert order is not None
    assert len(sender.calls) == 1
    assert "订单已排队" in sender.calls[0]["message"]
