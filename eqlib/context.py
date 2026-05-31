"""Context, Portfolio, and Position objects (mirrors EasyQuant's context paradigm)."""

import datetime


class Position:
    """Holds the state of a single stock position."""

    def __init__(self, security):
        self.security = security
        self.amount = 0
        self.avg_cost = 0.0
        self.total_value = 0.0
        self.closeable_amount = 0.0
        self._current_price = 0.0

    @property
    def current_price(self):
        """Current market price of the security."""
        return self._current_price

    @property
    def price(self):
        """Alias for ``current_price``.

        .. deprecated::
            Access ``avg_cost`` for cost basis or ``current_price`` for the
            latest market price.  This alias is kept for backward compatibility.
        """
        return self._current_price

    def update(self, price):
        self._current_price = price
        self.total_value = self.amount * price

    def __repr__(self):
        return (
            f"Position({self.security}, amount={self.amount}, "
            f"avg_cost={self.avg_cost:.3f}, value={self.total_value:.2f})"
        )


class Portfolio:
    """Portfolio state: cash, positions, total value (mirrors EasyQuant's context.portfolio)."""

    def __init__(self, starting_cash=100000.0):
        self.starting_cash = starting_cash
        self.available_cash = starting_cash
        self.positions = {}
        self.total_value = starting_cash

    # 兼容性属性：让用户可以用 cash 和 portfolio_value
    @property
    def cash(self):
        return self.available_cash

    @property
    def portfolio_value(self):
        return self.total_value

    @property
    def returns(self):
        if self.starting_cash == 0:
            return 0
        return (self.total_value - self.starting_cash) / self.starting_cash

    def _sync_total_value(self, prices):
        self.total_value = self.available_cash
        for sec, pos in self.positions.items():
            p = prices.get(sec, pos.avg_cost)
            pos.update(p)
            self.total_value += pos.total_value

    def __repr__(self):
        return (
            f"Portfolio(cash={self.available_cash:,.2f}, "
            f"total={self.total_value:,.2f}, "
            f"positions={len(self.positions)})"
        )


class Context:
    """
    Strategy execution context (mirrors EasyQuant's context).

    Attributes:
        current_dt: Current simulated datetime
        previous_date: Previous trading date
        portfolio: Portfolio object
        universe: List of securities in the strategy universe
        run_params: Dict of backtest parameters
    """

    def __init__(self, start_date, end_date, frequency="daily", starting_cash=100000.0):
        self.current_dt = datetime.datetime.combine(start_date, datetime.time(9, 30))
        self.previous_date = None
        self.start_date = start_date
        self.end_date = end_date
        self.frequency = frequency  # "daily" or "minute"
        self.portfolio = Portfolio(starting_cash)
        self.universe = []
        self.run_params = {
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "starting_cash": starting_cash,
        }

    def __repr__(self):
        return f"Context(dt={self.current_dt}, {self.portfolio})"
