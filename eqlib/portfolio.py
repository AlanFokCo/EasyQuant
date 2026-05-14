"""Portfolio backtest mode: define a strategy, stock universe, and capital,
then run a backtest that manages positions across all stocks simultaneously.

Usage:
    from eqlib.portfolio import StrategyConfig, run_portfolio_backtest

    config = StrategyConfig(
        starting_cash=200000,
        securities=['601390', '600519', '000858'],
        benchmark='000300.XSHG',
        position_pct=0.33,
        start_date='2024-01-01',
        end_date='2024-12-31',
        rebalance_frequency='monthly',
    )

    def my_strategy(context):
        for sec in context.universe:
            ...

    result = run_portfolio_backtest(config, my_strategy)
"""

import datetime
from typing import Optional


class StrategyConfig:
    """Configuration for a portfolio backtest.

    Attributes:
        starting_cash: initial capital (default 100,000)
        securities: list of stock codes to include in the universe
        benchmark: benchmark index code (default '000300.XSHG')
        position_pct: fraction of available cash per stock (default 0.33)
        position_amount: fixed share count per signal (overrides position_pct when > 0)
        start_date: backtest start date
        end_date: backtest end date
        report_suffix: optional suffix for report filenames
        frequency: 'daily' or 'minute'
        rebalance_frequency: how often to re-run portfolio optimization /
            strategy logic.  One of 'daily' (default), 'weekly', or 'monthly'.
            When set to 'weekly' or 'monthly', strategy_func is only called on
            the first trading day of each week/month; otherwise the portfolio
            is held as-is.  This reduces trading costs and models realistic
            rebalancing schedules.
        use_local: if True, use locally cached CSV data instead of fetching
            from akshare.  Requires pre-downloaded data via
            ``download_stock_data()`` / ``save_stock_local()``.  Default False
            (fetch from network, then cache).
    """

    def __init__(
        self,
        securities: list[str],
        start_date,
        end_date,
        starting_cash: float = 100000.0,
        benchmark: str = "000300.XSHG",
        position_pct: float = 0.33,
        position_amount: int = 0,
        report_suffix: str = "",
        frequency: str = "daily",
        rebalance_frequency: str = "daily",
        use_local: bool = False,
    ):
        self.starting_cash = starting_cash
        self.securities = list(securities)
        self.benchmark = benchmark
        self.position_pct = position_pct
        self.position_amount = position_amount
        self.report_suffix = report_suffix
        self.start_date = start_date
        self.end_date = end_date
        self.frequency = frequency
        if rebalance_frequency not in ("daily", "weekly", "monthly"):
            raise ValueError("rebalance_frequency must be 'daily', 'weekly', or 'monthly'")
        self.rebalance_frequency = rebalance_frequency
        self.use_local = use_local

    def __repr__(self):
        return (
            f"StrategyConfig(securities={self.securities}, "
            f"start={self.start_date}, end={self.end_date}, "
            f"cash={self.starting_cash:,.0f}, "
            f"pct={self.position_pct}, amt={self.position_amount}, "
            f"rebalance={self.rebalance_frequency})"
        )


def _should_rebalance(rebalance_frequency: str, day: datetime.date,
                      prev_day: Optional[datetime.date]) -> bool:
    """Return True if strategy_func should be called on *day*.

    Parameters:
        rebalance_frequency: 'daily', 'weekly', or 'monthly'
        day: current trading day
        prev_day: previous trading day (None on the first bar)
    """
    if rebalance_frequency == "daily":
        return True
    if prev_day is None:
        return True   # Always run on the first bar
    if rebalance_frequency == "weekly":
        # Rebalance on Monday (or the first trading day of the week)
        return day.isocalendar()[1] != prev_day.isocalendar()[1]
    if rebalance_frequency == "monthly":
        return day.month != prev_day.month
    return True


def run_portfolio_backtest(config: StrategyConfig, strategy_func,
                           report_dir: str = "reports",
                           generate_reports: bool = True):
    """Run a portfolio backtest using a StrategyConfig.

    Parameters:
        config: StrategyConfig with capital, universe, and settings
        strategy_func: callable taking (context) — the daily logic.
        report_dir: directory for output reports
        generate_reports: whether to generate chart/md/json/html reports

    Returns:
        dict with context, trade_log, recorded_values, benchmark, config
    """
    from eqlib.engine import run_backtest, run_daily
    from eqlib import set_benchmark, set_universe

    start_date = _parse_date(config.start_date)
    end_date = _parse_date(config.end_date)

    rebalance_freq = config.rebalance_frequency
    # Closure state: track the last rebalance day
    _state = {"prev_day": None}

    def _wrapped_strategy(context):
        day = context.current_dt.date()
        if _should_rebalance(rebalance_freq, day, _state["prev_day"]):
            strategy_func(context)
            _state["prev_day"] = day

    def initialize(context):
        context.universe = config.securities
        set_benchmark(config.benchmark)
        set_universe(config.securities)
        run_daily(_wrapped_strategy, time="every_bar")

    result = run_backtest(
        initialize, start_date, end_date,
        starting_cash=config.starting_cash,
        benchmark=config.benchmark,
        securities=config.securities,
        frequency=config.frequency,
        use_local=config.use_local,
    )

    if result is None:
        print("Backtest failed: no result returned.")
        return None

    result["config"] = config

    if generate_reports:
        suffix = f"_{config.report_suffix}" if config.report_suffix else ""
        from eqlib.report import (
            generate_chart, generate_report_md,
            generate_report_json, generate_html_report,
        )
        import os
        os.makedirs(report_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        generate_chart(result, f"{report_dir}/backtest_{ts}{suffix}.png")
        generate_html_report(result, f"{report_dir}/backtest_{ts}{suffix}.html")
        generate_report_md(result, f"{report_dir}/backtest_{ts}{suffix}.md")
        generate_report_json(result, f"{report_dir}/backtest_{ts}{suffix}.json")

        ctx = result["context"]
        pnl = ctx.portfolio.total_value - ctx.portfolio.starting_cash
        pnl_pct = pnl / ctx.portfolio.starting_cash * 100

        print(f"\n{'='*50}")
        print(f"Portfolio Backtest: {config.start_date} → {config.end_date}")
        print(f"Universe: {config.securities}")
        print(f"Rebalance: {config.rebalance_frequency}")
        print(f"{'='*50}")
        print(f"Starting Cash:    {ctx.portfolio.starting_cash:>15,.2f}")
        print(f"Final Value:      {ctx.portfolio.total_value:>15,.2f}")
        print(f"P&L:              {pnl:>+14,.2f} ({pnl_pct:+.2f}%)")
        print(f"Total Trades:     {len(result['trade_log'])}")

        print(f"\n--- Per-Stock Summary ---")
        stock_trades: dict = {}
        for t in result["trade_log"]:
            sec = t["security"]
            if sec not in stock_trades:
                stock_trades[sec] = {"buys": 0, "sells": 0, "shares": 0, "revenue": 0}
            st = stock_trades[sec]
            if t["type"] == "BUY":
                st["buys"] += 1
                st["shares"] += t["amount"]
                st["revenue"] -= t["price"] * t["amount"] + t.get("commission", 0)
            else:
                st["sells"] += 1
                st["shares"] -= t["amount"]
                st["revenue"] += t["price"] * t["amount"] - t.get("commission", 0)

        for sec, st_stats in sorted(stock_trades.items()):
            pos = ctx.portfolio.positions.get(sec)
            holding = f" (holding {pos.amount} shares)" if pos and pos.amount > 0 else ""
            print(f"  {sec}: {st_stats['buys']} buys, {st_stats['sells']} sells, "
                  f"net shares {st_stats['shares']}, "
                  f"realized ¥{st_stats['revenue']:,.2f}{holding}")

        print(f"\nChart:  {report_dir}/backtest_{ts}{suffix}.png")
        print(f"Report: {report_dir}/backtest_{ts}{suffix}.html")
        print(f"Data:   {report_dir}/backtest_{ts}{suffix}.json")

    return result


def _parse_date(d) -> datetime.date:
    """Convert a date string or date object to ``datetime.date``.

    Parameters:
        d: a ``datetime.date``, ``datetime.datetime``, or ``'YYYY-MM-DD'``
            string.  ``None`` is not accepted — pass an explicit date.

    Returns:
        ``datetime.date`` object.

    Raises:
        ValueError: if ``d`` is ``None``.
    """
    if d is None:
        raise ValueError("start_date and end_date cannot be None in StrategyConfig")
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    return d
