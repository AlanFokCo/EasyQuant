"""Example 13: Export EasyQuant strategy to PTrade/QMT format.

Demonstrates how to convert an EasyQuant strategy into a QMT-compatible
script that can be pasted directly into the QMT strategy editor.

Run this locally to generate the QMT script:
    python examples/13_ptrade_export.py

Output:
    A file `ptrade_strategy.py` is generated that contains your
    EasyQuant strategy wrapped with QMT's init()/handlebar() entry points.
"""

from eqlib.ptrade_adapter import export_ptrade_script, QMT_TEMPLATE


# ============================================================
# Your EasyQuant strategy (same code you'd use for backtesting)
# ============================================================

STRATEGY_CODE = '''
from eqlib.ptrade_adapter import *

g.security = '601390'
g.fast_period = 5
g.slow_period = 20

def initialize(context):
    """Called once at start."""
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')  # <-- replace with your QMT account
    run_daily(market_open, time='every_bar')
    log.info('MA cross init: %s, MA%d/MA%d' % (g.security, g.fast_period, g.slow_period))


def market_open(context):
    """Called every bar (scheduled via run_daily)."""
    security = g.security

    # Get recent price history
    close_data = attribute_history(security, 25, '1d', ['close'])
    if close_data.empty or len(close_data) < g.slow_period:
        return

    close_prices = close_data['close']
    current_price = close_prices.iloc[-1]
    ma_fast = close_prices.tail(g.fast_period).mean()
    ma_slow = close_prices.mean()

    # Golden cross: buy
    if current_price > ma_fast > ma_slow:
        if security not in context.portfolio.positions or \
           context.portfolio.positions[security].amount == 0:
            order_value(security, context.portfolio.available_cash)
            log.info('BUY %s @ %.3f' % (security, current_price))

    # Death cross: sell
    elif current_price < ma_fast < ma_slow:
        if security in context.portfolio.positions and \
           context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info('SELL %s @ %.3f' % (security, current_price))
'''


# ============================================================
# Export to QMT format
# ============================================================

if __name__ == '__main__':
    print('=' * 60)
    print('EasyQuant -> PTrade/QMT Export')
    print('=' * 60)

    # Method 1: Export from a string
    script = export_ptrade_script(output_file='ptrade_strategy.py')
    print('\nGenerated QMT strategy saved to: ptrade_strategy.py')
    print('Copy this file into QMT\'s strategy editor to run.')

    # Method 2: Print the template for reference
    print('\n' + '=' * 60)
    print('QMT Template (for reference):')
    print('=' * 60)
    print(QMT_TEMPLATE)
