"""Portfolio backtest mode: define a strategy, stock universe, and capital,
then run a backtest that manages positions across all stocks simultaneously.

Usage:
    from eqlib.portfolio import StrategyConfig, run_portfolio_backtest

    config = StrategyConfig(
        starting_cash=200000,
        securities=['601390', '600519', '000858'],
        benchmark='000300.XSHG',
        position_pct=0.33,       # 33% of cash per stock
        start_date='2024-01-01',
        end_date='2024-12-31',
    )

    def my_strategy(context):
        # pick stocks from context.universe
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
        position_pct: fraction of available cash to allocate per stock
            when the strategy signals a buy. 1.0 = full cash on one stock,
            0.33 = one-third of cash per stock. (default 0.33)
        position_amount: fixed number of shares to buy per signal.
            If set (non-zero), overrides position_pct. (default 0)
        start_date: backtest start date
        end_date: backtest end date
        report_suffix: optional string appended to report filenames
            to distinguish versions (e.g., 'v1', 'ma_crossover_test')
        frequency: 'daily' or 'minute'
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

    def __repr__(self):
        return (
            f"StrategyConfig(securities={self.securities}, "
            f"start={self.start_date}, end={self.end_date}, "
            f"cash={self.starting_cash:,.0f}, "
            f"pct={self.position_pct}, amt={self.position_amount})"
        )


def run_portfolio_backtest(config: StrategyConfig, strategy_func,
                           report_dir: str = "reports",
                           generate_reports: bool = True):
    """Run a portfolio backtest using a StrategyConfig.

    Parameters:
        config: StrategyConfig with capital, universe, and settings
        strategy_func: callable taking (context) — the daily logic.
            Within this function, use `context.universe` to access
            the stock list, and the standard trade APIs (order,
            order_value, etc.) to execute trades.
        report_dir: directory for output reports
        generate_reports: whether to generate chart/md/json/html reports

    Returns:
        dict with keys:
            context, trade_log, recorded_values, benchmark,
            config (the StrategyConfig used)
    """
    from eqlib.engine import run_backtest, run_daily
    from eqlib import set_benchmark, set_universe

    start_date = _parse_date(config.start_date)
    end_date = _parse_date(config.end_date)

    def initialize(context):
        context.universe = config.securities
        set_benchmark(config.benchmark)
        set_universe(config.securities)
        run_daily(strategy_func, time="every_bar")

    result = run_backtest(
        initialize, start_date, end_date,
        starting_cash=config.starting_cash,
        benchmark=config.benchmark,
        securities=config.securities,
        frequency=config.frequency,
    )

    if result is None:
        print("Backtest failed: no result returned.")
        return None

    # Attach config to result
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
        pnl_pct = (pnl / ctx.portfolio.starting_cash) * 100

        print(f"\n{'='*50}")
        print(f"Portfolio Backtest: {config.start_date} → {config.end_date}")
        print(f"Universe: {config.securities}")
        print(f"{'='*50}")
        print(f"Starting Cash:    {ctx.portfolio.starting_cash:>15,.2f}")
        print(f"Final Value:      {ctx.portfolio.total_value:>15,.2f}")
        print(f"P&L:              {pnl:>+14,.2f} ({pnl_pct:+.2f}%)")
        print(f"Total Trades:     {len(result['trade_log'])}")

        # Per-stock summary
        print(f"\n--- Per-Stock Summary ---")
        stock_trades = {}
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

        for sec, st in sorted(stock_trades.items()):
            info = ctx.portfolio.positions.get(sec)
            holding = ""
            if info and info.amount > 0:
                holding = f" (holding {info.amount} shares)"
            print(f"  {sec}: {st['buys']} buys, {st['sells']} sells, "
                  f"net shares {st['shares']}, "
                  f"realized ¥{st['revenue']:,.2f}{holding}")

        print(f"\nChart:  {report_dir}/backtest_{ts}{suffix}.png")
        print(f"Report: {report_dir}/backtest_{ts}{suffix}.html")
        print(f"Data:   {report_dir}/backtest_{ts}{suffix}.json")

    return result


def _parse_date(d):
    """Convert date string or date object."""
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    return d
