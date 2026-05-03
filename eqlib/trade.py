"""Trade execution: order, order_target, order_value, order_target_value
(mirrors EasyQuant's trade API)."""

import datetime
import math
from eqlib.logger import log
import eqlib._state as st
from eqlib.data import get_price


def _get_current_price(security):
    """Get current price from preloaded data or fetch from network."""
    ctx = st._context
    if ctx is None:
        return None

    # Try preloaded data first
    from eqlib.engine import _preloaded
    day = ctx.current_dt.date()
    price = _preloaded.get_close(day, security)
    if price is not None:
        return price

    # Fallback: fetch from network
    from eqlib.data import fetch_stock_data
    end_date = ctx.current_dt
    days_back = max((ctx.current_dt.date() - ctx.start_date).days, 10)
    start_date = end_date - datetime.timedelta(days=days_back)
    df = fetch_stock_data(security, start_date, end_date)
    if df.empty:
        return None
    return df["close"].iloc[-1]


def _calc_commission(price, amount, is_buy):
    """Calculate trading commission based on OrderCost settings."""
    if st._order_cost is None:
        from eqlib.objects import OrderCost
        cost = OrderCost()
    else:
        cost = st._order_cost

    if is_buy:
        return cost.calc_open_cost(price, amount)
    else:
        return cost.calc_close_cost(price, amount)


def _round_lot(amount):
    """Round to nearest 100 shares (A-share lot size)."""
    return int(amount // 100) * 100


def order(security, amount, style=None):
    """
    Buy or sell a fixed number of shares
    (mirrors EasyQuant's order).

    Parameters:
        security: stock code, e.g., '601390'
        amount: number of shares (positive=buy, negative=sell)
        style: order style (None = market order)

    Returns:
        Order ID or None if order failed
    """
    if amount == 0:
        return None

    price = _get_current_price(security)
    if price is None:
        log.warn(f"order: no price data for {security}")
        return None

    portfolio = st._context.portfolio

    if amount > 0:
        # Buy
        rounded = _round_lot(amount)
        if rounded == 0:
            return None
        cost = price * rounded
        commission = _calc_commission(price, rounded, is_buy=True)
        total_cost = cost + commission

        if total_cost > portfolio.available_cash:
            # Max affordable
            max_shares = int((portfolio.available_cash) / (price * 1.001) // 100) * 100
            if max_shares <= 0:
                log.warn(f"order: insufficient cash for {security}")
                return None
            rounded = max_shares
            cost = price * rounded
            commission = _calc_commission(price, rounded, is_buy=True)
            total_cost = cost + commission

        portfolio.available_cash -= total_cost

        if security not in portfolio.positions:
            from eqlib.context import Position
            portfolio.positions[security] = Position(security)

        pos = portfolio.positions[security]
        total_cost_basis = pos.avg_cost * pos.amount + cost
        pos.amount += rounded
        pos.closeable_amount = pos.amount
        pos.avg_cost = total_cost_basis / pos.amount if pos.amount > 0 else 0

        log.info(f"order BUY {security}: {rounded} shares @ {price:.3f}, commission={commission:.2f}")

        # Record trade
        st._trade_log.append({
            "type": "BUY",
            "date": st._context.current_dt.date(),
            "security": security,
            "price": price,
            "amount": rounded,
            "commission": commission,
        })

        return f"BUY_{security}_{rounded}"

    else:
        # Sell
        sell_amount = abs(amount)
        if security not in portfolio.positions:
            return None
        pos = portfolio.positions[security]
        sell_amount = min(sell_amount, int(pos.closeable_amount))

        if sell_amount <= 0:
            return None

        revenue = price * sell_amount
        commission = _calc_commission(price, sell_amount, is_buy=False)
        net = revenue - commission

        portfolio.available_cash += net
        pos.amount -= sell_amount
        pos.closeable_amount -= sell_amount

        if pos.amount <= 0:
            pos.amount = 0
            pos.closeable_amount = 0
            pos.avg_cost = 0

        log.info(f"order SELL {security}: {sell_amount} shares @ {price:.3f}, commission={commission:.2f}")

        # Record trade
        st._trade_log.append({
            "type": "SELL",
            "date": st._context.current_dt.date(),
            "security": security,
            "price": price,
            "amount": sell_amount,
            "commission": commission,
        })

        return f"SELL_{security}_{sell_amount}"


def order_target(security, amount, style=None):
    """
    Adjust position to target number of shares
    (mirrors EasyQuant's order_target).

    Parameters:
        security: stock code
        amount: target number of shares (0 = close position)
        style: order style

    Returns:
        Order ID or None
    """
    if security in st._context.portfolio.positions:
        current = st._context.portfolio.positions[security].amount
    else:
        current = 0

    delta = amount - current
    return order(security, delta, style)


def order_value(security, value, style=None):
    """
    Buy or sell a target monetary value
    (mirrors EasyQuant's order_value).

    Parameters:
        security: stock code
        value: target transaction value (positive=buy, negative=sell)
        style: order style

    Returns:
        Order ID or None
    """
    if value == 0:
        return None

    price = _get_current_price(security)
    if price is None or price <= 0:
        return None

    shares = abs(int(value / price))
    shares = _round_lot(shares) if value > 0 else shares

    if shares <= 0:
        return None

    if value < 0:
        shares = -shares

    return order(security, shares, style)


def order_target_value(security, value, style=None):
    """
    Adjust position to target monetary value
    (mirrors EasyQuant's order_target_value).

    Parameters:
        security: stock code
        value: target position value (0 = close position)
        style: order style

    Returns:
        Order ID or None
    """
    price = _get_current_price(security)
    if price is None or price <= 0:
        return None

    target_shares = int(value / price)
    target_shares = _round_lot(target_shares) if value > 0 else target_shares

    return order_target(security, target_shares, style)


def order_market(security, amount, price, style=None):
    """
    Place an order with explicit price (for backtest engine use).

    Parameters:
        security: stock code
        amount: number of shares (positive=buy, negative=sell)
        price: execution price

    Returns:
        dict with order details
    """
    portfolio = st._context.portfolio

    if amount > 0:
        rounded = _round_lot(amount)
        if rounded == 0:
            return None
        cost = price * rounded
        commission = _calc_commission(price, rounded, is_buy=True)
        total_cost = cost + commission

        if total_cost > portfolio.available_cash:
            max_shares = int(portfolio.available_cash / (price * 1.001) // 100) * 100
            if max_shares <= 0:
                return None
            rounded = max_shares
            cost = price * rounded
            commission = _calc_commission(price, rounded, is_buy=True)
            total_cost = cost + commission

        portfolio.available_cash -= total_cost

        if security not in portfolio.positions:
            from eqlib.context import Position
            portfolio.positions[security] = Position(security)

        pos = portfolio.positions[security]
        total_cb = pos.avg_cost * pos.amount + cost
        pos.amount += rounded
        pos.closeable_amount = pos.amount
        pos.avg_cost = total_cb / pos.amount if pos.amount > 0 else 0

        return {
            "type": "BUY",
            "security": security,
            "price": price,
            "amount": rounded,
            "commission": commission,
        }
    else:
        sell_amount = abs(amount)
        if security not in portfolio.positions:
            return None
        pos = portfolio.positions[security]
        sell_amount = min(sell_amount, int(pos.closeable_amount))
        if sell_amount <= 0:
            return None

        revenue = price * sell_amount
        commission = _calc_commission(price, sell_amount, is_buy=False)
        net = revenue - commission

        portfolio.available_cash += net
        pos.amount -= sell_amount
        pos.closeable_amount -= sell_amount
        if pos.amount <= 0:
            pos.amount = 0
            pos.closeable_amount = 0
            pos.avg_cost = 0

        return {
            "type": "SELL",
            "security": security,
            "price": price,
            "amount": sell_amount,
            "commission": commission,
        }
