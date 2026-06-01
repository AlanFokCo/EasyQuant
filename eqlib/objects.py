"""EasyQuant-like global objects: g, Order, OrderCost."""

import datetime
import uuid


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

    def calc_close_cost(self, price, amount, is_today=False, is_etf=False,
                        trade_date=None):
        """Calculate total closing cost (stamp duty + commission).

        Parameters:
            price: execution price
            amount: number of shares sold
            is_today: True for intraday close (uses close_today_commission)
            is_etf: True for ETF sells — stamp duty is waived for ETFs
            trade_date: the trade date (datetime.date or None). When provided,
                applies the date-dependent A-share stamp duty rate:
                0.05% (万五) for trades on or after 2023-08-28 (MoF Announcement
                2023 No. 33), and 0.1% (千一) for earlier dates.  When None,
                falls back to the configured ``close_tax`` rate.
        """
        value = price * amount
        # Determine effective stamp duty rate
        if is_etf:
            tax = 0.0
        elif trade_date is not None:
            _cutoff = datetime.date(2023, 8, 28)
            _date = trade_date if isinstance(trade_date, datetime.date) else trade_date.date()
            effective_tax_rate = 0.0005 if _date >= _cutoff else 0.001
            tax = value * effective_tax_rate
        else:
            tax = value * self.close_tax
        comm_rate = self.close_today_commission if is_today else self.close_commission
        commission = max(value * comm_rate, self.min_commission)
        return tax + commission


class Order:
    """Represents a single order with comprehensive status tracking."""

    # Order status constants
    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_PARTIAL_FILL = "partial_fill"
    STATUS_FILLED = "filled"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    # Valid status transitions
    _VALID_TRANSITIONS = {
        STATUS_PENDING: [STATUS_SUBMITTED, STATUS_CANCELLED],
        STATUS_SUBMITTED: [STATUS_PARTIAL_FILL, STATUS_FILLED, STATUS_REJECTED, STATUS_CANCELLED, STATUS_EXPIRED],
        STATUS_PARTIAL_FILL: [STATUS_PARTIAL_FILL, STATUS_FILLED, STATUS_CANCELLED, STATUS_EXPIRED],
    }

    def __init__(self, security, amount, style=None, side=None, order_id=None):
        """Initialize an Order.

        Parameters:
            security: stock code
            amount: requested number of shares (positive for buy, negative for sell)
            style: LimitOrder or MarketOrder (default MarketOrder)
            side: "buy" or "sell" (auto-detected from amount if None)
            order_id: unique identifier (auto-generated if None)
        """
        self.order_id = order_id or f"ORD_{security}_{uuid.uuid4().hex[:12]}"
        self.security = security
        self.amount = abs(amount)  # requested amount (always positive)
        self.style = style or MarketOrder()
        self.side = side or ("buy" if amount > 0 else "sell")
        self.status = self.STATUS_PENDING

        # Fill tracking
        self.filled_amount = 0
        self.avg_cost = 0.0
        self.commission = 0.0
        self.partial_fills = []  # list of (amount, price, timestamp) tuples

        # Timing
        self.datetime = datetime.datetime.now()
        self.submit_time = None
        self.fill_time = None

        # Rejection info
        self.reject_reason = None

    def can_transition_to(self, new_status: str) -> bool:
        """Check if status transition is valid."""
        allowed = self._VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status: str, reason: str = None):
        """Transition to a new status with validation."""
        if not self.can_transition_to(new_status):
            raise ValueError(f"Invalid transition: {self.status} → {new_status}")
        self.status = new_status
        if new_status == self.STATUS_REJECTED:
            self.reject_reason = reason
        elif new_status == self.STATUS_FILLED:
            self.fill_time = datetime.datetime.now()

    def add_partial_fill(self, amount: int, price: float, timestamp=None):
        """Record a partial fill."""
        self.partial_fills.append((amount, price, timestamp or datetime.datetime.now()))
        self.filled_amount += amount
        # Update average cost (only consider amount and price, ignore timestamp)
        total_cost = sum(a * p for a, p, _ in self.partial_fills)
        self.avg_cost = total_cost / self.filled_amount if self.filled_amount > 0 else 0
        self.transition_to(self.STATUS_PARTIAL_FILL)

    def is_complete(self) -> bool:
        """Check if order is fully filled."""
        return self.filled_amount >= self.amount

    def remaining_amount(self) -> int:
        """Get unfilled amount."""
        return max(0, self.amount - self.filled_amount)

    def __repr__(self):
        return (
            f"Order({self.order_id}, {self.security}, side={self.side}, "
            f"amount={self.amount}, filled={self.filled_amount}, status={self.status})"
        )


class MarketOrder:
    """Market order style - execute at best available price."""
    def __init__(self):
        self.limit_price = None


class LimitOrder:
    """Limit order style - execute only at specified price or better."""
    def __init__(self, limit_price: float):
        if limit_price <= 0:
            raise ValueError(f"Invalid limit price: {limit_price}")
        self.limit_price = limit_price
