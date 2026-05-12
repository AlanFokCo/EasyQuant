"""Quick backtest to verify the new HTML/MD/JSON report output."""

import datetime
import os
from eqlib import *


def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')


def market_open(context):
    close_data = attribute_history(g.security, 20, '1d', ['close'])
    if close_data.empty:
        return
    MA20 = close_data['close'].mean()
    current_price = close_data['close'].iloc[-1]

    if current_price > 1.005 * MA20 and not context.portfolio.positions.get(g.security):
        order_value(g.security, context.portfolio.available_cash)
    elif current_price < 0.995 * MA20 and context.portfolio.positions.get(g.security):
        order_target(g.security, 0)

    record(price=current_price, cash=context.portfolio.available_cash)


if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)

    result = run_backtest(
        initialize,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 6, 1),
        starting_cash=100000,
        securities=['601390'],
        use_local=True,
    )

    if result is None:
        print("Backtest failed.")
        raise SystemExit(1)

    ctx = result["context"]
    pnl = ctx.portfolio.total_value - ctx.portfolio.starting_cash
    pnl_pct = (pnl / ctx.portfolio.starting_cash) * 100

    print(f"\nFinal value: {ctx.portfolio.total_value:,.2f}")
    print(f"P&L: {pnl:,.2f} ({pnl_pct:+.2f}%)")
    print(f"Trades: {len(result['trade_log'])}")

    # Generate all report formats
    from eqlib.report import generate_chart, generate_html_report, generate_report_md, generate_report_json

    generate_chart(result, "reports/quick_test.png")
    generate_html_report(result, "reports/quick_test.html")
    generate_report_md(result, "reports/quick_test.md")
    generate_report_json(result, "reports/quick_test.json")

    # Also print key metrics from analyze_returns
    from eqlib.attribution import analyze_returns
    metrics = analyze_returns(result)
    if metrics:
        print("\n=== Key Metrics ===")
        for k in ['total_return', 'annual_return', 'annual_volatility', 'sharpe_ratio',
                  'sortino_ratio', 'max_drawdown', 'calmar_ratio', 'alpha', 'beta',
                  'information_ratio', 'win_rate_trade', 'win_count', 'loss_count',
                  'profit_loss_ratio', 'excess_return', 'benchmark_return',
                  'excess_return_max_drawdown', 'excess_return_sharpe', 'daily_excess_return',
                  'benchmark_volatility']:
            v = metrics.get(k, 'N/A')
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")
