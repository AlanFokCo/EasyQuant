"""Trade execution: order, order_target, order_value, order_target_value
(mirrors EasyQuant's trade API).

Orders placed during strategy execution (in handle_data or run_daily callbacks)
are buffered in ``session._pending_orders`` and filled at the **next trading
day's open price** by the engine.  This eliminates look-ahead bias: a signal
generated from today's closing bar cannot affect today's execution.
"""

import eqlib._state as st
from eqlib.logger import log


def _get_pending_price(security):
    """Return a reference price for validation purposes only.

    Used only for basic sanity checks (e.g., computing approximate shares from
    a value order).  The actual execution price is determined by the engine at
    fill time using tomorrow's open.
    """
    sess = st.get_session()
    ctx = sess._context
    if ctx is None:
        return None

    from eqlib.engine import _get_preloaded, _get_open_fast
    day = ctx.current_dt.date()
    # Prefer today's open as a price reference; fall back to close
    price = _get_open_fast(security, day)
    if price is not None:
        return price
    return _get_preloaded().get_close(day, security)


def _round_lot(amount) -> int:
    """Round down to nearest 100 shares (A-share lot size)."""
    return int(amount // 100) * 100


def _buffer_order(action: str, **kwargs) -> str:
    """Add an order request to the pending queue for next-day execution."""
    sess = st.get_session()
    if sess._context is None:
        log.warn(f"_buffer_order: no active context (order ignored)")
        return None
    req = {"action": action, "security": kwargs.pop("security"), **kwargs}
    sess._pending_orders.append(req)
    return f"PENDING_{action}_{req['security']}"


def order(security, amount, style=None):
    """Buy or sell a fixed number of shares (mirrors EasyQuant's order).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code, e.g., '601390'
        amount: number of shares (positive = buy, negative = sell)
        style: order style (reserved; currently ignored)

    Returns:
        Pending order ID string, or None if the request was invalid.
    """
    if amount == 0:
        return None
    log.info(f"order queued: {'+' if amount > 0 else ''}{amount} {security} "
             f"(fills at next open)")
    return _buffer_order("ORDER", security=security, amount=int(amount))


def order_target(security, amount, style=None):
    """Adjust position to a target share count (mirrors EasyQuant's order_target).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        amount: target number of shares (0 = close entire position)
        style: order style (reserved)

    Returns:
        Pending order ID string, or None.
    """
    log.info(f"order_target queued: {security} → {amount} shares (fills at next open)")
    return _buffer_order("ORDER_TARGET", security=security, target_amount=int(amount))


def order_value(security, value, style=None):
    """Buy or sell a target monetary value (mirrors EasyQuant's order_value).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        value: transaction value in CNY (positive = buy, negative = sell)
        style: order style (reserved)

    Returns:
        Pending order ID string, or None.
    """
    if value == 0:
        return None
    log.info(f"order_value queued: {security} {value:+.0f} CNY (fills at next open)")
    return _buffer_order("ORDER_VALUE", security=security, value=float(value))


def order_target_value(security, value, style=None):
    """Adjust position to a target monetary value (mirrors EasyQuant's order_target_value).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        value: target position value in CNY (0 = close entire position)
        style: order style (reserved)

    Returns:
        Pending order ID string, or None.
    """
    log.info(f"order_target_value queued: {security} → {value:.0f} CNY (fills at next open)")
    return _buffer_order("ORDER_TARGET_VALUE", security=security, target_value=float(value))

