"""EasyQuant-like global objects: g, Order, OrderCost."""

import datetime


class GlobalObject:
    """User-facing global object for storing strategy-level variables (like EasyQuant's `g`)."""

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"GlobalObject({attrs})"


class OrderCost:
    """Transaction cost specification (mirrors EasyQuant's OrderCost)."""

    def __init__(
        self,
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ):
        self.open_tax = open_tax
        self.close_tax = close_tax
        self.open_commission = open_commission
        self.close_commission = close_commission
        self.close_today_commission = close_today_commission
        self.min_commission = min_commission

    def calc_open_cost(self, price, amount):
        value = price * amount
        tax = value * self.open_tax
        commission = max(value * self.open_commission, self.min_commission)
        return tax + commission

    def calc_close_cost(self, price, amount, is_today=False, is_etf=False):
        """Calculate total closing cost (stamp duty + commission).

        Parameters:
            price: execution price
            amount: number of shares sold
            is_today: True for intraday close (uses close_today_commission)
            is_etf: True for ETF sells — stamp duty is waived for ETFs
        """
        value = price * amount
        # ETFs are exempt from stamp duty (close_tax only applies to stocks)
        tax = 0.0 if is_etf else value * self.close_tax
        comm_rate = self.close_today_commission if is_today else self.close_commission
        commission = max(value * comm_rate, self.min_commission)
        return tax + commission


class Order:
    """Represents a single order (simplified EasyQuant Order)."""

    def __init__(self, security, amount, style, side, status="pending"):
        self.security = security
        self.amount = amount
        self.style = style  # LimitOrder, MarketOrder
        self.side = side    # "buy" or "sell"
        self.status = status
        self.filled_amount = 0
        self.avg_cost = 0
        self.datetime = None

    def __repr__(self):
        return (
            f"Order({self.security}, side={self.side}, "
            f"amount={self.amount}, status={self.status})"
        )
