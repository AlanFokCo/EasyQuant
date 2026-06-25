"""Grid Trading Strategy.

Divides price range into grids, buys at lower grid lines and sells at upper grid lines.
Works best in sideways markets.

Ideal for: learning range-bound trading and position sizing.
"""
from eqlib import *


def initialize(context):
    """Initialize grid trading strategy."""
    g.security = "601390"
    g.grid_count = 5           # Number of grid levels
    g.grid_percent = 0.03      # Grid spacing (3% between levels)
    g.lookback = 60            # Days to determine price range

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")
    log.info("Grid Trading initialized | security=%s | grids=%d | spacing=%.1f%%"
             % (g.security, g.grid_count, g.grid_percent * 100))


def market_open(context):
    """Daily grid check: buy at lower grids, sell at upper grids."""
    security = g.security
    hist = attribute_history(security, g.lookback, "1d", ["close"])

    if hist is None or len(hist) < g.lookback:
        return

    current_price = hist["close"].iloc[-1]
    price_high = hist["close"].max()
    price_low = hist["close"].min()

    # Calculate grid levels
    grid_step = (price_high - price_low) / g.grid_count
    grids = [price_low + i * grid_step for i in range(g.grid_count + 1)]

    # Find current grid position
    current_grid = 0
    for i, level in enumerate(grids):
        if current_price >= level:
            current_grid = i

    position = context.portfolio.positions.get(security)
    has_position = position is not None and position.amount > 0

    # Buy signal: price falls to a lower grid level
    if not has_position and current_grid < g.grid_count:
        target_price = grids[current_grid]
        if current_price <= target_price * 1.01:  # Within 1% of grid line
            cash = context.portfolio.available_cash
            order_value(security, cash)
            log.info("Grid BUY: %s @ %.3f (grid #%d/%d)"
                     % (security, current_price, current_grid + 1, g.grid_count))

    # Sell signal: price rises to an upper grid level
    elif has_position and current_grid > 0:
        target_price = grids[current_grid]
        if current_price >= target_price * 0.99:  # Within 1% of grid line
            order_target(security, 0)
            log.info("Grid SELL: %s @ %.3f (grid #%d/%d)"
                     % (security, current_price, current_grid, g.grid_count))

    record(price=current_price, grid_low=grids[0], grid_high=grids[-1])


# Convenience: expose as a callable strategy object
grid_trading_strategy = {
    "name": "Grid Trading",
    "initialize": initialize,
    "market_open": market_open,
}
