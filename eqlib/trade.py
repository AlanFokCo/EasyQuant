"""Trade execution: order, order_target, order_value, order_target_value
(mirrors EasyQuant's trade API).

Orders placed during strategy execution (in handle_data or run_daily callbacks)
are buffered in ``session._pending_orders`` and filled at the **next trading
day's open price** by the engine.  This eliminates look-ahead bias: a signal
generated from today's closing bar cannot affect today's execution.

Phase 2 enhancements:
- Order objects track status (pending→submitted→partial_fill→filled)
- Large orders may partially fill if exceeding daily volume limits
- Remaining unfilled amounts stay in pending queue
"""

import datetime
import eqlib._state as st
from eqlib.logger import log
from eqlib.objects import Order, MarketOrder, LimitOrder


def _bare_code(security: str) -> str:
    """Strip exchange suffix (.XSHG / .XSHE) from a security code."""
    return security.replace(".XSHG", "").replace(".XSHE", "")


def _infer_exchange_suffix(code: str) -> str:
    """Infer .XSHG / .XSHE suffix from a bare A-share code."""
    if code.startswith(("6", "9")):
        return ".XSHG"
    if code.startswith(("0", "3", "2")):
        return ".XSHE"
    return ".XSHG"


def _normalize_security(security: str) -> str:
    """Normalize a security code to suffixed form.

    - If already suffixed (e.g. ``601398.XSHG``), return as-is.
    - If bare (e.g. ``601398``), infer exchange and append suffix.
    - Non-string inputs are returned untouched (caller will raise later).
    """
    if not isinstance(security, str):
        return security
    if ".XSHG" in security or ".XSHE" in security:
        return security
    return security + _infer_exchange_suffix(security)


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


def _buffer_order(action: str, **kwargs) -> Order:
    """Add an order request to the pending queue for next-day execution.

    Creates an Order object for status tracking and attaches it to the request.

    Raises ValueError if an absolute order type (ORDER) is mixed with a
    target order type (ORDER_TARGET / ORDER_VALUE / ORDER_TARGET_VALUE)
    for the same security within a single callback.

    Returns:
        Order object with STATUS_PENDING.
    """
    sess = st.get_session()
    if sess._context is None:
        log.warn(f"_buffer_order: no active context (order ignored)")
        return None

    security = _normalize_security(kwargs.pop("security"))
    amount = kwargs.get("amount", kwargs.get("target_amount", 0))
    style = kwargs.get("style")

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

    # Create Order object for status tracking
    # B3: For target-based orders, side cannot be determined until the engine
    # computes the actual delta. Set side=None; engine will assign at fill time.
    if action in _TARGET_ACTIONS:
        order_obj = Order(security, amount, style=style, side=None)
    else:
        order_obj = Order(security, amount, style=style)

    # ── Phase 2.4: Record order timestamp for timeout tracking ───────────
    # A-REG1: Store submission date (not datetime) for trading-day-based timeout.
    # In backtest mode, orders fill on T+1, so wall-clock timeout is wrong.
    ctx = getattr(sess, '_context', None)
    current_dt = getattr(ctx, 'current_dt', None) if ctx else None
    if current_dt is not None:
        # Backtest: store just the date for trading-day counting
        sess._order_timestamps[order_obj.order_id] = current_dt.date() if hasattr(current_dt, 'date') else current_dt
    else:
        # Live/paper: store full datetime for wall-clock timeout
        sess._order_timestamps[order_obj.order_id] = datetime.datetime.now()

    req = {"action": action, "security": security, "order_obj": order_obj, **kwargs}
    sess._pending_orders.append(req)
    log.debug("order buffered: action=%s security=%s queue_size=%s order_id=%s",
              action, req["security"], len(sess._pending_orders), order_obj.order_id)

    # ── Trigger user callbacks for order queued (if registered) ───────────
    for func in sess._on_order_queued_funcs:
        try:
            func(order_obj, sess._context)
        except Exception as e:
            log.warn(f"on_order_queued callback error: {e}")

    return order_obj


def order(security, amount, style=None) -> Order:
    """Buy or sell a fixed number of shares (mirrors EasyQuant's order).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code, e.g., '601390'
        amount: number of shares (positive = buy, negative = sell)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    Returns:
        Order object with status tracking, or None if the request was invalid.
    """
    if amount == 0:
        return None
    log.action("Queue order", security,
               amount=f"{'+' if amount > 0 else ''}{int(amount)}",
               fill="next_open")
    return _buffer_order("ORDER", security=security, amount=int(amount), style=style)


def order_target(security, amount, style=None) -> Order:
    """Adjust position to a target share count (mirrors EasyQuant's order_target).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        amount: target number of shares (0 = close entire position)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    Raises:
        ValueError: if mixed with ``order`` / ``order_value`` /
        ``order_target_value`` for the same security in one callback.

    Returns:
        Order object, or None.
    """
    log.action("Queue target-shares", security,
               target_shares=int(amount), fill="next_open")
    return _buffer_order("ORDER_TARGET", security=security, target_amount=int(amount), style=style)


def order_value(security, value, style=None) -> Order:
    """Buy or sell a target monetary value (mirrors EasyQuant's order_value).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        value: transaction value in CNY (positive = buy, negative = sell)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    Returns:
        Order object, or None.
    """
    if value == 0:
        return None
    log.action("Queue order-value", security,
               value_cny=f"{float(value):+.0f}", fill="next_open")
    return _buffer_order("ORDER_VALUE", security=security, value=float(value), style=style)


def order_target_value(security, value, style=None) -> Order:
    """Adjust position to a target monetary value (mirrors EasyQuant's order_target_value).

    Orders are buffered and filled at the next trading day's open price.

    Parameters:
        security: stock code
        value: target position value in CNY (0 = close entire position)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    .. note::
        The target delta is computed at *fill time* from the current position
        at tomorrow's open price.  However, the share count is derived from
        today's buffered target value, so mixing ``order_value`` and
        ``order_target_value`` calls for the same security in a single callback
        may produce unexpected results.

    Returns:
        Order object, or None.
    """
    log.action("Queue target-value", security,
               target_cny=f"{float(value):.0f}", fill="next_open")
    return _buffer_order("ORDER_TARGET_VALUE", security=security, target_value=float(value), style=style)


def cancel_order(order_obj):
    """Cancel a pending order before it fills.

    Removes the order from the pending queue and transitions it to
    STATUS_CANCELLED. Has no effect if the order has already been
    filled or cancelled.

    Parameters:
        order_obj: the Order object returned by order(), order_target(), etc.

    Returns:
        The Order object (with updated status).
    """
    if order_obj is None:
        return None

    sess = st.get_session()
    sess._pending_orders = [
        req for req in sess._pending_orders
        if req.get("order_obj") is not order_obj
    ]
    if order_obj.status in (Order.STATUS_PENDING, Order.STATUS_SUBMITTED):
        order_obj.transition_to(Order.STATUS_CANCELLED, reason="user cancelled")
    return order_obj


def order_lots(security, lots, style=None) -> Order:
    """Buy or sell a number of lots (1 lot = 100 shares in A-share market).

    Convenience wrapper around :func:`order`. Positive lots = buy,
    negative lots = sell.

    Parameters:
        security: stock code (bare or suffixed)
        lots: number of lots (positive = buy, negative = sell)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    Returns:
        Order object with status tracking, or None if the request was invalid.

    Example::

        order_lots("601398", 5)   # Buy 5 lots (500 shares)
    """
    return order(security, int(lots) * 100, style=style)


def order_pct(security, pct, style=None) -> Order:
    """Buy or sell using a percentage of available cash.

    Convenience wrapper around :func:`order_value`. Positive pct = buy,
    negative pct = sell (sell pct of current position value).

    Parameters:
        security: stock code (bare or suffixed)
        pct: percentage of available cash to use (e.g. 0.5 = 50%%)
        style: order style - MarketOrder() or LimitOrder(limit_price)

    Returns:
        Order object with status tracking, or None if the request was invalid.

    Example::

        order_pct("601398", 0.5)   # Use 50%% of available cash to buy
    """
    sess = st.get_session()
    ctx = getattr(sess, "_context", None)
    if ctx is None:
        log.warn("order_pct: no active context (order ignored)")
        return None

    security = _normalize_security(security)

    if pct == 0:
        return None

    if pct > 0:
        # Buy: use pct of available cash
        value = ctx.portfolio.available_cash * pct
    else:
        # Sell: sell pct of current position value
        position = ctx.portfolio.positions.get(security)
        if position is None or position.amount <= 0:
            log.warn("order_pct: no position to sell for %s", security)
            return None
        value = position.total_value * pct  # pct is negative, so value is negative

    return order_value(security, value, style=style)
