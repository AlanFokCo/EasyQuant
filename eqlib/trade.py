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

    .. note::
        This function uses a late import from ``eqlib.engine`` to avoid a
        circular import: ``engine`` imports ``data`` which imports ``_state``,
        while ``trade`` would otherwise need ``engine`` at module level.  The
        late import is intentional and safe — it runs only when a strategy
        callback is active (i.e. after ``engine`` is fully loaded).
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


# Order type categories: "absolute" orders specify a fixed change,
# while "target" orders specify a desired end state.  Mixing both
# for the same security in one callback produces silently wrong results.
_ABSOLUTE_ACTIONS = {"ORDER"}
_TARGET_ACTIONS = {"ORDER_TARGET", "ORDER_VALUE", "ORDER_TARGET_VALUE"}


def _buffer_order(action: str, **kwargs) -> str:
    """Add an order request to the pending queue for next-day execution.

    Raises ValueError if an absolute order type (ORDER) is mixed with a
    target order type (ORDER_TARGET / ORDER_VALUE / ORDER_TARGET_VALUE)
    for the same security within a single callback.
    """
    sess = st.get_session()
    if sess._context is None:
        log.warn(f"_buffer_order: no active context (order ignored)")
        return None

    security = kwargs.pop("security")

    # ── BLOCKER-5: detect mixed absolute / target order types ─────────
    if action in _ABSOLUTE_ACTIONS:
        conflicting = _TARGET_ACTIONS
    else:
        conflicting = _ABSOLUTE_ACTIONS

    for existing in sess._pending_orders:
        if existing["security"] == security and existing["action"] in conflicting:
            raise ValueError(
                f"Cannot mix order/order_target/order_value/order_target_value "
                f"on same security '{security}' in one callback "
                f"(existing={existing['action']}, new={action})"
            )

    req = {"action": action, "security": security, **kwargs}
    sess._pending_orders.append(req)
    log.debug("order buffered: action=%s security=%s queue_size=%s",
              action, req["security"], len(sess._pending_orders))
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
    log.action("Queue order", security,
               amount=f"{'+' if amount > 0 else ''}{int(amount)}",
               fill="next_open")
    return _buffer_order("ORDER", security=security, amount=int(amount))


def order_target(security, amount, style=None):
    """Adjust position to a target share count (mirrors EasyQuant's order_target).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        amount: target number of shares (0 = close entire position)
        style: order style (reserved)

    Raises:
        ValueError: if mixed with ``order`` / ``order_value`` /
        ``order_target_value`` for the same security in one callback.

    Returns:
        Pending order ID string, or None.
    """
    log.action("Queue target-shares", security,
               target_shares=int(amount), fill="next_open")
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
    log.action("Queue order-value", security,
               value_cny=f"{float(value):+.0f}", fill="next_open")
    return _buffer_order("ORDER_VALUE", security=security, value=float(value))


def order_target_value(security, value, style=None):
    """Adjust position to a target monetary value (mirrors EasyQuant's order_target_value).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        value: target position value in CNY (0 = close entire position)
        style: order style (reserved)

    .. note::
        The target delta is computed at *fill time* from the current position
        at tomorrow's open price.  However, the share count is derived from
        today's buffered target value, so mixing ``order_value`` and
        ``order_target_value`` calls for the same security in a single callback
        may produce unexpected results.

    Returns:
        Pending order ID string, or None.
    """
    log.action("Queue target-value", security,
               target_cny=f"{float(value):.0f}", fill="next_open")
    return _buffer_order("ORDER_TARGET_VALUE", security=security, target_value=float(value))
