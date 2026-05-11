"""Example 13: Export EasyQuant strategy to PTrade/QMT format.

Demonstrates how to convert an EasyQuant strategy into a QMT-compatible
script that can be pasted directly into the QMT strategy editor.

Run this locally to generate the QMT script:
    python examples/13_ptrade_export.py

Output:
    ``examples/ptrade_strategy_generated.py`` — generated from
    ``03_run_backtest.py`` as a sample strategy you can paste into QMT.
"""

import os

from eqlib.ptrade_adapter import export_ptrade_script, QMT_TEMPLATE


if __name__ == '__main__':
    print('=' * 60)
    print('EasyQuant -> PTrade/QMT Export')
    print('=' * 60)

    _here = os.path.dirname(os.path.abspath(__file__))
    _strategy_src = os.path.join(_here, '03_run_backtest.py')
    _out = os.path.join(_here, 'ptrade_strategy_generated.py')

    export_ptrade_script(
        strategy_file=_strategy_src,
        output_file=_out,
    )
    print('\nGenerated QMT strategy saved to: examples/ptrade_strategy_generated.py')
    print('Copy this file into QMT\'s strategy editor to run.')

    # Method 2: Print the template for reference
    print('\n' + '=' * 60)
    print('QMT Template (for reference):')
    print('=' * 60)
    print(QMT_TEMPLATE)
