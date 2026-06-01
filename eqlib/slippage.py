"""Slippage models for realistic trade simulation.

Provides:
- SlippageModel: base class / no-op
- FixedSlippage: constant percentage per trade
- VolumeSlippage: impact proportional to order size relative to daily volume
"""


class SlippageModel:
    """Base slippage model — no slippage (pass-through)."""

    def get_execution_price(self, price: float, amount: int, is_buy: bool,
                            daily_volume: float = 0) -> float:
        """Return the execution price after applying slippage.

        Parameters:
            price: theoretical execution price (e.g., next-day open)
            amount: number of shares being traded
            is_buy: True for buys, False for sells
            daily_volume: today's total volume for the security

        Returns:
            Adjusted execution price.
        """
        return price


class FixedSlippage(SlippageModel):
    """Fixed-percentage slippage applied uniformly to every trade.

    Buys execute at ``price * (1 + pct)``; sells at ``price * (1 - pct)``.

    Parameters:
        pct: slippage fraction (default 0.001 = 0.1 %)
    """

    def __init__(self, pct: float = 0.001):
        self.pct = pct
        # HIGH-11: expose max_pct so the cash-buffer calculation in the engine
        # can use the exact worst-case slippage instead of the default fallback.
        self.max_pct = pct

    def get_execution_price(self, price: float, amount: int, is_buy: bool,
                            daily_volume: float = 0) -> float:
        if is_buy:
            return price * (1.0 + self.pct)
        return price * (1.0 - self.pct)


class VolumeSlippage(SlippageModel):
    """Volume-proportional slippage (similar to Zipline's VolumeShareSlippage).

    Price impact scales with the fraction of daily volume being traded::

        impact_pct = impact * (order_shares / daily_volume)

    Capped at ``max_slippage_pct`` to prevent unrealistic slippage when
    daily volume is very low.

    Buys execute at ``price * (1 + impact_pct)``; sells at the inverse.
    When ``daily_volume`` is 0 or unknown, falls back to no slippage.

    Parameters:
        impact: price impact coefficient (default 0.05). This value is
            calibrated for A-share markets with open-price passive execution.
            Typical range: 0.01–0.05 for large/mid-cap A-shares, 0.05–0.1 for
            small-cap stocks with lower liquidity.  For reference, an order
            representing 10% of daily volume with ``impact=0.05`` results in
            0.5% slippage.  Adjust based on the target universe's average
            daily turnover (Almgren & Chriss, 2001).
        max_slippage_pct: maximum allowed slippage fraction (default 0.05 = 5%).
    """

    def __init__(self, impact: float = 0.05, max_slippage_pct: float = 0.05):
        self.impact = impact
        self.max_slippage_pct = max_slippage_pct
        self.max_pct = max_slippage_pct

    def get_execution_price(self, price: float, amount: int, is_buy: bool,
                            daily_volume: float = 0) -> float:
        if daily_volume <= 0:
            return None  # F3: Signal engine to skip trade on zero-volume stocks
        impact_pct = min(self.impact * (amount / daily_volume), self.max_slippage_pct)
        if is_buy:
            return price * (1.0 + impact_pct)
        return price * (1.0 - impact_pct)
