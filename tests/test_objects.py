"""Test core objects: Portfolio, Position, OrderCost, Context."""

from eqlib.objects import OrderCost, GlobalObject
from eqlib.context import Portfolio, Position, Context


class TestPosition:
    def test_position_creation(self):
        pos = Position(security="601390")
        pos.amount = 100
        pos.avg_cost = 10.0
        assert pos.amount == 100
        assert pos.avg_cost == 10.0

    def test_position_value_with_price(self):
        pos = Position(security="601390")
        pos.amount = 200
        pos.update(55.0)
        assert pos.total_value == 11000.0

    def test_position_empty(self):
        pos = Position(security="601390")
        assert pos.amount == 0


class TestPortfolio:
    def test_portfolio_init(self):
        port = Portfolio(starting_cash=100000)
        assert port.starting_cash == 100000
        assert port.available_cash == 100000
        assert port.total_value == 100000

    def test_portfolio_positions(self):
        port = Portfolio(starting_cash=100000)
        assert isinstance(port.positions, dict)
        assert len(port.positions) == 0


class TestOrderCost:
    def test_order_cost_defaults(self):
        cost = OrderCost()
        assert cost.open_tax == 0
        assert cost.close_tax == 0.001
        assert cost.open_commission == 0.0003
        assert cost.close_commission == 0.0003
        assert cost.min_commission == 5

    def test_order_cost_custom(self):
        cost = OrderCost(
            open_tax=0, close_tax=0.0005,
            open_commission=0.0002, close_commission=0.0002,
            min_commission=3,
        )
        assert cost.close_tax == 0.0005
        assert cost.min_commission == 3


class TestGlobalObject:
    def test_global_object(self):
        g = GlobalObject()
        # Can set arbitrary attributes
        g.security = "601390"
        assert g.security == "601390"
